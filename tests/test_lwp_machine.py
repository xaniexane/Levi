"""Hermetic tests for the Forge content machine (levi.lwp.machine).

No network, no HOME writes (ledger, symbiosis dir, and born registry all
go under tmp_path), no randomness: every assertion is deterministic. All
example data is synthetic. These tests run against the REAL
``levi.lwp.twinpair`` module — pair names, risks, fit rules, and result
shapes are read from its declarations, never hardcoded.

Execution model: briefs run through interpenetrating twin-pair passes
(Echo×Mandella expands and stakes; REIM×RIEM composts failure into
genome) rather than a linear stage walk. STAGES/STAGE_SPEC stay as declared
pressures/seats/risks data. Stage labels are the machine's namespace —
the pair name normalized (× → _), e.g. "echo_mandella:pass1" — while
veto and PairResult records keep the module's verbatim pair names.
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
from levi.lwp.twinpair import (
    CANON_PAIRS,
    ECHO_MANDELLA,
    REIM_RIEM,
    ExpansionReport,
    VetoVerdict,
)
from levi.lwp.symbiosis import SymbioticLedger
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


def _drive_to_sealed(machine, brief, passes=2):
    """Run the full press through every human gate; return the sealed run."""
    run = machine.run_brief(brief, passes=passes)
    while machine.pending():
        for p in machine.pending():
            run = machine.approve(p["proposal_id"], note="keeper: approved")
    assert run.status == "sealed"
    return run


def _stage(pair_name, pass_no):
    """The machine's stage label for a pair-pass (× → _)."""
    return f"{pair_name.replace('×', '_')}:pass{pass_no}"


# Twin risks, read from the declarations themselves.
_TWIN_RISKS = {
    t.name: RiskLevel(t.risk) for p in CANON_PAIRS for t in (p.twin_a, p.twin_b)
}


def _twin_records(run, pair_name, pass_no):
    return [r for r in run.records if r.stage == _stage(pair_name, pass_no)]


# -- pressures as data -----------------------------------------------------


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


def test_run_brief_rejects_bad_passes(tmp_path):
    m = _machine(tmp_path)
    with pytest.raises(BriefError):
        m.run_brief(_brief(), passes=0)
    assert m._runs == {}


def test_run_brief_validates_before_any_work(tmp_path):
    m = _machine(tmp_path)
    with pytest.raises(BriefError):
        m.run_brief(_brief(title=""))
    assert m._runs == {}
    assert not (tmp_path / "ledger.jsonl").exists()


# -- rail compliance -----------------------------------------------------


def test_run_brief_halts_at_assembly_gate(tmp_path):
    m = _machine(tmp_path)
    run = m.run_brief(_brief())
    # Assembly (MODERATE) halts for a human; nothing is receipted yet.
    assert run.status == "awaiting_approval"
    assert run.pending_stage == "draft_assembly"
    assert run.pending_proposal_id
    assert run.pending_preview is not None
    assert run.records == []


def test_every_pair_pass_receipted_on_full_run(tmp_path):
    m = _machine(tmp_path)
    run = _drive_to_sealed(m, _brief())
    labels = [r.stage for r in run.records]
    assert labels[0] == "draft_assembly"
    assert labels[-1] == "publish_ready"
    for p in (1, 2):
        rep = run.expansions[f"pass{p}"]
        for pair in CANON_PAIRS:
            n = sum(1 for pr in rep["pair_results"] if pr["pair_name"] == pair.name)
            recs = _twin_records(run, pair.name, p)
            # one record per twin per pair result the expander returned
            assert len(recs) == 2 * n, f"{pair.name}:pass{p}"
            if n:
                assert {r.twin for r in recs} == {pair.twin_a.name, pair.twin_b.name}
    for r in run.records:
        assert r.proposal_id and r.receipt_id
        assert r.verified is True
        if r.stage == "draft_assembly":
            assert r.risk == "MODERATE"
        elif r.stage == "publish_ready":
            assert r.risk == "HIGH"
        else:
            assert r.risk == _TWIN_RISKS[r.twin].name
    # Every receipt resolves in the policy engine's registry.
    assert len(m.policy._receipts) == len(run.records)


