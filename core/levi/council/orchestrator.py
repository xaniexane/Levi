"""Council orchestrator: LEVI's minds argue, the techniques judge.

Pipeline, identical for every mind:

  generate → static gates → tests → property checks → mutation sample
  → peer review → synthesize.

Rules:
- A candidate that fails static gates or tests never enters review.
- Test evidence outranks opinions: selection sorts by test pass rate
  first, review scores second.
- All minds are LEVI-native. No network, no keys, no external models.
- Unavailable minds skip with a note; the council runs with whoever
  shows up. A council with no candidates produces a receipt, not an
  error.
"""

from __future__ import annotations

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from .minds import mind_for
from .sandbox import run_candidate
from .seats import ALL_SEATS, detect_seats
from .techniques import (
    mutation_sample,
    parse_checklist,
    run_properties,
    static_gates,
    test_first_check,
)

_MAX_TEST_RUNS = 8  # cap on total candidate test executions per run


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _checklist_mean(checklist: dict) -> float:
    vals = {"PASS": 1.0, "UNKNOWN": 0.5, "FAIL": 0.0}
    scores = [vals.get(checklist[d]["verdict"], 0.5) for d in checklist]
    return sum(scores) / len(scores) if scores else 0.0


def _review_mean(cand: dict) -> float | None:
    means = [
        r["checklist_mean"]
        for r in cand.get("reviews", [])
        if r.get("checklist_mean") is not None
    ]
    return sum(means) / len(means) if means else None


