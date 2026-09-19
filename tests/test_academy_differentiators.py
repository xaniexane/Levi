"""Academy differentiators tests — home-scoped, deterministic, no network."""

from __future__ import annotations

import json

import pytest

from levi.academy.differentiators import compost, decay, livefire, mastery, receipts, stakes
from levi.academy.differentiators import _seal


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


# --- sealed skill receipts -------------------------------------------------

def test_receipt_mint_verify_roundtrip(home):
    r = receipts.mint_receipt("ada", "crypto-101", 0.92,
                              [{"name": "key exchange", "passed": True},
                               {"name": "threat model", "passed": True}])
    assert r["sealed"] is True
    payload = receipts.verify_receipt("ada", r["receipt_id"])
    assert payload["learner_id"] == "ada"
    assert payload["module_id"] == "crypto-101"
    assert payload["score"] == 0.92
    assert payload["checks_passed"] == 2


def test_receipt_tamper_detected(home):
    r = receipts.mint_receipt("ada", "crypto-101", 0.8,
                              [{"name": "x", "passed": True}])
    path = (home / "academy" / "differentiators" / "receipts" / "ada"
            / f"{r['receipt_id']}.json")
    record = json.loads(path.read_text())
    record["payload"]["score"] = 1.0  # tamper with the stored payload
    path.write_text(json.dumps(record))
    with pytest.raises(_seal.SealError):
        receipts.verify_receipt("ada", r["receipt_id"])


