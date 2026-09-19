"""Tests for the meetup-safety module (both tracks, privacy-first)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from levi.creator import TRACK_AI, TRACK_SI
from levi.creator.ai.rules import RulesError
from levi.creator.safety import (
    SafetyDeniedError,
    SafetyError,
    add_contact,
    check_in,
    create_plan,
    end_plan,
    list_contacts,
    list_escalations,
    plan_status,
    run_escalation_check,
)
from levi.creator.store import ai_read_all, si_read_all
from levi.plaiground.gate import (
    CONFIRMATION_PHRASE,
    GateLockedError,
    enable_adult_mode,
)


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


def _enable(home):
    return enable_adult_mode(CONFIRMATION_PHRASE, home=home)


def _future_iso(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


# -- SI gate law ----------------------------------------------------------


def test_si_safety_locked_without_gate(home):
    with pytest.raises(GateLockedError):
        add_contact("u1", "Mom", "tel:555-0100", TRACK_SI, home)


def test_si_plan_locked_without_gate(home):
    with pytest.raises(GateLockedError):
        create_plan("u1", "Alex", "cafe", _future_iso(60), 30, ["c1"], TRACK_SI, home=home)


# -- SI happy path --------------------------------------------------------


def _si_setup(home):
    _enable(home)
    c1 = add_contact("u1", "Mom", "tel:555-0100", TRACK_SI, home)
    c2 = add_contact("u1", "Rae", "tel:555-0101", TRACK_SI, home)
    return c1, c2


def test_si_contacts_owner_only(home):
    _si_setup(home)
    assert len(list_contacts("u1", TRACK_SI, home)) == 2
    # Another user sees nothing — not an error, just nothing.
    assert list_contacts("u2", TRACK_SI, home) == []


def test_si_plan_requires_own_contacts(home):
    _enable(home)
    add_contact("u1", "Mom", "tel:555-0100", TRACK_SI, home)
    with pytest.raises(SafetyError):
        create_plan("u1", "Alex", "cafe", _future_iso(60), 30, ["nope"], TRACK_SI, home=home)
    with pytest.raises(SafetyError):
        create_plan("u1", "Alex", "cafe", _future_iso(60), 30, [], TRACK_SI, home=home)


def test_si_plan_checkin_cycle(home):
    c1, _ = _si_setup(home)
    plan = create_plan(
        "u1", "Alex", "Riverside cafe", _future_iso(60), 30, [c1["id"]],
        TRACK_SI, disclosure="Call if I miss check-in.", home=home,
    )
    assert plan["status"] == "active"
    st = plan_status(plan["id"], "u1", TRACK_SI, home)
    assert st["status"] == "active" and st["missed"] is False
    check_in(plan["id"], "u1", TRACK_SI, home)
    st2 = plan_status(plan["id"], "u1", TRACK_SI, home)
    assert st2["last_checkin_at"] is not None


def test_si_plan_private_to_owner(home):
    c1, _ = _si_setup(home)
    plan = create_plan("u1", "Alex", "cafe", _future_iso(60), 30, [c1["id"]], TRACK_SI, home=home)
    with pytest.raises(SafetyDeniedError):
        plan_status(plan["id"], "u2", TRACK_SI, home)
    with pytest.raises(SafetyDeniedError):
        check_in(plan["id"], "u2", TRACK_SI, home)


def test_si_missed_checkin_escalates_once(home):
    c1, c2 = _si_setup(home)
    plan = create_plan(
        "u1", "Alex", "Riverside cafe", _future_iso(60), 5, [c1["id"], c2["id"]],
        TRACK_SI, disclosure="I am meeting Alex.", home=home,
    )
    future = datetime.now(timezone.utc) + timedelta(minutes=30)
    fired = run_escalation_check(TRACK_SI, home, now=future)
    assert len(fired) == 1
    esc = fired[0]
    # Only the pre-authorized disclosure leaves: contacts, who/where/when.
    assert {c["name"] for c in esc["contacts"]} == {"Mom", "Rae"}
    assert esc["who"] == "Alex" and esc["where"] == "Riverside cafe"
    assert esc["disclosure"] == "I am meeting Alex."
    assert esc["delivery"] == "pending"
    assert plan_status(plan["id"], "u1", TRACK_SI, home)["status"] == "escalated"
    # Never repeats.
    assert run_escalation_check(TRACK_SI, home, now=future) == []


def test_si_checkin_before_deadline_no_escalation(home):
    c1, _ = _si_setup(home)
    plan = create_plan("u1", "Alex", "cafe", _future_iso(60), 30, [c1["id"]], TRACK_SI, home=home)
    check_in(plan["id"], "u1", TRACK_SI, home)
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    assert run_escalation_check(TRACK_SI, home, now=future) == []


def test_si_end_plan_closes_checkin(home):
    c1, _ = _si_setup(home)
    plan = create_plan("u1", "Alex", "cafe", _future_iso(60), 30, [c1["id"]], TRACK_SI, home=home)
    end_plan(plan["id"], "u1", TRACK_SI, home)
    assert plan_status(plan["id"], "u1", TRACK_SI, home)["status"] == "ended"
    with pytest.raises(SafetyError):
        check_in(plan["id"], "u1", TRACK_SI, home)
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    assert run_escalation_check(TRACK_SI, home, now=future) == []


def test_si_escalations_owner_only(home):
    c1, _ = _si_setup(home)
    plan = create_plan("u1", "Alex", "cafe", _future_iso(60), 5, [c1["id"]], TRACK_SI, home=home)
    future = datetime.now(timezone.utc) + timedelta(minutes=30)
    run_escalation_check(TRACK_SI, home, now=future)
    assert len(list_escalations("u1", TRACK_SI, home)) == 1
    assert list_escalations("u2", TRACK_SI, home) == []


def test_si_safety_sealed_at_rest(home):
    c1, _ = _si_setup(home)
    create_plan("u1", "Alex", "Secret Hideout Cafe", _future_iso(60), 30, [c1["id"]],
                TRACK_SI, home=home)
    raw = (home / ".levi" / "creator" / "si" / "safety_plans.jsonl").read_text()
    assert "Secret Hideout Cafe" not in raw  # sealed envelope only


# -- AI track: same shape, SFW, no gate -----------------------------------


def test_ai_safety_no_gate_needed(home):
    c = add_contact("u1", "Mom", "tel:555-0100", TRACK_AI, home)
    plan = create_plan("u1", "Jordan", "Central Park", _future_iso(60), 30, [c["id"]],
                       TRACK_AI, home=home)
    assert plan["status"] == "active"
    check_in(plan["id"], "u1", TRACK_AI, home)
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    assert run_escalation_check(TRACK_AI, home, now=future) == []


def test_ai_safety_sfw_enforced(home):
    with pytest.raises(RulesError):
        add_contact("u1", "xxx friend", "tel:555-0100", TRACK_AI, home)


def test_ai_missed_checkin_escalates(home):
    c = add_contact("u1", "Mom", "tel:555-0100", TRACK_AI, home)
    create_plan("u1", "Jordan", "Central Park", _future_iso(60), 5, [c["id"]],
                TRACK_AI, disclosure="Text me if silent.", home=home)
    future = datetime.now(timezone.utc) + timedelta(minutes=30)
    fired = run_escalation_check(TRACK_AI, home, now=future)
    assert len(fired) == 1
    assert fired[0]["contacts"][0]["name"] == "Mom"
    assert fired[0]["disclosure"] == "Text me if silent."


def test_ai_plan_private_to_owner(home):
    c = add_contact("u1", "Mom", "tel:555-0100", TRACK_AI, home)
    plan = create_plan("u1", "Jordan", "park", _future_iso(60), 30, [c["id"]], TRACK_AI, home=home)
    with pytest.raises(SafetyDeniedError):
        plan_status(plan["id"], "u2", TRACK_AI, home)


# -- Track isolation -------------------------------------------------------


def test_safety_tracks_never_merge(home):
    _enable(home)
    add_contact("u1", "Mom", "tel:555-0100", TRACK_SI, home)
    add_contact("u1", "Dad", "tel:555-0102", TRACK_AI, home)
    assert [c["name"] for c in si_read_all(home, "safety_contacts")] == ["Mom"]
    assert [c["name"] for c in ai_read_all(home, "safety_contacts")] == ["Dad"]