def test_clean_pass_vetoes_reim_riem_honestly(tmp_path):
    # REIM×RIEM's fit rule needs failures to compost; a clean pass has
    # none, so the breaker refuses it — recorded, never forced.
    m = _machine(tmp_path)
    run = _drive_to_sealed(m, _brief())
    assert len(run.vetoes) == 2  # one per pass
    assert {v["pair"] for v in run.vetoes} == {REIM_RIEM.name}
    assert all("failures" in v["reason"] for v in run.vetoes)
    # ...and no reim/riem records were forced.
    assert not [r for r in run.records if r.twin in ("reim", "riem")]


def test_twin_gates_follow_declared_risks(tmp_path):
    m = _machine(tmp_path)
    run = m.run_brief(_brief())
    run = m.approve(run.pending_proposal_id, note="keeper: assemble it")
    for r in run.records:
        if r.stage in ("draft_assembly", "publish_ready"):
            assert r.explicit_approval is True  # human gates
        else:
            assert r.explicit_approval == (_TWIN_RISKS[r.twin] > RiskLevel.LOW), r.stage
    seal_run = _drive_to_sealed(
        ContentMachine(ledger_path=tmp_path / "l2.jsonl"), _brief()
    )
    seal = [r for r in seal_run.records if r.stage == "publish_ready"][0]
    assert seal.explicit_approval is True


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
    # requires the explicit human gate on the seal.
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
    assert len(out["stage_receipts"]) == len(run.records)
    assert out["receipt_id"]
    assert m.get_run(run.run_id).status == "published"
    assert m.get_run(run.run_id).publish_receipt_id == out["receipt_id"]


def test_publish_rail_approval_note_is_honest(tmp_path):
    # The machine self-approves its own CRITICAL publish rail proposal only
    # to receipt the execution — the permission is the operator's earlier
    # explicit publish_ready seal approval. The rail note must say so, and
    # the receipt must carry the seal's proposal chain as the permission
    # record, not a claim of fresh operator authorization.
    m = _machine(tmp_path)
    run = _drive_to_sealed(m, _brief())
    seal_records = [r for r in run.records if r.stage == "publish_ready"]
    out = m.publish(run.run_id, note="keeper: release")
    receipt = m.policy._receipts[out["receipt_id"]]
    rail = next(p for p in m.policy._history if p.id == receipt.action_id)
    assert "earlier explicit publish_ready seal approval" in (rail.decision_note or "")
    assert "authorized by operator" not in (rail.decision_note or "")
    assert "grants no new permission" in (rail.decision_note or "")
    assert receipt.details["seal"] == run.seal
    assert receipt.details["seal_proposal_ids"] == [r.proposal_id for r in seal_records]


# -- assembly honors Direction / Phase / Power ---------------------------


def test_assembly_honors_dpp(tmp_path):
    m = _machine(tmp_path)
    run = m.run_brief(_brief(direction="reverse", phase="finale", power="immortal"))
    run = m.approve(run.pending_proposal_id, note="keeper: assemble it")
    assembly = [r for r in run.records if r.stage == "draft_assembly"][0]
    assert "[L.W.P. reverse/finale/immortal · prose · draft]" in assembly.notes
    assert _words(run.final_text) > 0


def test_run_is_deterministic(tmp_path):
    brief = _brief(direction="inverse", phase="peak", power="booster")
    seals, texts = [], []
    for i in range(2):
        m = ContentMachine(ledger_path=tmp_path / f"l{i}.jsonl")
        run = _drive_to_sealed(m, brief)
        seals.append(run.seal)
        texts.append(run.final_text)
    assert seals[0] == seals[1]
    assert texts[0] == texts[1]


def test_social_kind_assembles_hook_and_mandella_validates(tmp_path):
    m = _machine(tmp_path)
    run = _drive_to_sealed(
        m,
        _brief(
            kind="social",
            platform="linkedin",
            brief_text="Operators run the press; the press does not run them.",
        ),
    )
    assembly = [r for r in run.records if r.stage == "draft_assembly"][0]
    assert any("hook formula" in n for n in assembly.notes)
    mandella = [r for r in run.records if r.twin == "mandella"]
    assert mandella
    assert any("platform validation (linkedin)" in n for r in mandella for n in r.notes)
    assert all(r.verified for r in mandella)


