# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Listing daemon — the daily resale listing draft engine (PROVISIONAL).

Every morning it takes up to 5 rows from Chauncey's resale inventory queue
and drafts marketplace listing copy with pricing guidance. Drafts land in
``~/workspace/ddd-inbox/`` and wait on his word. It never posts a listing
anywhere — drafting only.

LAWS (inherited + specific):
  L1/L2/L3 draft-only, no payment, no outbound — listings are drafted,
     never posted.
  L4 honest zero-state — empty queue → honest receipt, never invents items.
  PRICING HONESTY: pricing guidance is advisory and labeled ESTIMATE.
     Cost basis comes only from the queue row; margins are suggestions.

NAMING: PROVISIONAL. Final name awaits Chauncey's word (naming sovereignty).
"""

from __future__ import annotations

from typing import Any, Dict, List

from levi.ddd.daemons.base import DDDDailyDaemon
from levi.dynasty.dna import AgentError

__all__ = ["ListingDaemon"]


def _pricing_guidance(item: str, cost_basis: str, condition: str) -> List[str]:
    """Advisory pricing guidance. Estimates, labeled as such."""
    lines = ["### Pricing guidance (ESTIMATE — advisory only)"]
    try:
        cost = float(cost_basis)
        lines.append(f"- Cost basis (from queue): ${cost:.2f}")
        low, high = round(cost * 1.5, 2), round(cost * 3.0, 2)
        lines.append(
            f"- Suggested list range: ${low:.2f}–${high:.2f} "
            "(1.5x–3x cost basis — ESTIMATE, Chauncey's call)"
        )
    except (TypeError, ValueError):
        lines.append(
            "- No numeric cost basis in the queue — no price suggested. "
            "Chauncey prices this one."
        )
    cond = (condition or "").strip().lower()
    if cond in ("new", "deadstock", "like new", "mint"):
        lines.append("- Condition reads strong — upper end of the range is defensible.")
    elif cond:
        lines.append(f"- Condition noted as {condition!r} — price accordingly.")
    lines.append("- Bundle angle: slow movers pair well in mystery-box lots.")
    return lines


class ListingDaemon(DDDDailyDaemon):
    """Drafts marketplace listings + pricing guidance, daily. Never posts."""

    agent_id = "listing-daemon"
    daemon_id = "listing-daemon"
    display_name = "Listing Daemon (provisional)"
    owns = "Daily resale listing drafts + pricing guidance"
    first_milestone = "first listing draft delivered with honest receipt"
    proficiency = {"copywriting": 8, "pricing": 7, "general": 6}
    specialties = [
        "inventory queue: read-only scan of items Chauncey queued",
        "listing drafts: title + description + keywords from the row",
        "pricing guidance: advisory estimates from cost basis, never posted",
    ]
    attributes = [
        {
            "name": "honest listing drafting",
            "assertion": (
                "the daemon drafts only from inventory rows Chauncey "
                "himself queued, labels pricing as estimates, and never "
                "posts a listing or invents an item."
            ),
        }
    ]

    queue_filename = "inventory.csv"
    queue_columns = (
        "item",
        "description",
        "keywords",
        "condition",
        "cost_basis",
        "photo_ref",
    )
    max_rows_per_day = 5

    def draft_for_rows(self, rows: List[Dict[str, str]]) -> tuple:
        lines = ["# DRAFT — resale listing drafts"]
        lines.append(f"- Items worked: {len(rows)} (from Chauncey's inventory queue)")
        lines.append("")
        for i, row in enumerate(rows, 1):
            item = row.get("item", "").strip() or "(unnamed item)"
            desc = row.get("description", "").strip()
            keywords = row.get("keywords", "").strip()
            condition = row.get("condition", "").strip()
            cost_basis = row.get("cost_basis", "").strip()
            photo_ref = row.get("photo_ref", "").strip()
            lines.append(f"## {i}. {item}")
            if condition:
                lines.append(f"- Condition: {condition}")
            if photo_ref:
                lines.append(f"- Photo ref: {photo_ref}")
            lines.append("")
            lines.append("### Listing copy (DRAFT — never posted)")
            title_bits = [item]
            if condition:
                title_bits.append(f"({condition})")
            lines.append(f"**Title:** {' '.join(title_bits)}")
            body = desc or "Description to be finished by Chauncey."
            lines.append(f"**Body:** {body}")
            if keywords:
                lines.append(f"**Keywords:** {keywords}")
            lines.append("")
            lines.extend(_pricing_guidance(item, cost_basis, condition))
            lines.append("")
            lines.append("---")
            lines.append("")
        lines.append(
            "DRAFT only: no listing posted anywhere, nothing priced for real. "
            "Waits on Chauncey's word."
        )
        return ("listings", "\n".join(lines))

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        kind = str(task.get("kind", "watch")).lower()
        self._guard_kind(kind)
        if kind == "watch":
            return self.watch()
        if kind == "run":
            return self.run_daily()
        raise AgentError(f"{self.daemon_id}: unknown task kind {kind!r}")
