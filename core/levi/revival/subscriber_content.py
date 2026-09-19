"""Subscriber-written local content inside a newspaper-run service.

Studied from: dead-networks-20260916/report.md (StarText).

The old mechanism: a newspaper ran a dialup service where subscribers
didn't just read — they wrote the local sections themselves. Copy went
through an editorial gate (accept, reject, publish, retract), and
regulars earned standing by the quality of what they filed. LEVI's
reimplementation is that newsroom in local memory: a submission queue,
editorial review, a published ledger with corrections and retractions
kept on the record, and a reputation score that is openly a heuristic —
documented, inspectable, never a claim about a person's worth.

Honest limits: reputation here is arithmetic (+2 accepted, -1
rejected), not editorial judgment; tiers gate sections by rule, not by
taste. Retractions stay in the ledger — the record is never rewritten.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/subscriber_content"

QUEUED = "queued"
APPROVED = "approved"
REJECTED = "rejected"
PUBLISHED = "published"
RETRACTED = "retracted"

# Reputation tiers: openly heuristic thresholds over the score.
TIER_NEW = "new"
TIER_CONTRIBUTOR = "contributor"
TIER_TRUSTED = "trusted"

# Sections that demand a minimum tier to file in.
SECTION_TIERS: Dict[str, str] = {
    "opinion": TIER_CONTRIBUTOR,
    "editorial": TIER_TRUSTED,
}

_TIER_RANK = {TIER_NEW: 0, TIER_CONTRIBUTOR: 1, TIER_TRUSTED: 2}


@dataclass
class Submission:
    sub_id: int
    author: str
    section: str
    title: str
    body: str
    status: str = QUEUED
    notes: List[str] = field(default_factory=list)
    corrections: List[str] = field(default_factory=list)


class Newsroom:
    """The paper's desk: queue, review, publish, correct, retract."""

    def __init__(self) -> None:
        self.submissions: Dict[int, Submission] = {}
        self.reputation: Dict[str, int] = {}
        self._next_id = 0

    # -- filing --------------------------------------------------------
    def submit(self, author: str, section: str, title: str, body: str) -> Submission:
        author = author.strip()
        section = section.strip().lower()
        if not author:
            raise ValueError("author required")
        if not section:
            raise ValueError("section required")
        if not title.strip() or not body.strip():
            raise ValueError("title and body required")
        self._check_tier(author, section)
        self.reputation.setdefault(author, 0)
        self._next_id += 1
        sub = Submission(
            sub_id=self._next_id,
            author=author,
            section=section,
            title=title.strip(),
            body=body.strip(),
        )
        self.submissions[sub.sub_id] = sub
        return sub

    def queue(self, section: Optional[str] = None) -> List[Submission]:
        subs = [s for s in self.submissions.values() if s.status == QUEUED]
        if section is not None:
            subs = [s for s in subs if s.section == section.strip().lower()]
        return subs

    # -- the editorial gate ---------------------------------------------
    def review(
        self, sub_id: int, editor: str, approved: bool, note: str = ""
    ) -> Submission:
        sub = self._get(sub_id)
        if sub.status not in (QUEUED, REJECTED):
            raise ValueError(f"submission {sub_id} is {sub.status}")
        sub.status = APPROVED if approved else REJECTED
        entry = f"{editor}: {'approved' if approved else 'rejected'}"
        if note.strip():
            entry += f" — {note.strip()}"
        sub.notes.append(entry)
        self.reputation[sub.author] = self.reputation.get(sub.author, 0) + (
            2 if approved else -1
        )
        return sub

    def publish(self, sub_id: int, editor: str) -> Submission:
        sub = self._get(sub_id)
        if sub.status != APPROVED:
            raise ValueError(
                f"submission {sub_id} is {sub.status}; only approved copy publishes"
            )
        sub.status = PUBLISHED
        sub.notes.append(f"{editor}: published")
        return sub

    def correct(self, sub_id: int, editor: str, correction: str) -> Submission:
        """Append a correction. The original body is never rewritten —
        the ledger shows both."""
        sub = self._get(sub_id)
        if sub.status != PUBLISHED:
            raise ValueError("only published copy can be corrected")
        if not correction.strip():
            raise ValueError("correction text required")
        sub.corrections.append(f"{editor}: {correction.strip()}")
        return sub

    def retract(self, sub_id: int, editor: str, reason: str) -> Submission:
        sub = self._get(sub_id)
        if sub.status != PUBLISHED:
            raise ValueError("only published copy can be retracted")
        if not reason.strip():
            raise ValueError("retraction reason required")
        sub.status = RETRACTED
        sub.notes.append(f"{editor}: retracted — {reason.strip()}")
        return sub

    # -- reading ---------------------------------------------------------
    def published(self, section: Optional[str] = None) -> List[Submission]:
        subs = [s for s in self.submissions.values() if s.status == PUBLISHED]
        if section is not None:
            subs = [s for s in subs if s.section == section.strip().lower()]
        return sorted(subs, key=lambda s: s.sub_id)

    def search(self, text: str) -> List[Submission]:
        needle = text.strip().lower()
        if not needle:
            return []
        return [
            s
            for s in self.published()
            if needle in s.title.lower() or needle in s.body.lower()
        ]

    def tier(self, author: str) -> str:
        score = self.reputation.get(author.strip(), 0)
        if score >= 10:
            return TIER_TRUSTED
        if score >= 3:
            return TIER_CONTRIBUTOR
        return TIER_NEW

    def desk_status(self) -> Dict[str, object]:
        counts: Dict[str, int] = {}
        for s in self.submissions.values():
            counts[s.status] = counts.get(s.status, 0) + 1
        return {
            "submissions": len(self.submissions),
            "by_status": counts,
            "contributors": len(self.reputation),
        }

    # -- internals -------------------------------------------------------
    def _get(self, sub_id: int) -> Submission:
        try:
            return self.submissions[sub_id]
        except KeyError:
            raise ValueError(f"no submission {sub_id}") from None

    def _check_tier(self, author: str, section: str) -> None:
        required = SECTION_TIERS.get(section)
        if required is None:
            return
        have = self.tier(author)
        if _TIER_RANK[have] < _TIER_RANK[required]:
            raise ValueError(
                f"section {section!r} needs tier {required!r}; {author} is {have!r}"
            )
