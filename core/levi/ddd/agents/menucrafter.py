# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""MenuCrafter — the MenuBoard Kit operator (PROVISIONAL).

MenuBoard Kit: $39 one-time, $5/mo for updates and new templates.
Menu CSV in, one-page digital menu + print-ready table tent out
(static HTML, zero build, zero external requests).

The crafter is advisory-only: it scans the menu queue and drafts the
board preview summary. It publishes no page.

NAMING: PROVISIONAL. Final name awaits Chauncey's word (naming sovereignty).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from levi.ddd.agents.base import DDDOperatorAgent
from levi.dynasty.dna import AgentError

__all__ = ["MenuCrafter"]


class MenuCrafter(DDDOperatorAgent):
    """Watches the menu queue; drafts board previews. Publishes nothing."""

    agent_id = "menucrafter"
    display_name = "Menu Crafter (provisional)"
    owns = "MenuBoard Kit preview drafts ($39 once + $5/mo)"
    first_milestone = "first board-preview draft delivered with receipt"
    proficiency = {"design": 8, "triage": 8, "general": 6}
    specialties = [
        "menu queue: read-only scan of menu rows",
        "board previews: section/item shape from rows present",
        "publishes nothing: drafts only, publishing is Chauncey's word",
    ]
    attributes = [
        {
            "name": "faithful preview drafting",
            "assertion": (
                "the crafter reads the menu queue and drafts the board "
                "preview from rows actually present — sections and items "
                "from the row's own fields — and it never publishes a page."
            ),
        }
    ]

    def watch(self) -> Dict[str, Any]:
        queues = self._scan_queues("menu*.csv", "dish*.csv", "board*.csv")
        n_rows = sum(len(self._read_rows(p)) for p in queues)
        return {
            "agent_id": self.agent_id,
            "product": "MenuBoard Kit",
            "price": "$39 once + $5/mo",
            "queue_files": [str(p) for p in queues],
            "n_rows": n_rows,
            "checked_at": self._checked_at(),
        }

    def draft_preview(self) -> str:
        """Draft the board preview summary. Text only; publishes nothing."""
        state = self.watch()
        lines = ["# DRAFT — MenuBoard Kit board preview"]
        lines.append(f"- Menu rows seen: {state['n_rows']}")
        shown = 0
        for qf in state["queue_files"][:2]:
            for row in self._read_rows(Path(qf), limit=8):
                name = (
                    row.get("item")
                    or row.get("dish")
                    or row.get("name")
                    or "(item column not found)"
                )
                section = row.get("section") or row.get("category") or "—"
                price = row.get("price") or "—"
                lines.append(f"  - [{section}] {name} — {price}")
                shown += 1
        if shown == 0:
            lines.append("- No menu rows. Nothing to preview.")
        lines.append("- DRAFT only: no page is published until Chauncey says so.")
        return "\n".join(lines)

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        kind = str(task.get("kind", "watch")).lower()
        self._guard_kind(kind)
        if kind == "watch":
            return self.watch()
        if kind == "draft":
            return {"draft": self.draft_preview()}
        raise AgentError(f"{self.agent_id}: unknown task kind {kind!r}")
