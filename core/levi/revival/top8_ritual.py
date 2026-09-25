"""The top-8 curation ritual: an explicit, visible inner circle.

Studied from: victims-of-giants-20260916-0017/report.md (Resurrection shortlist #9)

The mechanism: the owner keeps exactly one ranked list of up to eight
*slots*, each holding a contact. Placement is deliberate — promote,
demote, insert, retire — and every change is journaled so the ritual
stays *visible* rather than drifting into an implicit graph the platform
infers for you.

Honest limit: this module stores the curation as data. It does not
detect friendships, score closeness, or sync with anything external —
it trusts the owner to say who matters.

stdlib-only. No network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


ORIGIN = "levi-revival/top8-ritual"

MAX_SLOTS = 8


@dataclass
class CurationEvent:
    """One visible act of curation, journaled with a timestamp."""

    action: str  # "place", "promote", "demote", "insert", "retire"
    contact: str
    detail: str = ""
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class TopEight:
    """A ranked inner-circle list of at most eight contacts."""

    owner: str
    slots: List[str] = field(default_factory=list)
    journal: List[CurationEvent] = field(default_factory=list)

    def _log(self, action: str, contact: str, detail: str = "") -> None:
        self.journal.append(
            CurationEvent(action=action, contact=contact, detail=detail)
        )

    # -- curation acts --------------------------------------------------
    def place(self, contact: str) -> int:
        """Fill the next open slot, or raise if the circle is full."""
        contact = _check_contact(contact)
        if contact in self.slots:
            raise ValueError(f"already in the circle: {contact!r}")
        if len(self.slots) >= MAX_SLOTS:
            raise ValueError("circle is full — retire someone first")
        self.slots.append(contact)
        self._log("place", contact, f"slot {len(self.slots)}")
        return len(self.slots)

    def insert(self, contact: str, rank: int) -> None:
        """Insert at an explicit rank (1-based), shifting others down."""
        contact = _check_contact(contact)
        if contact in self.slots:
            raise ValueError(f"already in the circle: {contact!r}")
        if len(self.slots) >= MAX_SLOTS:
            raise ValueError("circle is full — retire someone first")
        rank = max(1, min(rank, len(self.slots) + 1))
        self.slots.insert(rank - 1, contact)
        self._log("insert", contact, f"rank {rank}")

    def promote(self, contact: str) -> int:
        """Move one slot closer to #1."""
        idx = self._index(contact)
        if idx == 0:
            raise ValueError(f"{contact!r} is already #1")
        self.slots[idx - 1], self.slots[idx] = self.slots[idx], self.slots[idx - 1]
        self._log("promote", contact, f"now rank {idx}")
        return idx  # new 1-based rank is idx (0-based idx means rank idx)

    def demote(self, contact: str) -> int:
        """Move one slot closer to #8."""
        idx = self._index(contact)
        if idx == len(self.slots) - 1:
            raise ValueError(f"{contact!r} is already last")
        self.slots[idx], self.slots[idx + 1] = self.slots[idx + 1], self.slots[idx]
        self._log("demote", contact, f"now rank {idx + 2}")
        return idx + 2

    def retire(self, contact: str) -> str:
        """Remove from the circle entirely (gracefully, with a journal entry)."""
        idx = self._index(contact)
        removed = self.slots.pop(idx)
        self._log("retire", removed, f"was rank {idx + 1}")
        return removed

    def rank_of(self, contact: str) -> Optional[int]:
        """1-based rank, or None if not in the circle."""
        return self.slots.index(contact) + 1 if contact in self.slots else None

    # -- ritual honesty -------------------------------------------------
    def full(self) -> bool:
        return len(self.slots) >= MAX_SLOTS

    def recent_changes(self, n: int = 5) -> List[CurationEvent]:
        """The last n visible acts, newest first."""
        return list(reversed(self.journal[-n:]))

    def to_dict(self) -> Dict:
        return {
            "owner": self.owner,
            "slots": list(self.slots),
            "journal": [
                {
                    "action": e.action,
                    "contact": e.contact,
                    "detail": e.detail,
                    "at": e.at,
                }
                for e in self.journal
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TopEight":
        top = cls(owner=data["owner"])
        top.slots = list(data.get("slots", []))
        top.journal = [
            CurationEvent(
                action=e["action"],
                contact=e["contact"],
                detail=e.get("detail", ""),
                at=e["at"],
            )
            for e in data.get("journal", [])
        ]
        return top

    def _index(self, contact: str) -> int:
        if contact not in self.slots:
            raise KeyError(f"not in the circle: {contact!r}")
        return self.slots.index(contact)


def _check_contact(contact: str) -> str:
    contact = (contact or "").strip()
    if not contact:
        raise ValueError("contact must be non-empty")
    return contact


def new_circle(owner: str) -> TopEight:
    """Start an empty inner-circle ritual for an owner."""
    if not owner or not owner.strip():
        raise ValueError("owner must be non-empty")
    return TopEight(owner=owner.strip())
