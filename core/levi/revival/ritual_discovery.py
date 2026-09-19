"""Ritualized local discovery — a weekly rediscovery over your own library.

Studied from: giant-patterns-hunt-20260916-0016/report.md [Additions 19].

The mechanism under study: a Discover-Weekly-style ritual that runs over
the user's OWN library and corpus — surfacing things they own but have
not touched in a while — with no engagement steering. This is an original,
from-scratch implementation for LEVI. Selection is deterministic per
week-id (seeded hashing, so the same week always yields the same ritual),
weighted toward long-unsurfaced items and toward kinds the user has not
seen recently. There is no popularity signal, no click optimization, no
external catalog: the pool is strictly what the user put in.

Public surface:
- ``Library``: add_item / remove_item / ritual(week_id, count).
- ``RitualPick``: the chosen item plus the plain-language reason it was
  picked (the reason is always about the user's own history, never about
  "engagement").

stdlib-only. No network. Deterministic: same library + week_id → same picks.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/ritual-discovery"


@dataclass
class LibraryItem:
    item_id: str
    title: str
    kind: str = "note"
    tags: List[str] = field(default_factory=list)
    added_week: int = 0
    last_surfaced_week: Optional[int] = None
    surfaced_count: int = 0


@dataclass
class RitualPick:
    item: LibraryItem
    reason: str


def _week_seed(week_id: str, item_id: str) -> int:
    digest = hashlib.sha256(f"{week_id}|{item_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


class Library:
    """The user's own library; rituals surface parts of it on a cadence."""

    def __init__(self) -> None:
        self._items: Dict[str, LibraryItem] = {}
        self._week = 0

    def add_item(
        self,
        item_id: str,
        title: str,
        kind: str = "note",
        tags: Optional[List[str]] = None,
    ) -> LibraryItem:
        if not item_id or not title:
            raise ValueError("item_id and title must not be empty")
        if item_id in self._items:
            raise ValueError(f"item {item_id!r} already in library")
        item = LibraryItem(
            item_id, title, kind, list(tags or []), added_week=self._week
        )
        self._items[item_id] = item
        return item

    def remove_item(self, item_id: str) -> bool:
        return self._items.pop(item_id, None) is not None

    def size(self) -> int:
        return len(self._items)

    def _weight(self, item: LibraryItem, week_id: str, week_num: int) -> float:
        # Long-unsurfaced weighs most; never-surfaced gets a novelty lift.
        if item.last_surfaced_week is None:
            recency = float(week_num - item.added_week + 2)
            novelty = 1.5
        else:
            recency = float(week_num - item.last_surfaced_week + 1)
            novelty = 1.0
        # Small deterministic jitter so ties break stably per week.
        jitter = (_week_seed(week_id, item.item_id) % 1000) / 1000.0
        return recency * novelty + jitter * 0.5 - item.surfaced_count * 0.25

    def ritual(self, week_id: str, count: int = 5) -> List[RitualPick]:
        """Pick this week's rediscoveries. Deterministic per week_id."""
        if count < 1:
            raise ValueError("count must be >= 1")
        if not self._items:
            return []
        week_num = self._week
        ranked = sorted(
            self._items.values(),
            key=lambda it: self._weight(it, week_id, week_num),
            reverse=True,
        )
        # Spread across kinds: prefer kinds not already represented.
        # Spread across kinds: first pass takes one per kind in weight
        # order, second pass fills the rest purely by weight.
        picks: List[LibraryItem] = []
        seen_kinds: set = set()
        for item in ranked:
            if len(picks) >= count:
                break
            if item.kind not in seen_kinds:
                picks.append(item)
                seen_kinds.add(item.kind)
        for item in ranked:
            if len(picks) >= count:
                break
            if item not in picks:
                picks.append(item)
        result: List[RitualPick] = []
        for item in picks:
            if item.last_surfaced_week is None:
                reason = f"new to your ritual — added {item.title!r} has never been resurfaced"
            else:
                gap = week_num - item.last_surfaced_week
                reason = (
                    f"haven't revisited {item.title!r} in {gap} week(s); "
                    f"it surfaced {item.surfaced_count} time(s) before"
                )
            item.last_surfaced_week = week_num
            item.surfaced_count += 1
            result.append(RitualPick(item, reason))
        self._week += 1
        return result
