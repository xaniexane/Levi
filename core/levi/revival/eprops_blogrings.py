"""eProps + blogrings: deliberate reputation, human-curated neighborhoods.

Studied from: victims-of-giants-20260916-0017 report.md
[Resurrection shortlist #19]

The studied shape: reputation as a countable, deliberate act — eProps
are *given*, one at a time, with a note, not twitched out by an
algorithm — and blogrings: human-curated topical neighborhoods where
membership is vouched, not mined.

LEVI-native re-expression: two small structures.

* **eProps**: a prop is a signed, dated, counted unit of appreciation
  from one person to another, always carrying a short note. Giving is
  rate-limited (N props per giver per day, one prop per giver-receiver
  pair per day) so each one costs attention. Tallies are public and
  monotone — props are never revoked or downvoted.

* **Blogrings**: a ring is a named topical neighborhood with a human
  curator. Joining requires a vouch from an existing member (the
  curator's own join is the seed vouch). Rings list members newest-last
  and keep a simple webring-style next/prev traversal.

Honest limits: eProps measure expressed appreciation, not worth —
tallies can be gamed by mutual back-scratching; the rate limits only
slow that down. Blogrings are curation, not moderation tooling.
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


ORIGIN = "levi-revival/eprops-blogrings"

PROPS_PER_GIVER_PER_DAY = 10
ONE_PER_PAIR_PER_DAY = True


@dataclass(frozen=True)
class EProp:
    id: int
    giver: str
    receiver: str
    note: str
    at: float = field(default_factory=time.time)
    day: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "day", time.strftime("%Y-%m-%d", time.localtime(self.at))
        )


class EPropsError(ValueError):
    pass


class EProps:
    """Deliberate, countable reputation: given, never twitched."""

    def __init__(self) -> None:
        self._props: List[EProp] = []
        self._ids = itertools.count(1)
        self._daily_given: Dict[tuple, int] = {}  # (giver, day) -> count
        self._pair_day: set = set()  # (giver, receiver, day)

    def give(
        self, giver: str, receiver: str, note: str, at: Optional[float] = None
    ) -> EProp:
        if giver == receiver:
            raise EPropsError("cannot give a prop to yourself")
        if not note.strip():
            raise EPropsError("a prop needs a note — the note is the point")
        if len(note) > 280:
            raise EPropsError("prop note is capped at 280 characters")
        ts = at if at is not None else time.time()
        day = time.strftime("%Y-%m-%d", time.localtime(ts))
        if self._daily_given.get((giver, day), 0) >= PROPS_PER_GIVER_PER_DAY:
            raise EPropsError(
                f"{giver} has given today's {PROPS_PER_GIVER_PER_DAY} props"
            )
        if ONE_PER_PAIR_PER_DAY and (giver, receiver, day) in self._pair_day:
            raise EPropsError(
                f"{giver} already propped {receiver} today — one per pair per day"
            )
        prop = EProp(
            id=next(self._ids), giver=giver, receiver=receiver, note=note.strip(), at=ts
        )
        self._props.append(prop)
        self._daily_given[(giver, day)] = self._daily_given.get((giver, day), 0) + 1
        self._pair_day.add((giver, receiver, day))
        return prop

    def received(self, person: str) -> List[EProp]:
        return [p for p in self._props if p.receiver == person]

    def given_by(self, person: str) -> List[EProp]:
        return [p for p in self._props if p.giver == person]

    def tally(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for p in self._props:
            counts[p.receiver] = counts.get(p.receiver, 0) + 1
        return counts

    def top(self, limit: int = 10) -> List[tuple]:
        return sorted(self.tally().items(), key=lambda kv: (-kv[1], kv[0]))[:limit]


@dataclass
class Ring:
    name: str
    topic: str
    curator: str
    members: List[str] = field(default_factory=list)
    vouches: Dict[str, str] = field(default_factory=dict)  # member -> voucher


class BlogringError(ValueError):
    pass


class Blogrings:
    """Human-curated topical neighborhoods; entry by vouch, not by mining."""

    def __init__(self) -> None:
        self._rings: Dict[str, Ring] = {}

    def found(self, name: str, topic: str, curator: str) -> Ring:
        if name in self._rings:
            raise BlogringError(f"ring {name!r} already exists")
        ring = Ring(name=name, topic=topic, curator=curator, members=[curator])
        self._rings[name] = ring
        return ring

    def get(self, name: str) -> Optional[Ring]:
        return self._rings.get(name)

    def rings(self) -> List[Ring]:
        return sorted(self._rings.values(), key=lambda r: r.name)

    def vouch(self, ring_name: str, newcomer: str, voucher: str) -> Ring:
        """An existing member vouches a newcomer in. The vouch is recorded."""
        ring = self._rings.get(ring_name)
        if ring is None:
            raise BlogringError(f"no ring {ring_name!r}")
        if voucher not in ring.members:
            raise BlogringError(f"{voucher!r} is not a member of {ring_name!r}")
        if newcomer in ring.members:
            raise BlogringError(f"{newcomer!r} is already in {ring_name!r}")
        ring.members.append(newcomer)
        ring.vouches[newcomer] = voucher
        return ring

    def leave(self, ring_name: str, member: str) -> bool:
        ring = self._rings.get(ring_name)
        if ring is None or member not in ring.members:
            return False
        if member == ring.curator:
            raise BlogringError("the curator cannot leave; hand the ring over first")
        ring.members.remove(member)
        return True

    def hand_over(self, ring_name: str, new_curator: str, by: str) -> Ring:
        ring = self._rings.get(ring_name)
        if ring is None:
            raise BlogringError(f"no ring {ring_name!r}")
        if by != ring.curator:
            raise BlogringError("only the curator can hand a ring over")
        if new_curator not in ring.members:
            raise BlogringError(f"{new_curator!r} is not a member")
        ring.curator = new_curator
        return ring

    def neighbors(self, ring_name: str, member: str) -> tuple:
        """Webring-style (prev, next) traversal around the member list."""
        ring = self._rings.get(ring_name)
        if ring is None or member not in ring.members:
            raise BlogringError(f"{member!r} is not in ring {ring_name!r}")
        i = ring.members.index(member)
        n = len(ring.members)
        return ring.members[(i - 1) % n], ring.members[(i + 1) % n]

    def member_rings(self, person: str) -> List[Ring]:
        return [r for r in self._rings.values() if person in r.members]
