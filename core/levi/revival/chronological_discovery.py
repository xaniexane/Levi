"""User-tunable chronological discovery: no ranked feed, by default or by design.

Studied from: github-pattern-hunt-20260916-0018/report.md [Ranked additions 8]

The mechanism: ``Discovery`` holds items (repos, people, notes — anything
discoverable) with timestamps. ``timeline`` returns them in strict
reverse-chronological order; ``filtered`` narrows by kind, author, tag, or
time window without reordering. Ranking exists, but it is strictly
opt-in: the feed has no ranking function until the user supplies one via
``enable_ranking`` — their own script, their own weights — and
``ranked`` refuses to run until then. ``disable_ranking`` returns the
feed to chronology. The default is the promise: newest first, nobody's
thumb on the scale.

Design notes, kept honest:

- Chronology is by ``at`` timestamps, which are caller-supplied. The feed
  sorts what it is given; it cannot verify that a timestamp is truthful.
- A user-supplied ranking function is arbitrary code the user chose to
  run. The module documents its contract (item -> score, higher first,
  stable for ties) and applies nothing by default.
- Filters are conjunctive (AND): an item must satisfy every given
  predicate. ``filtered`` never reorders; it only removes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Sequence

ORIGIN = "levi-revival/chronological-discovery"


@dataclass
class Item:
    """One discoverable thing: who made it, what it is, when, and its tags."""

    id: str
    kind: str  # e.g. "repo" | "person" | "note"
    author: str
    title: str
    at: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    meta: Dict = field(default_factory=dict)


class Discovery:
    """The feed with no ranked feed: chronology first, ranking strictly opt-in."""

    def __init__(self):
        self._items: Dict[str, Item] = {}
        self._ranking: Callable[[Item], float] | None = None
        self._ranking_name: str = ""

    # -- intake ------------------------------------------------------------
    def add(self, item: Item) -> Item:
        self._items[item.id] = item
        return item

    def remove(self, item_id: str) -> bool:
        return self._items.pop(item_id, None) is not None

    def count(self) -> int:
        return len(self._items)

    # -- chronology: the default -------------------------------------------
    def timeline(self) -> List[Item]:
        """Strict reverse-chronological order. No ranking, ever, here."""
        return sorted(self._items.values(), key=lambda i: (i.at, i.id), reverse=True)

    def filtered(
        self,
        kinds: Sequence[str] | None = None,
        authors: Sequence[str] | None = None,
        tags: Sequence[str] | None = None,
        after: float | None = None,
        before: float | None = None,
    ) -> List[Item]:
        """Conjunctive filter over the timeline; order untouched."""
        out = []
        for item in self.timeline():
            if kinds is not None and item.kind not in kinds:
                continue
            if authors is not None and item.author not in authors:
                continue
            if tags is not None and not set(tags) <= set(item.tags):
                continue
            if after is not None and item.at <= after:
                continue
            if before is not None and item.at >= before:
                continue
            out.append(item)
        return out

    # -- ranking: strictly opt-in and user-scriptable ------------------------
    @property
    def ranking_enabled(self) -> bool:
        return self._ranking is not None

    def enable_ranking(
        self, fn: Callable[[Item], float], name: str = "user-script"
    ) -> None:
        """Install the user's own ranking script. Nothing ships with one."""
        if not callable(fn):
            raise TypeError("ranking must be a callable: item -> score")
        self._ranking = fn
        self._ranking_name = name

    def disable_ranking(self) -> None:
        """Back to chronology."""
        self._ranking = None
        self._ranking_name = ""

    def ranked(self) -> List[Item]:
        """Apply the user's ranking script. Refuses until one is installed.

        Contract for the script: item -> score (higher sorts first);
        ties keep chronological order (stable sort).
        """
        if self._ranking is None:
            raise RuntimeError(
                "no ranking installed: this feed is chronological by default; "
                "call enable_ranking with your own script to opt in"
            )
        fn = self._ranking
        return sorted(
            self.timeline(), key=lambda i: fn(i), reverse=True
        )  # stable: timeline order breaks ties

    def ranking_name(self) -> str:
        return self._ranking_name
