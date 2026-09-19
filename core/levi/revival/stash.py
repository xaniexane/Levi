"""Stash: save pages now, search them later — a keep-for-later drawer with recall.

Studied from: desktop-casualties-20260916/report.md (item 1: Opera)

The mechanism: a saved page is a snapshot (url, title, captured text,
tags) plus a save timestamp. Saving is cheap and instant; the real
value is recall: full-text search across titles and captured text,
filterable by tag. Snapshots are static — the drawer keeps what you saw,
not a live page.

Honest limits: in-memory store; captured text is supplied by the caller
(no fetching); search is plain substring matching, not an index.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterator, List


ORIGIN = "levi-revival/stash"


@dataclass
class StashedPage:
    stash_id: str
    url: str
    title: str
    snapshot: str = ""
    tags: List[str] = field(default_factory=list)
    save_order: int = 0


class Stash:
    """A keep-for-later drawer of saved page snapshots."""

    def __init__(self) -> None:
        self._pages: Dict[str, StashedPage] = {}
        self._counter = 0

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------
    def save(
        self, url: str, title: str, snapshot: str = "", tags: List[str] | None = None
    ) -> StashedPage:
        if not url or not url.strip():
            raise ValueError("url must be non-empty")
        if not title or not title.strip():
            raise ValueError("title must be non-empty")
        self._counter += 1
        page = StashedPage(
            stash_id=f"stash-{self._counter}",
            url=url,
            title=title,
            snapshot=snapshot,
            tags=list(tags or []),
            save_order=self._counter,
        )
        self._pages[page.stash_id] = page
        return page

    def discard(self, stash_id: str) -> None:
        if stash_id not in self._pages:
            raise KeyError(f"unknown stashed page: {stash_id!r}")
        del self._pages[stash_id]

    def retag(self, stash_id: str, tags: List[str]) -> StashedPage:
        page = self._get(stash_id)
        page.tags = list(tags)
        return page

    # ------------------------------------------------------------------
    # Recall
    # ------------------------------------------------------------------
    def search(self, query: str) -> List[StashedPage]:
        """Substring search across titles and snapshots, newest first."""
        q = query.strip().lower()
        hits = [
            p
            for p in self._pages.values()
            if q in p.title.lower() or q in p.snapshot.lower()
        ]
        return sorted(hits, key=lambda p: p.save_order, reverse=True)

    def by_tag(self, tag: str) -> List[StashedPage]:
        return sorted(
            (p for p in self._pages.values() if tag in p.tags),
            key=lambda p: p.save_order,
            reverse=True,
        )

    def newest(self, limit: int = 10) -> List[StashedPage]:
        ordered = sorted(self._pages.values(), key=lambda p: p.save_order, reverse=True)
        return ordered[:limit]

    def tags(self) -> List[str]:
        seen: List[str] = []
        for page in self._pages.values():
            for tag in page.tags:
                if tag not in seen:
                    seen.append(tag)
        return seen

    def __len__(self) -> int:
        return len(self._pages)

    def __iter__(self) -> Iterator[StashedPage]:
        return iter(
            sorted(self._pages.values(), key=lambda p: p.save_order, reverse=True)
        )

    def _get(self, stash_id: str) -> StashedPage:
        try:
            return self._pages[stash_id]
        except KeyError:
            raise KeyError(f"unknown stashed page: {stash_id!r}") from None
