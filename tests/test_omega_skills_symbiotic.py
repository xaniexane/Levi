"""Omega SKILLS symbiotic proof (worker 🖐️).

INVARIANT (declared in ``levi.revival.omega.si.skill_core``): "No skill
runs without a declared risk tier and a receipt. Every run is
challengeable."

PROOF STATEMENT (honest, not formal): these tests drive register_skill,
run_skill_guarded, and the substrate interrogation path and assert the
observable consequences — ValueError on an unapproved elevated
registration, receipts for registrations and runs, refusals for unknown
skills and missing approval, the ceiling-inheritance that makes even a
"low"-risk skill need approval, and quarantine/release of a run receipt
through the daemon's challenge. They do not formally prove the
invariant in general; they prove this implementation holds the line on
every path it offers.

Covers:
- register_skill: elevated + substrate + no approval -> ValueError and
  no receipt; with approved_by -> ok and a skill_registered receipt.
  Empty name / bad tier -> ValueError. Re-registering overwrites.
- get_skill / list_skills.
- run_skill_guarded: unknown skill -> refusal; known skill without
  approved_by -> refused (no skill_run receipt, a standard-tier
  skill_refusal receipt instead); with approved_by -> ok, receipt
  exists, ceiling recorded, runs counter increments.
- ceiling inheritance: a skill registered at "low" still refuses
  without approval — the skill organ's elevated ceiling governs.
- interrogation: the daemon challenges a run receipt -> is_consumable
  False (quarantined); a dismissed challenge releases it; an upheld
  challenge holds it forever.
"""

import pytest

from levi.revival.omega import substrate as sub
from levi.revival.omega.si import skill_core


@pytest.fixture(autouse=True)
def _clean_registry():
    skill_core._REGISTRY.clear()
    skill_core._PROCEDURES.clear()
    yield
    skill_core._REGISTRY.clear()
    skill_core._PROCEDURES.clear()


def _substrate():
    return sub.SharedSubstrate()


# ---------------------------------------------------------------------------
# register_skill
# ---------------------------------------------------------------------------


def test_register_elevated_without_approval_raises():
    s = _substrate()
    with pytest.raises(ValueError):
        skill_core.register_skill(
            "status-brief", "draft a status brief", risk="elevated", substrate=s
        )
    # Loud refusal, not a silent record: nothing in the bloodstream.
    assert s.receipts(organ="skill", kind="skill_registered") == []


def test_register_with_approval_records_receipt():
    s = _substrate()
    out = skill_core.register_skill(
        "status-brief",
        "draft a status brief",
        risk="elevated",
        approved_by="test",
        substrate=s,
    )
    assert out == {"ok": True, "name": "status-brief", "risk": "elevated"}
    receipts = s.receipts(organ="skill", kind="skill_registered")
    assert len(receipts) == 1
    rcpt = receipts[0]
    assert rcpt.payload["name"] == "status-brief"
    assert rcpt.payload["capability"] == "draft a status brief"
    assert rcpt.risk == "elevated"
    assert rcpt.approved_by == "test"


def test_register_low_risk_needs_no_approval():
    s = _substrate()
    out = skill_core.register_skill(
        "ping", "say pong", risk="low", substrate=s
    )
    assert out["ok"] is True
    receipts = s.receipts(organ="skill", kind="skill_registered")
    assert len(receipts) == 1
    assert receipts[0].risk == "low"


def test_register_validates_name_and_tier():
    with pytest.raises(ValueError):
        skill_core.register_skill("", "no name")
    with pytest.raises(ValueError):
        skill_core.register_skill("   ", "blank name")
    with pytest.raises(ValueError):
        skill_core.register_skill("ok-name", "cap", risk="bogus")
    assert skill_core.list_skills() == []


def test_reregister_overwrites_documented():
    skill_core.register_skill("brief", "first draft", risk="low")
    skill_core._REGISTRY["brief"]["runs"] = 7  # simulate prior runs
    skill_core.register_skill("brief", "second draft", risk="low")
    entry = skill_core.get_skill("brief")
    assert entry["capability"] == "second draft"
    assert entry["runs"] == 0  # overwrite is current-state, not history


def test_get_skill_and_list_skills():
    assert skill_core.get_skill("nope") is None
    skill_core.register_skill("a", "does a", risk="low")
    skill_core.register_skill("b", "does b", risk="standard")
    assert sorted(skill_core.list_skills()) == ["a", "b"]
    entry = skill_core.get_skill("a")
    assert entry == {"capability": "does a", "risk": "low", "runs": 0}
    # The returned dict is a copy: mutating it must not touch the registry.
    entry["runs"] = 999
    assert skill_core.get_skill("a")["runs"] == 0


# ---------------------------------------------------------------------------
# run_skill_guarded
# ---------------------------------------------------------------------------


def test_run_unknown_skill_refused():
    out = skill_core.run_skill_guarded(_substrate(), "ghost", "do it")
    assert out == {"ok": False, "refusal": "unknown skill"}


