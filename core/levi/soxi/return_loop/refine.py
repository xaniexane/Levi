"""Refinement (R2).

Corrections are folded back as NEW correction-kind lessons that
reference the originals. Raw originals are never overwritten —
refined lessons are versioned and sit alongside them. Each correction
records: the original lesson_id, what was wrong, and the fix.

A correction's fix text follows the teacher brief's correction form:
the wrong answer, the fix, and why.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .common import append_receipt, base_dir, check_batch_id, read_chain, utcnow
from .verify import verdicts_path


def corrections_dir(base: Path | None = None) -> Path:
    p = (base or base_dir()) / "corrections"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _verdict(batch_id: str, base: Path) -> dict[str, Any]:
    for rec in read_chain(verdicts_path(base)):
        if rec.get("batch_id") == batch_id:
            return rec
    raise ValueError("refine: no verdict found for %s" % batch_id)


def _raw_lesson(batch_id: str, index: int, base: Path) -> dict[str, Any]:
    raw_path = base / "raw" / (batch_id + ".jsonl")
    lines = raw_path.read_text(encoding="utf-8").splitlines()
    return json.loads(lines[index])


def _suggest_fix(entry: dict, raw: dict) -> str:
    """Best-effort mechanical fix text. Facts beyond arithmetic are
    left to Chauncey's spot-check queue — the correction says so."""
    reasons = "; ".join(entry["reasons"])
    if any("arithmetic answer wrong" in r for r in reasons):
        from .verify import check_arithmetic

        status, detail = check_arithmetic(raw["text"])
        fix = (
            f"Wrong answer: the lesson as taught was wrong. {detail}. "
            "Rework the steps and the final answer before trusting this lesson."
        )
        why = "machine re-check of the strict arithmetic pattern"
    elif any("hype words" in r for r in reasons):
        fix = (
            "Wrong: lesson used hype language. Fix: strip the hype "
            "words and restate the same fact in plain ASCII, terse "
            "register, per the teacher brief."
        )
        why = "teacher brief forbids hype words; lessons must be plain"
    elif any("re-teach" in r for r in reasons):
        fix = (
            "Wrong: this ground was already taught. Fix: do not "
            "re-teach it; the store already holds this lesson under "
            "the same identity."
        )
        why = "no-duplicate-topics law (R4)"
    elif any("non-ASCII" in r for r in reasons):
        fix = (
            "Wrong: lesson carried non-ASCII characters. Fix: "
            "re-teach the same lesson in plain ASCII."
        )
        why = "teacher brief requires plain ASCII"
    elif any("sentience" in r for r in reasons):
        fix = (
            "Wrong: lesson claimed feelings, consciousness, or being "
            "alive. Fix: remove the claim and restate factually — the "
            "teacher is a text generator, not a being."
        )
        why = "teacher brief forbids sentience claims"
    else:
        fix = (
            "Wrong: %s. Fix: re-teach this lesson corrected, keeping "
            "the same subject and plain ASCII register."
        ) % reasons
        why = "verification finding"
    return (
        "Correction for lesson %s.\n"
        "What was wrong: %s\n"
        "The fix: %s\n"
        "Why: %s"
    ) % (entry["lesson_id"], reasons, fix, why)


def refine_batch(batch_id: str, base: Path | None = None) -> dict[str, Any]:
    """Build correction-kind lessons for one verified batch.

    Only runs on PASS_WITH_CORRECTIONS batches (PASS needs nothing,
    QUARANTINE cannot be refined — its bytes wait in quarantine).
    Corrections are written to corrections/<batch_id>.jsonl and
    recorded in a chained receipt. Raw originals are untouched (R2).
    """
    base = base or base_dir()
    batch_id = check_batch_id(batch_id)
    v = _verdict(batch_id, base)
    if v["verdict"] == "QUARANTINE":
        raise ValueError("refine: quarantined batch %s cannot be refined" % batch_id)
    needed = v.get("corrections_needed", [])
    if not needed:
        return {"batch_id": batch_id, "corrections": 0, "path": None}

    cpath = corrections_dir(base) / (batch_id + ".jsonl")
    written: list[dict[str, Any]] = []
    with open(cpath, "w", encoding="utf-8") as f:
        for entry in needed:
            raw = _raw_lesson(batch_id, entry["index"], base)
            correction = {
                "persona_condition": raw["persona_condition"],
                "kind": "correction",
                "topic": raw.get("topic", ""),
                "topic_id": "corr-" + entry["lesson_id"][:16],
                "text": _suggest_fix(entry, raw),
                "correction_of": entry["lesson_id"],
                "original_reasons": entry["reasons"],
                "batch_id": batch_id,
                "version": 2,
            }
            f.write(json.dumps(correction, ensure_ascii=False) + "\n")
            written.append(
                {"correction_of": entry["lesson_id"], "reasons": entry["reasons"]}
            )

    rec = append_receipt(
        base / "refinements.jsonl",
        {
            "ts": utcnow(),
            "batch_id": batch_id,
            "verdict": v["verdict"],
            "corrections": len(written),
            "corrections_file": cpath.name,
            "items": written,
        },
    )
    return {"batch_id": batch_id, "corrections": len(written),
            "path": str(cpath), "receipt": rec}
