"""Symmetric voting: bury is a first-class citizen, thresholds are public.

Studied from: victims-of-giants-20260916-0017 / report.md [Resurrection
shortlist #5] (symmetric voting: a bury/downvote with transparent promotion
thresholds in curation surfaces).

This is an original, from-scratch implementation for LEVI. A ``Surface``
holds ``Item``s that members score with two symmetric verbs: ``upvote``
(promote) and ``bury`` (demote). Both verbs carry the same weight — a bury
is not a flag, not a report, not a shadowban request; it is a vote, counted
in the open.

The curation math is transparent by construction: ``policy()`` publishes
the exact thresholds (promotion score, burial score, quorum), and every
item's ``standing`` shows its raw counts and current tier. Tiers are
``rising`` (score >= promote_at), ``contested`` (buried enough to argue
about but not enough to sink), ``sunk`` (score <= bury_at), and ``new``
(everything else). One member, one vote per item per verb — ``change_vote``
lets a voter honestly change their mind.

Honest limits:
- One vote per verb per member per item is enforced, but identity is just a
  string — the module cannot stop sockpuppets; the surrounding system must
  own identity.
- Thresholds are configurable, not sacred; changing them mid-surface is
  allowed and visible via ``policy()``, and standings recompute live.
- Ties and quorum edge cases resolve deterministically (tiers checked in
  fixed order: sunk, rising, contested, new).

Public surface:
- ``Vote``, ``Item``, ``Surface``: ``add_item``, ``upvote``, ``bury``,
  ``retract``, ``change_vote``, ``standing``, ``ranked``, ``policy``,
  ``set_policy``.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional

ORIGIN = "levi-revival/symmetric-voting"


@dataclass(frozen=True)
class Policy:
    """The published promotion math. Visible to everyone on the surface."""

    promote_at: int = 5  # score >= this -> rising
    bury_at: int = -3  # score <= this -> sunk
    quorum: int = 3  # votes needed before any tier applies

    def __post_init__(self) -> None:
        if self.quorum < 1:
            raise SurfaceError("quorum must be at least 1")
        if self.bury_at >= self.promote_at:
            raise SurfaceError("bury_at must be below promote_at")


class SurfaceError(ValueError):
    """Raised when a vote or item reference is invalid."""


@dataclass
class Item:
    """One curatable thing with open, symmetric vote counts."""

    id: int
    title: str
    body: str = ""
    _ups: FrozenSet[str] = field(default_factory=frozenset, repr=False)
    _buries: FrozenSet[str] = field(default_factory=frozenset, repr=False)

    @property
    def upvotes(self) -> int:
        return len(self._ups)

    @property
    def buries(self) -> int:
        return len(self._buries)

    @property
    def score(self) -> int:
        return self.upvotes - self.buries

    @property
    def total_votes(self) -> int:
        return self.upvotes + self.buries


class Surface:
    """A curation surface with published thresholds and symmetric verbs."""

    def __init__(self, name: str = "surface", policy: Optional[Policy] = None) -> None:
        self.name = name
        self._policy = policy or Policy()
        self._items: Dict[int, Item] = {}
        self._next_id = 1

    # -- items ---------------------------------------------------------------

    def add_item(self, title: str, body: str = "") -> Item:
        if not title.strip():
            raise SurfaceError("an item needs a title")
        item = Item(id=self._next_id, title=title.strip(), body=body.strip())
        self._items[item.id] = item
        self._next_id += 1
        return item

    def get(self, item_id: int) -> Item:
        try:
            return self._items[item_id]
        except KeyError:
            raise SurfaceError(f"no item #{item_id}") from None

    # -- the two symmetric verbs ----------------------------------------------

    def _cast(self, item_id: int, voter: str, verb: str) -> Item:
        voter = voter.strip()
        if not voter:
            raise SurfaceError("a vote needs a voter")
        item = self.get(item_id)
        ups = set(item._ups)
        buries = set(item._buries)
        if verb == "up":
            if voter in ups:
                raise SurfaceError(f"{voter!r} already upvoted item #{item_id}")
            buries.discard(voter)
            ups.add(voter)
        elif verb == "bury":
            if voter in buries:
                raise SurfaceError(f"{voter!r} already buried item #{item_id}")
            ups.discard(voter)
            buries.add(voter)
        else:  # pragma: no cover - internal misuse
            raise SurfaceError(f"unknown verb {verb!r}")
        item._ups = frozenset(ups)
        item._buries = frozenset(buries)
        return item

    def upvote(self, item_id: int, voter: str) -> Item:
        """Promote. Same weight as a bury, counted in the open."""
        return self._cast(item_id, voter, "up")

    def bury(self, item_id: int, voter: str) -> Item:
        """Demote. A vote, not a flag — symmetric with upvote."""
        return self._cast(item_id, voter, "bury")

    def change_vote(self, item_id: int, voter: str, to: str) -> Item:
        """Honestly change your mind: 'up' or 'bury'. Replaces the old vote."""
        if to not in ("up", "bury"):
            raise SurfaceError("change_vote target must be 'up' or 'bury'")
        return self._cast(item_id, voter, to)

    def retract(self, item_id: int, voter: str) -> Item:
        """Take a vote back entirely."""
        voter = voter.strip()
        item = self.get(item_id)
        ups = set(item._ups)
        buries = set(item._buries)
        if voter not in ups and voter not in buries:
            raise SurfaceError(f"{voter!r} has no vote on item #{item_id}")
        ups.discard(voter)
        buries.discard(voter)
        item._ups = frozenset(ups)
        item._buries = frozenset(buries)
        return item

    # -- transparent curation ---------------------------------------------------

    def policy(self) -> Policy:
        return self._policy

    def set_policy(self, policy: Policy) -> None:
        self._policy = policy

    def standing(self, item_id: int) -> Dict[str, object]:
        """Raw counts, score, and tier — the whole truth about an item."""
        item = self.get(item_id)
        p = self._policy
        tier = "new"
        if item.total_votes >= p.quorum:
            if item.score <= p.bury_at:
                tier = "sunk"
            elif item.score >= p.promote_at:
                tier = "rising"
            elif item.buries > 0 and item.upvotes > 0:
                tier = "contested"
        return {
            "id": item.id,
            "title": item.title,
            "upvotes": item.upvotes,
            "buries": item.buries,
            "score": item.score,
            "total_votes": item.total_votes,
            "tier": tier,
        }

    def ranked(self, tier: Optional[str] = None) -> List[Dict[str, object]]:
        """All items by score, highest first. Filter by tier if asked."""
        standings = [self.standing(i) for i in self._items]
        standings.sort(key=lambda s: (-s["score"], s["id"]))
        if tier is not None:
            standings = [s for s in standings if s["tier"] == tier]
        return standings

    def __len__(self) -> int:
        return len(self._items)
