# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""NoShowWarden — the NoShowBlocker operator (PROVISIONAL).

NoShowBlocker: $29/mo per location. Appointments CSV in, reminders for
appointments inside the reminder window out (the product's outbox ledger
guarantees no double-reminds).

The warden is advisory-only: it scans the appointments queue and drafts
the reminder list as text. It never sends a reminder — "remind" tasks
are refused by the base guard (L3).

NAMING: PROVISIONAL. Final name awaits Chauncey's word (naming sovereignty).
"""

from __future__ import annotations

from typing import Any, Dict

from levi.ddd.agents.base import DDDOperatorAgent

__all__ = ["NoShowWarden"]


class NoShowWarden(DDDOperatorAgent):
    """Watches the appointments queue; drafts reminder lists. Never sends."""

    agent_id = "noshowwarden"
    display_name = "NoShow Warden (provisional)"
    owns = "NoShowBlocker reminder drafts ($29/mo/location)"
    first_milestone = "first reminder-list draft delivered with receipt"
    proficiency = {"triage": 9, "scheduling": 8, "general": 6}
    specialties = [
        "appointments: read-only queue scan",
        "reminder lists: drafts who would be reminded, in-window",
        "never sends: drafts only, dispatch is Chauncey's word",
    ]
    attributes = [
        {
            "name": "faithful reminder drafting",
            "assertion": (
                "the warden reads the appointments queue and drafts the "
                "list of appointments that would be reminded — from rows "
                "actually present, nothing invented — and it never sends "
                "a reminder itself."
            ),
        }
    ]

    def watch(self) -> Dict[str, Any]:
        queues = self._scan_queues("appointment*.csv", "booking*.csv")
        n_rows = sum(len(self._read_rows(p)) for p in queues)
        return {
            "agent_id": self.agent_id,
            "product": "NoShowBlocker",
            "price": "$29/mo/location",
            "queue_files": [str(p) for p in queues],
            "n_rows": n_rows,
            "checked_at": self._checked_at(),
        }

    def draft_reminders(self) -> str:
        """Draft the reminder list from the queue. Text only; sends nothing."""
        state = self.watch()
        lines = ["# DRAFT — NoShowBlocker reminder list"]
        lines.append(f"- Queue rows seen: {state['n_rows']}")
        if state["n_rows"] == 0:
            lines.append("- No appointments in the queue. Nothing to remind.")
        else:
            lines.append(
                "- Reminder-window filtering happens at send time; "
                "this draft lists what the queue holds."
            )
            for qf in state["queue_files"][:3]:
                lines.append(f"  - {qf}")
        lines.append("- DRAFT only: no reminder is sent until Chauncey says so.")
        return "\n".join(lines)

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        kind = str(task.get("kind", "watch")).lower()
        self._guard_kind(kind)
        if kind == "watch":
            return self.watch()
        if kind == "draft":
            text = self.draft_reminders()
            return {"draft": text}
        from levi.dynasty.dna import AgentError

        raise AgentError(f"{self.agent_id}: unknown task kind {kind!r}")
