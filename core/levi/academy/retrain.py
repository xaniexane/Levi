#!/usr/bin/env python3
"""Graduation brain retrain for LEVI Boot Camp.

Launched once, in the background, when Session 120 completes:

  1. merge ``train/corpus.jsonl`` (courses + identity) with
     ``train/corpus_academy.jsonl`` (120 academy lessons) into
     ``train/corpus_graduation.jsonl``
  2. train with the SAME hyperparams as the original run
     (600 steps, seed 1337, AdamW, CPU) via ``train.train()``
  3. save the new checkpoint VERSIONED
     (``weights/tiny-gpt-academy-<ts>.pt``) — the existing
     ``tiny-gpt.pt`` is never overwritten and stays the fallback
  4. journal the outcome (growth-tagged) whether it succeeds or fails

CPU-heavy (~20 min for 600 steps on the original run). Runs detached;
the session worker returns immediately after launching it.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT / "core") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "core"))

ACADEMY_PKG = Path(__file__).resolve().parent
TRAIN_DIR = ACADEMY_PKG.parent / "brain" / "train"
WEIGHTS_DIR = ACADEMY_PKG.parent / "brain" / "weights"


def _count(path: Path) -> tuple[int, int]:
    records, chars = 0, 0
    if not path.exists():
        return 0, 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            records += 1
            chars += len(rec.get("text", ""))
    return records, chars


def _journal(kind: str, tags: list[str], **fields) -> None:
    try:
        from levi.growth import journal as gjournal
        gjournal.append_entry({"kind": kind, "tags": tags, **fields})
    except Exception as exc:  # journal failure must not kill the retrain
        print(f"journal write failed: {exc}", flush=True)


def main() -> int:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    t0 = time.time()
    base = TRAIN_DIR / "corpus.jsonl"
    acad = TRAIN_DIR / "corpus_academy.jsonl"
    merged = TRAIN_DIR / "corpus_graduation.jsonl"

    base_n, base_c = _count(base)
    acad_n, acad_c = _count(acad)
    if base_n == 0:
        _journal("academy-retrain", ["growth", "levi-learned", "academy", "retrain-failed"],
                 note="Retrain aborted: base corpus.jsonl missing or empty.")
        print("retrain aborted: base corpus missing", flush=True)
        return 1

    # 1. merge (streaming; academy file may be large after 120 sessions)
    with open(merged, "w", encoding="utf-8") as out:
        for src in (base, acad):
            if not src.exists():
                continue
            with open(src, encoding="utf-8") as fh:
                shutil.copyfileobj(fh, out)
    merged_n, merged_c = _count(merged)
    print(f"merged corpus: {merged_n} records, {merged_c} chars "
          f"(base={base_n}, academy={acad_n})", flush=True)

    # 2. train — same hyperparams as the original 600-step run
    try:
        sys.path.insert(0, str(TRAIN_DIR))
        from train import train as train_fn
    except Exception as exc:
        _journal("academy-retrain", ["growth", "levi-learned", "academy", "retrain-failed"],
                 note=f"Retrain aborted: could not load training pipeline: {exc}")
        print(f"retrain aborted: {exc}", flush=True)
        return 1

    staging = WEIGHTS_DIR / "retrain_staging"
    try:
        log = train_fn(merged, 600, staging, seed=1337)
    except SystemExit as exc:
        _journal("academy-retrain", ["growth", "levi-learned", "academy", "retrain-failed"],
                 note=f"Retrain aborted by training pipeline: {exc}")
        return 1
    except Exception as exc:
        _journal("academy-retrain", ["growth", "levi-learned", "academy", "retrain-failed"],
                 note=f"Retrain failed: {type(exc).__name__}: {exc}")
        print(f"retrain failed: {exc}", flush=True)
        return 1

    # 3. versioned checkpoint — never overwrite tiny-gpt.pt
    versioned = WEIGHTS_DIR / f"tiny-gpt-academy-{ts}.pt"
    shutil.move(str(staging / "tiny-gpt.pt"), str(versioned))
    retrain_log = {
        "ts": ts,
        "corpus_file": str(merged),
        "corpus_records": merged_n,
        "corpus_chars": merged_c,
        "academy_records": acad_n,
        "academy_chars": acad_c,
        "checkpoint": str(versioned),
        "fallback_kept": str(WEIGHTS_DIR / "tiny-gpt.pt"),
        "train": log,
        "seconds": round(time.time() - t0, 1),
    }
    (WEIGHTS_DIR / f"retrain_log_{ts}.json").write_text(
        json.dumps(retrain_log, indent=1))
    shutil.rmtree(staging, ignore_errors=True)

    # 4. journal the outcome
    _journal(
        "academy-retrain",
        ["growth", "levi-learned", "academy", "retrain-complete"],
        note=(f"Graduation brain retrain complete in {retrain_log['seconds']}s: "
              f"{merged_n} records ({acad_n} academy lessons), loss "
              f"{log.get('loss_first', '?'):.4f} -> {log.get('loss_last', '?'):.4f}. "
              f"New checkpoint {versioned.name}; previous tiny-gpt.pt kept as fallback."),
        checkpoint=str(versioned),
        corpus_records=merged_n,
    )
    print(f"retrain complete: {versioned}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