def run_council(
    task: str,
    tests: str,
    properties: str | None = None,
    seats: list[str] | None = None,
    timeout: float = 120.0,
    prop_trials: int = 30,
    max_mutants: int = 12,
    run_id: str | None = None,
    minds: dict[str, Any] | None = None,
    executor: Any | None = None,
) -> dict:
    """Run the full council pipeline. Returns {"receipt": ..., "winner_code": ...}."""
    run_id = run_id or datetime.now(timezone.utc).strftime("council-%Y%m%dT%H%M%SZ")
    t_start = time.time()
    detected = {s.id: s for s in detect_seats()}
    minds = minds or {}

    if seats:
        unknown = [s for s in seats if s not in ALL_SEATS]
        requested = [s for s in seats if s in ALL_SEATS]
    else:
        requested = [s.id for s in detect_seats() if s.available]
        unknown = []

    notes: list[str] = []
    if unknown:
        notes.append(f"unknown seat ids ignored: {', '.join(unknown)}")

    # Drop requested seats whose minds are unavailable — skip, never error.
    seated: list[str] = []
    for seat_id in requested:
        seat = detected.get(seat_id)
        if seat is not None and seat.available:
            seated.append(seat_id)
        else:
            reason = seat.note if seat else "unknown seat"
            notes.append(f"seat '{seat_id}' sat out: {reason}")

    seat_rows = [
        {
            "id": s.id,
            "available": s.available,
            "label": s.label,
            "note": s.note,
        }
        for s in detect_seats()
    ]

    candidates: list[dict] = []
    test_runs = 0

    # -- generation (each LEVI mind independently) ----------------------
    own_executor = executor is None
    pool = executor or ThreadPoolExecutor(max_workers=max(1, len(seated)))

    def _gen(seat_id: str) -> dict:
        mind = minds.get(seat_id) or mind_for(seat_id)
        result = mind.generate(task, tests)
        return {
            "seat": seat_id,
            "model": result.model or seat_id,
            "code": result.text or "",
            "generated_ok": result.ok,
            "error": result.error,
            "note": result.note,
            "sha256": _sha256(result.text or ""),
            "bytes": len((result.text or "").encode("utf-8")),
        }

    try:
        for cand in pool.map(_gen, seated):
            candidates.append(cand)
    finally:
        if own_executor:
            pool.shutdown(wait=True)

    for cand in candidates:
        if not cand["generated_ok"]:
            notes.append(f"mind '{cand['seat']}' produced nothing: {cand['error']}")

    # -- gates + tests -------------------------------------------------
    def _gate_fail(cand: dict, gate: str, evidence: str) -> None:
        cand["gated"] = gate
        cand["reviews"] = []
        cand["review_mean"] = None
        notes.append(f"candidate from '{cand['seat']}' failed {gate}: {evidence[:120]}")

    for cand in candidates:
        cand["techniques"] = []
        if not cand["generated_ok"] or not cand["code"].strip():
            _gate_fail(cand, "generation", cand.get("error") or "empty code")
            continue

        static = static_gates(cand["code"])
        cand["techniques"].append(static.as_dict())
        if static.status == "fail":
            _gate_fail(cand, "static", static.evidence)
            continue

        tf = test_first_check(tests)
        cand["techniques"].append(tf.as_dict())
        if tf.status == "fail":
            _gate_fail(cand, "test-first", tf.evidence)
            continue

        if test_runs >= _MAX_TEST_RUNS:
            _gate_fail(cand, "tests", "test-run cap reached")
            continue
        test_runs += 1
        tres = run_candidate(
            cand["code"], tests, timeout=timeout, run_id=run_id, seat=cand["seat"]
        )
        test_info = {
            "ok": tres.ok,
            "timed_out": tres.timed_out,
            "passed": list(tres.passed),
            "failed": [
                {"name": f["name"], "error": f["error"][:300]} for f in tres.failed
            ],
            "pass_rate": round(tres.pass_rate, 3),
            "error": (tres.error or "")[:300],
            "elapsed_s": round(tres.elapsed_s, 2),
        }
        cand["tests"] = test_info
        if not tres.ok or tres.pass_rate == 0:
            _gate_fail(cand, "tests", tres.error or "no tests passed")
            continue

        prop = run_properties(
            cand["code"],
            properties,
            trials=prop_trials,
            timeout=timeout,
            run_id=run_id,
            seat=cand["seat"],
        )
        cand["techniques"].append(prop.as_dict())
        if prop.status == "fail":
            _gate_fail(cand, "properties", prop.evidence)
            continue

        mut = mutation_sample(
            cand["code"],
            tests,
            baseline_passed=test_info["passed"],
            timeout=min(timeout, 30.0),
            max_mutants=max_mutants,
            run_id=run_id,
            seat=cand["seat"],
        )
        cand["techniques"].append(mut.as_dict())
        cand["mutation"] = mut.details
        cand["gated"] = None

    # -- peer review between the minds ---------------------------------
    reviewable = [c for c in candidates if c.get("gated") is None]
    for cand in reviewable:
        cand["reviews"] = []
        for reviewer_id in seated:
            if reviewer_id == cand["seat"]:
                continue
            mind = minds.get(reviewer_id) or mind_for(reviewer_id)
            summary = (
                f"{len(cand['tests']['passed'])} passed, "
                f"{len(cand['tests']['failed'])} failed "
                f"(pass rate {cand['tests']['pass_rate']})"
            )
            rres = mind.review(task, cand["code"], summary)
            checklist = parse_checklist(rres.text)
            cand["reviews"].append(
                {
                    "reviewer": reviewer_id,
                    "ok": rres.ok,
                    "text": (rres.text or "")[:3000],
                    "checklist": checklist,
                    "checklist_mean": (
                        round(_checklist_mean(checklist), 3) if rres.ok else None
                    ),
                }
            )
        cand["review_mean"] = (
            round(_review_mean(cand), 3) if _review_mean(cand) is not None else None
        )

    # -- synthesize: test evidence beats opinions ----------------------
    def _sort_key(c: dict) -> tuple:
        rm = c.get("review_mean")
        kill = (c.get("mutation") or {}).get("kill_rate", 0.0)
        return (
            -(c.get("tests", {}).get("pass_rate", 0.0)),
            -(rm if rm is not None else 0.0),
            -(kill or 0.0),
            c["seat"],
        )

    ranked = sorted(reviewable, key=_sort_key)
    winner = ranked[0] if ranked else None

    receipt = {
        "task": task,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(time.time() - t_start, 2),
        "seats": seat_rows,
        "requested_seats": requested,
        "seated": seated,
        "candidates": [{k: v for k, v in c.items() if k != "code"} for c in candidates],
        "ranked_seats": [c["seat"] for c in ranked],
        "winner": winner["seat"] if winner else None,
        "winner_model": winner["model"] if winner else None,
        "notes": notes
        + [
            "all minds are LEVI-native: no network, no keys, no external models",
            "selection: test pass rate first, review scores second — "
            "test evidence outranks opinions",
            "mutation kill rate is advisory: a low rate indicts the "
            "tests, not the candidate",
        ],
    }
    return {
        "receipt": receipt,
        "winner_code": winner["code"] if winner else None,
    }
