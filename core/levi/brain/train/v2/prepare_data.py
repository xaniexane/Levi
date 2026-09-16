"""Snapshot + split corpora into seeded train/val/test manifests for a v2 run.

Usage (from the repo root):
    PYTHONPATH=core python3 core/levi/brain/train/v2/prepare_data.py \\
        --run-dir runs/tiny-gpt-v2-20260916 [--seed 1337]

READ-ONLY on the source corpus files under core/levi/brain/train/.
Writes ONLY into <run-dir>/corpora/:
    train.jsonl / val.jsonl / test.jsonl
    train.manifest.json / val.manifest.json / test.manifest.json

Why a snapshot: sibling crews keep editing the live corpus files. The
manifests pin sha256 of the split files, so a run trains on exactly the
data that was staged — reproducible and auditable. Re-running with the
same seed reproduces identical splits (deterministic by construction).

The news-exclusion policy is enforced by build_manifest (tags + path
hints); a violation aborts before anything is written.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from levi.brain.train.v2.corpus_manager import (
    build_manifest,
    dedupe,
    load_jsonl_docs,
    save_manifest,
    split_docs,
    write_split_jsonl,
)

# Source corpora (read-only; never modified by this script).
SOURCES = [
    "core/levi/brain/train/corpus.jsonl",
    "core/levi/brain/train/corpus_academy.jsonl",
    "core/levi/brain/train/corpus_graduation.jsonl",
]

TAGS = ("levi-brain-v2",)
VERSION = "2026-09-16"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Snapshot corpora into seeded train/val/test manifests."
    )
    ap.add_argument("--run-dir", required=True, help="run directory to populate")
    ap.add_argument("--seed", type=int, default=1337, help="split seed")
    ap.add_argument(
        "--train-frac", type=float, default=0.90, help="train split fraction"
    )
    ap.add_argument("--val-frac", type=float, default=0.05, help="val split fraction")
    args = ap.parse_args(argv)

    run_dir = Path(args.run_dir)
    corpora_dir = run_dir / "corpora"

    docs = []
    for src in SOURCES:
        src_docs = load_jsonl_docs(src)
        print(f"prepare_data: {src}: {len(src_docs)} docs")
        docs.extend(src_docs)
    print(f"prepare_data: {len(docs)} docs before dedupe")
    docs, removed = dedupe(docs)
    print(f"prepare_data: {len(docs)} docs after dedupe ({removed} duplicates dropped)")
    if not docs:
        print("prepare_data: ERROR: no docs found", file=sys.stderr)
        return 1

    test_frac = round(1.0 - args.train_frac - args.val_frac, 9)
    splits = split_docs(
        docs,
        train=args.train_frac,
        val=args.val_frac,
        test=test_frac,
        seed=args.seed,
    )

    corpora_dir.mkdir(parents=True, exist_ok=True)
    for name, split_docs_list in splits.items():
        split_path = corpora_dir / f"{name}.jsonl"
        write_split_jsonl(split_docs_list, split_path)
        manifest = build_manifest(
            f"tiny-gpt-v2-{name}",
            VERSION,
            [split_path],
            tags=TAGS,
            base_dir=corpora_dir,
        )
        manifest_path = corpora_dir / f"{name}.manifest.json"
        save_manifest(manifest, manifest_path)
        n_chars = manifest.n_chars
        print(
            f"prepare_data: {name}: {manifest.n_docs} docs, "
            f"{n_chars} chars -> {manifest_path.name}"
        )
    print(f"prepare_data: done -> {corpora_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
