"""Tests for levi.automation.followup — the follow-up planner."""

from __future__ import annotations

import pytest

from levi.automation import followup
from levi.automation.routines import Routine, RoutineRun, RoutineStep


def _routine(n=3):
    return Routine(
        id="r-1",
        name="Evening sweep",
        created_utc="2026-09-28T00:00:00Z",
        source="manual",
        steps=[RoutineStep(label=f"step {i}", minion_id=None) for i in range(1, n + 1)],
    )


def _run(routine_id="r-1", ok=False, notes=()):
    return RoutineRun(
        routine_id=routine_id, ok=ok, note="", step_notes=list(notes), dry_run=True
    )


def test_clean_run_returns_none():
    routine = _routine()
    assert (
        followup.plan_followup(routine, _run(ok=True, notes=["ok", "ok", "ok"])) is None
    )
    assert followup.plan_followup(routine, _run(ok=True, notes=[])) is None


def test_failed_run_carries_unfinished_forward():
    routine = _routine(3)
    plan = followup.plan_followup(
        routine, _run(ok=False, notes=["ok", "denied: hitl", "skipped"])
    )
    assert plan is not None
    assert plan.carried_steps == 2
    assert plan.unfinished == 2
    assert [s.label for s in plan.routine.steps] == ["step 2", "step 3"]
    # completed step 1 stays in the receipt — never replayed
    assert plan.routine.source == "followup:r-1"
    assert "carried from run" in plan.routine.steps[0].note
    assert plan.routine.id == "r-1-follow-up"


def test_failed_run_without_step_notes_carries_all():
    routine = _routine(2)
    plan = followup.plan_followup(routine, _run(ok=False, notes=[]))
    assert plan is not None
    assert plan.carried_steps == 2


def test_wrong_routine_refused():
    routine = _routine()
    with pytest.raises(followup.FollowupError):
        followup.plan_followup(routine, _run(routine_id="other"))


def test_too_many_notes_refused():
    routine = _routine(1)
    with pytest.raises(followup.FollowupError):
        followup.plan_followup(routine, _run(ok=False, notes=["ok", "ok", "ok"]))


def test_summarize():
    assert followup.summarize(None) == "run clean: no follow-up needed."
    routine = _routine(2)
    plan = followup.plan_followup(routine, _run(ok=False, notes=["fail"]))
    text = followup.summarize(plan)
    assert "2 unfinished step(s)" in text
    assert "Evening sweep (follow-up)" in text


def test_manifest_entry_shape():
    entry = followup.MANIFEST_ENTRY["automation-followup"]
    assert "automation.followup.plan" in entry["provides"]
    assert entry["requires"] == ["automation"]
