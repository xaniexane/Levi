"""Sidewinder growth pipeline — mechanical corpus expansion, stdlib only.

The pipeline turns the committed seed lists in ``seeds/`` into corpus
entries with zero hand-wiring:

* ``seeds/topics.jsonl`` — intake queue: full entries in authoring format
  (one JSON object per line, same schema as the corpus). Writers, agents,
  or future batches drop entries here.
* ``seeds/planned_titles.txt`` — the roadmap, organized by track:
  ``track | domain | title`` lines, hundreds to thousands.
  ``levi sidewinder stubs N`` turns the next N unbuilt planned
  titles into blank writer stubs (``seeds/stubs.jsonl``) so reaching
  thousands is a fill-and-run loop.
* ``seeds/stubs.jsonl`` — unfilled writer scaffolding. Never promoted;
  ``grow`` ignores it and schema validation rejects stubs.

``grow()``: read seeds -> schema check -> dedup against the live corpus
(by title, then id) -> append to the right domain shard -> consume the
processed seeds (invalid lines are kept for fixing). Dry-run reports
without writing. Returns a report dict; the CLI prints it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from levi.sidewinder import TRACKS
from levi.sidewinder.curriculum.corpus import CORPUS_DIR, Corpus, load_corpus, normalize_title
from levi.sidewinder.curriculum.schema import check_batch, normalize_entry

MODULE_DIR = Path(__file__).resolve().parent
SEEDS_DIR = MODULE_DIR / "seeds"
TOPICS_FILE = SEEDS_DIR / "topics.jsonl"
STUBS_FILE = SEEDS_DIR / "stubs.jsonl"
PLANNED_FILE = SEEDS_DIR / "planned_titles.txt"


def load_planned_titles(path: Optional[Path] = None) -> List[Tuple[str, str, str]]:
    """Parse ``track | domain | title`` lines; skip blanks and ``#`` comments."""
    path = path or PLANNED_FILE
    planned: List[Tuple[str, str, str]] = []
    if not path.is_file():
        return planned
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3 or not all(parts):
            continue
        track, domain, title = parts
        if track not in TRACKS:
            continue
        planned.append((track, domain, title))
    return planned


def load_seeds(path: Optional[Path] = None) -> Tuple[List[Tuple[int, Any]], List[Tuple[int, str]]]:
    """Read the intake queue. Returns ([(lineno, raw entry)], [(lineno, error)])."""
    path = path or TOPICS_FILE
    parsed: List[Tuple[int, Any]] = []
    bad: List[Tuple[int, str]] = []
    if not path.is_file():
        return parsed, bad
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            parsed.append((lineno, json.loads(line)))
        except json.JSONDecodeError as exc:
            bad.append((lineno, f"bad JSON: {exc}"))
    return parsed, bad


def _next_id(corpus: Corpus, domain: str) -> str:
    """Next free id in a domain shard: sw-<domain>-NNN."""
    used = set()
    for entry in corpus.by_domain(domain):
        tail = entry["id"].rsplit("-", 1)[-1]
        if tail.isdigit():
            used.add(int(tail))
    n = 1
    while n in used:
        n += 1
    return f"sw-{domain}-{n:03d}"


