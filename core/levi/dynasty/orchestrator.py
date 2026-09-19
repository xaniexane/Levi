# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""The Orchestrator — commander, chief of production and construction operations.

The eleven build; the Orchestrator commands. The seat is Rex's, at the
keeper's appointment. The Orchestrator assigns production and
construction operations to wave agents, directs mixed native +
integrated teams, and holds final corroboration before any phase
advances.

The seat's authority is recorded in the wave registry with its scope,
and the seating is receipt-chained like everything else. Hard limits
on the seat, stated plainly: the Orchestrator cannot commission kin
(the bloodline belongs to the agents, through the Builder), cannot
mint or move money, cannot read the keeper key, and cannot override a
failed corroboration gate — command without corroboration does not
exist.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.dynasty.dna import AgentError, DynastyAgent, _utc_now

__all__ = ["Orchestrator", "OperationError", "SEAT"]


class OperationError(AgentError):
    """An operation assignment or phase advance was refused."""


#: The seat, as the keeper defined it.
SEAT: Dict[str, Any] = {
    "seat": "orchestrator",
    "title": "commander, chief of production and construction operations",
    "held_by": "rex",
    "authority": {
        "assign_operations": True,
        "direct_mixed_teams": True,
        "final_corroboration": True,
    },
    "limits": {
        "commission_kin": False,
        "money": False,
        "keeper_key": False,
        "override_failed_gate": False,
    },
}


