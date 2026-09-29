# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""SwitchKeeper — the PhoneServer Kit operator (PROVISIONAL).

PhoneServer Kit: $49 one-time + $10/mo for updates. A self-hosted phone
server kit (kit, server, setup, invoice pieces).

The keeper is advisory-only: it checks kit readiness (which pieces are
present) and drafts the setup checklist. It provisions nothing, touches
no phone line, spends nothing.

NAMING: PROVISIONAL. Final name awaits Chauncey's word (naming sovereignty).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from levi.ddd.agents.base import DDDOperatorAgent
from levi.dynasty.dna import AgentError

__all__ = ["SwitchKeeper"]

_KIT_PIECES = ("kit.py", "server.py", "setup.sh", "invoice.py")


class SwitchKeeper(DDDOperatorAgent):
    """Watches kit readiness; drafts the setup checklist. Provisions nothing."""

    agent_id = "switchkeeper"
    display_name = "Switch Keeper (provisional)"
    owns = "PhoneServer Kit readiness drafts ($49 once + $10/mo)"
    first_milestone = "first setup-checklist draft delivered with receipt"
    proficiency = {"systems": 9, "triage": 8, "general": 6}
    specialties = [
        "kit pieces: read-only readiness check",
        "setup checklist: present/missing per piece",
        "provisions nothing: drafts only, setup is Chauncey's word",
    ]
    attributes = [
        {
            "name": "faithful readiness check",
            "assertion": (
                "the keeper checks which PhoneServer Kit pieces are present "
                "on disk and drafts a setup checklist from what is actually "
                "there — and it provisions nothing and touches no line."
            ),
        }
    ]

    def watch(self) -> Dict[str, Any]:
        kit_dir = Path.home() / "workspace" / "ddd" / "services" / "phoneserver"
        pieces: List[Dict[str, Any]] = []
        for name in _KIT_PIECES:
            p = kit_dir / name
            pieces.append({"piece": name, "present": p.is_file()})
        return {
            "agent_id": self.agent_id,
            "product": "PhoneServer Kit",
            "price": "$49 once + $10/mo",
            "kit_dir": str(kit_dir),
            "pieces": pieces,
            "n_present": sum(1 for x in pieces if x["present"]),
            "checked_at": self._checked_at(),
        }

    def draft_checklist(self) -> str:
        """Draft the kit setup checklist. Text only; provisions nothing."""
        state = self.watch()
        lines = ["# DRAFT — PhoneServer Kit setup checklist"]
        for piece in state["pieces"]:
            mark = "present" if piece["present"] else "MISSING"
            lines.append(f"  - [{mark}] {piece['piece']}")
        lines.append(
            f"- Readiness: {state['n_present']}/{len(state['pieces'])} pieces."
        )
        lines.append("- DRAFT only: nothing is provisioned until Chauncey says so.")
        return "\n".join(lines)

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        kind = str(task.get("kind", "watch")).lower()
        self._guard_kind(kind)
        if kind == "watch":
            return self.watch()
        if kind == "draft":
            return {"draft": self.draft_checklist()}
        raise AgentError(f"{self.agent_id}: unknown task kind {kind!r}")
