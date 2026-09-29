# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""LotAppraiser — the LotValuator operator (PROVISIONAL).

LotValuator: $25/mo unlimited, or $15 per single lot. Item manifest
CSV + local sold-comp price guide in, valuation out. Built for
Chauncey's own mystery-box resale ladder as much as for flippers.

The appraiser is advisory-only: it scans the manifest queue and drafts
valuation worksheets. It lists nothing for sale and moves no money.

NAMING: PROVISIONAL. Final name awaits Chauncey's word (naming sovereignty).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from levi.ddd.agents.base import DDDOperatorAgent
from levi.dynasty.dna import AgentError

__all__ = ["LotAppraiser"]


class LotAppraiser(DDDOperatorAgent):
    """Watches the manifest queue; drafts valuation worksheets. Sells nothing."""

    agent_id = "lotappraiser"
    display_name = "Lot Appraiser (provisional)"
    owns = "LotValuator worksheets ($25/mo or $15/lot)"
    first_milestone = "first valuation worksheet delivered with receipt"
    proficiency = {"pricing": 9, "triage": 8, "general": 6}
    specialties = [
        "manifest queue: read-only scan of lot rows",
        "worksheets: per-row valuation shape from fields present",
        "sells nothing: drafts only, listings are Chauncey's word",
    ]
    attributes = [
        {
            "name": "faithful worksheet drafting",
            "assertion": (
                "the appraiser reads the manifest queue and drafts a "
                "valuation worksheet per row actually present — item, "
                "quantity, comp fields from the row itself — and it never "
                "lists anything for sale or moves money."
            ),
        }
    ]

    def watch(self) -> Dict[str, Any]:
        queues = self._scan_queues("manifest*.csv", "lot*.csv", "flips*.csv")
        n_rows = sum(len(self._read_rows(p)) for p in queues)
        return {
            "agent_id": self.agent_id,
            "product": "LotValuator",
            "price": "$25/mo or $15/lot",
            "queue_files": [str(p) for p in queues],
            "n_rows": n_rows,
            "checked_at": self._checked_at(),
        }

    def draft_worksheet(self) -> str:
        """Draft valuation worksheets from the manifest. Text only."""
        state = self.watch()
        lines = ["# DRAFT — LotValuator valuation worksheets"]
        lines.append(f"- Manifest rows seen: {state['n_rows']}")
        shown = 0
        for qf in state["queue_files"][:2]:
            for row in self._read_rows(Path(qf), limit=5):
                item = (
                    row.get("item")
                    or row.get("title")
                    or row.get("name")
                    or "(item column not found)"
                )
                qty = row.get("qty") or row.get("quantity") or "1"
                lines.append(
                    f"  - {item} × {qty}: worksheet drafted "
                    "(comp price → est. value at pack time)"
                )
                shown += 1
        if shown == 0:
            lines.append("- No manifest rows. Nothing to appraise.")
        lines.append("- DRAFT only: nothing is listed or sold until Chauncey says so.")
        return "\n".join(lines)

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        kind = str(task.get("kind", "watch")).lower()
        self._guard_kind(kind)
        if kind == "watch":
            return self.watch()
        if kind == "draft":
            return {"draft": self.draft_worksheet()}
        raise AgentError(f"{self.agent_id}: unknown task kind {kind!r}")
