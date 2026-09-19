"""Symmetric downvote: the bury is first-class; the front page is net sentiment.

Studied from: fallen-platforms-hunt-20260916/report.md (item 3: buried items)

The mechanism: every item carries two public counters — diggs (up) and
buries (down). Ranking is by net score (diggs minus buries), so burying
moves an item down the front page without ever deleting it. Bury is a
symmetric citizen: every voter action is visible as a count, and bury can
be undone (unbury) exactly like diggs can be undigged. Buried items rank
down, never vanish; nothing disappears by vote.

Honest limits: one vote per voter per direction is enforced in memory;
no identity layer beyond a voter key string.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set


ORIGIN = "levi-revival/symmetric-downvote"


@dataclass
class RankedItem:
    item_id: str
    title: str
    diggers: Set[str] = field(default_factory=set)
    buriers: Set[str] = field(default_factory=set)

    @property
    def diggs(self) -> int:
        return len(self.diggers)

    @property
    def buries(self) -> int:
        return len(self.buriers)

    @property
    def score(self) -> int:
        return self.diggs - self.buries

    @property
    def buried(self) -> bool:
        return self.score < 0


class FrontPage:
    """A front page ranked by net sentiment: digg minus bury."""

    def __init__(self) -> None:
        self._items: Dict[str, RankedItem] = {}
        self._counter = 0

    # ------------------------------------------------------------------
    # Submission and voting
    # ------------------------------------------------------------------
    def submit(self, title: str) -> RankedItem:
        if not title or not title.strip():
            raise ValueError("title must be non-empty")
        self._counter += 1
        item = RankedItem(item_id=f"item-{self._counter}", title=title)
        self._items[item.item_id] = item
        return item

    def digg(self, item_id: str, voter: str) -> RankedItem:
        return self._vote(item_id, voter, up=True)

    def bury(self, item_id: str, voter: str) -> RankedItem:
        return self._vote(item_id, voter, up=False)

    def undigg(self, item_id: str, voter: str) -> RankedItem:
        item = self._get(item_id)
        item.diggers.discard(voter)
        return item

    def unbury(self, item_id: str, voter: str) -> RankedItem:
        item = self._get(item_id)
        item.buriers.discard(voter)
        return item

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------
    def front_page(self) -> List[RankedItem]:
        """Everything, ordered by net score — buried items rank down,
        never vanish."""
        return sorted(
            self._items.values(),
            key=lambda i: (i.score, -int(i.item_id.split("-")[1])),
            reverse=True,
        )

    def buried_items(self) -> List[RankedItem]:
        return [i for i in self.front_page() if i.buried]

    def controversial(self) -> List[RankedItem]:
        """High total votes but near-zero net — fought-over items."""

        def heat(item: RankedItem) -> int:
            return item.diggs + item.buries - abs(item.score)

        return sorted(self._items.values(), key=heat, reverse=True)

    def __len__(self) -> int:
        return len(self._items)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _vote(self, item_id: str, voter: str, up: bool) -> RankedItem:
        if not voter or not voter.strip():
            raise ValueError("voter must be non-empty")
        item = self._get(item_id)
        if up:
            item.buriers.discard(voter)
            item.diggers.add(voter)
        else:
            item.diggers.discard(voter)
            item.buriers.add(voter)
        return item

    def _get(self, item_id: str) -> RankedItem:
        try:
            return self._items[item_id]
        except KeyError:
            raise KeyError(f"unknown item: {item_id!r}") from None
