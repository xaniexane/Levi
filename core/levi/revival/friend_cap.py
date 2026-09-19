"""Friend cap — the cap is the product.

Studied from: fallen-platforms-evening-20260916, report.md [2. Path].

The mechanism, functionally: intimacy enforced by architecture, not
policy. A person has a bounded audience — 50, later 150/500 — and the
boundary is hard: adds beyond the cap are denied at add-time, so
something must be removed before someone new can enter. There are no
follower counts to perform for; the circle is finite by construction.

This module is a software analog of that pattern: ``CappedCircle`` with
a hard cap enforced in ``add()``, deny-closed semantics (a failed add
returns a structured denial, never a silent drop), a waiting list only
in the sense of explicit pending requests, and capacity introspection
that reports counts but never a "follower" metric.

Honesty: a cap is a number enforced by an ``if`` — the intimacy comes
from the social consequence (someone must leave for someone to enter),
not from anything the code understands. It cannot tell a real friend
from a slot.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

ORIGIN = "levi-revival/friend-cap"


class CapDenied(Exception):
    """Raised when the circle is full: remove someone first."""


@dataclass
class Denial:
    """A structured denial: who was refused, why, when."""

    person: str
    reason: str
    at: float = field(default_factory=time.time)


class CappedCircle:
    """A bounded audience: the cap is enforced at add-time, hard."""

    DEFAULT_CAPS = (50, 150, 500)

    def __init__(self, owner: str, cap: int = 50) -> None:
        if cap < 1:
            raise ValueError("cap must be positive")
        self.owner = owner
        self.cap = cap
        self._members: Dict[str, float] = {}
        self.denials: List[Denial] = []
        self.pending: Set[str] = set()

    # -- the architecture of intimacy ------------------------------------

    def add(self, person: str) -> bool:
        """Add a member. Denied (``CapDenied``) when full — removal is the
        only way back in, which is the whole point."""
        person = person.strip()
        if not person:
            raise ValueError("person must be non-empty")
        if person in self._members:
            return False  # already inside; not a denial
        if len(self._members) >= self.cap:
            self.denials.append(Denial(person, f"circle full ({self.cap})"))
            raise CapDenied(f"circle is full at {self.cap}; remove someone first")
        self._members[person] = time.time()
        self.pending.discard(person)
        return True

    def remove(self, person: str) -> bool:
        if person in self._members:
            del self._members[person]
            return True
        return False

    def request(self, person: str) -> None:
        """An explicit knock on a full circle: recorded, never auto-added."""
        self.pending.add(person.strip())

    def approve(self, person: str) -> bool:
        """Approve a pending request — still subject to the cap."""
        person = person.strip()
        if person not in self.pending:
            return False
        self.add(person)  # may raise CapDenied; the cap does not bend
        return True

    # -- capacity introspection (no follower counts) ----------------------

    @property
    def size(self) -> int:
        return len(self._members)

    @property
    def remaining(self) -> int:
        return self.cap - len(self._members)

    def is_full(self) -> bool:
        return len(self._members) >= self.cap

    def members(self) -> List[str]:
        return sorted(self._members)

    def member_since(self, person: str) -> Optional[float]:
        return self._members.get(person)

    def set_cap(self, cap: int) -> None:
        """Raise the cap (50 -> 150 -> 500 tiers); it can never be set
        below the current membership — no silent evictions."""
        if cap < len(self._members):
            raise ValueError(
                f"cannot shrink cap to {cap} with {len(self._members)} members"
            )
        self.cap = cap
