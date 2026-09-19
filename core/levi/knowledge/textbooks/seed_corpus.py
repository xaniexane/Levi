"""Seed the brain training corpus from the ingested textbook chapters.

Reads raw/<book-slug>/*.txt and writes
core/levi/brain/train/corpus_textbooks.jsonl — one JSONL doc per chapter,
capped so no single book dominates the next training generation. Shape
mirrors the course docs in corpus.jsonl (header lines + text, kind/subject
metadata, source + license kept for attribution).

Usage: python3 seed_corpus.py [--max-chars N]
Idempotent: rewrites corpus_textbooks.jsonl from scratch.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
RAW = BASE / "raw"
OUT = BASE.parent.parent / "brain" / "train" / "corpus_textbooks.jsonl"

DEFAULT_MAX_CHARS = 4_000


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Seed brain corpus from textbooks.")
    ap.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    args = ap.parse_args(argv)

    try:
        books = {
            b["slug"]: b
            for b in json.loads((BASE / "books.json").read_text(encoding="utf-8"))
        }
    except FileNotFoundError:
        print("seed: books.json not found; run ingest first")
        return 1

    docs = 0
    chars = 0
    with open(OUT, "w", encoding="utf-8") as out:
        for slug in sorted(books):
            book = books[slug]
            bdir = RAW / slug
            if not bdir.exists():
                continue
            for fp in sorted(bdir.glob("*.txt")):
                raw = fp.read_text(encoding="utf-8", errors="replace")
                # Split our own attribution header from the chapter text.
                if "\n\n" in raw:
                    header, text = raw.split("\n\n", 1)
                else:
                    header, text = raw[:400], raw
                text = text.strip()
                if len(text) < 200:
                    continue
                if len(text) > args.max_chars:
                    text = text[: args.max_chars] + "\n[truncated]"
                doc = {
                    "text": header.strip() + "\n\n" + text,
                    "kind": "textbook",
                    "subject": book.get("subject", ""),
                    "book": book.get("title", slug),
                }
                out.write(json.dumps(doc) + "\n")
                docs += 1
                chars += len(doc["text"])
    print(f"seed: {docs} docs, {chars} chars -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