def test_stake_failure_accumulates_and_composts_on_later_pass(tmp_path):
    # X's 280-char limit cannot hold the assembled thread: the stake
    # fails, but the run does NOT halt — the failure accumulates, pass 2's
    # REIM×RIEM (now fitted, failures exist) composts it, and the dossier
    # carries what is still uncomposted to the human seal gate.
    m = _machine(tmp_path)
    run = _drive_to_sealed(
        m, _brief(kind="social", platform="x", brief_text="word " * 400)
    )
    assert run.status == "sealed"
    mandella = [r for r in run.records if r.twin == "mandella"]
    assert len(mandella) == 2
    assert all(r.verified is False for r in mandella)
    # Pass 2 ran REIM×RIEM for real: reim + riem records, verified.
    rr_p2 = _twin_records(run, REIM_RIEM.name, 2)
    assert {r.twin for r in rr_p2} == {"reim", "riem"}
    assert all(r.verified for r in rr_p2)
    # The pass-1 failure was composted on the later pass; the pass-2
    # failure is still queued in the dossier.
    assert len(run.failures) == 2
    assert run.composted == [run.failures[0]]
    assert len(run.compost) == 1
    assert "platform validation (x)" in run.compost[0]["failure"]
    assert run.compost[0]["lesson"]
    seal = [r for r in run.records if r.stage == "publish_ready"][0]
    assert any("uncomposted" in n for n in seal.notes)
    led = SymbioticLedger(directory=tmp_path / "ledger.symbiosis")
    assert led.by_kind("compost")


# -- phantoms + vetoes: the expander's residue ----------------------------


def test_phantoms_filed_to_dossier_and_symbiosis_ledger(tmp_path):
    m = _machine(tmp_path)
    run = _drive_to_sealed(m, _brief())
    assert run.phantoms
    led = SymbioticLedger(directory=tmp_path / "ledger.symbiosis")
    recs = led.by_kind("phantom")
    assert len(recs) == len(run.phantoms)
    assert {r.body["pair"] for r in recs} == {ECHO_MANDELLA.name}
    assert all(r.body.get("unchosen") for r in recs)
    d = run.to_dict()
    assert len(d["phantoms"]) == len(run.phantoms)
    assert d["born"]


def test_vetoed_pairs_recorded_never_forced(tmp_path):
    m = _machine(tmp_path)
    run = m.run_brief(_brief())
    report = ExpansionReport(
        material_id="test",
        rounds_run=1,
        pair_results=[],
        born=[],
        refused=[
            VetoVerdict(
                paired=False, pair_name=REIM_RIEM.name, reason="test veto: bad fit"
            )
        ],
    )
    rep = report.to_dict()
    rep["material_failures"] = []
    added = m._ingest_expansion(run, rep, 1)
    assert added is False
    # Nothing forced: the run keeps only its assembly act, no twin acts.
    assert [a["kind"] for a in run.act_plan] == ["assembly"]
    assert run.vetoes == [
        {"pass": 1, "pair": REIM_RIEM.name, "reason": "test veto: bad fit"}
    ]


def test_passes_configurable(tmp_path):
    m = ContentMachine(ledger_path=tmp_path / "l.jsonl")
    run = _drive_to_sealed(m, _brief(), passes=1)
    assert run.status == "sealed"
    assert run.passes == 1
    assert not any(r.stage == _stage(ECHO_MANDELLA.name, 2) for r in run.records)
    assert any(r.stage == _stage(ECHO_MANDELLA.name, 1) for r in run.records)


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
        echo_recs = [r for r in run.records if r.seat_key == "echo"]
        assert echo_recs
        assert all(r.seat_nature == "ai" for r in echo_recs)
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