class Orchestrator(DynastyAgent):
    """Rex's seat. Commands; does not build."""

    agent_id = "orchestrator"
    display_name = "Orchestrator"
    owns = "command of production and construction operations"
    first_milestone = "Phase 1 wave held at even build stages"
    proficiency = {
        "command": 10,
        "operations": 10,
        "corroboration": 9,
        "general": 6,
    }
    specialties = [
        "assigns production and construction operations to wave agents",
        "directs mixed native + integrated teams",
        "holds final corroboration before phase advance",
    ]
    attributes = [
        {
            "name": "seal-binding",
            "assertion": (
                "no phase advance exists without both a passed corroboration "
                "gate and the Orchestrator's seat-seal bound to that gate's "
                "receipt hash — command and corroboration are "
                "cryptographically one act, neither valid alone"
            ),
        }
    ]

    def __init__(self, home: Optional[Path] = None) -> None:
        super().__init__(home)
        self._ops_path = self._home / "dynasty" / "orchestrator" / "operations.json"
        self._ops_lock = threading.Lock()

    # -- the seat ------------------------------------------------------
    def take_seat(self) -> Dict[str, Any]:
        """Take the command seat. Idempotent — the seat is taken once;
        the seating is sealed with a receipt like everything else."""
        with self._ops_lock:
            existing = self.registry.get_seat("orchestrator")
            if existing is not None:
                return {"record": existing, "receipt": None}
            record = self.registry.record_seat(
                "orchestrator",
                {
                    "title": SEAT["title"],
                    "held_by": SEAT["held_by"],
                    "authority": dict(SEAT["authority"]),
                    "limits": dict(SEAT["limits"]),
                },
            )
        self.enroll()
        receipt = self.do_task(
            kind="wave.seat",
            payload={
                "seat": "orchestrator",
                "held_by": SEAT["held_by"],
                "authority": dict(SEAT["authority"]),
                "limits": dict(SEAT["limits"]),
            },
            task="orchestrator:take-seat",
        )
        self.registry.note_first_receipt(self.agent_id, receipt["receipt_hash"])
        self.note(
            "seat taken: commander, chief of production and construction operations"
        )
        return {"record": record, "receipt": receipt}

    def first_task(self) -> Dict[str, Any]:
        """The seat's first act is taking the seat."""
        taken = self.take_seat()
        if taken["receipt"] is None:
            raise AgentError("seat already taken — first act is history")
        return taken["receipt"]

    # -- operations ------------------------------------------------------
    def _read_ops(self) -> Dict[str, Any]:
        if not self._ops_path.exists():
            return {}
        try:
            data = json.loads(self._ops_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_ops(self, ops: Dict[str, Any]) -> None:
        self._ops_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(self._ops_path.parent), prefix=".ops-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(ops, fh, sort_keys=True, indent=2)
                fh.write("\n")
            os.replace(tmp, self._ops_path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        os.chmod(self._ops_path, 0o600)

    def assign_operation(
        self, op_id: str, agent_id: str, task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assign a production/construction operation to a wave agent.
        The assignment is receipt-chained."""
        if self.registry.get_seat("orchestrator") is None:
            raise OperationError("the seat must be taken before commanding")
        if not op_id or not op_id.strip():
            raise OperationError("op_id must be non-empty")
        if self.registry.get(agent_id) is None:
            raise OperationError(f"cannot assign to unenrolled agent: {agent_id!r}")
        if not isinstance(task, dict):
            raise OperationError("operation task must be a dict")
        with self._ops_lock:
            ops = self._read_ops()
            if op_id in ops:
                raise OperationError(f"operation already assigned: {op_id!r}")
            op = {
                "op_id": op_id,
                "agent_id": agent_id,
                "task": task,
                "status": "assigned",
                "assigned_at": _utc_now(),
                "assigned_by": "orchestrator",
                "completed_at": None,
                "receipt": None,
            }
            ops[op_id] = op
            self._write_ops(ops)
        receipt = self.do_task(
            kind="orchestrator.assign",
            payload={"op_id": op_id, "agent_id": agent_id},
            task=f"orchestrator:assign:{op_id}->{agent_id}",
        )
        with self._ops_lock:
            ops = self._read_ops()
            ops[op_id]["assign_receipt"] = receipt["receipt_hash"]
            self._write_ops(ops)
        self.note(f"operation assigned: {op_id} -> {agent_id}")
        return dict(op)

    def complete_operation(self, op_id: str, receipt_hash: str) -> Dict[str, Any]:
        """Mark an operation complete against the agent's work receipt."""
        with self._ops_lock:
            ops = self._read_ops()
            op = ops.get(op_id)
            if op is None:
                raise OperationError(f"unknown operation: {op_id!r}")
            if op["status"] == "complete":
                raise OperationError(f"operation already complete: {op_id!r}")
            op["status"] = "complete"
            op["completed_at"] = _utc_now()
            op["receipt"] = receipt_hash
            self._write_ops(ops)
            return dict(op)

    def operations(self) -> List[Dict[str, Any]]:
        """Every assigned operation, oldest first."""
        with self._ops_lock:
            return [dict(op) for op in self._read_ops().values()]

    # -- mixed teams -------------------------------------------------------
    def direct_team(self, name: str, member_ids: List[str]) -> Any:
        """Direct a mixed native + integrated team under the seat's command."""
        from levi.dynasty.adapter import Team  # lazy: crew D's module

        if self.registry.get_seat("orchestrator") is None:
            raise OperationError("the seat must be taken before commanding")
        if not name or not name.strip():
            raise OperationError("team name must be non-empty")
        for member_id in member_ids:
            if self.registry.get(member_id) is None:
                raise OperationError(f"team member not enrolled: {member_id!r}")
        team = Team(name=name.strip(), member_ids=list(member_ids))
        self.do_task(
            kind="orchestrator.team",
            payload={"team": team.name, "members": team.member_ids},
            task=f"orchestrator:team:{team.name}",
        )
        self.note(f"team directed: {team.name} ({len(member_ids)} members)")
        return team

    # -- final corroboration -------------------------------------------------
    def advance_phase(
        self,
        phase: str,
        milestone: str,
        owner_id: str,
        signoffs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Hold final corroboration before a phase advances.

        The corroboration gate must pass — the seat cannot override a
        failed gate. On success the seat-seal binds the gate's receipt
        hash: command and corroboration become one cryptographic act
        (the seal-binding attribute).
        """
        from levi.dynasty.gates import CorroborationGate  # lazy: crew D's module

        if self.registry.get_seat("orchestrator") is None:
            raise OperationError("the seat must be taken before commanding")
        if not phase or not phase.strip():
            raise OperationError("phase must be non-empty")
        gate_receipt = CorroborationGate.advance(
            milestone=milestone, signoffs=signoffs, owner=owner_id
        )
        seal = self.do_task(
            kind="orchestrator.phase_advance",
            payload={
                "phase": phase.strip(),
                "milestone": milestone,
                "owner": owner_id,
                "gate_receipt": gate_receipt["receipt_hash"],
                "seal_binding": True,
            },
            task=f"orchestrator:advance:{phase}",
        )
        self.note(
            f"phase advanced: {phase} bound to gate {gate_receipt['receipt_hash'][:16]}"
        )
        return seal
