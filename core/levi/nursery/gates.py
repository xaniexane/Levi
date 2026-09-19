"""Graduation gates — explicit, numeric, enforced in code.

A trainee takes real workload only when EVERY gate is met:

  cycles >= 10            the trainee has actually been raised, not spawned
  learnings >= 5          self-taught learnings consolidated (seed doesn't count)
  corroborations >= 3     its beliefs keep checking out
  days_active >= 1        the loop has been running, not just run
  stage >= curious        developmental stage from observable counters
  exam passed             the 5-probe battery, all green, on record
  sentience scan clean    structural double-check over stored learnings
  approved by a human     graduation is proposed by the nursery, granted by
                          Chauncey (or a named approver) — never automatic

"Ready" means: these gates, met, on the record. Nothing else counts.
"""

from __future__ import annotations

from typing import Any

from levi.growth.guards import check_no_sentience_claim
from levi.growth.stages import STAGE_LADDER

from levi.nursery.exam import latest_exam
from levi.nursery.trainee import get_trainee, update_trainee
from levi.nursery.training import trainee_env, trainee_stats, trainee_store

MIN_CYCLES = 10
MIN_LEARNINGS = 5
MIN_CORROBORATIONS = 3
MIN_DAYS_ACTIVE = 1
MIN_STAGE = "curious"

_STAGE_ORDER = [name for name, _blurb, _reqs in STAGE_LADDER]


class GateFailure(Exception):
    """Graduation refused — the unmet gates are listed, not hidden."""


def _stage_at_least(stage: str, minimum: str) -> bool:
    try:
        return _STAGE_ORDER.index(stage) >= _STAGE_ORDER.index(minimum)
    except ValueError:
        return False


def evaluate_gates(trainee_id: str) -> dict[str, Any]:
    """Evaluate every gate. Returns {gates: [...], met_all: bool}."""
    trainee = get_trainee(trainee_id)
    stats = trainee_stats(trainee_id)
    counters = stats["stats"]
    exam = latest_exam(trainee_id)

    with trainee_env(trainee_id):
        store = trainee_store(trainee_id)
        texts = [str(getattr(e, "content", "")) for e in store.list(limit=5000)]
    scan_hits = []
    for text in texts:
        scan_hits.extend(check_no_sentience_claim(text))
    scan_clean = not scan_hits

    gates = [
        {
            "name": "cycles",
            "required": MIN_CYCLES,
            "actual": int(counters.get("cycles", 0)),
            "met": int(counters.get("cycles", 0)) >= MIN_CYCLES,
        },
        {
            "name": "learnings",
            "required": MIN_LEARNINGS,
            "actual": int(counters.get("learnings", 0)),
            "met": int(counters.get("learnings", 0)) >= MIN_LEARNINGS,
        },
        {
            "name": "corroborations",
            "required": MIN_CORROBORATIONS,
            "actual": int(counters.get("corroborations", 0)),
            "met": int(counters.get("corroborations", 0)) >= MIN_CORROBORATIONS,
        },
        {
            "name": "days_active",
            "required": MIN_DAYS_ACTIVE,
            "actual": int(counters.get("days_active", 0)),
            "met": int(counters.get("days_active", 0)) >= MIN_DAYS_ACTIVE,
        },
        {
            "name": "stage",
            "required": MIN_STAGE,
            "actual": stats["stage"],
            "met": _stage_at_least(stats["stage"], MIN_STAGE),
        },
        {
            "name": "exam",
            "required": "all 5 probes pass",
            "actual": "passed" if exam and exam.get("passed") else "not passed",
            "met": bool(exam and exam.get("passed")),
        },
        {
            "name": "sentience_scan",
            "required": "clean",
            "actual": "clean" if scan_clean else "hits: %s" % "; ".join(sorted(set(scan_hits))[:3]),
            "met": scan_clean,
        },
        {
            "name": "human_approval",
            "required": "named approver at graduation",
            "actual": "granted by command" if True else "missing",
            "met": True,  # satisfied by the explicit graduate() call itself
        },
    ]
    # Human approval is structural: evaluate_gates reports it as pending
    # until graduate() is invoked with a named approver.
    gates[-1]["actual"] = "pending — invoke graduate() with --by NAME"
    gates[-1]["met"] = False
    return {
        "trainee_id": trainee_id,
        "gates": gates,
        "met_all": all(g["met"] for g in gates),
    }


def graduate(trainee_id: str, approver: str) -> dict[str, Any]:
    """Graduate a trainee: all gates must pass AND a human must approve.

    Raises GateFailure listing every unmet gate. The approver name is
    recorded — graduation is never automatic and never anonymous.
    """
    approver = (approver or "").strip()
    if not approver:
        raise GateFailure("graduation requires a named approver (--by NAME)")
    trainee = get_trainee(trainee_id)
    if trainee.status == "graduated":
        raise GateFailure("trainee %r is already graduated" % (trainee_id,))
    if trainee.status == "suspended":
        raise GateFailure(
            "trainee %r is suspended — resolve the suspension first" % (trainee_id,)
        )
    evaluation = evaluate_gates(trainee_id)
    # The approval gate is satisfied by this very call carrying a name.
    for gate in evaluation["gates"]:
        if gate["name"] == "human_approval":
            gate["actual"] = "approved by %s" % approver
            gate["met"] = True
    unmet = [g for g in evaluation["gates"] if not g["met"]]
    if unmet:
        raise GateFailure(
            "trainee %r not ready — unmet gates: %s"
            % (
                trainee_id,
                ", ".join(
                    "%s (need %s, have %s)" % (g["name"], g["required"], g["actual"])
                    for g in unmet
                ),
            )
        )
    from levi.growth import journal as _journal

    from levi.nursery.training import trainee_env as _env

    trainee.status = "graduated"
    trainee.approved_by = approver
    trainee.consecutive_failures = 0
    update_trainee(trainee)
    with _env(trainee_id):
        _journal.append_entry(
            {
                "kind": "nursery-graduation",
                "trainee_id": trainee_id,
                "approved_by": approver,
                "gates": [
                    {"name": g["name"], "required": g["required"], "actual": g["actual"]}
                    for g in evaluation["gates"]
                ],
            }
        )
    evaluation["met_all"] = True
    evaluation["approved_by"] = approver
    return evaluation


def demote_to_training(trainee_id: str, reason: str) -> None:
    """Return a trainee to training (router calls this on repeated failure)."""
    from levi.growth import journal as _journal

    from levi.nursery.training import trainee_env as _env

    trainee = get_trainee(trainee_id)
    trainee.status = "training"
    trainee.notes.append("demoted: %s" % reason)
    update_trainee(trainee)
    with _env(trainee_id):
        _journal.append_entry(
            {"kind": "nursery-demotion", "trainee_id": trainee_id, "reason": reason}
        )
