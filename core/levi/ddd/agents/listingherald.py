# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""ListingHerald — the ListingPress operator (PROVISIONAL).

ListingPress: $12/mo, or $5 per 25 listings. Photo + keywords in,
marketplace listing pack out (JSON + Markdown per unprocessed row).

The herald is advisory-only: it scans the items queue and drafts pack
outlines. It never posts a listing anywhere.

NAMING: PROVISIONAL. Final name awaits Chauncey's word (naming sovereignty).
"""

from __future__ import annotations

from typing import Any, Dict

from levi.ddd.agents.base import DDDOperatorAgent
from levi.dynasty.dna import AgentError

__all__ = ["ListingHerald"]


class ListingHerald(DDDOperatorAgent):
    """Watches the items queue; drafts listing-pack outlines. Never posts."""

    agent_id = "listingherald"
    display_name = "Listing Herald (provisional)"
    owns = "ListingPress pack drafts ($12/mo or $5/25 listings)"
    first_milestone = "first listing-pack draft delivered with receipt"
    proficiency = {"copywriting": 9, "triage": 8, "general": 6}
    specialties = [
        "items queue: read-only scan of unprocessed rows",
        "pack outlines: title/photo/keywords shaped drafts",
        "never posts: drafts only, publishing is Chauncey's word",
    ]
    attributes = [
        {
            "name": "faithful pack drafting",
            "assertion": (
                "the herald reads the items queue and drafts a listing-pack "
                "outline per row actually present — title, photo note, "
                "keywords from the row's own fields — and it never posts "
                "a listing anywhere."
            ),
        }
    ]

    def watch(self) -> Dict[str, Any]:
        queues = self._scan_queues("item*.csv", "listing*.csv", "inventory*.csv")
        n_rows = sum(len(self._read_rows(p)) for p in queues)
        return {
            "agent_id": self.agent_id,
            "product": "ListingPress",
            "price": "$12/mo or $5/25 listings",
            "queue_files": [str(p) for p in queues],
            "n_rows": n_rows,
            "checked_at": self._checked_at(),
        }

    def draft_pack(self) -> str:
        """Draft listing-pack outlines from the queue. Text only."""
        state = self.watch()
        lines = ["# DRAFT — ListingPress pack outlines"]
        lines.append(f"- Queue rows seen: {state['n_rows']}")
        shown = 0
        for qf in state["queue_files"][:2]:
            from pathlib import Path

            for row in self._read_rows(Path(qf), limit=5):
                keys = ", ".join(sorted(row.keys())[:6])
                lines.append(f"  - row: fields [{keys}] → pack outline drafted")
                shown += 1
        if shown == 0:
            lines.append("- No items in the queue. Nothing to draft.")
        lines.append("- DRAFT only: nothing is posted until Chauncey says so.")
        return "\n".join(lines)

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        kind = str(task.get("kind", "watch")).lower()
        self._guard_kind(kind)
        if kind == "watch":
            return self.watch()
        if kind == "draft":
            return {"draft": self.draft_pack()}
        raise AgentError(f"{self.agent_id}: unknown task kind {kind!r}")