def test_run_without_approval_refused_no_run_receipt():
    s = _substrate()
    skill_core.register_skill(
        "status-brief", "draft a status brief", approved_by="test", substrate=s
    )
    out = skill_core.run_skill_guarded(s, "status-brief", "brief the team")
    assert out["ok"] is False
    assert out["refusal"] == "approval required"
    assert out["ceiling"] == "elevated"
    # Nothing ran: no skill_run receipt, runs counter untouched.
    assert s.receipts(organ="skill", kind="skill_run") == []
    assert skill_core.get_skill("status-brief")["runs"] == 0
    # But the refusal itself is observed: a standard-tier receipt, no
    # approval needed (records the refusal without the approval Catch-22).
    refusals = s.receipts(organ="skill", kind="skill_refusal")
    assert len(refusals) == 1
    assert refusals[0].risk == "standard"
    assert refusals[0].payload["reason"] == "approval required"


def test_run_with_approval_ok_receipt_and_ceiling():
    s = _substrate()
    skill_core.register_skill(
        "status-brief", "draft a status brief", approved_by="test", substrate=s
    )
    out = skill_core.run_skill_guarded(
        s, "status-brief", "brief the team", approved_by="daemon-loop"
    )
    assert out["ok"] is True
    assert out["ceiling"] == "elevated"
    assert out["result"]["skill"] == "status-brief"
    assert out["result"]["task"] == "brief the team"
    receipt = s.get_receipt(out["receipt_id"])
    assert receipt is not None
    assert receipt.kind == "skill_run"
    assert receipt.organ == "skill"
    assert receipt.risk == "elevated"  # the ceiling is recorded on the receipt
    assert receipt.approved_by == "daemon-loop"
    assert receipt.payload["skill"] == "status-brief"
    assert skill_core.get_skill("status-brief")["runs"] == 1


def test_run_without_substrate_refused():
    # The invariant: no skill runs without a receipt. No substrate means
    # no receipt, so the run is refused even with approval.
    skill_core.register_skill("status-brief", "draft a status brief", risk="low")
    out = skill_core.run_skill_guarded(
        None, "status-brief", "brief the team", approved_by="daemon-loop"
    )
    assert out["ok"] is False
    assert "receipt" in out["refusal"]


def test_low_risk_skill_still_needs_approval_ceiling_inheritance():
    # Strictest-ceiling inheritance: the skill organ itself declares
    # elevated, so a "low"-risk skill still runs under the elevated
    # ceiling and still needs a recorded approval.
    s = _substrate()
    skill_core.register_skill("ping", "say pong", risk="low", substrate=s)
    out = skill_core.run_skill_guarded(s, "ping", "ping")
    assert out["ok"] is False
    assert out["refusal"] == "approval required"
    assert out["ceiling"] == "elevated"
    assert s.receipts(organ="skill", kind="skill_run") == []


def test_attached_procedure_runs_real_code():
    s = _substrate()
    skill_core.register_skill("adder", "add two numbers", approved_by="t", substrate=s)
    skill_core.attach_procedure("adder", lambda task: {"ok": True, "sum": 2 + 2})
    out = skill_core.run_skill_guarded(s, "adder", "2+2", approved_by="daemon")
    assert out["ok"] is True
    assert out["result"]["sum"] == 4
    assert "declared" not in out["result"]
    with pytest.raises(KeyError):
        skill_core.attach_procedure("ghost", lambda task: {})
    with pytest.raises(ValueError):
        skill_core.attach_procedure("adder", "not-callable")


# ---------------------------------------------------------------------------
# Interrogation: the daemon quarantines a skill result through challenge
# ---------------------------------------------------------------------------


def _approved_run(s, name="status-brief"):
    skill_core.register_skill(name, "draft a status brief", approved_by="t", substrate=s)
    out = skill_core.run_skill_guarded(s, name, "brief the team", approved_by="daemon-loop")
    assert out["ok"] is True
    return out["receipt_id"]


def test_daemon_challenge_quarantines_run_receipt():
    s = _substrate()
    receipt_id = _approved_run(s)
    assert s.is_consumable(receipt_id) is True
    # The daemon interrogates the result: quarantine, immediately.
    ch = s.challenge("daemon", receipt_id, "result looked wrong")
    assert ch.challenger == "daemon"
    assert ch.target_organ == "skill"
    assert s.is_consumable(receipt_id) is False
    assert s.get_receipt(receipt_id).quarantined is True


def test_dismissed_challenge_releases_run_receipt():
    s = _substrate()
    receipt_id = _approved_run(s)
    ch = s.challenge("daemon", receipt_id, "result looked wrong")
    assert s.is_consumable(receipt_id) is False
    s.resolve_challenge(ch.id, "dismissed", note="re-ran it, result was fine")
    assert s.is_consumable(receipt_id) is True


def test_upheld_challenge_holds_run_receipt_forever():
    s = _substrate()
    receipt_id = _approved_run(s)
    ch = s.challenge("daemon", receipt_id, "result looked wrong")
    s.resolve_challenge(ch.id, "upheld", note="confirmed bad")
    assert s.is_consumable(receipt_id) is False
    # A second look cannot release an upheld challenge.
    with pytest.raises(ValueError):
        s.resolve_challenge(ch.id, "dismissed")
    assert s.is_consumable(receipt_id) is False


def test_challenge_unknown_receipt_raises_loudly():
    s = _substrate()
    with pytest.raises(KeyError):
        s.challenge("daemon", "rcpt_does_not_exist", "grounds")
