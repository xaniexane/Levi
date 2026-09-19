"""Hermetic tests for the Forge content machine (levi.lwp.machine).

No network, no HOME writes (ledger goes to tmp_path), no randomness:
every assertion is deterministic. All example data is synthetic.
"""

import json

import pytest

from levi.lwp.machine import (
    STAGES,
    STAGE_SPEC,
    BriefError,
    ContentMachine,
    ProductionBrief,
    PublishPermissionError,
)
from levi.lwp import ContentMachine as ExportedMachine  # package export check
from levi.policy.gates import PolicyEngine, RiskLevel
from levi.founders.roster import current_nature, reseat, switch_nature


def _brief(**over):
    kw = dict(
        title="The Press Test",
        brief_text="A machine that turns briefs into finished content, honestly.",
        kind="prose",
        direction="forward",
        phase="gold_push",
        power="gain",
    )
    kw.update(over)
    return ProductionBrief(**kw)


def _machine(tmp_path):
    return ContentMachine(ledger_path=tmp_path / "ledger.jsonl")


def _drive_to_sealed(machine, brief):
    """Run the full line through both human gates; return the sealed run."""
    run = machine.run_brief(brief)
    while machine.pending():
        for p in machine.pending():
            run = machine.approve(p["proposal_id"], note="keeper: approved")
    assert run.status == "sealed"
    return run


# -- stages as data ------------------------------------------------------


def test_stages_are_data_in_order():
    assert STAGES == ("ideation", "drafting", "revision", "polish", "publish_ready")
    assert set(STAGE_SPEC) == set(STAGES)
    for stage in STAGES:
        spec = STAGE_SPEC[stage]
        assert spec["seat"] and spec["charge"]
        assert isinstance(spec["risk"], RiskLevel)


def test_hierarchy_honored_in_default_seats():
    # Alpha first, Omega last, Levi head of the machine.
    assert STAGE_SPEC["ideation"]["seat"] == "alpha"
    assert STAGE_SPEC["drafting"]["seat"] == "levi"
    assert STAGE_SPEC["publish_ready"]["seat"] == "omega"


def test_package_exports_machine():
    assert ExportedMachine is ContentMachine


# -- brief validation ----------------------------------------------------


def test_brief_rejects_empty_title():
    with pytest.raises(BriefError):
        _brief(title="  ").validate()


def test_brief_rejects_bad_kind_direction_phase_power():
    with pytest.raises(BriefError):
        _brief(kind="screenplay").validate()
    with pytest.raises(BriefError):
        _brief(direction="sideways").validate()
    with pytest.raises(BriefError):
        _brief(phase="naptime").validate()
    with pytest.raises(BriefError):
        _brief(power="overdrive").validate()


def test_brief_rejects_unknown_platform():
    with pytest.raises(ValueError):
        _brief(kind="social", platform="myspace").validate()


def test_brief_rejects_bad_target_words():
    with pytest.raises(BriefError):
        _brief(target_words=0).validate()


def test_run_brief_validates_before_any_work(tmp_path):
    m = _machine(tmp_path)
    with pytest.raises(BriefError):
        m.run_brief(_brief(title=""))
    assert m._runs == {}
    assert not (tmp_path / "ledger.jsonl").exists()


# -- rail compliance -----------------------------------------------------


def test_run_brief_halts_at_drafting_gate(tmp_path):
    m = _machine(tmp_path)
    run = m.run_brief(_brief())
    # ideation (LOW) auto-approves; drafting (MODERATE) halts for a human.
    assert run.status == "awaiting_approval"
    assert run.pending_stage == "drafting"
    assert run.pending_proposal_id
    assert run.pending_preview is not None
    assert [r.stage for r in run.records] == ["ideation"]
    assert all(r.receipt_id for r in run.records)


def test_every_stage_receipted_on_full_run(tmp_path):
    m = _machine(tmp_path)
    run = _drive_to_sealed(m, _brief())
    assert [r.stage for r in run.records] == list(STAGES)
    for r in run.records:
        assert r.proposal_id and r.receipt_id
        assert r.verified is True
    # Every receipt resolves in the policy engine's registry.
    assert len(m.policy._receipts) == len(STAGES)


def test_low_stages_auto_approve_high_stages_halt(tmp_path):
    m = _machine(tmp_path)
    run = m.run_brief(_brief())
    ideation = run.records[0]
    assert ideation.explicit_approval is False  # auto-approved by policy
    run = m.approve(run.pending_proposal_id, note="keeper: draft it")
    drafting = [r for r in run.records if r.stage == "drafting"][0]
    assert drafting.explicit_approval is True  # human gate
    seal_run = _drive_to_sealed(
        ContentMachine(ledger_path=tmp_path / "l2.jsonl"), _brief()
    )
    pub = [r for r in seal_run.records if r.stage == "publish_ready"][0]
    assert pub.explicit_approval is True


def test_approve_unknown_proposal_raises(tmp_path):
    m = _machine(tmp_path)
    with pytest.raises(ValueError):
        m.approve("no-such-proposal")
    with pytest.raises(ValueError):
        m.deny("no-such-proposal")


def test_deny_stops_run_and_blocks_publish(tmp_path):
    m = _machine(tmp_path)
    run = m.run_brief(_brief())
    run = m.deny(run.pending_proposal_id, note="keeper: not this angle")
    assert run.status == "denied"
    assert m.pending() == []
    with pytest.raises(PublishPermissionError):
        m.publish(run.run_id)


# -- the nothing-publishes-without-permission invariant ------------------


def test_publish_before_seal_raises(tmp_path):
    m = _machine(tmp_path)
    run = m.run_brief(_brief())
    with pytest.raises(PublishPermissionError):
        m.publish(run.run_id)


