"""Sidewinder corpus loader, dedup, and search — stdlib only.

The corpus is sharded by domain: ``corpus/<domain>.jsonl``, one entry per
line. Shards keep the shared branch merge-clean (writers touch different
files) and keep the growth pipeline mechanical: the batch generator in
``grow.py`` appends validated, deduped entries to the right shard.

Dedup key: normalized title (lowercased, punctuation stripped). Ids must
also be unique. ``load_corpus`` raises nothing — malformed lines are
collected in ``load_report["bad_lines"]`` so one bad line never kills the
manual.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from levi.sidewinder import DOMAINS
from levi.sidewinder.curriculum.schema import normalize_entry, validate_entry

MODULE_DIR = Path(__file__).resolve().parent
CORPUS_DIR = MODULE_DIR / "corpus"

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^a-z0-9 ]+")


def normalize_title(title: str) -> str:
    """Dedup key: lowercase, punctuation stripped, whitespace collapsed."""
    t = title.lower()
    t = _PUNCT_RE.sub("", t)
    return _WS_RE.sub(" ", t).strip()


def _tokenize(text: str) -> List[str]:
    return [t for t in _PUNCT_RE.sub(" ", text.lower()).split() if len(t) > 2]


def _tok_match(tok: str, cand: str) -> bool:
    """Fuzzy token match: exact, query-token inside candidate (plurals),
    or candidate inside query-token when the candidate is long enough to
    be meaningful (avoids 'out' matching 'spout')."""
    if tok == cand or tok in cand:
        return True
    return cand in tok and len(cand) >= 5


class Corpus:
    """The loaded field manual: entries + dedup indexes + keyword search."""

    def __init__(self, entries: List[Dict[str, Any]], bad_lines: Optional[List[Tuple[str, int, str]]] = None):
        self.entries: List[Dict[str, Any]] = entries
        self.bad_lines: List[Tuple[str, int, str]] = bad_lines or []
        self._by_id: Dict[str, Dict[str, Any]] = {}
        self._by_title: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            self._by_id[entry["id"]] = entry
            self._by_title[normalize_title(entry["title"])] = entry

    def __len__(self) -> int:
        return len(self.entries)

    def get(self, entry_id: str) -> Optional[Dict[str, Any]]:
        return self._by_id.get(entry_id)

    def has_title(self, title: str) -> bool:
        return normalize_title(title) in self._by_title

    def has_id(self, entry_id: str) -> bool:
        return entry_id in self._by_id

    def by_domain(self, domain: str) -> List[Dict[str, Any]]:
        return [e for e in self.entries if e["domain"] == domain]

    def domains_present(self) -> List[str]:
        seen = [d for d in DOMAINS if any(e["domain"] == d for e in self.entries)]
        return seen

    def stats(self) -> Dict[str, Any]:
        per_domain = {d: len(self.by_domain(d)) for d in self.domains_present()}
        return {
            "entries": len(self.entries),
            "domains": len(per_domain),
            "per_domain": per_domain,
            "bad_lines": len(self.bad_lines),
        }

    def search(self, query: str, domain: Optional[str] = None, limit: int = 3,
               track: Optional[str] = None) -> List[Dict[str, Any]]:
        """Keyword search over title (x3), domain (x2), and body (x1).

        Returns up to ``limit`` entries sorted by score, then title.
        """
        tokens = _tokenize(query)
        if not tokens:
            return []
        scored: List[Tuple[int, Dict[str, Any]]] = []
        for entry in self.entries:
            if domain and entry["domain"] != domain:
                continue
            if track and track not in entry["tracks"]:
                continue
            title_toks = set(_tokenize(entry["title"]))
            domain_toks = set(_tokenize(entry["domain"]))
            body = " ".join(
                entry["mechanism_check"]
                + entry["improvised_tools"]
                + entry["steps"]
                + entry["stop_conditions"]
            )
            body_toks = set(_tokenize(body))
            score = 0
            for tok in tokens:
                score += 3 * sum(1 for t in title_toks if _tok_match(tok, t))
                score += 2 * sum(1 for t in domain_toks if _tok_match(tok, t))
                score += 1 * sum(1 for t in body_toks if _tok_match(tok, t))
            if score:
                scored.append((score, entry))
        scored.sort(key=lambda pair: (-pair[0], pair[1]["title"]))
        return [entry for _, entry in scored[:limit]]


def load_corpus(corpus_dir: Optional[Path] = None) -> Corpus:
    """Load every ``<domain>.jsonl`` shard; dedup by title, then by id."""
    corpus_dir = corpus_dir or CORPUS_DIR
    entries: List[Dict[str, Any]] = []
    bad_lines: List[Tuple[str, int, str]] = []
    seen_titles: set = set()
    seen_ids: set = set()
    if corpus_dir.is_dir():
        for shard in sorted(corpus_dir.glob("*.jsonl")):
            try:
                lines = shard.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for lineno, line in enumerate(lines, 1):
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    bad_lines.append((shard.name, lineno, f"bad JSON: {exc}"))
                    continue
                errors = validate_entry(raw)
                if errors:
                    bad_lines.append((shard.name, lineno, "; ".join(errors)))
                    continue
                entry = normalize_entry(raw)
                title_key = normalize_title(entry["title"])
                if title_key in seen_titles or entry["id"] in seen_ids:
                    bad_lines.append((shard.name, lineno, "duplicate title or id"))
                    continue
                seen_titles.add(title_key)
                seen_ids.add(entry["id"])
                entries.append(entry)
    return Corpus(entries, bad_lines)


def format_entry(entry: Dict[str, Any]) -> str:
    """Terse Sidewinder rendering: MECHANISM -> IMPROVISE -> STEPS -> STOP."""
    lines = [
        f"SIDEWINDER — {entry['title']} [{entry['id']} · {entry['domain']} · "
        f"{'/'.join(entry['tracks'])} · {entry['level']} · difficulty {entry['difficulty']}/3]"
    ]
    lines.append("MECHANISM: " + " / ".join(entry["mechanism_check"]))
    lines.append("IMPROVISE: " + " / ".join(entry["improvised_tools"]))
    lines.append("STEPS:")
    for i, step in enumerate(entry["steps"], 1):
        lines.append(f"  {i}. {step}")
    lines.append("STOP: " + " / ".join(entry["stop_conditions"]))
    return "\n".join(lines)
