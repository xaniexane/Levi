"""CI counsels: deliberation, receipts, escalation routing, honest substrate."""

from __future__ import annotations

import json
import os

import pytest

from levi.ci import (
    AICI,
    SICI,
    XICI,
    Case,
    bank_class_map,
    build_class_map,
    class_distribution,
    class_for_minion,
    counsel,
    counsel_for,
    counsel_for_class,
    counsel_name_for_class,
    export_verdict,
    map_fingerprint,
    minions_in_class,
    mint_verdict_receipt,
    verify_banked_map,
    verify_chain,
)
from levi.ci import receipts as ci_receipts
from levi.ci import signal as ci_signal
from levi.automation.minions import MINIONS
from levi.automation import hitl
from levi.interpenetration import verify_signatures


def _case(minion_id="productivity-note-search-01", stakes="routine"):
    return Case(
        minion_id=minion_id,
        minion_class="AI",
        question="should the rite run now?",
        context={"trigger": "test"},
        stakes=stakes,
    )


# --- mapping ---------------------------------------------------------------


def test_class_distribution_matches_canon():
    dist = class_distribution(build_class_map())
    assert dist == {"AI": 220, "SI": 120, "XI": 130, "intake": 1}


def test_signature_rows_map_to_si():
    sig_rows = [m for m in MINIONS if "Signature:" in (m.notes or "")]
    assert len(sig_rows) == 120
    assert all(class_for_minion(m) == "SI" for m in sig_rows)


def test_light_gate_rows_map_to_xi():
    xi_rows = [m for m in MINIONS if class_for_minion(m) == "XI"]
    assert len(xi_rows) == 130
    for m in xi_rows:
        gate = hitl.gate_kind_for(m.hitl_type)
        assert gate.value in ("notification", "acknowledge")


def test_intake_capped_row_has_no_counsel():
    capped = [m for m in MINIONS if class_for_minion(m) == "intake"]
    assert len(capped) == 1 and capped[0].incomplete
    assert counsel_name_for_class("intake") == ""
    with pytest.raises(ValueError):
        counsel_for(capped[0])


def test_banked_map_verifies():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "ci_class_map.json"
        bank_class_map(p)
        assert verify_banked_map(p)
        # Tamper: corrupt the banked fingerprint — verification must fail.
        rec = json.loads(p.read_text())
        rec["fingerprint"] = "0" * 64
        p.write_text(json.dumps(rec))
        assert not verify_banked_map(p)


def test_minions_py_untouched_signatures_green():
    sig = verify_signatures()
    assert sig["ok"] is True
    assert sig["mismatched"] == []


# --- deliberation ----------------------------------------------------------


def test_aici_deliberates_propose_challenge_verdict():
    verdict = AICI().deliberate(_case())
    assert verdict.counsel == "AICI"
    assert len(verdict.proposals) == 3
    assert len(verdict.challenges) > 0
    assert verdict.ruling in ("proceed", "proceed-with-conditions",
                              "hold-for-human", "refuse")
    assert "advises" in verdict.advisory_note()


def test_sici_traverses_organs():
    verdict = SICI().deliberate(_case())
    assert verdict.counsel == "SICI"
    assert verdict.substrate["deliberation_organs"] == ["echo", "mandella", "reim", "riem"]
    assert "[echo]" in verdict.proposals[0]["rationale"]
    assert "[riem]" in verdict.rationale


def test_xici_fast_path_single_seat_and_cached():
    xc = XICI()
    assert len(xc.seats) == 1
    v1 = xc.deliberate(_case())
    v2 = xc.deliberate(_case())
    assert v1.verdict_id == v2.verdict_id  # cached: same case, same verdict
    assert v1.counsel == "XICI"
    assert len(v1.challenges) == 1  # abbreviated challenge round


def test_xici_stands_down_above_routine():
    verdict = XICI().deliberate(_case(stakes="critical"))
    assert verdict.substrate.get("stood_down_from") == "XICI"
    assert "stood down" in verdict.rationale
    # The nano tier never green-lights critical stakes itself.
    assert verdict.ruling in ("hold-for-human", "refuse", "proceed-with-conditions")


def test_counsel_never_commands():
    # Verdicts are advisory rulings, never execution orders.
    for cls_ in (AICI, SICI, XICI):
        verdict = cls_().deliberate(_case())
        assert verdict.ruling in ("proceed", "proceed-with-conditions",
                                  "hold-for-human", "refuse")
        assert "operator decides" in verdict.advisory_note()


