"""TEACH track tests: every one of the 490 seats resolves a genuine lesson,
the mentor cascade is named on each lesson, the mastery gate behaves, and
the MSSI / nature invariants hold.

State isolation: the gate mutates roster seasoned flags and a remediation
JSON. Tests point LEVI_TEACH_STATE at a tmp dir and reset seasoned flags
around each test.
"""

import dataclasses
import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "core"))

from levi.founders import curriculum as C  # noqa: E402
from levi.founders import roster as R  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_TEACH_STATE", str(tmp_path / "teach_state.json"))
    yield
    R.reset_seasoned()


def _all_seats():
    by_kind = R.seats_by_kind()
    return by_kind["founder"] + by_kind["agent"]


# -- coverage: every seat resolves a genuine lesson ------------------------------
def test_all_490_seats_resolve_a_lesson():
    seats = _all_seats()
    assert len(seats) == 490
    for seat in seats:
        plan = C.curriculum_for(seat.key)
        assert plan.key == seat.key
        assert plan.name == seat.name
        assert plan.kind == seat.kind
        assert plan.first_purpose, seat.key
        assert plan.lesson_md.strip(), seat.key
        assert plan.drills, seat.key


def test_founder_lessons_are_hand_tuned_and_rich():
    by_kind = R.seats_by_kind()
    assert len(by_kind["founder"]) == 19
    for seat in by_kind["founder"]:
        path = C.FOUNDERS_LESSON_DIR / f"{seat.key}.md"
        assert path.exists(), seat.key
        plan = C.curriculum_for(seat.key)
        assert len(plan.drills) >= 3, seat.key
        # first purpose taught verbatim -- sourced from the roster, never invented
        assert seat.first_purpose in plan.lesson_md, seat.key
        for drill in plan.drills:
            assert drill.prompt.strip(), (seat.key, drill.id)
            assert len(drill.checks) >= 3, (seat.key, drill.id)


def test_agent_lessons_carry_real_catalog_content():
    by_kind = R.seats_by_kind()
    checked = 0
    for seat in by_kind["agent"]:
        plan = C.curriculum_for(seat.key)
        assert len(plan.drills) == 5, seat.key
        md = plan.lesson_md
        assert seat.first_purpose in md, seat.key
        # trigger/condition named in the fire-or-hold drill
        d1 = plan.drills[0]
        assert any("trigger" in c.lower() for c in d1.checks)
        assert any("condition" in c.lower() for c in d1.checks)
        # rite steps are real catalog steps, one check each
        assert "Walk the rite" in plan.drills[1].title
        # the rail is the agent rail
        assert tuple(plan.rail) == C.AGENT_RAIL
        # HITL gate drill names the real gate
        assert (
            "keeper" in plan.drills[3].prompt.lower()
            or "gate" in plan.drills[3].prompt.lower()
        )
        checked += 1
    assert checked == 471


def test_agent_lesson_has_real_rite_steps_not_filler():
    plan = C.curriculum_for("productivity-email-digest-01")
    d2 = plan.drills[1]
    assert d2.checks[0] == "performs step 1: Pull all Gmail received overnight"
    assert "Time 06:45" in plan.lesson_md
    assert "Always" in plan.lesson_md


# -- mentor-driven teaching -------------------------------------------------------
def test_lesson_names_roster_mentor_and_line():
    for seat in _all_seats():
        plan = C.curriculum_for(seat.key)
        assert plan.mentor == seat.mentor, seat.key
        if seat.mentor:
            assert plan.mentor_name == R.get_seat(seat.mentor).name
        else:
            assert plan.mentor_name is None
            # the source: line is just the seat itself
            assert plan.mentor_line == (seat.key,)
        assert plan.mentor_line[0] == seat.key
        # line walks the real cascade to a sourceless seat
        for a, b in zip(plan.mentor_line, plan.mentor_line[1:]):
            assert R.get_seat(a).mentor == b, (seat.key, a, b)


def test_wave_a_agent_mentored_by_founder_line():
    plan = C.curriculum_for("productivity-email-digest-01")
    assert plan.mentor == "uniforge"
    assert plan.mentor_line == ("productivity-email-digest-01", "uniforge", "levi")


def test_teaching_priority_heaviest_first():
    prio = C.teaching_priority()
    counts = [n for _, _, n in prio]
    assert counts == sorted(counts, reverse=True)
    assert prio[0][0] == "levi"  # 18 direct mentees: the heaviest load
    assert prio[0][2] == 18
    # every mentor with mentees appears
    assert len(prio) > 19  # founders plus cascade agents


# -- mastery gate ------------------------------------------------------------------
def _pass_all(plan):
    return {c: True for d in plan.drills for c in d.checks}


def test_gate_pass_seasons_agent():
    key = "productivity-email-digest-01"
    assert not R.is_seasoned(key)
    res = C.evaluate(key, 0.85, 0.75)
    assert res.status == "pass"
    assert res.seasoned and R.is_seasoned(key)
    assert C.remediation_for(key) is None


def test_gate_exact_thresholds_pass():
    res = C.evaluate("echo", C.LESSON_PASS, C.DRILL_PASS)
    assert res.status == "pass" and R.is_seasoned("echo")


