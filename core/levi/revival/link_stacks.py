"""Link stacks — curated lists built on top of a bookmark pool.

Studied from: fallen-platforms-evening-20260916, report.md [1. Delicious]
(Stacks, AVOS, 2011).

The mechanism, functionally: curation is a second, deliberate layer above
the folksonomy pool. A stack is an ordered list of links with a curator's
voice — title, blurb per link, explicit ordering, publish/unpublish —
assembled by pulling entries out of the shared pool. Forking lets a
reader diverge a stack into their own without harming the original.

This module is a software analog of that pattern: ``LinkStack`` (ordered
entries, reorder/add/remove, publish state, fork) and ``StackLibrary``
(pull from a pool by tag query, listing published stacks, usage-ranked
ordering). It imports ``folksonomy.Folksonomy`` only as the pool; it
never depends on network access.

Honesty: ranking is by inclusion counts, a popularity heuristic, not a
quality judgment; blurbs are the curator's own words, never auto-written.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .folksonomy import Folksonomy, Bookmark

ORIGIN = "levi-revival/link-stacks"


@dataclass
class StackEntry:
    """One curated link: the curator's pick, in their own words."""

    bookmark_id: str
    url: str
    title: str
    blurb: str = ""
    added_at: float = field(default_factory=time.time)


class LinkStack:
    """An ordered, curated list of links with a curator's voice."""

    _seq = 0

    def __init__(self, name: str, curator: str, description: str = "") -> None:
        LinkStack._seq += 1
        self.id = f"stack{LinkStack._seq:04d}"
        self.name = name
        self.curator = curator
        self.description = description
        self.entries: List[StackEntry] = []
        self.published = False
        self.created_at = time.time()
        self.forked_from: Optional[str] = None

    # -- building the curation ------------------------------------------

    def add(self, entry: StackEntry, position: Optional[int] = None) -> StackEntry:
        """Place a link in the stack; position defaults to the end."""
        if any(e.bookmark_id == entry.bookmark_id for e in self.entries):
            raise ValueError(f"{entry.bookmark_id} already in stack {self.id}")
        if position is None:
            self.entries.append(entry)
        else:
            self.entries.insert(max(0, min(position, len(self.entries))), entry)
        return entry

    def add_bookmark(
        self, bm: Bookmark, blurb: str = "", position: Optional[int] = None
    ) -> StackEntry:
        return self.add(
            StackEntry(bookmark_id=bm.id, url=bm.url, title=bm.title, blurb=blurb),
            position,
        )

    def remove(self, bookmark_id: str) -> bool:
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.bookmark_id != bookmark_id]
        return len(self.entries) < before

    def move(self, bookmark_id: str, position: int) -> bool:
        """Reorder: the ordering IS the curation."""
        idx = next(
            (i for i, e in enumerate(self.entries) if e.bookmark_id == bookmark_id),
            None,
        )
        if idx is None:
            return False
        entry = self.entries.pop(idx)
        self.entries.insert(max(0, min(position, len(self.entries))), entry)
        return True

    # -- publishing & forking --------------------------------------------

    def publish(self) -> None:
        self.published = True

    def unpublish(self) -> None:
        self.published = False

    def fork(self, curator: str, name: Optional[str] = None) -> "LinkStack":
        """Diverge a copy: forks never touch the original."""
        child = LinkStack(name or f"{self.name} (forked)", curator, self.description)
        child.entries = [
            StackEntry(e.bookmark_id, e.url, e.title, e.blurb, e.added_at)
            for e in self.entries
        ]
        child.forked_from = self.id
        return child

    def __len__(self) -> int:
        return len(self.entries)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"LinkStack({self.id}, {self.name!r}, {len(self)} entries)"


class StackLibrary:
    """The shared shelf: published stacks and pool-sourced building."""

    def __init__(self) -> None:
        self.stacks: Dict[str, LinkStack] = {}
        self.inclusion_counts: Dict[str, int] = {}

    def register(self, stack: LinkStack) -> LinkStack:
        self.stacks[stack.id] = stack
        return stack

    def published(self) -> List[LinkStack]:
        return [s for s in self.stacks.values() if s.published]

    def from_pool(
        self,
        pool: Folksonomy,
        name: str,
        curator: str,
        tags: Iterable[str],
        blurb_template: str = "",
        limit: int = 20,
    ) -> LinkStack:
        """Draft a stack by pulling pool bookmarks matching ``tags``.

        The pool is the raw material; the curator still writes blurbs and
        sets the order before publishing.
        """
        stack = LinkStack(name, curator)
        for bm in pool.search(tags, match="any", limit=limit):
            try:
                stack.add_bookmark(bm, blurb=blurb_template)
            except ValueError:
                continue
        return stack

    def note_inclusion(self, stack: LinkStack) -> None:
        for e in stack.entries:
            self.inclusion_counts[e.bookmark_id] = (
                self.inclusion_counts.get(e.bookmark_id, 0) + 1
            )

    def most_included(self, limit: int = 10) -> List[tuple]:
        """Links appearing across many stacks — a use heuristic, not a
        quality verdict."""
        return sorted(
            self.inclusion_counts.items(), key=lambda kv: kv[1], reverse=True
        )[:limit]
