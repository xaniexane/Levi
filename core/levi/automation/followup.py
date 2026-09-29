"""Follow-up planner — the honest answer to "what's still open?".

A :class:`~levi.automation.routines.RoutineRun` is a receipt: what the
routine tried, step by step, through the automation rail. When a run
comes back not fully green, this module PLANS the follow-up — a new
:mod:`~levi.automation.routines` Routine carrying only the unfinished
steps forward, annotated with where it came from. It never executes
anything: the follow-up is plain data, and playback still goes through
the rail (Plan -> Preview -> Permission -> Execute -> Verify -> Receipt).

- :func:`plan_followup` — given a ``RoutineRun`` (and its
  ``Routine``), build the follow-up plan. A fully-ok run returns
  ``None``: nothing follows up, and the planner says so instead of
  inventing work. Steps are carried only from the first unfinished
  step onward; earlier successes stay in the receipt, never replayed.
- :func:`summarize` — one-line verdict of what the run needs next.

Laws
----
- plan-only: no execution, no side effects — the caller holds the plan
- deny-closed: the run must reference the routine's own id; a run with
  no unfinished steps returns ``None`` (never an empty routine); step
  notes longer than the step list are refused, never truncated
- honest carry: the follow-up carries only unfinished steps, with the
  original run id in its source — it never claims to be a fresh routine

Stdlib only, local-first.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from levi.automation.routines import Routine, RoutineRun, RoutineStep


class FollowupError(ValueError):
    """Raised when a follow-up cannot be planned honestly."""


@dataclass
class FollowupPlan:
    """The plan: a follow-up routine plus why it exists."""

    routine: Routine
    from_run_ok: bool
    unfinished: int
    carried_steps: int
    reason: str

    def to_dict(self):
        return {
            "routine": self.routine.to_dict(),
            "from_run_ok": self.from_run_ok,
            "unfinished": self.unfinished,
            "carried_steps": self.carried_steps,
            "reason": self.reason,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _first_unfinished(run: RoutineRun) -> Optional[int]:
    """Index of the first step whose note is not a success, or None."""
    if not run.step_notes:
        # no per-step evidence: an ok run is clean; a failed run with no
        # notes gives nothing honest to carry
        return None if run.ok else 0
    for i, note in enumerate(run.step_notes):
        if not note.strip().lower().startswith("ok"):
            return i
    return None


def plan_followup(
    routine: Routine,
    run: RoutineRun,
    *,
    name_suffix: str = "follow-up",
) -> Optional[FollowupPlan]:
    """Plan the follow-up for a routine run.

    Returns ``None`` when the run is clean (nothing follows up).
    Raises :class:`FollowupError` when the run cannot honestly map to the
    routine (wrong routine id, malformed step evidence).
    """
    if not isinstance(routine, Routine) or not isinstance(run, RoutineRun):
        raise FollowupError("followup: routine must be a Routine and run a RoutineRun")
    if run.routine_id != routine.id:
        raise FollowupError(
            f"followup: run references routine {run.routine_id!r}, "
            f"not {routine.id!r} — refused, never cross-wired"
        )
    if len(run.step_notes) > len(routine.steps):
        raise FollowupError(
            "followup: run has more step notes than the routine has steps"
        )

    first_bad = _first_unfinished(run)
    if first_bad is None:
        return None  # clean run: nothing to follow up, honestly

    unfinished = len(routine.steps) - first_bad
    carried: List[RoutineStep] = []
    for idx in range(first_bad, len(routine.steps)):
        step = routine.steps[idx]
        carried.append(
            RoutineStep(
                label=step.label,
                minion_id=step.minion_id,
                event_summary=step.event_summary,
                event_payload=dict(step.event_payload),
                note=f"carried from run {run.routine_id}: unfinished at step {idx + 1}",
            )
        )

    followup = Routine(
        id=f"{routine.id}-{name_suffix}",
        name=f"{routine.name} ({name_suffix})",
        created_utc=_utc_now(),
        source=f"followup:{run.routine_id}",
        steps=carried,
    )
    reason = (
        f"run ended not-ok ({unfinished} of {len(routine.steps)} steps "
        f"unfinished, first at step {first_bad + 1}); carrying unfinished "
        f"steps forward — completed steps stay in the receipt"
    )
    return FollowupPlan(
        routine=followup,
        from_run_ok=run.ok,
        unfinished=unfinished,
        carried_steps=len(carried),
        reason=reason,
    )


def summarize(plan: Optional[FollowupPlan]) -> str:
    """One-line verdict of what a run needs next."""
    if plan is None:
        return "run clean: no follow-up needed."
    return (
        f"follow-up planned: {plan.carried_steps} unfinished step(s) "
        f"carried into '{plan.routine.name}'."
    )


MANIFEST_ENTRY = {
    "automation-followup": {
        "provides": ["automation.followup.plan", "automation.followup.summarize"],
        "requires": ["automation"],
    },
}