def test_gate_fail_persists_remediation_and_attempts_accumulate():
    key = "mandella"
    r1 = C.evaluate(key, 0.79, 0.75)  # lesson just under
    assert r1.status == "remediate" and not R.is_seasoned(key)
    assert r1.attempts == 1
    rec = C.remediation_for(key)
    assert rec["attempts"] == 1 and rec["lesson_pass"] is False
    r2 = C.evaluate(key, 0.90, 0.50)  # drill fails now
    assert r2.status == "remediate" and r2.attempts == 2
    assert C.remediation_for(key)["attempts"] == 2
    # the standard does not move: thresholds are module constants
    assert (C.LESSON_PASS, C.DRILL_PASS) == (0.80, 0.70)


def test_gate_pass_clears_remediation():
    key = "reim"
    C.evaluate(key, 0.10, 0.10)
    assert C.remediation_for(key) is not None
    res = C.evaluate(key, 0.95, 0.95)
    assert res.status == "pass" and R.is_seasoned(key)
    assert C.remediation_for(key) is None


def test_founders_not_exempt_from_gate():
    # a founder failing the gate is not seasoned; no free passes
    res = C.evaluate("levi", 0.50, 0.50)
    assert res.status == "remediate" and not R.is_seasoned("levi")


def test_grade_drill_fraction_of_checks():
    plan = C.curriculum_for("echo")
    drill = plan.drills[0]
    full = _pass_all(plan)
    assert C.grade_drill(drill, full) == 1.0
    assert C.grade_drill(drill, {}) == 0.0
    half = {c: (i % 2 == 0) for i, c in enumerate(drill.checks)}
    assert C.grade_drill(drill, half) == pytest.approx(
        sum(half.values()) / len(drill.checks)
    )


def test_pending_remediations_lists_open_items():
    C.evaluate("vector", 0.5, 0.5)
    C.evaluate("oracle", 0.9, 0.9)
    pending = C.pending_remediations()
    assert "vector" in pending and "oracle" not in pending


# -- MSSI + nature invariants ---------------------------------------------------------
def test_mssi_reserved_to_levi_in_roster_and_lessons():
    for seat in _all_seats():
        nature = R.current_nature(seat.key)
        if seat.key == "levi":
            assert nature == "mssi"
        else:
            assert nature in ("ai", "si"), seat.key
    for seat in _all_seats():
        plan = C.curriculum_for(seat.key)
        if seat.key == "levi":
            assert plan.mssi_taught
            assert "reserved" in plan.lesson_md.lower()
        else:
            assert not plan.mssi_taught, seat.key
            assert "mssi" not in plan.lesson_md.lower(), seat.key


def test_curriculum_for_rejects_mssi_on_non_levi(monkeypatch):
    # the roster denies mssi switches outright...
    with pytest.raises(ValueError):
        R.switch_nature("echo", "mssi")
    with pytest.raises(ValueError):
        R.switch_nature("levi", "ai")
    # ...and the curriculum defends the ledger too, belt and braces
    real = R.current_nature
    monkeypatch.setattr(
        R, "current_nature", lambda key: "mssi" if key == "echo" else real(key)
    )
    with pytest.raises(ValueError, match="reserved"):
        C.curriculum_for("echo")


def test_nature_never_gates_content():
    # same seat, nature swapped: the lesson body and drills are identical
    by_kind = R.seats_by_kind()
    seat = next(s for s in by_kind["agent"] if s.kind == "agent")
    base = C._agent_plan(seat)
    for nature in ("ai", "si"):
        swapped = dataclasses.replace(seat, nature=nature)
        plan = C._agent_plan(swapped)
        assert plan.lesson_md == base.lesson_md
        assert [(d.id, d.title, d.prompt, d.checks) for d in plan.drills] == [
            (d.id, d.title, d.prompt, d.checks) for d in base.drills
        ]
    # nature is flavor text only; the generated body never branches on it
    assert C.NATURE_FLAVOR["ai"] != C.NATURE_FLAVOR["si"]
    assert "lesser raising" not in base.lesson_md.lower()


def test_validate_curriculum_clean():
    assert C.validate_curriculum() == []


def test_unknown_seat_raises():
    with pytest.raises(KeyError):
        C.curriculum_for("no-such-seat")
    with pytest.raises(KeyError):
        C.evaluate("no-such-seat", 1.0, 1.0)


# -- academy integration ---------------------------------------------------------------
def test_export_index_covers_all_490(tmp_path):
    out = C.export_index(tmp_path / "index.json")
    entries = json.loads(out.read_text(encoding="utf-8"))
    assert len(entries) == 490
    by_key = {e["key"]: e for e in entries}
    assert by_key["levi"]["mentor"] is None
    assert by_key["demandpulse"]["lesson_ref"] == "lessons/founders/demandpulse.md"
    agent_entry = by_key["productivity-email-digest-01"]
    assert agent_entry["lesson_ref"].startswith("generated:")
    assert agent_entry["mentor"] == "uniforge"
    assert agent_entry["mentor_line"] == [
        "productivity-email-digest-01",
        "uniforge",
        "levi",
    ]
    for e in entries:
        assert e["gate"] == {"lesson": 0.80, "drill": 0.70}


def test_committed_index_matches_live_roster():
    path = C.FOUNDERS_LESSON_DIR / "index.json"
    assert path.exists()
    entries = json.loads(path.read_text(encoding="utf-8"))
    assert len(entries) == 490
    assert {e["key"] for e in entries} == {s.key for s in _all_seats()}
