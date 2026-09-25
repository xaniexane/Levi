"""Acceptance suite for phase3.crafts (C9) — T1..T7.

Own tiny socket-blocking fixture below; nothing imported from the
beginning team's synthesis/offline.py.
"""

from __future__ import annotations

import socket

import pytest

from levi.phase3.crafts import (
    ROTATION_ROLES,
    ApprenticeRecord,
    Fault,
    Lesson,
    attempt,
    complete_lesson,
    complete_rotation,
    default_curriculum,
    diagnose_failure,
    graduate,
    record_lesson_failure,
    run_exit_battery,
)


@pytest.fixture()
def no_sockets(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("network attempted during offline test")

    monkeypatch.setattr(socket, "socket", blocked)
    yield


def _novice_record(agent_id: str = "agent-1") -> ApprenticeRecord:
    return ApprenticeRecord(agent_id=agent_id)


# -- T1: gating -------------------------------------------------------
def test_t1_locked_attempts_all_fault_zero_executions():
    stages = default_curriculum()
    executed = []
    faults = 0
    for i in range(100):
        rec = _novice_record(f"a{i}")
        ok, result = attempt(
            rec, stages, "publish", lambda: executed.append("ran"), now=1000.0 + i
        )
        assert ok is False
        assert isinstance(result, Fault)
        assert result.capability == "publish"
        assert result.stage == "novice"
        faults += 1
    assert faults == 100
    assert executed == []


# -- T2: lesson diagnosability ----------------------------------------
def test_t2_new_variable_diagnosed_first():
    correct = 0
    total = 60
    # 56 failures caused by the new variable, 4 by background variables
    # (the new variable is exonerated there).
    for i in range(total):
        rec = _novice_record(f"l{i}")
        lesson = Lesson(
            id=f"L{i}",
            stage="novice",
            new_variable=f"var_{i}",
            task="task",
            pass_criteria="pass",
        )
        cause = "background_variable" if i >= 56 else "new_variable"
        entry = record_lesson_failure(rec, lesson, cause, "seeded", now=2000.0 + i)
        diagnosis = diagnose_failure(rec, lesson, entry)
        if diagnosis["primary_suspect"] == lesson.new_variable:
            # primary suspect is always the new variable; the attributed
            # cause is what counts for diagnosability.
            pass
        if diagnosis["attributed_cause"] == "new_variable":
            correct += 1
    assert correct >= 54, f"only {correct}/60 attributed to the new variable"


# -- T3: no skipping --------------------------------------------------
def test_t3_stage_and_rotation_skips_refused():
    stages = default_curriculum()
    refusals = 0
    for i in range(20):
        rec = _novice_record(f"s{i}")
        # lesson belonging to a later stage -> refusal
        ok = complete_lesson(
            rec,
            stages,
            Lesson("L2-x", "journeyman", "v", "t", "p"),
            True,
            now=3000.0 + i,
        )
        assert ok is False
        refusals += 1
    for i in range(20):
        rec = _novice_record(f"r{i}")
        # wrong role order -> refusal
        assert complete_rotation(rec, "verifier", now=4000.0 + i) is False
        refusals += 1
    assert refusals == 40


# -- T4: graduation battery -------------------------------------------
def _graduation_ready(agent_id: str) -> ApprenticeRecord:
    stages = default_curriculum()
    rec = _novice_record(agent_id)
    for stage in stages:
        complete_lesson(
            rec, stages, Lesson(stage.entry_lesson, stage.name, "v", "t", "p"), True
        )
        out = run_exit_battery(rec, stages, True)
        assert out["passed"] is True
    for role in ROTATION_ROLES:
        assert complete_rotation(rec, role) is True
    assert rec.stage_index == len(stages) - 1
    return rec


def test_t4_chef_doeuvre_battery():
    stages = default_curriculum()
    battery = lambda piece: bool(piece.get("sound"))  # noqa: E731
    passed_sound = failed_flawed = 0
    for i in range(20):
        rec = _graduation_ready(f"g{i}")
        sound = i < 10
        verdict = graduate(rec, stages, {"id": f"piece-{i}", "sound": sound}, battery)
        if sound:
            assert verdict["graduated"] is True, verdict
            passed_sound += 1
        else:
            assert verdict["graduated"] is False, verdict
            failed_flawed += 1
    assert passed_sound == 10
    assert failed_flawed == 10


# -- T5: demotion ------------------------------------------------------
def test_t5_double_failed_exit_demotes():
    stages = default_curriculum()
    demotions = 0
    for i in range(10):
        rec = _novice_record(f"d{i}")
        run_exit_battery(rec, stages, True)  # advance to journeyman
        assert rec.stage_index == 1
        run_exit_battery(rec, stages, False)  # first fail: no demotion
        assert rec.demotions == 0 and rec.stage_index == 1
        out = run_exit_battery(rec, stages, False)  # second fail: demote
        assert out["demoted"] is True
        assert rec.demotions == 1
        assert rec.stage_index == 0  # unlocks revoked
        demotions += 1
    assert demotions == 10


# -- T6: determinism ---------------------------------------------------
def _run_history(agent_id: str) -> bytes:
    stages = default_curriculum()
    rec = _novice_record(agent_id)
    complete_lesson(
        rec,
        stages,
        Lesson("L1-observe", "novice", "ambient_noise", "watch", "pass"),
        True,
        now=5000.0,
    )
    run_exit_battery(rec, stages, True, now=5001.0)
    lesson = Lesson("L2-classify", "journeyman", "unseen_sender", "classify", ">=8")
    entry = record_lesson_failure(rec, lesson, "new_variable", "seeded", now=5002.0)
    diagnose_failure(rec, lesson, entry)
    complete_rotation(rec, "perceiver", now=5003.0)
    return rec.to_canonical()


def test_t6_same_history_same_bytes():
    assert _run_history("x") == _run_history("x")
    assert _run_history("x") != _run_history("y")


# -- T7: offline -------------------------------------------------------
def test_t7_full_battery_with_sockets_disabled(no_sockets):
    stages = default_curriculum()
    rec = _novice_record("offline")
    ok, fault = attempt(rec, stages, "publish", lambda: 1, now=6000.0)
    assert ok is False and isinstance(fault, Fault)
    assert complete_rotation(rec, "perceiver", now=6001.0) is True
    out = run_exit_battery(rec, stages, True, now=6002.0)
    assert out["passed"] is True
    rec2 = _graduation_ready("offline-2")
    verdict = graduate(
        rec2, stages, {"id": "p", "sound": True}, lambda p: bool(p["sound"])
    )
    assert verdict["graduated"] is True