def test_publish_after_deny_raises(tmp_path):
    m = _machine(tmp_path)
    run = m.run_brief(_brief())
    m.deny(run.pending_proposal_id)
    with pytest.raises(PublishPermissionError):
        m.publish(run.run_id, note="sneaky")


def test_publish_survives_permissive_engine(tmp_path):
    # Even with an engine that auto-approves CRITICAL, publish() still
    # requires the explicit human gate on publish_ready.
    permissive = PolicyEngine(auto_approve_up_to=RiskLevel.CRITICAL)
    m = ContentMachine(ledger_path=tmp_path / "ledger.jsonl", policy=permissive)
    run = m.run_brief(_brief())
    assert run.status == "sealed"  # everything auto-approved
    with pytest.raises(PublishPermissionError):
        m.publish(run.run_id)


def test_publish_happy_path_returns_full_receipt_chain(tmp_path):
    m = _machine(tmp_path)
    run = _drive_to_sealed(m, _brief())
    out = m.publish(run.run_id, note="keeper: release")
    assert out["status"] == "published"
    assert out["seal"] == run.seal
    assert len(out["stage_receipts"]) == len(STAGES)
    assert out["receipt_id"]
    assert m.get_run(run.run_id).status == "published"
    assert m.get_run(run.run_id).publish_receipt_id == out["receipt_id"]


# -- drafting honors Direction / Phase / Power ---------------------------


def test_drafting_honors_dpp(tmp_path):
    m = _machine(tmp_path)
    run = m.run_brief(_brief(direction="reverse", phase="finale", power="immortal"))
    run = m.approve(run.pending_proposal_id, note="keeper: draft it")
    drafting = [r for r in run.records if r.stage == "drafting"][0]
    assert "[L.W.P. reverse/finale/immortal · prose · draft]" in drafting.notes
    assert _words(run.final_text) > 0


def test_drafting_is_deterministic(tmp_path):
    brief = _brief(direction="inverse", phase="peak", power="booster")
    seals = []
    for i in range(2):
        m = ContentMachine(ledger_path=tmp_path / f"l{i}.jsonl")
        run = _drive_to_sealed(m, brief)
        seals.append(run.seal)
    assert seals[0] == seals[1]


def test_social_kind_drafts_with_hook_and_validates(tmp_path):
    m = _machine(tmp_path)
    run = _drive_to_sealed(
        m,
        _brief(
            kind="social",
            platform="linkedin",
            brief_text="Operators run the press; the press does not run them.",
        ),
    )
    drafting = [r for r in run.records if r.stage == "drafting"][0]
    assert any("hook formula" in n for n in drafting.notes)
    polish = [r for r in run.records if r.stage == "polish"][0]
    assert any("platform validation (linkedin)" in n for n in polish.notes)
    assert polish.verified is True


def test_polish_failure_halts_with_needs_attention(tmp_path):
    # X's 280-char limit cannot hold the assembled thread: polish verify
    # fails and the line halts instead of advancing to the seal.
    m = _machine(tmp_path)
    run = m.run_brief(_brief(kind="social", platform="x", brief_text="word " * 400))
    while m.pending():
        for p in m.pending():
            run = m.approve(p["proposal_id"], note="keeper: approved")
    assert run.status == "needs_attention"
    polish = [r for r in run.records if r.stage == "polish"][0]
    assert polish.verified is False
    with pytest.raises(PublishPermissionError):
        m.publish(run.run_id)


# -- seats: operators run it, fluidity law --------------------------------


def test_seat_natures_read_live_from_roster(tmp_path):
    m = _machine(tmp_path)
    run = _drive_to_sealed(m, _brief())
    for r in run.records:
        assert r.seat_nature == current_nature(r.seat_key)


def test_fluidity_switch_reflected_at_execution(tmp_path):
    try:
        switch_nature("echo", "ai")
        assert current_nature("echo") == "ai"
        m = _machine(tmp_path)
        run = _drive_to_sealed(m, _brief())
        revision = [r for r in run.records if r.stage == "revision"][0]
        assert revision.seat_key == "echo"
        assert revision.seat_nature == "ai"
    finally:
        reseat()


def test_seat_reassignment_validates_roster(tmp_path):
    m = _machine(tmp_path)
    out = m.seat("revision", "mandella")
    assert out["seat"] == "mandella"
    assert out["nature"] == current_nature("mandella")
    with pytest.raises(ValueError):
        m.seat("revision", "not-a-seat")
    with pytest.raises(ValueError):
        m.seat("not-a-stage", "echo")


# -- receipts on everything: ledger completeness --------------------------


def test_ledger_covers_every_stage_and_publish(tmp_path):
    m = _machine(tmp_path)
    run = _drive_to_sealed(m, _brief())
    m.publish(run.run_id, note="keeper: release")
    events = [
        json.loads(line)
        for line in (tmp_path / "ledger.jsonl").read_text().splitlines()
    ]
    completed = [e for e in events if e["event"] == "stage_completed"]
    assert [e["stage"] for e in completed] == list(STAGES)
    assert all(e["receipt_id"] for e in completed)
    published = [e for e in events if e["event"] == "published"]
    assert len(published) == 1
    assert published[0]["seal"] == run.seal
    # Ledger receipt ids match the run's stage records.
    ledger_ids = [e["receipt_id"] for e in completed]
    assert ledger_ids == [r.receipt_id for r in run.records]


def test_run_dossier_serializes(tmp_path):
    m = _machine(tmp_path)
    run = _drive_to_sealed(m, _brief())
    d = run.to_dict()
    assert d["run_id"] == run.run_id
    assert d["brief"]["title"] == "The Press Test"
    assert len(d["records"]) == len(STAGES)
    json.dumps(d)  # must be JSON-serializable


def _words(t):
    return len(t.split())
