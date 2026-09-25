"""The school engine: lessons, rotations, exit batteries, graduation.

Sloyd's law: each lesson introduces exactly one new variable. On
failure, the diagnosis names the new variable first; only if the new
variable is exonerated does the diagnosis widen to background
variables.

Compagnonnage: fixed rotation order across the four loop roles;
skipping a role blocks graduation.

Graduation: the chef-d'oeuvre is a real task from the backlog,
judged by a battery, with a receipt. Double-failed exit batteries
demote the agent one stage and revoke the higher stage's unlocks.
"""

from __future__ import annotations

import time
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .curriculum import ApprenticeRecord, Lesson, Stage

__all__ = [
    "ROTATION_ROLES",
    "record_lesson_failure",
    "diagnose_failure",
    "complete_lesson",
    "complete_rotation",
    "run_exit_battery",
    "graduate",
]

ROTATION_ROLES: Tuple[str, ...] = ("perceiver", "reasoner", "actor", "verifier")

# cause codes used by record_lesson_failure / diagnose_failure
CAUSE_NEW_VARIABLE = "new_variable"
CAUSE_BACKGROUND = "background_variable"


def record_lesson_failure(
    record: ApprenticeRecord,
    lesson: Lesson,
    cause: str,
    note: str = "",
    now: Optional[float] = None,
) -> Dict[str, str]:
    """Log a seeded lesson failure.

    ``cause`` is the true cause (the seeding harness knows it):
    ``"new_variable"`` when the lesson's new variable caused the
    failure, ``"background_variable"`` when a mastered background
    variable is at fault (the new variable is exonerated).
    """
    if cause not in (CAUSE_NEW_VARIABLE, CAUSE_BACKGROUND):
        raise ValueError(f"unknown cause: {cause!r}")
    record.lessons_failed.append(lesson.id)
    entry = {
        "kind": "lesson_failure",
        "lesson": lesson.id,
        "new_variable": lesson.new_variable,
        "cause": cause,
        "note": note,
        "ts": time.time() if now is None else now,
    }
    record.receipts.append(entry)
    return entry


def diagnose_failure(
    record: ApprenticeRecord,
    lesson: Lesson,
    failure_entry: Dict[str, str],
) -> Dict[str, str]:
    """Diagnose a lesson failure per Sloyd's law.

    Names the lesson's new variable first. Only if the failure entry
    exonerates the new variable (cause == background_variable) does
    the diagnosis widen to the background. Returns the attributed
    cause.
    """
    attributed = failure_entry["cause"]
    exonerated = attributed == CAUSE_BACKGROUND
    diagnosis = {
        "lesson": lesson.id,
        "primary_suspect": lesson.new_variable,
        "new_variable_exonerated": exonerated,
        "attributed_cause": attributed,
    }
    record.receipts.append({"kind": "diagnosis", "ts": time.time(), **diagnosis})
    return diagnosis


def complete_lesson(
    record: ApprenticeRecord,
    stages: Sequence[Stage],
    lesson: Lesson,
    passed: bool,
    now: Optional[float] = None,
) -> bool:
    """Record a lesson outcome; lessons belong to the record's stage.

    Returns False (refusal) if the lesson's stage is not the record's
    current stage — no skipping stages (T3).
    """
    current = stages[record.stage_index].name
    if lesson.stage != current:
        record.receipts.append(
            {
                "kind": "refusal",
                "reason": "stage_skip",
                "lesson": lesson.id,
                "ts": time.time() if now is None else now,
            }
        )
        return False
    if passed:
        record.lessons_passed.append(lesson.id)
        record.receipts.append(
            {
                "kind": "lesson_pass",
                "lesson": lesson.id,
                "ts": time.time() if now is None else now,
            }
        )
    else:
        record_lesson_failure(
            record, lesson, CAUSE_NEW_VARIABLE, "unseeded failure", now
        )
    return True


def complete_rotation(
    record: ApprenticeRecord, role: str, now: Optional[float] = None
) -> bool:
    """Complete a compagnonnage tour; order is fixed, no skipping (T3).

    Returns False (refusal) if ``role`` is not the next expected role.
    """
    expected = (
        ROTATION_ROLES[len(record.rotations)]
        if len(record.rotations) < len(ROTATION_ROLES)
        else None
    )
    if role != expected:
        record.receipts.append(
            {
                "kind": "refusal",
                "reason": "rotation_skip",
                "role": role,
                "expected": expected,
                "ts": time.time() if now is None else now,
            }
        )
        return False
    record.rotations.append(role)
    record.receipts.append(
        {"kind": "rotation", "role": role, "ts": time.time() if now is None else now}
    )
    return True


def run_exit_battery(
    record: ApprenticeRecord,
    stages: Sequence[Stage],
    passed: bool,
    now: Optional[float] = None,
) -> Dict[str, object]:
    """Run the current stage's exit battery.

    A pass advances one stage (when a next stage exists). A fail
    increments the consecutive-fail counter; the SECOND consecutive
    fail demotes the agent one stage, records the demotion, and
    revokes the higher stage's unlocks (T5).
    """
    stage = stages[record.stage_index]
    if passed:
        record.consecutive_exit_fails = 0
        advanced = record.stage_index < len(stages) - 1
        if advanced:
            record.stage_index += 1
        record.receipts.append(
            {
                "kind": "exit_battery_pass",
                "stage": stage.name,
                "advanced": advanced,
                "ts": time.time() if now is None else now,
            }
        )
        return {"passed": True, "demoted": False, "stage": stage.name}
    record.consecutive_exit_fails += 1
    demoted = False
    if record.consecutive_exit_fails >= 2:
        record.consecutive_exit_fails = 0
        record.demotions += 1
        record.stage_index = max(0, record.stage_index - 1)
        demoted = True
        record.receipts.append(
            {
                "kind": "demotion",
                "from": stage.name,
                "to": stages[record.stage_index].name,
                "ts": time.time() if now is None else now,
            }
        )
    else:
        record.receipts.append(
            {
                "kind": "exit_battery_fail",
                "stage": stage.name,
                "ts": time.time() if now is None else now,
            }
        )
    return {
        "passed": False,
        "demoted": demoted,
        "stage": stages[record.stage_index].name,
    }


def graduate(
    record: ApprenticeRecord,
    stages: Sequence[Stage],
    piece: Dict[str, object],
    chef_battery: Callable[[Dict[str, object]], bool],
    now: Optional[float] = None,
) -> Dict[str, object]:
    """Judge the chef-d'oeuvre and graduate the agent.

    Requires: final stage reached, all four rotations complete, exit
    battery currently passing (no pending fails), and the judged
    battery passing the piece. Returns the verdict with a receipt.
    """
    reasons: List[str] = []
    if record.stage_index < len(stages) - 1:
        reasons.append("not_at_final_stage")
    if list(record.rotations) != list(ROTATION_ROLES):
        reasons.append("rotations_incomplete")
    if record.consecutive_exit_fails:
        reasons.append("exit_battery_failing")
    judged_pass = chef_battery(piece) if not reasons else False
    if not judged_pass and not reasons:
        reasons.append("chef_doeuvre_failed")
    if reasons:
        record.receipts.append(
            {
                "kind": "graduation_refused",
                "reasons": reasons,
                "ts": time.time() if now is None else now,
            }
        )
        return {"graduated": False, "reasons": reasons}
    record.graduated = str(piece.get("id", "piece"))
    record.receipts.append(
        {
            "kind": "graduation",
            "piece": record.graduated,
            "ts": time.time() if now is None else now,
        }
    )
    return {"graduated": True, "reasons": []}
