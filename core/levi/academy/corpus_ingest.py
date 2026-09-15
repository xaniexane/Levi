"""Ingest academy lessons into the offline brain corpus.

Every academy session's synthesized lesson is ALSO appended to LEVI's
offline brain corpus (the corpus behind the native brain weights), so
training compounds alongside the growth journal:

- growth journal  -> experiential memory (what was learned, when)
- offline corpus  -> parametric memory (via retrain at graduation)

Format matches ``core/levi/brain/train/corpus.jsonl`` exactly: one JSON
record per line, UTF-8, ``ensure_ascii=False``, ``{"text": ..., "kind":
"academy", ...}``. Text is cleaned and chunked with the SAME rules as
``prepare_corpus.py`` (~512 whitespace tokens, min 100 chars, drop
>60%-non-alpha lines, de-dup lines). Ingestion is monotonic and
idempotent: records are hashed (sha256 of normalized text) and re-runs
never duplicate.

Academy records live in their own file,
``core/levi/brain/train/corpus_academy.jsonl``, so re-running
``prepare_corpus.py`` (which rewrites corpus.jsonl from courses) can
never wipe them. The graduation retrain merges both files.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ACADEMY_DIR = Path(__file__).resolve().parent
TRAIN_DIR = ACADEMY_DIR.parent / "brain" / "train"


def corpus_path() -> Path:
    """Academy corpus file. ``LEVI_ACADEMY_CORPUS`` overrides it (tests)."""
    override = os.environ.get("LEVI_ACADEMY_CORPUS")
    return Path(override) if override else TRAIN_DIR / "corpus_academy.jsonl"


def _clean_and_chunk():
    """Import the canonical cleaning/chunking from prepare_corpus.

    Importing (not copying) guarantees the academy corpus matches the
    training pipeline's expected format exactly.
    """
    import sys
    train_pkg = str(TRAIN_DIR)
    if train_pkg not in sys.path:
        sys.path.insert(0, train_pkg)
    from prepare_corpus import clean_lines, chunk  # noqa: E402
    return clean_lines, chunk


def _existing_hashes(path: Path) -> set[str]:
    hashes: set[str] = set()
    if not path.exists():
        return hashes
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            h = rec.get("sha256")
            if h:
                hashes.add(h)
    return hashes


def _hash(text: str) -> str:
    norm = " ".join(text.split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def ingest_lesson(day: int, block: int, track: str, title: str,
                  lesson_markdown: str, mastery: dict | None = None) -> dict:
    """Append one session's POST-MASTERY lesson to the academy corpus.

    Idempotent. Only distilled, corrected, retained knowledge is ingested:
    the runner calls this exclusively on gate passes (or remedial passes),
    so the brain trains on verified knowledge, never first drafts. Each
    record is tagged with its mastery level.

    Returns ``{"added": n, "skipped_dupes": n, "records": total,
    "chars": total_chars}``.
    """
    clean_lines, chunk = _clean_and_chunk()
    path = corpus_path()
    header = (
        f"Academy lesson — Day {day}, Block {block}, Track {track}: {title}\n"
    )
    chunks = chunk(clean_lines(header + "\n" + lesson_markdown))
    existing = _existing_hashes(path)
    added = 0
    skipped = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for c in chunks:
            h = _hash(c)
            if h in existing:
                skipped += 1
                continue
            rec = {
                "text": c,
                "kind": "academy",
                "track": track,
                "day": day,
                "block": block,
                "title": title,
                "sha256": h,
            }
            if mastery:
                rec["mastery"] = {
                    "mastery_score": mastery.get("mastery_score"),
                    "exercise_score": mastery.get("exercise_score"),
                    "attempts": mastery.get("attempts", 1),
                    "remediated": bool(mastery.get("remediated", False)),
                }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            existing.add(h)
            added += 1
    total_records = 0
    total_chars = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            total_records += 1
            total_chars += len(rec.get("text", ""))
    return {"added": added, "skipped_dupes": skipped,
            "records": total_records, "chars": total_chars}


def corpus_stats() -> dict:
    """Current academy corpus stats for status displays."""
    path = corpus_path()
    total_records = 0
    total_chars = 0
    by_track: dict[str, int] = {}
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                total_records += 1
                total_chars += len(rec.get("text", ""))
                t = rec.get("track", "?")
                by_track[t] = by_track.get(t, 0) + 1
    return {"records": total_records, "chars": total_chars,
            "by_track": by_track, "path": str(path)}
