"""Carve a deterministic held-out set from the dialogue corpus.

Takes ~20 records OUT of the training pool so the eval gate measures
genuinely unseen material. Stratified by kind (dialogue / lwp_prose),
seeded shuffle, fully deterministic.

Outputs (persistent, beside the corpus — never /tmp):
  corpus_dialogue_train.jsonl    515 records (the training input)
  corpus_dialogue_heldout.jsonl   20 records (eval-gate only)

Usage:
    python3 carve_heldout.py [--heldout-n 20] [--seed 20260921]
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "corpus_dialogue.jsonl"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--heldout-n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20260921)
    args = ap.parse_args(argv)

    recs = [
        json.loads(line)
        for line in open(SRC, encoding="utf-8")
        if line.strip()
    ]
    by_kind: dict[str, list[int]] = {}
    for i, r in enumerate(recs):
        by_kind.setdefault(r.get("kind", "dialogue"), []).append(i)

    rng = random.Random(args.seed)
    heldout_idx: list[int] = []
    # stratified: proportional per kind, at least 1 of each
    for kind, idxs in sorted(by_kind.items()):
        n = max(1, round(len(idxs) / len(recs) * args.heldout_n))
        rng.shuffle(idxs)
        heldout_idx.extend(idxs[:n])
    # fix rounding so the total is exact
    rng.shuffle(heldout_idx)
    heldout_idx = heldout_idx[: args.heldout_n]
    heldout_set = set(heldout_idx)

    train_recs = [r for i, r in enumerate(recs) if i not in heldout_set]
    held_recs = [recs[i] for i in heldout_idx]

    train_path = HERE / "corpus_dialogue_train.jsonl"
    held_path = HERE / "corpus_dialogue_heldout.jsonl"
    with open(train_path, "w", encoding="utf-8") as fh:
        for r in train_recs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(held_path, "w", encoding="utf-8") as fh:
        for r in held_recs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    from collections import Counter

    print(f"source records : {len(recs)}")
    print(f"train records  : {len(train_recs)} -> {train_path.name}")
    print(f"heldout records: {len(held_recs)} -> {held_path.name}")
    print("heldout kinds  :", dict(Counter(r.get('kind') for r in held_recs)))
    print("heldout chars  :", sum(len(r.get('text', '')) for r in held_recs))
    # determinism receipt: re-hash the heldout ids
    print("heldout id hash:", __import__("hashlib").sha256(
        ",".join(map(str, sorted(heldout_idx))).encode()).hexdigest()[:16])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
