"""Starred canon: the keeper's private list of starred items inside the reader.

Studied from: fallen-platforms-hunt-20260916/report.md (item 1: shared shelf)

The mechanism: starring is private, not social. A star marks an item as
worth keeping — the reader's canon, the set of things they would defend.
Each star carries the reader's own keeper note (why it was kept) and
optional tags. Order is by star time; unstar is a deliberate act that
removes without ceremony.

Honest limits: single-reader canon, in-memory only; no sync, no dedup
across readers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterator, List


ORIGIN = "levi-revival/starred-canon"


@dataclass
class Star:
    item_id: str
    url: str
    title: str
    keeper_note: str = ""
    tags: List[str] = field(default_factory=list)
    star_order: int = 0


class StarredCanon:
    """One reader's private starred canon."""

    def __init__(self) -> None:
        self._stars: Dict[str, Star] = {}
        self._counter = 0

    # ------------------------------------------------------------------
    # Keeping
    # ------------------------------------------------------------------
    def star(
        self, url: str, title: str, keeper_note: str = "", tags: List[str] | None = None
    ) -> Star:
        if not url or not url.strip():
            raise ValueError("url must be non-empty")
        if not title or not title.strip():
            raise ValueError("title must be non-empty")
        self._counter += 1
        star = Star(
            item_id=f"star-{self._counter}",
            url=url,
            title=title,
            keeper_note=keeper_note,
            tags=list(tags or []),
            star_order=self._counter,
        )
        self._stars[star.item_id] = star
        return star

    def unstar(self, item_id: str) -> None:
        if item_id not in self._stars:
            raise KeyError(f"unknown starred item: {item_id!r}")
        del self._stars[item_id]

    def annotate(self, item_id: str, keeper_note: str) -> Star:
        star = self._get(item_id)
        star.keeper_note = keeper_note
        return star

    def tag(self, item_id: str, tag: str) -> Star:
        star = self._get(item_id)
        if tag and tag not in star.tags:
            star.tags.append(tag)
        return star

    # ------------------------------------------------------------------
    # Reading the canon
    # ------------------------------------------------------------------
    def canon(self) -> List[Star]:
        """The full canon, earliest-kept first — a keeper's timeline."""
        return sorted(self._stars.values(), key=lambda s: s.star_order)

    def by_tag(self, tag: str) -> List[Star]:
        return [s for s in self.canon() if tag in s.tags]

    def keepers_notes(self) -> List[Star]:
        return [s for s in self.canon() if s.keeper_note.strip()]

    def __len__(self) -> int:
        return len(self._stars)

    def __iter__(self) -> Iterator[Star]:
        return iter(self.canon())

    def _get(self, item_id: str) -> Star:
        try:
            return self._stars[item_id]
        except KeyError:
            raise KeyError(f"unknown starred item: {item_id!r}") from None