def test_receipt_envelope_tamper_detected(home):
    r = receipts.mint_receipt("ada", "crypto-101", 0.8,
                              [{"name": "x", "passed": True}])
    path = (home / "academy" / "differentiators" / "receipts" / "ada"
            / f"{r['receipt_id']}.json")
    record = json.loads(path.read_text())
    record["envelope"]["ct"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    path.write_text(json.dumps(record))
    with pytest.raises(_seal.SealError):
        receipts.verify_receipt("ada", r["receipt_id"])


def test_receipt_list_and_validation(home):
    receipts.mint_receipt("ada", "m1", 0.5, [{"name": "a", "passed": True}])
    receipts.mint_receipt("ada", "m2", 0.9, [{"name": "b", "passed": False}])
    listed = receipts.list_receipts("ada")
    assert len(listed) == 2
    with pytest.raises(ValueError):
        receipts.mint_receipt("", "m1", 0.5, [{"name": "a", "passed": True}])
    with pytest.raises(ValueError):
        receipts.mint_receipt("ada", "m1", 1.5, [{"name": "a", "passed": True}])
    with pytest.raises(KeyError):
        receipts.verify_receipt("ada", "nope")


# --- failure compost --------------------------------------------------------

def test_compost_generates_targeted_drill(home):
    d = compost.compost_failure("ada", "crypto-101", "ex-3", [
        {"name": "key exchange", "hint": "Revisit Diffie-Hellman steps."},
        {"name": "threat model", "hint": "List the attacker capabilities."},
    ])
    assert d["status"] == "assigned"
    assert d["targets"] == ["key exchange", "threat model"]
    drills = compost.list_drills("ada")
    assert len(drills) == 1
    prompts = [i["prompt"] for i in drills[0]["items"]]
    assert all("Diffie-Hellman" in p or "attacker capabilities" in p for p in prompts)


def test_compost_complete_all_and_partial(home):
    d = compost.compost_failure("ada", "m", "ex", [
        {"name": "a", "hint": "h1"}, {"name": "b", "hint": "h2"}])
    out = compost.complete_drill("ada", d["drill_id"], {"a": True, "b": False})
    assert out["status"] == "partial" and out["passed"] == 1
    out = compost.complete_drill("ada", d["drill_id"], {"b": True})
    assert out["status"] == "completed" and out["passed"] == 2
    with pytest.raises(KeyError):
        compost.complete_drill("ada", "nope", {})
    with pytest.raises(ValueError):
        compost.compost_failure("ada", "m", "ex", [])


# --- stake-under-fog drills --------------------------------------------------

def test_stakes_place_reveal_correct(home):
    assert stakes.balance("ada") == 100
    s = stakes.place_stake("ada", "drill-1", "q1", "answer-a", 40)
    assert s["balance"] == 60
    assert s["implicit_confidence"] == 0.4
    r = stakes.reveal("ada", "drill-1", "q1", True)
    assert r["payout"] == 80 and r["balance"] == 140


def test_stakes_wrong_loses_stake(home):
    stakes.place_stake("ada", "drill-1", "q1", "answer-a", 30)
    r = stakes.reveal("ada", "drill-1", "q1", False)
    assert r["payout"] == 0 and r["balance"] == 70


def test_stakes_guards(home):
    stakes.place_stake("ada", "d", "q", "a", 10)
    with pytest.raises(ValueError):
        stakes.place_stake("ada", "d", "q", "a2", 10)  # double stake
    with pytest.raises(ValueError):
        stakes.place_stake("ada", "d", "q2", "a", 1000)  # over balance
    with pytest.raises(ValueError):
        stakes.place_stake("ada", "d", "q2", "a", 0)  # below minimum
    with pytest.raises(KeyError):
        stakes.reveal("ada", "d", "never-staked", True)


def test_stakes_calibration_brier(home):
    stakes.place_stake("ada", "d", "q1", "a", 50)
    stakes.reveal("ada", "d", "q1", True)   # p=0.5, outcome=1 -> 0.25
    stakes.place_stake("ada", "d", "q2", "a", 100)
    stakes.reveal("ada", "d", "q2", False)  # p=1.0, outcome=0 -> 1.0
    rep = stakes.calibration_report("ada")
    assert rep["n"] == 2
    assert rep["brier"] == round((0.25 + 1.0) / 2, 3)
    empty = stakes.calibration_report("nobody")
    assert empty["n"] == 0 and empty["brier"] is None


# --- corroboration-gated mastery --------------------------------------------

def test_mastery_needs_three_contexts(home):
    mastery.record_demonstration("ada", "s1", "lab-sim", True)
    mastery.record_demonstration("ada", "s1", "written", True)
    st = mastery.mastery_status("ada", "s1")
    assert st["mastered"] is False and st["distinct_passed_contexts"] == 2
    st = mastery.record_demonstration("ada", "s1", "live-fire", True)
    assert st["mastered"] is True
    assert st["passed_contexts"] == ["lab-sim", "live-fire", "written"]


def test_mastery_failed_context_does_not_count(home):
    mastery.record_demonstration("ada", "s1", "c1", True)
    mastery.record_demonstration("ada", "s1", "c2", False)
    mastery.record_demonstration("ada", "s1", "c3", True)
    st = mastery.mastery_status("ada", "s1")
    assert st["mastered"] is False
    # a later pass in the same context overwrites — latest evidence wins
    mastery.record_demonstration("ada", "s1", "c2", True)
    assert mastery.mastery_status("ada", "s1")["mastered"] is True


def test_mastery_unknown_skill(home):
    st = mastery.mastery_status("ada", "never-seen")
    assert st["mastered"] is False and st["distinct_passed_contexts"] == 0


# --- skill decay --------------------------------------------------------------

def test_decay_half_life(home):
    now = 1_700_000_000.0
    decay.touch_skill("ada", "s1", now=now)
    assert decay.skill_strength("ada", "s1", now=now) == 1.0
    assert decay.skill_strength("ada", "s1", now=now + 30 * 86400) == 0.5
    assert decay.skill_strength("ada", "s1", now=now + 60 * 86400) == 0.25
    assert decay.skill_strength("ada", "ghost", now=now) == 0.0


def test_decay_due_and_retest(home):
    now = 1_700_000_000.0
    decay.touch_skill("ada", "fresh", now=now)
    decay.touch_skill("ada", "stale", now=now - 90 * 86400)
    due = decay.due_for_retest("ada", now=now)
    assert [d["skill_id"] for d in due] == ["stale"]
    r = decay.retest("ada", "stale", True, now=now)
    assert r["passed"] is True and r["strength"] == 1.0
    assert decay.due_for_retest("ada", now=now) == []
    r = decay.retest("ada", "fresh", False, now=now)
    assert r["needs_remediation"] is True and r["strength"] == 0.0
    with pytest.raises(KeyError):
        decay.retest("ada", "ghost", True)


# --- live-fire finals -----------------------------------------------------------

def test_live_fire_pass_mints_receipt(home):
    a = livefire.assign_live_fire("ada")
    assert a["task_kind"] == "sort_lines" and a["status"] == "assigned"
    out = livefire.run_live_fire("ada", a["final_id"],
                                 {"lines": ["b", "a", "c"]})
    assert out["status"] == "passed"
    payload = receipts.verify_receipt("ada", out["receipt_id"])
    assert payload["module_id"] == "live-fire-final"


def test_live_fire_failure_recorded_not_raised(home):
    a = livefire.assign_live_fire("ada")
    out = livefire.run_live_fire("ada", a["final_id"], {"nope": 1})
    assert out["status"] == "failed"
    assert "error" in out
    with pytest.raises(KeyError):
        livefire.run_live_fire("ada", "nope", {"lines": ["a"]})
    with pytest.raises(ValueError):
        livefire.run_live_fire("ada", a["final_id"], {"lines": ["a"]})  # already run
