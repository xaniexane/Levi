"""LEVI OS v0.1 — law-guard-prove.

Laws under test:
  L1. Every plan step is backed by a real pool skill, or planning fails
      loudly (no invented steps).
  L2. No step executes without a receipt; the chain verifies end-to-end;
      tampering is detected.
  L3. The memory/context path is network-free — proven with all sockets
      blocked, not asserted.
  L4. The provider seam never imports the held model layer
      (levi.model.abstraction / ministral_cloud): subprocess check.
  L5. Devices are honest: stubbed surfaces labeled; unroutable steps
      defer/block instead of faking.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "core"))

from levi.legion.skill_pool.mastery import clear_mastery, set_mastery  # noqa: E402
from levi.os import (  # noqa: E402
    ChatClient,
    LocalRulesProvider,
    OSContext,
    OSPlanError,
    builtin_devices,
    enumerate_devices,
    execute,
    required_capabilities,
    route_step,
    state_outcome,
    swap_provider,
    verify,
)
from levi.os.receipts import GENESIS_HEAD, os_dir  # noqa: E402

OUTCOME = "check my gmail inbox. review this NDA"


# -- L1: skill-backed planning -------------------------------------------


def test_state_outcome_decomposes_to_skill_backed_steps():
    plan = state_outcome(OUTCOME)
    assert len(plan.steps) == 2
    assert plan.steps[0].skill_id == "legion_gmail"
    assert plan.steps[1].skill_id == "legion_legal_contract"
    for step in plan.steps:
        assert step.rank == "II"  # provisional default
        assert step.rank_description  # shaped to a real ladder rung


def test_state_outcome_empty_fails_loudly():
    with pytest.raises(OSPlanError):
        state_outcome("   ")


def test_state_outcome_unplannable_clause_fails_loudly():
    with pytest.raises(OSPlanError) as exc:
        state_outcome("check my gmail inbox. zzqx qqqq jjj")
    assert "zzqx qqqq jjj" in str(exc.value)  # the miss is named


def test_mastery_rank_flows_into_plan():
    member = "levios-test-member"
    try:
        set_mastery(member, "legion_legal_contract", "III")
        plan = state_outcome("review this NDA", member=member)
        assert plan.steps[0].rank == "III"
    finally:
        clear_mastery(member)


# -- L2: receipts ---------------------------------------------------------


def test_execute_writes_receipt_per_step_and_chain_verifies(tmp_path):
    plan = state_outcome(OUTCOME)
    report = execute(plan, home=tmp_path)
    assert len(report.results) == 2
    assert report.chain_ok is True
    ok, broken = verify(tmp_path, report.session_id)
    assert ok and broken is None


def test_receipt_chain_starts_at_genesis(tmp_path):
    plan = state_outcome("review this NDA")
    execute(plan, home=tmp_path)
    first = json.loads(
        (os_dir(tmp_path) / "receipts.jsonl").read_text().splitlines()[0]
    )
    assert first["prev"] == GENESIS_HEAD


def test_receipt_chain_tamper_detected(tmp_path):
    plan = state_outcome("review this NDA")
    report = execute(plan, home=tmp_path)
    path = os_dir(tmp_path) / "receipts.jsonl"
    lines = path.read_text().splitlines()
    tampered = json.loads(lines[0])
    tampered["detail"]["status"] = "forged"
    lines[0] = json.dumps(tampered)
    path.write_text("\n".join(lines) + "\n")
    ok, broken = verify(tmp_path, report.session_id)
    assert ok is False and broken == 1


def test_needs_wiring_step_blocked_honestly(tmp_path):
    plan = state_outcome("check my gmail inbox")
    report = execute(plan, home=tmp_path)
    result = report.results[0]
    assert result.status == "blocked"
    assert "no connector" in result.note
    assert report.chain_ok is True  # blocked steps still get receipts


def test_playbook_step_delivered_on_real_device(tmp_path):
    plan = state_outcome("review this NDA")
    report = execute(plan, home=tmp_path)
    result = report.results[0]
    assert result.status == "delivered"
    assert result.device_id == "local"
    assert "Procedure" in result.note


# -- L5: honest devices ---------------------------------------------------


def test_devices_enumerate_honest():
    devices = {d.id: d for d in enumerate_devices()}
    assert devices["local"].status == "real"
    assert devices["termux"].status == "stubbed"
    assert devices["termux"].notes  # the stub says why
    assert devices["android-app"].status == "stubbed"
    assert {d.id for d in builtin_devices()} == {
        "local",
        "termux",
        "android-app",
    }


def test_route_step_network_impossible():
    # No device declares the network capability: unroutable by construction.
    assert route_step({"network"}) is None
    assert route_step(required_capabilities("playbook-only")).id == "local"
    with pytest.raises(ValueError):
        required_capabilities("not-a-backend")


# -- provider seam --------------------------------------------------------


def test_provider_swap_preserves_context(tmp_path):
    ctx = OSContext(tmp_path, "sess-1")
    ctx.remember("project", "levi-os")
    ctx.remember("step", 3)
    old = LocalRulesProvider()

    class Other(LocalRulesProvider):
        name = "other"

    receipt = swap_provider(old, ctx, Other())
    assert receipt["context_unchanged"] is True
    assert receipt["context_keys_preserved"] == ["project", "step"]
    assert ctx.recall("project") == "levi-os"  # same object, untouched
    assert receipt["old_provider"] == "local-rules"
    assert receipt["new_provider"] == "other"


def test_context_rejects_bad_keys(tmp_path):
    ctx = OSContext(tmp_path, "sess-2")
    with pytest.raises(ValueError):
        ctx.remember("  ", "x")
    with pytest.raises(ValueError):
        OSContext(tmp_path, "")


def test_provider_seam_never_imports_held_model_layer():
    code = (
        "import sys; sys.path.insert(0, 'core');"
        "import levi.os;"
        "bad = [m for m in sys.modules if m == 'levi.model'"
        " or m.startswith('levi.model.')];"
        "assert not bad, bad;"
        "print('seam-clean')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert "seam-clean" in proc.stdout


# -- L3: local-first PROOF ------------------------------------------------
# The headline differentiator, machine-checked: the entire
# outcome -> plan -> execute -> memory -> provider-swap loop runs with
# every socket creation blocked, and not a single socket is attempted.


def test_memory_path_makes_zero_network_calls(tmp_path, monkeypatch):
    attempts = []

    def counting_socket(*args, **kwargs):
        attempts.append((args, kwargs))
        raise OSError("network disabled by levios local-first proof")

    def no_connection(*args, **kwargs):
        attempts.append((args, kwargs))
        raise OSError("network disabled by levios local-first proof")

    monkeypatch.setattr(socket, "socket", counting_socket)
    monkeypatch.setattr(socket, "create_connection", no_connection)

    # Full loop under the socket blockade.
    plan = state_outcome(OUTCOME)
    report = execute(plan, home=tmp_path, session_id="proof-session")
    assert report.chain_ok is True

    ctx = OSContext(tmp_path, "proof-session")
    ctx.remember("outcome", OUTCOME)
    assert ctx.recall("outcome") == OUTCOME

    provider = LocalRulesProvider()
    text = provider.complete("summarize", ctx.provider_view())
    assert "local-rules" in text

    class Next(LocalRulesProvider):
        name = "next-model"

    receipt = swap_provider(provider, ctx, Next())
    assert receipt["context_unchanged"] is True

    # The proof: green run, zero socket attempts.
    assert attempts == []


# -- chat client ----------------------------------------------------------


def test_chat_client_roundtrip(tmp_path):
    client = ChatClient(home=tmp_path)
    prose = client.run_outcome(OUTCOME)
    assert "legion_gmail" in prose
    assert "legion_legal_contract" in prose
    assert "receipts verified: True" in prose
    receipts = client.recent_receipts()
    assert len(receipts) == 2
    assert all(r["zone"] == "os" for r in receipts)
