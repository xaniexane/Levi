"""Dunbar-capped intimacy circles: small audiences enforced by structure.

Studied from: victims-of-giants-20260916-0017 report.md
[Resurrection shortlist #16]

The studied shape: enforced small-audience modes for sharing — the
dead-web intuition that a post means something different when it can
only reach fifteen people than when it can reach fifteen thousand.
Intimacy is a property of the audience cap, not of vibes.

LEVI-native re-expression: named circles with hard membership caps
drawn from the Dunbar layers (5 / 15 / 50 / 150). A share carries an
explicit audience mode naming a circle; the composer refuses to post
beyond a circle's cap, and membership moves are checked against it.
Modes are explicit — `inner` (5), `close` (15), `kindred` (50),
`tribe` (150) — plus a per-circle custom cap.

Honest limits: caps are enforced on membership counts only. This does
not stop screenshots or re-sharing; it is a structural nudge toward
small audiences, not a privacy guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


ORIGIN = "levi-revival/intimacy-circles"

# Dunbar layers as hard audience ceilings.
LAYER_CAPS = {"inner": 5, "close": 15, "kindred": 50, "tribe": 150}


@dataclass
class Share:
    """A share record with an explicit, capped audience."""

    id: int
    body: str
    circle: str
    audience_cap: int
    visible_to: Set[str] = field(default_factory=set)


class IntimacyError(ValueError):
    """Raised when a cap or membership rule is violated."""


class IntimacyCircle:
    """One named circle: hard-capped membership, explicit share modes."""

    def __init__(
        self, name: str, layer: str = "close", custom_cap: Optional[int] = None
    ) -> None:
        if layer not in LAYER_CAPS and custom_cap is None:
            raise IntimacyError(
                f"unknown layer {layer!r}; choose from {sorted(LAYER_CAPS)}"
            )
        self.name = name
        self.layer = layer
        self.cap = custom_cap if custom_cap is not None else LAYER_CAPS[layer]
        if self.cap < 1:
            raise IntimacyError("cap must be >= 1")
        self.members: List[str] = []  # insertion order = seniority
        self.shares: List[Share] = []
        self._next_share_id = 1

    def add(self, person: str) -> None:
        if person in self.members:
            return  # idempotent
        if len(self.members) >= self.cap:
            raise IntimacyError(
                f"circle {self.name!r} is full at {self.cap} (layer {self.layer!r})"
            )
        self.members.append(person)

    def remove(self, person: str) -> bool:
        if person in self.members:
            self.members.remove(person)
            return True
        return False

    def headroom(self) -> int:
        return self.cap - len(self.members)

    def is_full(self) -> bool:
        return len(self.members) >= self.cap

    def share(self, body: str, author: str) -> Share:
        if author not in self.members:
            raise IntimacyError(f"{author!r} is not a member of {self.name!r}")
        share = Share(
            id=self._next_share_id,
            body=body,
            circle=self.name,
            audience_cap=self.cap,
            visible_to=set(self.members),
        )
        self._next_share_id += 1
        self.shares.append(share)
        return share

    def can_see(self, person: str) -> bool:
        return person in self.members

    def recent(self, person: str, limit: int = 20) -> List[Share]:
        if not self.can_see(person):
            return []
        return list(reversed(self.shares[-limit:]))


class CircleDeck:
    """A person's set of circles across layers."""

    def __init__(self, owner: str) -> None:
        self.owner = owner
        self.circles: Dict[str, IntimacyCircle] = {}

    def create(
        self, name: str, layer: str = "close", custom_cap: Optional[int] = None
    ) -> IntimacyCircle:
        if name in self.circles:
            raise IntimacyError(f"circle {name!r} already exists")
        circle = IntimacyCircle(name, layer=layer, custom_cap=custom_cap)
        self.circles[name] = circle
        return circle

    def get(self, name: str) -> Optional[IntimacyCircle]:
        return self.circles.get(name)

    def share_to(self, circle_name: str, body: str) -> Share:
        circle = self.get(circle_name)
        if circle is None:
            raise IntimacyError(f"no circle {circle_name!r}")
        return circle.share(body, self.owner)

    def feed(self, person: str, limit: int = 20) -> List[Share]:
        """Everything `person` can see, newest first across circles."""
        seen: List[Share] = []
        for circle in self.circles.values():
            seen.extend(circle.recent(person, limit=limit))
        seen.sort(key=lambda s: s.id, reverse=True)
        return seen[:limit]