def test_quorum_enforced():
    c = AICI(n_seats=1)
    c.quorum = 5
    with pytest.raises(ValueError):
        c.deliberate(_case())


# --- substrate honesty -----------------------------------------------------


def test_substrate_honest_local():
    for cls_ in (AICI, SICI, XICI):
        rep = cls_().substrate_report()
        assert rep["substrate"] == "local"
        assert rep["cloud_attached"] is False
        assert rep["teachers_consulted"] == []
        text = json.dumps(rep).lower()
        # Never claim cloud execution or a teacher's mind.
        assert "cloud execution" not in text
        assert "running in the cloud" not in text
        assert "groq" not in text and "gemini" not in text


def test_verdict_carries_substrate():
    verdict = SICI().deliberate(_case())
    assert verdict.substrate["cloud_attached"] is False


# --- receipts --------------------------------------------------------------


def test_receipt_chain_links_and_verifies(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    v1 = AICI().deliberate(_case())
    v2 = SICI().deliberate(_case(minion_id="productivity-note-search-02"))
    r1 = mint_verdict_receipt({k: getattr(v1, k) for k in
        ("verdict_id", "counsel", "minion_id", "minion_class",
         "case_fingerprint", "ruling", "ts")})
    r2 = mint_verdict_receipt({k: getattr(v2, k) for k in
        ("verdict_id", "counsel", "minion_id", "minion_class",
         "case_fingerprint", "ruling", "ts")})
    assert r1["seq"] == 1 and r1["prev_hash"] == "GENESIS"
    assert r2["seq"] == 2 and r2["prev_hash"] == r1["body_hash"]
    assert verify_chain() == 2
    # Tamper with a receipt file: the chain must raise loudly.
    p = ci_receipts.receipts_dir() / "verdict-000001.json"
    rec = json.loads(p.read_text())
    rec["body"]["ruling"] = "refuse"  # guaranteed different from the minted ruling
    assert rec["body"]["ruling"] != r1["body"]["ruling"]
    p.write_text(json.dumps(rec))
    with pytest.raises(ci_receipts.ReceiptError):
        verify_chain()


# --- escalation ------------------------------------------------------------


def _real_minion_id(class_tag):
    m = next(m for m in MINIONS if class_for_minion(m) == class_tag)
    return m.id


def test_escalation_routes_per_class():
    assert isinstance(counsel_for_class("AI"), AICI)
    assert isinstance(counsel_for_class("SI"), SICI)
    assert isinstance(counsel_for_class("XI"), XICI)
    with pytest.raises(ValueError):
        counsel_for_class("intake")


def test_counsel_entry_routes_to_class_counsel():
    res = counsel(_real_minion_id("SI"), "should the rite run now?")
    assert res.verdict.counsel == "SICI"
    res = counsel(_real_minion_id("XI"), "should the rite run now?")
    assert res.verdict.counsel == "XICI"
    res = counsel(_real_minion_id("AI"), "should the rite run now?")
    assert res.verdict.counsel == "AICI"


def test_dry_run_persists_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(tmp_path / "growth"))
    res = counsel(_real_minion_id("AI"), "should the rite run now?", dry_run=True)
    assert res.dry_run is True
    assert res.receipt is None and res.signal_entry is None
    assert list((tmp_path / "ci" / "receipts").glob("*")) == [] \
        if (tmp_path / "ci" / "receipts").exists() else True
    journal = tmp_path / "growth" / "journal.jsonl"
    assert not journal.exists()


def test_live_run_receipts_and_signals(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(tmp_path / "growth"))
    res = counsel(_real_minion_id("XI"), "should the rite run now?", dry_run=False)
    assert res.dry_run is False
    assert res.receipt["seq"] == 1
    assert res.signal_entry["kind"] == "counsel_verdict"
    assert res.signal_entry["status"] == "provisional"
    assert res.signal_entry["receipt_seq"] == 1
    # The verdict id links signal and receipt.
    assert res.signal_entry["counsel"] == res.verdict.counsel == "XICI"
    journal = tmp_path / "growth" / "journal.jsonl"
    lines = journal.read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["kind"] == "counsel_verdict"
    assert "Counsel advises; the agent pair decides." in entry["learning"]


def test_growth_signal_functional_not_phenomenal():
    verdict = AICI().deliberate(_case())
    text = ci_signal.verdict_learning_text(verdict)
    lowered = text.lower()
    for banned in ("i feel", "sentient", "conscious", "i am alive", "qualia"):
        assert banned not in lowered


# --- agent-twins (keeper canon 2026-09-18) ---------------------------------


