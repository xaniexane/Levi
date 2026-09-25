"""Proof for the omega daemon organ's invariant.

INVARIANT: "The daemon never executes a quarantined input or an
above-ceiling action. Every stage checks is_consumable and the ceiling;
a failed check halts the loop with a receipt, never silently."

PROOF (honest): behavioral verification — property tests over the
invariant (happy path, halt at blueprint/alpha/verify/nexus, schedule
drain, quarantine path, ceiling/approval guards), not a formal proof.
Hermetic: no network, no disk writes outside tmp, no sibling timing —
all sibling entrypoints are exercised through their committed fallbacks,
with a stub skill_registrar injected.
"""

from datetime import datetime, timedelta, timezone

import pytest

from levi.revival.omega import blueprint as bp
from levi.revival.omega import loop
from levi.revival.omega import substrate as sub

APPROVER = "daemon-test"


def _substrate() -> sub.SharedSubstrate:
    return sub.SharedSubstrate()


def _stub_registrar(calls):
    def registrar(name, capability, risk="elevated", approved_by=None, substrate=None):
        calls.append(
            {
                "name": name,
                "capability": capability,
                "risk": risk,
                "approved_by": approved_by,
            }
        )

        class _Ref:
            id = "skill_stub_1"

        return _Ref()

    return registrar


# ---------------------------------------------------------------------------
# happy path: the full echo → alpha → nexus → skill chain completes
# ---------------------------------------------------------------------------


def test_happy_path_full_chain():
    substrate = _substrate()
    calls = []
    out = loop.run_symbiotic_loop(
        substrate,
        "build a tiny todo cli tool",
        approved_by=APPROVER,
        skill_registrar=_stub_registrar(calls),
    )
    assert out["ok"] is True
    chain = out["chain"]
    assert {"blueprint", "build", "route", "skill"} <= set(chain)

    # every receipt id in the chain is a real recorded receipt
    for rid in (chain["blueprint"], chain["build"], chain["route"]):
        assert substrate.get_receipt(rid) is not None

    # the loop receipt is recorded, organ-tagged daemon, ok True
    loop_receipts = substrate.receipts(organ="daemon", kind="loop")
    assert any(
        r.id == out["loop_receipt"] and r.payload.get("ok") is True
        for r in loop_receipts
    )

    # skill wrap compounded through the injected registrar
    assert len(calls) == 1
    assert calls[0]["name"].startswith("omega-")
    assert calls[0]["risk"] == "elevated"
    assert calls[0]["approved_by"] == APPROVER
    assert chain["skill"] == "skill_stub_1"

    # every recorded receipt in the loop runs at or under the loop ceiling
    ceiling = sub.ceiling_for(*loop.LOOP_ORGANS)
    for r in substrate.receipts():
        assert sub.RISK_ORDER.index(r.risk) <= sub.RISK_ORDER.index(ceiling)


def test_happy_path_without_registrar_records_skill_wrap():
    substrate = _substrate()
    out = loop.run_symbiotic_loop(
        substrate, "build a notes cli", approved_by=APPROVER, skill_registrar=None
    )
    assert out["ok"] is True
    wraps = substrate.receipts(organ="skill", kind="skill_wrap")
    assert len(wraps) == 1
    assert wraps[0].id == out["chain"]["skill"]
    assert wraps[0].payload["name"].startswith("omega-")


# ---------------------------------------------------------------------------
# interrogation fires INSIDE the loop
# ---------------------------------------------------------------------------


def test_halt_at_verify_when_build_fails_echo_check(monkeypatch):
    substrate = _substrate()
    monkeypatch.setattr(
        bp,
        "verify_build",
        lambda blueprint, files: {
            "ok": False,
            "missing": ["build-tiny-todo-cli/build_tiny_todo_cli.py"],
            "empty": [],
            "verdict": "tampered: files do not match blueprint",
        },
        raising=False,
    )
    out = loop.run_symbiotic_loop(
        substrate, "build a notes cli", approved_by=APPROVER, skill_registrar=None
    )
    assert out["ok"] is False
    assert out["halted_at"] == "verify"
    build_id = out["chain"]["build"]

    # the build receipt was quarantined by the challenge
    assert substrate.is_consumable(build_id) is False

    # an open interrogation exists: echo challenging alpha's build
    open_challenges = substrate.challenges(status="open")
    assert any(
        c.target_receipt_id == build_id and c.challenger == "echo"
        for c in open_challenges
    )

    # the halt itself is a receipt, never silent
    halt_receipt = substrate.get_receipt(out["loop_receipt"])
    assert halt_receipt is not None
    assert halt_receipt.payload["halted_at"] == "verify"
    assert halt_receipt.payload["detail"]["challenge"] is not None


def test_halt_at_blueprint_when_challenged_before_alpha(monkeypatch):
    substrate = _substrate()
    orig_record = sub.SharedSubstrate.record_receipt

    def spy(self, organ, kind, payload, **kwargs):
        receipt = orig_record(self, organ, kind, payload, **kwargs)
        if kind == "blueprint":
            # "challenge it yourself first": interrogate before alpha consumes
            self.challenge(
                "echo", receipt.id, "daemon test: interrogating the blueprint"
            )
        return receipt

    monkeypatch.setattr(sub.SharedSubstrate, "record_receipt", spy)
    out = loop.run_symbiotic_loop(
        substrate, "build a notes cli", approved_by=APPROVER, skill_registrar=None
    )
    assert out["ok"] is False
    assert out["halted_at"] == "blueprint"
    bp_id = out["chain"]["blueprint"]
    assert substrate.is_consumable(bp_id) is False


