# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""AuditWarden — the AuditNow operator (PROVISIONAL).

AuditNow: $49 per audit. URL in, one-page website health PDF out
(page speed, SEO basics, broken links, mobile).

The warden is advisory-only: it scans the targets queue and drafts
per-URL audit briefs (what the audit would check). It runs no paid
audit and delivers no customer-facing report without Chauncey's word.

NAMING: PROVISIONAL. Final name awaits Chauncey's word (naming sovereignty).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from levi.ddd.agents.base import DDDOperatorAgent
from levi.dynasty.dna import AgentError

__all__ = ["AuditWarden"]

_AUDIT_CHECKS = ("page speed", "SEO basics", "broken links", "mobile")


class AuditWarden(DDDOperatorAgent):
    """Watches the targets queue; drafts audit briefs. Runs no paid audit."""

    agent_id = "auditwarden"
    display_name = "Audit Warden (provisional)"
    owns = "AuditNow audit briefs ($49/audit)"
    first_milestone = "first audit brief draft delivered with receipt"
    proficiency = {"auditing": 9, "web": 8, "general": 6}
    specialties = [
        "targets queue: read-only scan of URLs awaiting audit",
        "audit briefs: per-URL checklists of what the audit covers",
        "no paid run: briefs only, delivery is Chauncey's word",
    ]
    attributes = [
        {
            "name": "faithful brief drafting",
            "assertion": (
                "the warden reads the targets queue and drafts a brief per "
                "URL actually present — the checks the $49 audit covers — "
                "and it never runs a customer-facing audit or delivers a "
                "report on its own."
            ),
        }
    ]

    def watch(self) -> Dict[str, Any]:
        queues = self._scan_queues("target*.csv", "url*.csv", "audit*.csv")
        n_rows = sum(len(self._read_rows(p)) for p in queues)
        return {
            "agent_id": self.agent_id,
            "product": "AuditNow",
            "price": "$49/audit",
            "queue_files": [str(p) for p in queues],
            "n_rows": n_rows,
            "checked_at": self._checked_at(),
        }

    def draft_brief(self) -> str:
        """Draft per-URL audit briefs. Text only; runs no paid audit."""
        state = self.watch()
        lines = ["# DRAFT — AuditNow audit briefs"]
        lines.append(f"- Targets seen: {state['n_rows']}")
        lines.append(f"- Each brief covers: {', '.join(_AUDIT_CHECKS)}")
        shown = 0
        for qf in state["queue_files"][:2]:
            for row in self._read_rows(Path(qf), limit=5):
                url = (
                    row.get("url")
                    or row.get("target")
                    or row.get("website")
                    or "(url column not found)"
                )
                lines.append(f"  - {url}: brief drafted")
                shown += 1
        if shown == 0:
            lines.append("- No targets in the queue. Nothing to brief.")
        lines.append(
            "- DRAFT only: no audit is run or delivered until Chauncey says so."
        )
        return "\n".join(lines)

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        kind = str(task.get("kind", "watch")).lower()
        self._guard_kind(kind)
        if kind == "watch":
            return self.watch()
        if kind == "draft":
            return {"draft": self.draft_brief()}
        raise AgentError(f"{self.agent_id}: unknown task kind {kind!r}")
