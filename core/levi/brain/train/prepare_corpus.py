"""Prepare the training corpus for LEVI's tiny brain (stdlib-only).

Reads:
  - core/levi/knowledge/courses/raw/**/*.txt   (ingested course pages)
  - core/levi/knowledge/courses/briefs/*.md   (subject field guides)
  - levi.persona.levi (14 original SI registers -> identity records)

Writes:
  - core/levi/brain/train/corpus.jsonl   (one {"text": ...} record per chunk)
  - core/levi/brain/train/corpus_stats.json

Cleaning (heuristic, deterministic):
  - drop lines whose characters are >60% non-alphabetic (nav/separator junk)
  - drop exact-duplicate lines beyond their first occurrence per file
  - chunk to ~512 whitespace-estimated tokens; skip chunks <100 chars

Identity records teach the tiny brain LEVI's own voice natively
(one record per register: name/id, voice, strengths, forbids, system block).
These registers are LEVI-original (see core/levi/persona/levi.py header).

Usage: python3 prepare_corpus.py [--out DIR]
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
COURSES = HERE.parent.parent / "knowledge" / "courses"
RAW = COURSES / "raw"
BRIEFS = COURSES / "briefs"

CHUNK_TOKENS = 512
MIN_CHUNK_CHARS = 100


def clean_lines(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        alpha = sum(c.isalpha() for c in line)
        if len(line) > 0 and alpha / len(line) < 0.4:
            continue  # nav/separator junk: >60% non-alpha
        if line in seen:
            continue  # repeated boilerplate
        seen.add(line)
        out.append(line)
    return out


def chunk(lines: list[str]) -> list[str]:
    chunks: list[str] = []
    cur: list[str] = []
    cur_tokens = 0
    for line in lines:
        toks = len(line.split())
        if cur and cur_tokens + toks > CHUNK_TOKENS:
            text = "\n".join(cur).strip()
            if len(text) >= MIN_CHUNK_CHARS:
                chunks.append(text)
            cur, cur_tokens = [], 0
        cur.append(line)
        cur_tokens += toks
    text = "\n".join(cur).strip()
    if len(text) >= MIN_CHUNK_CHARS:
        chunks.append(text)
    return chunks


def identity_records() -> list[dict]:
    """One training record per LEVI register (LEVI-original voice)."""
    from levi.persona.levi import all_variants

    records = []
    for v in all_variants():
        text = (
            f"Register: {v.name} ({v.id})\n"
            f"Voice: {v.voice}\n"
            f"Strengths: {', '.join(v.strengths)}\n"
            f"Never: {', '.join(v.forbids)}\n"
            f"System: {v.system_block}"
        )
        records.append({"text": text, "kind": "identity", "register": v.id})
    return records


def main(argv: list[str]) -> int:
    out_dir = Path(argv[argv.index("--out") + 1]) if "--out" in argv else HERE
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    files_in = 0
    # Identity records first: the brain meets LEVI's own voice before the corpus.
    identity = identity_records()
    records.extend(identity)

    sources = sorted(RAW.rglob("*.txt")) + sorted(BRIEFS.glob("*.md"))
    for path in sources:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files_in += 1
        for c in chunk(clean_lines(text)):
            records.append({"text": c, "kind": "course", "source": path.name})

    jsonl_path = out_dir / "corpus.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    total_chars = sum(len(r["text"]) for r in records)
    kinds = Counter(r.get("kind", "?") for r in records)
    stats = {
        "files_in": files_in,
        "chunks": len(records),
        "identity_records": kinds.get("identity", 0),
        "course_chunks": kinds.get("course", 0),
        "total_chars": total_chars,
        "chunk_tokens": CHUNK_TOKENS,
        "min_chunk_chars": MIN_CHUNK_CHARS,
    }
    (out_dir / "corpus_stats.json").write_text(json.dumps(stats, indent=1))
    print(f"files in : {files_in}")
    print(
        f"chunks   : {len(records)} "
        f"(identity={stats['identity_records']}, course={stats['course_chunks']})"
    )
    print(f"chars    : {total_chars}")
    print(f"wrote    : {jsonl_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
