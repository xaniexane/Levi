# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""RentRollKeeper — the LandlordLedger operator (PROVISIONAL).

LandlordLedger: $12/mo per landlord. Tenants CSV in, monthly rent
roll + late-notice drafts out (late notices go through the product's
messaging outbox with deterministic ids — the human sends).

The keeper is advisory-only: it scans the tenants queue and drafts
the rent roll and late-notice drafts as text. It sends no notice.

NAMING: PROVISIONAL. Final name awaits Chauncey's word (naming sovereignty).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from levi.ddd.agents.base import DDDOperatorAgent
from levi.dynasty.dna import AgentError

__all__ = ["RentRollKeeper"]


class RentRollKeeper(DDDOperatorAgent):
    """Watches the tenants queue; drafts rent rolls. Sends no notice."""

    agent_id = "rentrollkeeper"
    display_name = "Rent-Roll Keeper (provisional)"
    owns = "LandlordLedger roll drafts ($12/mo/landlord)"
    first_milestone = "first rent-roll draft delivered with receipt"
    proficiency = {"bookkeeping": 9, "triage": 8, "general": 6}
    specialties = [
        "tenants queue: read-only scan",
        "rent rolls: monthly roll + late-notice drafts from rows present",
        "sends nothing: drafts only, sending is Chauncey's word",
    ]
    attributes = [
        {
            "name": "faithful roll drafting",
            "assertion": (
                "the keeper reads the tenants queue and drafts the monthly "
                "rent roll and late-notice drafts from rows actually "
                "present — and it never sends a notice itself."
            ),
        }
    ]

    def watch(self) -> Dict[str, Any]:
        queues = self._scan_queues("tenant*.csv", "rent*.csv", "lease*.csv")
        n_rows = sum(len(self._read_rows(p)) for p in queues)
        return {
            "agent_id": self.agent_id,
            "product": "LandlordLedger",
            "price": "$12/mo/landlord",
            "queue_files": [str(p) for p in queues],
            "n_rows": n_rows,
            "checked_at": self._checked_at(),
        }

    def draft_roll(self) -> str:
        """Draft the rent roll + late-notice drafts. Text only; sends none."""
        state = self.watch()
        lines = ["# DRAFT — LandlordLedger monthly rent roll"]
        lines.append(f"- Tenant rows seen: {state['n_rows']}")
        shown = 0
        for qf in state["queue_files"][:2]:
            for row in self._read_rows(Path(qf), limit=8):
                name = (
                    row.get("tenant")
                    or row.get("name")
                    or row.get("renter")
                    or "(tenant column not found)"
                )
                amount = row.get("rent") or row.get("amount") or "—"
                status = row.get("status") or "—"
                lines.append(f"  - {name}: {amount} [{status}]")
                shown += 1
        if shown == 0:
            lines.append("- No tenant rows. Nothing to roll.")
        else:
            lines.append(
                "- Late-notice drafts: one per row marked late/overdue, "
                "text only — the human sends."
            )
        lines.append("- DRAFT only: no notice is sent until Chauncey says so.")
        return "\n".join(lines)

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        kind = str(task.get("kind", "watch")).lower()
        self._guard_kind(kind)
        if kind == "watch":
            return self.watch()
        if kind == "draft":
            return {"draft": self.draft_roll()}
        raise AgentError(f"{self.agent_id}: unknown task kind {kind!r}")
