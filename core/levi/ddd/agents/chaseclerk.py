# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""ChaseClerk — the InvoiceChaser operator (PROVISIONAL).

InvoiceChaser: $9/mo per user. Invoices CSV in, an escalating polite
payment-chase sequence at 3 / 7 / 14 / 30 days overdue out. Paid
invoices are never chased.

The clerk is advisory-only: it scans the invoices queue and drafts
the chase list by overdue bucket. It never sends a chase — "chase"
tasks are refused by the base guard (L3).

NAMING: PROVISIONAL. Final name awaits Chauncey's word (naming sovereignty).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from levi.ddd.agents.base import DDDOperatorAgent
from levi.dynasty.dna import AgentError

__all__ = ["ChaseClerk"]

_BUCKETS = (3, 7, 14, 30)


class ChaseClerk(DDDOperatorAgent):
    """Watches the invoices queue; drafts chase lists by bucket. Never sends."""

    agent_id = "chaseclerk"
    display_name = "Chase Clerk (provisional)"
    owns = "InvoiceChaser chase drafts ($9/mo/user)"
    first_milestone = "first chase-list draft delivered with receipt"
    proficiency = {"triage": 9, "bookkeeping": 8, "general": 6}
    specialties = [
        "invoices queue: read-only scan, paid rows skipped",
        "chase lists: overdue buckets 3/7/14/30 days",
        "never sends: drafts only, sending is Chauncey's word",
    ]
    attributes = [
        {
            "name": "faithful chase drafting",
            "assertion": (
                "the clerk reads the invoices queue, skips rows marked "
                "paid, buckets the rest by overdue days, and drafts the "
                "chase list as text — and it never sends a chase itself."
            ),
        }
    ]

    def watch(self) -> Dict[str, Any]:
        queues = self._scan_queues("invoice*.csv", "bill*.csv")
        rows: List[Dict[str, str]] = []
        for qf in queues:
            rows.extend(self._read_rows(qf))
        unpaid = [
            r
            for r in rows
            if str(r.get("status", r.get("paid", "unpaid"))).strip().lower()
            not in ("paid", "yes", "true", "1", "settled")
        ]
        return {
            "agent_id": self.agent_id,
            "product": "InvoiceChaser",
            "price": "$9/mo/user",
            "queue_files": [str(p) for p in queues],
            "n_rows": len(rows),
            "n_unpaid": len(unpaid),
            "buckets": list(_BUCKETS),
            "checked_at": self._checked_at(),
        }

    def _bucket(self, row: Dict[str, str]) -> str:
        raw = (
            row.get("days_overdue")
            or row.get("overdue_days")
            or row.get("days late")
            or ""
        )
        try:
            days = int(float(str(raw).strip()))
        except (TypeError, ValueError):
            return "unbucketed (no due-date data)"
        for b in _BUCKETS:
            if days <= b:
                return f"{b}-day bucket"
        return "30+-day bucket"

    def draft_chase_list(self) -> str:
        """Draft the chase list by overdue bucket. Text only; sends nothing."""
        state = self.watch()
        lines = ["# DRAFT — InvoiceChaser chase list"]
        lines.append(
            f"- Invoices seen: {state['n_rows']} "
            f"({state['n_unpaid']} unpaid; paid rows skipped)"
        )
        if state["n_unpaid"] == 0:
            lines.append("- Nothing overdue in the queue. Nothing to chase.")
        else:
            buckets: Dict[str, int] = {}
            for qf in state["queue_files"][:2]:
                for row in self._read_rows(Path(qf)):
                    buckets[self._bucket(row)] = buckets.get(self._bucket(row), 0) + 1
            for name in sorted(buckets):
                lines.append(f"  - {name}: {buckets[name]} invoice(s)")
        lines.append("- DRAFT only: no chase is sent until Chauncey says so.")
        return "\n".join(lines)

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        kind = str(task.get("kind", "watch")).lower()
        self._guard_kind(kind)
        if kind == "watch":
            return self.watch()
        if kind == "draft":
            return {"draft": self.draft_chase_list()}
        raise AgentError(f"{self.agent_id}: unknown task kind {kind!r}")
