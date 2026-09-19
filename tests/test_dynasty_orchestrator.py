"""Dynasty Orchestrator tests — the command seat.

Hermetic: every test runs under a tmp LEVI_HOME via monkeypatch. No
network, no daemons, no writes to the real user HOME.
"""

from __future__ import annotations

import pytest

from levi.dynasty import receipts
from levi.dynasty.dna import DynastyAgent, WaveRegistry
from levi.dynasty.orchestrator import OperationError, Orchestrator, SEAT


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    home = tmp_path / "levi-home"
    monkeypatch.setenv("LEVI_HOME", str(home))
    return home


class BuilderAgent(DynastyAgent):
    agent_id = "builder_probe"
    display_name = "Builder Probe"
    proficiency = {"general": 6}
    attributes = [{"name": "a", "assertion": "b"}]

    def first_task(self):
        return self.do_task("wave.first_task", {}, task="builder_probe:first")


@pytest.fixture
def seated(tmp_home):
    orch = Orchestrator()
    orch.take_seat()
    agent = BuilderAgent()
    agent.enroll()
    return orch


# -- the seat ---------------------------------------------------------------


def test_take_seat_records_authority(tmp_home):
    orch = Orchestrator()
    taken = orch.take_seat()
    assert taken["receipt"] is not None
    assert taken["receipt"]["kind"] == "wave.seat"
    record = WaveRegistry().get_seat("orchestrator")
    assert record["held_by"] == "rex"
    assert record["authority"] == SEAT["authority"]
    assert record["limits"]["override_failed_gate"] is False
    assert receipts.verify_chain() >= 1


def test_take_seat_idempotent(tmp_home):
    orch = Orchestrator()
    first = orch.take_seat()
    second = orch.take_seat()
    assert second["receipt"] is None
    assert second["record"]["recorded_at"] == first["record"]["recorded_at"]


def test_first_task_is_taking_seat(tmp_home):
    orch = Orchestrator()
    receipt = orch.run_first_task()
    assert receipt["kind"] == "wave.seat"


# -- operations ---------------------------------------------------------------


def test_assign_operation_receipt_chained(seated):
    op = seated.assign_operation(
        "op-1", "builder_probe", {"shape": "echo", "text": "build it"}
    )
    assert op["status"] == "assigned"
    assert op["assigned_by"] == "orchestrator"
    kinds = [r["kind"] for r in _receipt_list()]
    assert "orchestrator.assign" in kinds


def test_assign_operation_refuses_unknown_agent(seated):
    with pytest.raises(OperationError):
        seated.assign_operation("op-x", "no_such_agent", {})


def test_assign_operation_refuses_duplicate(seated):
    seated.assign_operation("op-1", "builder_probe", {})
    with pytest.raises(OperationError):
        seated.assign_operation("op-1", "builder_probe", {})


def test_assign_before_seat_refused(tmp_home):
    orch = Orchestrator()  # seat not taken
    with pytest.raises(OperationError):
        orch.assign_operation("op-1", "builder_probe", {})


def test_complete_operation(seated):
    seated.assign_operation("op-1", "builder_probe", {})
    done = seated.complete_operation("op-1", "deadbeef" * 8)
    assert done["status"] == "complete"
    assert done["receipt"] == "deadbeef" * 8
    with pytest.raises(OperationError):
        seated.complete_operation("op-1", "x")


def _receipt_list():
    import json
    import os
    from pathlib import Path

    home = Path(os.environ["LEVI_HOME"])
    out = []
    for path in sorted((home / "dynasty" / "receipts").glob("*.json")):
        out.append(json.loads(path.read_text(encoding="utf-8")))
    return out


# -- final corroboration -------------------------------------------------------
#
# The gate module is crew D's build; this test proves the seat holds
# final corroboration: the gate must pass, and the seat-seal binds the
# gate's receipt hash (seal-binding). It runs once gates.py lands.


def test_advance_phase_binds_gate_receipt(seated):
    from levi.dynasty.gates import CorroborationGate  # noqa: F401  (proves it lands)

    owner = BuilderAgent()
    owner_sign = owner.wares.invoke("sign_milestone", "phase-1-complete")
    # second distinct agent signs: use a commissioned kin
    kin = owner.commission_kin(
        agent_id="verifier_probe",
        display_name="Verifier Probe",
        proficiency={"general": 5},
        owns="verifying",
        attributes=[{"name": "a", "assertion": "b"}],
    )
    verifier_sign = kin.wares.invoke("sign_milestone", "phase-1-complete")

    seal = seated.advance_phase(
        phase="phase-1",
        milestone="phase-1-complete",
        owner_id="builder_probe",
        signoffs=[owner_sign, verifier_sign],
    )
    assert seal["kind"] == "orchestrator.phase_advance"
    assert seal["payload"]["seal_binding"] is True
    gate_hash = seal["payload"]["gate_receipt"]
    kinds = {r["kind"]: r for r in _receipt_list()}
    assert "gate.advance" in kinds
    assert kinds["gate.advance"]["receipt_hash"] == gate_hash
    assert receipts.verify_chain() >= 1


def test_advance_phase_cannot_override_failed_gate(seated):
    owner = BuilderAgent()
    only_sign = owner.wares.invoke("sign_milestone", "phase-1-complete")
    from levi.dynasty import gates

    with pytest.raises(gates.GateError):
        seated.advance_phase(
            phase="phase-1",
            milestone="phase-1-complete",
            owner_id="builder_probe",
            signoffs=[only_sign],  # solo signoff: the gate must refuse
        )
    # and no phase-advance seal was minted for the failed attempt
    kinds = [r["kind"] for r in _receipt_list()]
    assert "orchestrator.phase_advance" not in kinds
