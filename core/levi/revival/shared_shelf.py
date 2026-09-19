"""Shared-items shelf: a public page of what one reader shared, note attached.

Studied from: fallen-platforms-hunt-20260916/report.md (item 1: shared shelf)

The mechanism: every item a reader shares appears on a public shelf page
for that reader. Each shared item carries the sharer's optional note —
the note is part of the item's public record, not a side channel. The
shelf is the reader's publishing surface: newest shares first, paged,
with per-reader ownership.

Honest limits: pure in-memory store; no auth, no feed fetching, no HTML
rendering — it models the data structure and page semantics, not a web
service.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterator, List


ORIGIN = "levi-revival/shared-shelf"


@dataclass
class SharedItem:
    item_id: str
    reader: str
    url: str
    title: str
    sharer_note: str = ""
    read: bool = False
    shared_order: int = 0


class SharedShelf:
    """One reader's public shelf of shared items."""

    def __init__(self, reader: str, page_size: int = 20) -> None:
        if not reader or not reader.strip():
            raise ValueError("reader must be non-empty")
        self.reader = reader
        self.page_size = page_size
        self._items: Dict[str, SharedItem] = {}
        self._counter = 0

    # ------------------------------------------------------------------
    # Sharing
    # ------------------------------------------------------------------
    def share(self, url: str, title: str, note: str = "") -> SharedItem:
        if not url or not url.strip():
            raise ValueError("url must be non-empty")
        if not title or not title.strip():
            raise ValueError("title must be non-empty")
        self._counter += 1
        item = SharedItem(
            item_id=f"sh-{self._counter}",
            reader=self.reader,
            url=url,
            title=title,
            sharer_note=note,
            shared_order=self._counter,
        )
        self._items[item.item_id] = item
        return item

    def remove(self, item_id: str) -> None:
        if item_id not in self._items:
            raise KeyError(f"unknown shared item: {item_id!r}")
        del self._items[item_id]

    def mark_read(self, item_id: str, read: bool = True) -> None:
        item = self._get(item_id)
        item.read = read

    # ------------------------------------------------------------------
    # The shelf page
    # ------------------------------------------------------------------
    def page(self, number: int = 1) -> List[SharedItem]:
        """Public shelf page, newest shares first."""
        if number < 1:
            raise ValueError("page number must be >= 1")
        ordered = sorted(
            self._items.values(), key=lambda i: i.shared_order, reverse=True
        )
        start = (number - 1) * self.page_size
        return ordered[start : start + self.page_size]

    def with_notes(self) -> List[SharedItem]:
        """Only items that carry a sharer note."""
        return [i for i in self._items.values() if i.sharer_note.strip()]

    def search(self, query: str) -> List[SharedItem]:
        q = query.strip().lower()
        return [
            i
            for i in self._items.values()
            if q in i.title.lower() or q in i.sharer_note.lower()
        ]

    def unread_count(self) -> int:
        return sum(1 for i in self._items.values() if not i.read)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[SharedItem]:
        return iter(
            sorted(self._items.values(), key=lambda i: i.shared_order, reverse=True)
        )

    def _get(self, item_id: str) -> SharedItem:
        try:
            return self._items[item_id]
        except KeyError:
            raise KeyError(f"unknown shared item: {item_id!r}") from None