def test_halt_at_alpha_when_blueprint_invalid():
    substrate = _substrate()
    # empty product types → no generators fire is fine; force invalid via a
    # blueprint the sibling publish path would reject: monkeypatch the fallback
    # build to hand back a structurally broken blueprint.
    broken = {"not": "a blueprint"}
    import levi.revival.omega.loop as loop_mod

    orig_echo = loop_mod._stage_echo

    def fake_echo(substrate, prompt, approved_by, chain):
        tier = sub.ceiling_for("daemon", "echo")
        receipt = substrate.record_receipt(
            "echo",
            "blueprint",
            {"prompt": prompt, "name": "broken"},
            risk=tier,
            approved_by=approved_by,
        )
        chain["blueprint"] = receipt.id
        return broken, receipt.id

    loop_mod._stage_echo = fake_echo
    try:
        out = loop.run_symbiotic_loop(
            substrate, "build a notes cli", approved_by=APPROVER, skill_registrar=None
        )
    finally:
        loop_mod._stage_echo = orig_echo
    assert out["ok"] is False
    assert out["halted_at"] == "alpha"
    assert out["chain"]["blueprint"] is not None


def test_halt_at_nexus_when_no_provider_eligible(monkeypatch):
    substrate = _substrate()
    # a fleet of references only: the sourcing law denies every one,
    # route_guarded refuses, and the loop halts at nexus with a receipt
    import levi.revival.omega.loop as loop_mod
    import levi.revival.omega.nexus as nx_mod

    monkeypatch.setattr(
        loop_mod,
        "_fleet_for",
        lambda task_kinds: [
            nx_mod.Provider(
                name="reference-only",
                source=nx_mod.SOURCE_REFERENCE,
                kinds=frozenset({"code", "automation"}),
                cost=9,
                quality=0.9,
            )
        ],
    )
    out = loop.run_symbiotic_loop(
        substrate, "build a notes cli", approved_by=APPROVER, skill_registrar=None
    )
    assert out["ok"] is False
    assert out["halted_at"] == "nexus"
    halt_receipt = substrate.get_receipt(out["loop_receipt"])
    assert halt_receipt.payload["detail"]["route"]["refusal"] == "no eligible provider"


# ---------------------------------------------------------------------------
# ceiling + approval guards
# ---------------------------------------------------------------------------


def test_loop_requires_recorded_approval():
    substrate = _substrate()
    with pytest.raises(ValueError):
        loop.run_symbiotic_loop(substrate, "build a notes cli", approved_by=None)


def test_loop_rejects_empty_prompt():
    substrate = _substrate()
    with pytest.raises(ValueError):
        loop.run_symbiotic_loop(substrate, "   ", approved_by=APPROVER)


# ---------------------------------------------------------------------------
# schedule: the daemon drains the SHARED pool
# ---------------------------------------------------------------------------


def _past_iso(minutes=5):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def _future_iso(hours=1):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def test_poll_schedule_runs_due_symbiotic_loop_job():
    substrate = _substrate()
    job = substrate.schedule(
        "daemon",
        "symbiotic_loop",
        _past_iso(),
        {"prompt": "build a notes cli", "approved_by": APPROVER},
    )
    results = loop.poll_schedule(substrate)
    assert len(results) == 1
    assert results[0]["job_id"] == job.id
    assert results[0]["ok"] is True
    assert results[0]["result"]["ok"] is True
    # job landed done and nothing is due anymore
    assert substrate.due_jobs() == []


def test_poll_schedule_ignores_not_due_jobs():
    substrate = _substrate()
    job = substrate.schedule(
        "daemon",
        "symbiotic_loop",
        _future_iso(),
        {"prompt": "build a notes cli", "approved_by": APPROVER},
    )
    assert loop.poll_schedule(substrate) == []
    assert substrate.due_jobs() == []


def test_poll_schedule_fails_unknown_job_without_executing():
    substrate = _substrate()
    job = substrate.schedule("daemon", "not_a_real_job", _past_iso(), {})
    results = loop.poll_schedule(substrate)
    assert len(results) == 1
    assert results[0]["ok"] is False
    assert "unknown job" in results[0]["error"]


def test_poll_schedule_marks_failed_job_failed():
    substrate = _substrate()
    # a loop job with no approval must fail loudly, never run anonymous
    job = substrate.schedule("daemon", "symbiotic_loop", _past_iso(), {"prompt": "x"})
    results = loop.poll_schedule(substrate)
    assert results[0]["ok"] is False
    assert substrate.due_jobs() == []


# ---------------------------------------------------------------------------
# quarantine: the daemon → quarantines → skill interrogation path
# ---------------------------------------------------------------------------


def test_quarantine_skill_result():
    substrate = _substrate()
    receipt = substrate.record_receipt(
        "skill",
        "skill_run",
        {"skill": "omega-notes-cli", "task": "run"},
        risk="elevated",
        approved_by=APPROVER,
    )
    ch = loop.quarantine_skill_result(
        substrate, receipt.id, "daemon: result drifted from the blueprint"
    )
    assert isinstance(ch, sub.Challenge)
    assert ch.challenger == "daemon"
    assert ch.target_receipt_id == receipt.id
    assert substrate.is_consumable(receipt.id) is False
    assert receipt in substrate.quarantined()


def test_quarantine_unknown_receipt_raises():
    substrate = _substrate()
    with pytest.raises(KeyError):
        loop.quarantine_skill_result(substrate, "rcpt_nope", "grounds")