def test_ledger_covers_every_pair_pass_and_publish(tmp_path):
    m = _machine(tmp_path)
    run = _drive_to_sealed(m, _brief())
    m.publish(run.run_id, note="keeper: release")
    events = [
        json.loads(line)
        for line in (tmp_path / "ledger.jsonl").read_text().splitlines()
    ]
    completed = [e for e in events if e["event"] == "stage_completed"]
    expected = ["draft_assembly"]
    for p in (1, 2):
        rep = run.expansions[f"pass{p}"]
        for pr in rep["pair_results"]:
            expected += [_stage(pr["pair_name"], p)] * 2  # twin_a + twin_b
    expected.append("publish_ready")
    assert [e["stage"] for e in completed] == expected
    assert all(e["receipt_id"] for e in completed)
    published = [e for e in events if e["event"] == "published"]
    assert len(published) == 1
    assert published[0]["seal"] == run.seal
    # Ledger receipt ids match the run's pair-pass records.
    ledger_ids = [e["receipt_id"] for e in completed]
    assert ledger_ids == [r.receipt_id for r in run.records]


def test_run_dossier_serializes(tmp_path):
    m = _machine(tmp_path)
    run = _drive_to_sealed(m, _brief())
    d = run.to_dict()
    assert d["run_id"] == run.run_id
    assert d["brief"]["title"] == "The Press Test"
    assert d["phantoms"] and d["born"]
    assert len(d["vetoes"]) == 2  # REIM×RIEM refused on both clean passes
    json.dumps(d)  # must be JSON-serializable


# -- seats: durable per-ledger overrides, no global leakage ----------------


def test_seat_override_persists_across_invocations(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    m1 = ContentMachine(ledger_path=ledger)
    out = m1.seat("revision", "mandella")
    assert out["seat"] == "mandella"
    # A new machine on the same ledger (a later `levi lwp` invocation)
    # sees the reassignment.
    m2 = ContentMachine(ledger_path=ledger)
    assert m2.seats()["revision"]["seat"] == "mandella"
    assert m2.stage_spec["revision"]["seat"] == "mandella"


def test_seat_override_does_not_leak_to_other_ledger_or_process(tmp_path):
    m1 = ContentMachine(ledger_path=tmp_path / "a.jsonl")
    m1.seat("revision", "mandella")
    # Another machine sharing the process but a different ledger still
    # sees the defaults — the old module-global mutation is gone.
    m2 = ContentMachine(ledger_path=tmp_path / "b.jsonl")
    assert m2.seats()["revision"]["seat"] == "echo"
    assert m2.stage_spec["revision"]["seat"] == "echo"
    from levi.lwp.machine import STAGE_SPEC as MODULE_SPEC

    assert MODULE_SPEC["revision"]["seat"] == "echo"


def test_run_brief_snapshots_seats_at_brief_time(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    m = ContentMachine(ledger_path=ledger)
    before = m.run_brief(_brief())
    m.seat("polish", "echo")  # Mandella's pressure now seats echo
    after = m.run_brief(_brief())
    # The earlier run keeps the seats it started with.
    assert before.seats["polish"] == "mandella"
    # The later run picks up the override.
    assert after.seats["polish"] == "echo"
    sealed = _drive_to_sealed(m, _brief())
    recs = [r for r in sealed.records if r.stage == _stage(ECHO_MANDELLA.name, 1)]
    assert recs
    # Both twins of the pair now operate under echo (revision's seat echo,
    # polish's seat reassigned to echo).
    assert {r.seat_key for r in recs} == {"echo"}
    assert all(r.seat_nature == current_nature("echo") for r in recs)


def test_symbiosis_ledger_is_per_ledger_file(tmp_path):
    m1 = ContentMachine(ledger_path=tmp_path / "a.jsonl")
    _drive_to_sealed(m1, _brief(title="Press One"))
    m2 = ContentMachine(ledger_path=tmp_path / "b.jsonl")
    _drive_to_sealed(m2, _brief(title="Press Two"))
    l1 = SymbioticLedger(directory=tmp_path / "a.symbiosis")
    l2 = SymbioticLedger(directory=tmp_path / "b.symbiosis")
    assert {r.body["brief_title"] for r in l1.by_kind("phantom")} == {"Press One"}
    assert {r.body["brief_title"] for r in l2.by_kind("phantom")} == {"Press Two"}


def _words(t):
    return len(t.split())
