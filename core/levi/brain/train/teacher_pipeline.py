"""Tag-team pipeline: curated teacher records -> training corpora.

Takes one or more curated records files (output of teacher_intake.py),
dedupes them by stable content ID (same content in, one record out —
cross-round safe), balances them across teachers (no single trainer
dominates the corpus), splits a deterministic held-out set, and writes
the two corpus files that ``continue.py`` consumes via --dialogue-corpus.

Deterministic: fixed teacher order, round-robin interleave, every Nth
record to held-out. No randomness anywhere.

Stdlib only.

Usage:
    python3 teacher_pipeline.py --in records1.jsonl records2.jsonl \\
        --train-out corpus_teacher_train.jsonl \\
        --heldout-out corpus_teacher_heldout.jsonl
    # then:
    python3 continue.py --steps 600 --dialogue-corpus corpus_teacher_train.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:  # package import (tests, library use)
    from levi.brain.train.teacher_intake import TEACHERS, record_id_for
except ImportError:  # script run from the train/ directory
    from teacher_intake import TEACHERS, record_id_for

HELDOUT_EVERY = 10  # every 10th record goes to held-out


def load_records(paths: list[Path]) -> list[dict]:
    records: list[dict] = []
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def record_id_of(rec: dict) -> str:
    """The record's stable content ID, recomputed for legacy records.

    Records written before IDs existed get their ID derived from the
    curated text — same content, same ID, so old and new corpora dedupe
    together.
    """
    return rec.get("record_id") or record_id_for(rec.get("text", ""))


def dedupe(records: list[dict]) -> tuple[list[dict], int, list[str]]:
    """Drop cross-round duplicates: same content in, one record out.

    First occurrence wins; provenance events from the dropped copies are
    merged into the survivor, so it stays traceable to every round that
    produced it. Deterministic on input order. Returns
    (unique_records, n_duplicates, duplicate_ids).
    """
    seen: dict[str, dict] = {}
    unique: list[dict] = []
    dupe_ids: list[str] = []
    for rec in records:
        rid = record_id_of(rec)
        if rid in seen:
            survivor = seen[rid]
            for ev in rec.get("provenance", []):
                events = survivor.setdefault("provenance", [])
                if ev not in events:
                    events.append(ev)
            dupe_ids.append(rid)
            continue
        seen[rid] = rec
        unique.append(rec)
    return unique, len(dupe_ids), dupe_ids


def balance(records: list[dict], max_per_teacher: int) -> tuple[list[dict], dict]:
    """Cap each teacher at max_per_teacher, then round-robin interleave.

    Round-robin keeps every training batch mixed across trainers instead
    of front-loading one voice. Deterministic on (teacher order, input order).
    """
    buckets: dict[str, list[dict]] = {t: [] for t in TEACHERS}
    dropped: dict[str, int] = {t: 0 for t in TEACHERS}
    for rec in records:
        src = rec.get("source", "")
        teacher = src.split(":", 1)[1] if ":" in src else ""
        if teacher in buckets and len(buckets[teacher]) < max_per_teacher:
            buckets[teacher].append(rec)
        else:
            dropped[teacher] = dropped.get(teacher, 0) + 1
    ordered = [t for t in TEACHERS if buckets[t]]
    interleaved: list[dict] = []
    idx = 0
    while True:
        added = False
        for t in ordered:
            if idx < len(buckets[t]):
                interleaved.append(buckets[t][idx])
                added = True
        if not added:
            break
        idx += 1
    return interleaved, dropped


def split_heldout(
    records: list[dict], every: int = HELDOUT_EVERY
) -> tuple[list[dict], list[dict]]:
    train = [r for i, r in enumerate(records) if (i + 1) % every != 0]
    heldout = [r for i, r in enumerate(records) if (i + 1) % every == 0]
    return train, heldout


def write_jsonl(path: Path, records: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build tag-team training corpora.")
    ap.add_argument(
        "--in",
        dest="in_paths",
        nargs="+",
        required=True,
        help="curated records JSONL files",
    )
    ap.add_argument("--train-out", required=True, help="training corpus output")
    ap.add_argument("--heldout-out", required=True, help="held-out corpus output")
    ap.add_argument(
        "--max-per-teacher",
        type=int,
        default=400,
        help="cap records per teacher (default 400)",
    )
    ap.add_argument("--heldout-every", type=int, default=HELDOUT_EVERY)
    args = ap.parse_args(argv)

    records = load_records([Path(p) for p in args.in_paths])
    records, n_dupes, _dupe_ids = dedupe(records)
    balanced, dropped = balance(records, args.max_per_teacher)
    train, heldout = split_heldout(balanced, args.heldout_every)
    write_jsonl(Path(args.train_out), train)
    write_jsonl(Path(args.heldout_out), heldout)

    per_teacher = {t: 0 for t in TEACHERS}
    per_modality: dict[str, int] = {}
    for rec in balanced:
        src = rec.get("source", "")
        t = src.split(":", 1)[1] if ":" in src else "?"
        per_teacher[t] = per_teacher.get(t, 0) + 1
        m = rec.get("modality", "text")  # old records predate the field
        per_modality[m] = per_modality.get(m, 0) + 1
    chars = sum(len(r.get("text", "")) for r in balanced)
    print(
        json.dumps(
            {
                "records_in": len(records) + n_dupes,
                "duplicates_dropped": n_dupes,
                "records_balanced": len(balanced),
                "train": len(train),
                "heldout": len(heldout),
                "chars": chars,
                "per_teacher": {t: n for t, n in per_teacher.items() if n},
                "per_modality": per_modality,
                "dropped_over_cap": {t: n for t, n in dropped.items() if n},
            },
            indent=2,
        )
    )
    print(f"\nnext: python3 continue.py --steps 600 --dialogue-corpus {args.train_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
