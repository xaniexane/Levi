"""Batch scorer for teacher-record candidate batches: pre-gate triage.

Ranks candidate batch files using ONLY signals the pipeline itself
measures — nothing invented:

- identity-law pass rate (teacher_intake.check_identity_law)
- trace density (fraction of records carrying explicit reasoning
  markers — a documented heuristic, not a quality claim)
- dedup uniqueness (stable content IDs recomputed)
- teacher balance (no single voice dominating)
- provenance completeness (verify_provenance)

This is TRIAGE, not evaluation. The true quality verdict stays with
eval_gate.py's held-out cross-entropy: a high triage score means "worth
spending eval time on", never "this batch is good".

Stdlib only. Deterministic.

Usage:
    python -m levi.brain.train.teacher_score score --in batch.jsonl
    python -m levi.brain.train.teacher_score rank --in a.jsonl b.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:  # package import (tests, library use)
    from levi.brain.train import diag as diag
    from levi.brain.train.teacher_intake import (
        check_identity_law,
        record_id_for,
        verify_provenance,
        Rejected,
    )
except ImportError:  # script run from the train/ directory
    import diag as diag  # type: ignore[no-redef]
    from teacher_intake import (  # type: ignore[no-redef]
        check_identity_law,
        record_id_for,
        verify_provenance,
        Rejected,
    )

# Documented heuristic markers for "shows its reasoning". These are
# surface cues only — the eval gate decides real quality.
TRACE_MARKERS = (
    "thinking:",
    "reasoning:",
    "step 1",
    "step1",
    "first,",
    "because ",
    "therefore",
    "let me think",
)

# Composite weights. Documented and arbitrary by design: triage order,
# not a quality claim.
W_IDENTITY = 0.35
W_TRACE = 0.25
W_UNIQUE = 0.20
W_BALANCE = 0.10
W_PROVENANCE = 0.10


def _levi_turn(text: str) -> str:
    parts = text.split("\nLEVI:", 1)
    return parts[1] if len(parts) == 2 else ""


def _tokenizer():
    try:
        from levi.brain.train.teacher_mint import _load_tokenizer
    except ImportError:
        from teacher_mint import _load_tokenizer  # type: ignore[no-redef]
    return _load_tokenizer()


def score_records(records: list[dict]) -> dict:
    """Score one batch. Returns named components + composite."""
    n = len(records)
    if n == 0:
        return {"n": 0, "composite": 0.0, "note": "empty batch scores 0"}
    identity_ok = 0
    trace_hits = 0
    ids: set[str] = set()
    per_teacher: dict[str, int] = {}
    chars_total = 0
    for rec in records:
        text = rec.get("text", "")
        chars_total += len(text)
        levi = _levi_turn(text)
        try:
            check_identity_law(levi)
            identity_ok += 1
        except Rejected:
            pass
        low = text.lower()
        if any(m in low for m in TRACE_MARKERS):
            trace_hits += 1
        rid = rec.get("record_id") or record_id_for(text)
        ids.add(rid)
        src = rec.get("source", "")
        teacher = src.split(":", 1)[1] if ":" in src else "?"
        per_teacher[teacher] = per_teacher.get(teacher, 0) + 1
    bad_idx: set[int] = set()
    for i, rec in enumerate(records):
        if verify_provenance([rec]):
            bad_idx.add(i)
    prov_rate = (n - len(bad_idx)) / n
    identity_rate = identity_ok / n
    trace_rate = trace_hits / n
    unique_rate = len(ids) / n
    counts = list(per_teacher.values())
    balance = (min(counts) / max(counts)) if counts and max(counts) else 0.0
    composite = (
        W_IDENTITY * identity_rate
        + W_TRACE * trace_rate
        + W_UNIQUE * unique_rate
        + W_BALANCE * balance
        + W_PROVENANCE * prov_rate
    )
    result = {
        "n": n,
        "identity_pass_rate": round(identity_rate, 4),
        "trace_density": round(trace_rate, 4),
        "dedup_uniqueness": round(unique_rate, 4),
        "teacher_balance": round(balance, 4),
        "provenance_rate": round(prov_rate, 4),
        "per_teacher": per_teacher,
        "avg_chars_per_record": round(chars_total / n, 1),
        "composite": round(composite, 4),
        "weights": {
            "identity": W_IDENTITY,
            "trace": W_TRACE,
            "unique": W_UNIQUE,
            "balance": W_BALANCE,
            "provenance": W_PROVENANCE,
        },
        "note": "triage only; quality verdict belongs to eval_gate.py",
    }
    return result


def score_file(path: Path) -> dict:
    records, _d = diag.read_jsonl(path, name="batch")
    result = score_records(records)
    result["path"] = str(path)
    try:
        tok = _tokenizer()
        toks = sum(len(tok.encode(r.get("text", ""))) for r in records)
        result["tokens"] = toks
        result["avg_tokens_per_record"] = round(toks / len(records), 1)
    except Exception as exc:  # tokenizer unavailable: tokens stay unknown
        result["tokens"] = None
        result["tokenizer_error"] = str(exc)
    return result


def rank_batches(paths: list[Path]) -> list[dict]:
    scored = [score_file(p) for p in paths]
    return sorted(scored, key=lambda s: s["composite"], reverse=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Triage-score teacher batch files.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_score = sub.add_parser("score", help="score one batch file")
    p_score.add_argument("--in", dest="in_path", required=True)
    p_rank = sub.add_parser("rank", help="rank several batch files")
    p_rank.add_argument("--in", dest="in_paths", nargs="+", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "score":
        diag.require_file(args.in_path, name="batch file")
        print(json.dumps(score_file(Path(args.in_path)), indent=2))
        return 0
    if args.cmd == "rank":
        for p in args.in_paths:
            diag.require_file(p, name="batch file")
        ranked = rank_batches([Path(p) for p in args.in_paths])
        for i, s in enumerate(ranked, 1):
            print(
                f"{i}. {s['composite']:.4f}  {s['path']} "
                f"(n={s['n']} identity={s['identity_pass_rate']} "
                f"trace={s['trace_density']} unique={s['dedup_uniqueness']})"
            )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