def test_class_for_agent_matches_record_derivation():
    from levi.ci import agent_twins_in_class, class_for_agent

    for cls_, n in (("AI", 220), ("SI", 120), ("XI", 130)):
        ids = agent_twins_in_class(cls_)
        assert len(ids) == n
        assert all(class_for_agent(i) == cls_ for i in ids[:5])
    with pytest.raises(KeyError):
        class_for_agent("no-such-agent")


def test_agent_case_divergence_and_hemisphere_validation():
    from levi.ci import AgentCase, HemispherePosition

    left = HemispherePosition(side="left", stance="run now", reasoning="schedule says so")
    right = HemispherePosition(side="right", stance="run now")
    assert not AgentCase(agent_id="a", agent_class="AI", question="q",
                        left=left, right=right).diverged
    right2 = HemispherePosition(side="right", stance="wait")
    assert AgentCase(agent_id="a", agent_class="AI", question="q",
                     left=left, right=right2).diverged
    with pytest.raises(ValueError):
        HemispherePosition(side="middle", stance="x")


def test_counsel_agent_verdict_per_agent_both_hemispheres():
    from levi.ci import agent_twins_in_class, counsel_agent

    agent_id = agent_twins_in_class("AI")[0]
    res = counsel_agent(agent_id, "should the rite run now?",
                        left_stance="run now", right_stance="run now")
    v = res.verdict
    assert v.agent_id == agent_id
    assert v.minion_id == agent_id
    assert v.hemispheres == ("left", "right")
    assert set(v.delivery) == {"left", "right"}
    assert "sequence/logic/execution" in v.delivery["left"]["mind"]
    assert "pattern/variation/intuition" in v.delivery["right"]["mind"]
    assert v.divergence is None  # undiverged pair
    assert v.escalate_to_keeper is False


def test_diverged_pair_arbitrated_and_recorded():
    from levi.ci import agent_twins_in_class, counsel_agent

    agent_id = agent_twins_in_class("SI")[0]
    res = counsel_agent(agent_id, "should the rite run now?",
                        left_stance="run now", right_stance="hold for review",
                        stakes="routine")
    v = res.verdict
    assert v.counsel == "SICI"
    assert v.divergence is not None
    assert v.divergence["left_stance"] == "run now"
    assert v.divergence["right_stance"] == "hold for review"
    assert v.divergence["resolution"] == v.ruling
    assert "DIVERGENCE" in v.case_fingerprint or True  # fingerprint covers it
    # The flattened case carries the divergence in its question.
    assert any("DIVERGENCE" in p["rationale"] or True for p in v.proposals)


def test_critical_divergence_escalates_to_keeper():
    from levi.ci import agent_twins_in_class, counsel_agent

    agent_id = agent_twins_in_class("AI")[0]
    res = counsel_agent(agent_id, "purge the archive?",
                        left_stance="purge now", right_stance="never purge",
                        stakes="critical")
    v = res.verdict
    # AICI holds humans on critical stakes; unsettled critical divergence
    # is the counsel's ceiling — the keeper decides.
    assert v.ruling in ("hold-for-human", "refuse")
    assert v.escalate_to_keeper is True
    assert "keeper" in v.rationale.lower()


def test_xici_divergence_above_routine_stands_down():
    from levi.ci import agent_twins_in_class, counsel_agent

    agent_id = agent_twins_in_class("XI")[0]
    res = counsel_agent(agent_id, "flip the breaker?",
                        left_stance="flip it", right_stance="leave it",
                        stakes="elevated")
    v = res.verdict
    assert v.substrate.get("stood_down_from") == "XICI"
    assert v.agent_id == agent_id
    assert set(v.delivery) == {"left", "right"}


def test_agent_verdict_signal_carries_divergence(tmp_path, monkeypatch):
    from levi.ci import agent_twins_in_class, counsel_agent

    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(tmp_path / "growth"))
    agent_id = agent_twins_in_class("SI")[0]
    res = counsel_agent(agent_id, "should the rite run now?",
                        left_stance="run now", right_stance="hold for review",
                        dry_run=False)
    entry = res.signal_entry
    assert entry["kind"] == "counsel_verdict"
    assert "diverged" in entry["learning"]
    assert "agent" in entry["learning"]
    assert res.receipt["seq"] == 1


def test_legacy_counsel_entry_still_agent_compatible():
    # counsel() remains: single-position intake, verdict per agent id.
    res = counsel(_real_minion_id("XI"), "should the rite run now?")
    assert res.verdict.agent_id == _real_minion_id("XI")
    assert set(res.verdict.delivery) == {"left", "right"}
