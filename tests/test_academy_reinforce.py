"""Academy reinforcement tests — remediation, staff, curriculum, wiring.

Home-scoped (LEVI_HOME -> tmp), deterministic, no network.
"""

from __future__ import annotations

import pytest

from levi.academy import remediation, staff, subjects
from levi.academy.session_exercises import EXERCISE_RUNNERS

NEW_SUBJECT_IDS = [
    "supply-chain-defense",
    "insider-risk",
    "incident-command",
    "secure-baseline",
    "threat-hunting",
    "recovery-drills",
]


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


# ------------------------------------------------------------- help tickets
def test_ticket_lifecycle(home):
    t = remediation.request_help("levi", "d1b1", "stuck on the coverage map")
    assert t["status"] == "open"
    assert t["ticket_id"]
    assert remediation.help_stats()["open"] == 1
    opened = remediation.open_tickets("levi")
    assert len(opened) == 1 and opened[0]["ticket_id"] == t["ticket_id"]

    r = remediation.resolve_help(
        "levi", t["ticket_id"], "walked through it with the tutor"
    )
    assert r["status"] == "resolved"
    assert r["resolution"]
    assert r["resolved_at"]
    stats = remediation.help_stats("levi")
    assert stats["open"] == 0 and stats["resolved"] == 1 and stats["total"] == 1


def test_ticket_validation(home):
    with pytest.raises(ValueError):
        remediation.request_help("", "d1b1", "reason")
    with pytest.raises(ValueError):
        remediation.request_help("levi", "d1b1", "   ")
    with pytest.raises(KeyError):
        remediation.resolve_help("levi", "nope", "fixed it")


# --------------------------------------------------------- auto-remediation
def _failed_record(**kw):
    rec = {
        "session": "d1b1",
        "gate_passed": False,
        "mastery_score": 0.5,
        "missed_objectives": ["Explain the order of volatility"],
        "missed_questions": ["Why does collection order matter?"],
    }
    rec.update(kw)
    return rec


def test_auto_remediate_triggers_on_gate_fail(home):
    plan = remediation.auto_remediate("levi", _failed_record())
    assert plan is not None
    assert plan["trigger"] == "gate_failed"
    assert plan["session_id"] == "d1b1"
    assert len(plan["feynman_redrills"]) == 1
    assert len(plan["spaced_reviews"]) == 1
    assert plan["spaced_reviews"][0]["review_on"]
    assert plan["missed_objectives"] == ["Explain the order of volatility"]
    assert plan["guidance"]


def test_auto_remediate_triggers_on_low_mastery(home):
    rec = _failed_record(gate_passed=True, mastery_score=0.69)
    plan = remediation.auto_remediate("levi", rec)
    assert plan is not None
    assert plan["trigger"] == "low_mastery"


def test_auto_remediate_quiet_when_healthy(home):
    rec = _failed_record(gate_passed=True, mastery_score=0.9)
    assert remediation.auto_remediate("levi", rec) is None


def test_escalation_on_third_failure(home):
    objective = "Name the classic crypto failure modes"
    plans = [
        remediation.auto_remediate(
            "levi", _failed_record(missed_objectives=[objective])
        )
        for _ in range(3)
    ]
    assert plans[0]["escalations"] == []
    assert plans[1]["escalations"] == []
    assert len(plans[2]["escalations"]) == 1
    esc = plans[2]["escalations"][0]
    assert esc["objective"] == objective
    tickets = remediation.open_tickets("levi")
    escalated = [t for t in tickets if t["status"] == "escalated"]
    assert len(escalated) == 1
    assert remediation.failure_count("levi", objective) == 3


# ------------------------------------------------------------------- staff
def test_roster_seed():
    people = staff.roster()
    roles = {p["role"] for p in people}
    assert set(staff.ROLES) <= roles
    for p in people:
        assert p["callsign"] and p["job"]


def test_assign_staff_deterministic():
    first = staff.assign_staff("d3b2", ["tutor", "grader", "counselor"])
    second = staff.assign_staff("d3b2", ["tutor", "grader", "counselor"])
    assert first == second
    assert set(first) == {"tutor", "grader", "counselor"}
    assert all(v["role"] == k for k, v in first.items())


def test_assign_staff_validation():
    with pytest.raises(ValueError):
        staff.assign_staff("d1b1", ["janitor"])
    with pytest.raises(ValueError):
        staff.assign_staff("", ["tutor"])


def test_add_remove_staff(home):
    added = staff.add_staff("Quill", "tutor", home=home)
    assert added["callsign"] == "Quill"
    assert any(p["callsign"] == "Quill" for p in staff.roster(home=home))
    with pytest.raises(ValueError):
        staff.add_staff("Quill", "tutor", home=home)
    with pytest.raises(ValueError):
        staff.add_staff("Ghost", "janitor", home=home)
    removed = staff.remove_staff("Quill", home=home)
    assert removed["callsign"] == "Quill"
    with pytest.raises(KeyError):
        staff.remove_staff("Quill", home=home)


# -------------------------------------------------------------- curriculum
def test_new_subjects_shape():
    for sid in NEW_SUBJECT_IDS:
        s = subjects.get_subject(sid)
        assert len(s["objectives"]) == 3, sid
        assert len(s["key_questions"]) == 3, sid
        assert s["exercise_type"] in EXERCISE_RUNNERS, sid
        assert s["description"]
    assert len(subjects.SUBJECTS) == 20


def test_new_subjects_in_track():
    track = subjects.as_track()
    assert len(track["days"]) == 20
    titles = [e["title"] for e in track["days"].values()]
    for sid in NEW_SUBJECT_IDS:
        assert subjects.get_subject(sid)["title"] in titles
    for entry in track["days"].values():
        assert set(entry) == {"title", "objectives", "key_questions", "exercise_type"}


# ----------------------------------------------------------------- wiring
def test_attach_remediation_additive(home):
    result = {
        "session": "d2b3",
        "day": 2,
        "block": 3,
        "track": "A",
        "title": "Network Traffic Analysis",
        "gate_passed": False,
        "mastery_score": 0.4,
        "exercise_score": 0.5,
        "missed_objectives": ["Spot beaconing in flow data"],
        "missed_questions": [],
    }
    before = set(result)
    out = remediation.attach_remediation(dict(result))
    assert set(out) >= before  # nothing removed
    for k in before:
        assert out[k] == result[k]  # nothing altered
    assert out["remediation"] is not None
    assert out["remediation"]["trigger"] == "gate_failed"


def test_attach_remediation_healthy_gets_none(home):
    result = {"session": "d2b3", "gate_passed": True, "mastery_score": 0.95}
    out = remediation.attach_remediation(dict(result))
    assert out["remediation"] is None
    assert out["mastery_score"] == 0.95
