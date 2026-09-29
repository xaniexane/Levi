# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: 2026-09-25.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""ReplyDrafter — the ReviewReply operator (PROVISIONAL).

ReviewReply: $15/mo per location. Reviews in, plain-speech reply DRAFTS
out. HARD RULE (standing): the daemon never posts — every draft is
labeled DRAFT and waits on the owner's word. The machine drafts, a
human posts.

The drafter is advisory-only: it scans the reviews queue and drafts
replies as text. It has no post path at all — "post"/"publish" tasks
are refused by the base guard (L3/L5).

NAMING: PROVISIONAL. Final name awaits Chauncey's word (naming sovereignty).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from levi.ddd.agents.base import DDDOperatorAgent
from levi.dynasty.dna import AgentError

__all__ = ["ReplyDrafter"]


class ReplyDrafter(DDDOperatorAgent):
    """Watches the reviews queue; drafts replies. Never posts — hard rule."""

    agent_id = "replydrafter"
    display_name = "Reply Drafter (provisional)"
    owns = "ReviewReply reply drafts ($15/mo/location) — never posts"
    first_milestone = "first reply-draft batch delivered with receipt"
    proficiency = {"copywriting": 10, "triage": 8, "general": 6}
    specialties = [
        "reviews queue: read-only scan",
        "reply drafts: plain-speech, one per review, labeled DRAFT",
        "never posts: hard rule — the machine drafts, a human posts",
    ]
    attributes = [
        {
            "name": "faithful draft-only replies",
            "assertion": (
                "the drafter reads the reviews queue and drafts a "
                "plain-speech reply per review actually present, each "
                "labeled DRAFT — and it never posts, publishes, or "
                "sends a reply anywhere. No post path exists."
            ),
        }
    ]

    def watch(self) -> Dict[str, Any]:
        queues = self._scan_queues("review*.csv", "feedback*.csv")
        n_rows = sum(len(self._read_rows(p)) for p in queues)
        return {
            "agent_id": self.agent_id,
            "product": "ReviewReply",
            "price": "$15/mo/location",
            "queue_files": [str(p) for p in queues],
            "n_rows": n_rows,
            "checked_at": self._checked_at(),
        }

    def draft_replies(self) -> str:
        """Draft plain-speech replies, one per review. Text only; posts none."""
        state = self.watch()
        lines = ["# DRAFT — ReviewReply reply drafts (NEVER POSTED)"]
        lines.append(f"- Reviews seen: {state['n_rows']}")
        shown = 0
        for qf in state["queue_files"][:2]:
            for row in self._read_rows(Path(qf), limit=5):
                text = (
                    row.get("review")
                    or row.get("text")
                    or row.get("comment")
                    or "(review text column not found)"
                )[:120]
                stars = row.get("stars") or row.get("rating") or "?"
                lines.append(f'  - [{stars}★] "{text}" → reply draft below')
                lines.append(
                    '    DRAFT reply: "Thanks for the feedback — '
                    'a human will follow up shortly."'
                )
                shown += 1
        if shown == 0:
            lines.append("- No reviews in the queue. Nothing to draft.")
        lines.append(
            "- HARD RULE: these drafts are never posted by the machine. "
            "A human posts, on Chauncey's word."
        )
        return "\n".join(lines)

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        kind = str(task.get("kind", "watch")).lower()
        self._guard_kind(kind)
        if kind == "watch":
            return self.watch()
        if kind == "draft":
            return {"draft": self.draft_replies()}
        raise AgentError(f"{self.agent_id}: unknown task kind {kind!r}")