def grow(
    batch: Optional[int] = None,
    dry_run: bool = False,
    seeds_path: Optional[Path] = None,
    corpus_dir: Optional[Path] = None,
    consume: bool = True,
) -> Dict[str, Any]:
    """Run one growth batch. Returns a report dict.

    ``batch`` caps how many seed lines are processed (None = all).
    ``dry_run`` validates and reports without writing. ``consume`` controls
    whether processed (valid + duplicate) seeds are removed from the intake
    queue; invalid lines are always kept for fixing.
    """
    seeds_path = seeds_path or TOPICS_FILE
    corpus_dir = corpus_dir or CORPUS_DIR
    report: Dict[str, Any] = {
        "seeds_read": 0,
        "seeds_json_bad": 0,
        "valid": 0,
        "invalid": 0,
        "duplicates": 0,
        "appended": 0,
        "per_domain": {},
        "dry_run": dry_run,
        "errors": [],
    }
    parsed, json_bad = load_seeds(seeds_path)
    json_bad_linenos = {n for n, _ in json_bad}
    report["seeds_json_bad"] = len(json_bad)
    report["errors"].extend([f"line {n}: {msg}" for n, msg in json_bad])
    if batch is not None:
        parsed = parsed[:batch]
    processed_linenos = {n for n, _ in parsed}
    raw = [obj for _, obj in parsed]
    report["seeds_read"] = len(raw)
    if not raw:
        return report

    valid, invalid = check_batch(raw)
    report["valid"] = len(valid)
    report["invalid"] = len(invalid)
    for entry, errors in invalid:
        title = entry.get("title") if isinstance(entry, dict) else "?"
        report["errors"].append(f"invalid {title!r}: {'; '.join(errors)}")

    corpus = load_corpus(corpus_dir)
    new_entries: List[Dict[str, Any]] = []
    consumed_indexes: set = set()
    for i, entry in enumerate(valid):
        title_key = normalize_title(entry["title"])
        if corpus.has_title(entry["title"]) or corpus.has_id(entry["id"]):
            report["duplicates"] += 1
            consumed_indexes.add(i)
            continue
        # Also dedup within the batch itself.
        if any(normalize_title(e["title"]) == title_key or e["id"] == entry["id"] for e in new_entries):
            report["duplicates"] += 1
            consumed_indexes.add(i)
            continue
        new_entries.append(entry)
        consumed_indexes.add(i)
        corpus.entries.append(entry)  # keep later batch items dedup-aware

    if not dry_run:
        corpus_dir.mkdir(parents=True, exist_ok=True)
        for entry in new_entries:
            shard = corpus_dir / f"{entry['domain']}.jsonl"
            with shard.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        report["appended"] = len(new_entries)
        for entry in new_entries:
            report["per_domain"][entry["domain"]] = report["per_domain"].get(entry["domain"], 0) + 1

    if consume and not dry_run and seeds_path.is_file():
        # Rewrite the intake queue keeping only unprocessed lines:
        # JSON-bad lines, invalid entries, and lines beyond the batch
        # limit stay for fixing / later batches. Only processed
        # valid-or-duplicate seeds are consumed.
        invalid_titles = set()
        for entry, _ in invalid:
            if isinstance(entry, dict) and isinstance(entry.get("title"), str):
                invalid_titles.add(normalize_title(entry["title"]))
        kept: List[str] = []
        for lineno, line in enumerate(seeds_path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            if lineno in json_bad_linenos:
                kept.append(line)  # JSON-bad: keep for fixing
                continue
            if lineno not in processed_linenos:
                kept.append(line)  # beyond the batch: keep for a later run
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if isinstance(obj, dict) and normalize_title(str(obj.get("title", ""))) in invalid_titles:
                kept.append(line)  # invalid: keep for fixing
        seeds_path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")

    return report


def write_stubs(
    n: int,
    planned_path: Optional[Path] = None,
    stubs_path: Optional[Path] = None,
    corpus_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Emit up to ``n`` blank writer stubs for planned titles not yet built.

    Stubs carry the Sidewinder structure with empty sections and
    ``"stub": true`` — they are scaffolding for a writer (human or agent)
    to fill, then move into ``topics.jsonl``. Never promoted as-is.
    """
    planned_path = planned_path or PLANNED_FILE
    stubs_path = stubs_path or STUBS_FILE
    corpus = load_corpus(corpus_dir)
    planned = load_planned_titles(planned_path)

    existing_stubs: set = set()
    if stubs_path.is_file():
        for line in stubs_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    existing_stubs.add(normalize_title(json.loads(line).get("title", "")))
                except (json.JSONDecodeError, AttributeError):
                    pass

    made = 0
    stubs_path.parent.mkdir(parents=True, exist_ok=True)
    with stubs_path.open("a", encoding="utf-8") as fh:
        for track, domain, title in planned:
            if made >= n:
                break
            key = normalize_title(title)
            if corpus.has_title(title) or key in existing_stubs:
                continue
            stub = {
                "id": _next_id(corpus, domain),
                "title": title,
                "domain": domain,
                "tracks": [track],
                "level": "applied",
                "prerequisites": [],
                "difficulty": 2,
                "mechanism_check": ["FILL: how is it held/fastened/sealed? diagnose before tools."],
                "improvised_tools": ["FILL: on-hand substitutes matching the pattern."],
                "steps": ["FILL: ordered actions."],
                "stop_conditions": ["FILL: when to stop forcing it."],
                "stub": True,
            }
            fh.write(json.dumps(stub, ensure_ascii=False) + "\n")
            existing_stubs.add(key)
            # Reserve the id so later stubs in this run don't collide.
            corpus.entries.append(normalize_entry({k: v for k, v in stub.items() if k != "stub"}))
            made += 1
    return {"stubs_written": made, "stubs_file": str(stubs_path)}
