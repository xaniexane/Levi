# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Leads daemon — the daily review-reply + lead-gen draft engine (PROVISIONAL).

Every morning it takes up to 5 rows from Chauncey's lead queue and drafts,
per row, a review-reply response and a lead-gen pitch draft. Drafts land in
``~/workspace/ddd-inbox/`` and wait on his word.

HARD RULES (inherited + specific):
  L1/L2/L3 draft-only, no payment, no outbound — drafts are never sent or
     posted, and nobody is ever contacted.
  L4 honest zero-state — empty queue → honest receipt, never invents leads.
  REVIEW HARD RULE: reply drafts are drafts only. The machine drafts, a
     human posts. (Carries the standing ReviewReply law.)

NAMING: PROVISIONAL. Final name awaits Chauncey's word (naming sovereignty).
"""

from __future__ import annotations

from typing import Any, Dict, List

from levi.ddd.daemons.base import DDDDailyDaemon
from levi.dynasty.dna import AgentError

__all__ = ["LeadsDaemon"]


class LeadsDaemon(DDDDailyDaemon):
    """Drafts review replies + lead-gen pitches, daily. Contacts nobody."""

    agent_id = "leads-daemon"
    daemon_id = "leads-daemon"
    display_name = "Leads Daemon (provisional)"
    owns = "Daily review-reply drafts + lead-gen pitch drafts"
    first_milestone = "first reply draft delivered with honest receipt"
    proficiency = {"copywriting": 8, "outreach": 7, "general": 6}
    specialties = [
        "lead queue: read-only scan of rows Chauncey queued",
        "review replies: DRAFT-labeled responses, never posted (hard rule)",
        "lead-gen pitches: draft-only pitch copy, nobody contacted",
    ]
    attributes = [
        {
            "name": "honest lead drafting",
            "assertion": (
                "the daemon drafts only from lead rows Chauncey himself "
                "queued, labels every reply DRAFT, never posts a reply, "
                "never contacts anyone, and never invents a lead."
            ),
        }
    ]

    queue_filename = "leads.csv"
    queue_columns = (
        "business",
        "review_text",
        "rating",
        "source",
        "contact_name",
        "notes",
    )
    max_rows_per_day = 5

    def draft_for_rows(self, rows: List[Dict[str, str]]) -> tuple:
        lines = ["# DRAFT — review replies + lead-gen pitches"]
        lines.append(f"- Leads worked: {len(rows)} (from Chauncey's lead queue)")
        lines.append(
            "- HARD RULE: every reply below is a DRAFT. The machine drafts, "
            "a human posts. Nothing is posted or sent by this daemon."
        )
        lines.append("")
        for i, row in enumerate(rows, 1):
            business = row.get("business", "").strip() or "(unnamed business)"
            review_text = row.get("review_text", "").strip()
            rating = row.get("rating", "").strip()
            source = row.get("source", "").strip()
            contact = row.get("contact_name", "").strip()
            notes = row.get("notes", "").strip()
            lines.append(f"## {i}. {business}")
            if source:
                lines.append(f"- Source: {source}")
            if rating:
                lines.append(f"- Rating: {rating}")
            if contact:
                lines.append(f"- Contact: {contact}")
            if notes:
                lines.append(f"- Notes: {notes}")
            lines.append("")
            lines.append("### Review-reply draft (DRAFT — NEVER POSTED by machine)")
            snippet = (
                (review_text[:160] + "…") if len(review_text) > 160 else review_text
            )
            if review_text:
                lines.append(f'> Review: "{snippet}"')
            try:
                stars = float(rating)
                warm = stars >= 4
            except (TypeError, ValueError):
                warm = True
            if warm:
                lines.append(
                    f"Thank you for the kind words about {business}! "
                    "We're glad you had a great experience — we appreciate "
                    "you taking the time to share it."
                )
            else:
                lines.append(
                    f"Thank you for flagging this — we're sorry {business} "
                    "missed the mark for you. We'd like to make it right; "
                    "please reach out directly so we can fix this properly."
                )
            lines.append("")
            lines.append("### Lead-gen pitch draft (DRAFT — nobody contacted)")
            who = contact or business
            lines.append(
                f"Hi {who} — noticed {business} has reviews going unanswered. "
                "Unanswered reviews cost trust; a short, human reply on each "
                "one turns them around. I draft review replies for $15/month "
                "per location — want a free sample week? — Chauncey"
            )
            lines.append("")
            lines.append("---")
            lines.append("")
        lines.append(
            "DRAFT only: no reply posted, no message sent, nobody contacted, "
            "nothing charged. Waits on Chauncey's word."
        )
        return ("leads", "\n".join(lines))

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        kind = str(task.get("kind", "watch")).lower()
        self._guard_kind(kind)
        if kind == "watch":
            return self.watch()
        if kind == "run":
            return self.run_daily()
        raise AgentError(f"{self.daemon_id}: unknown task kind {kind!r}")
