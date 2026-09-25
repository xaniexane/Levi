"""Tickler file: the 43-folder future-attention queue, as a resurfacing engine.

Origin: a 19th-century office method (in use by 1888; popularized much later
by GTD's David Allen — credit the 19th-century office, not the 2001 book):
31 day folders + 12 month folders, cycled perpetually. Anything needing
future attention is filed in the folder of the day it becomes relevant;
each morning you open today's folder.

What it is in LEVI: a resurfacing engine with superpowers. Filed items carry
their full material (title, body, the reason you filed them) — not just a
ping — so ``open_today`` returns the complete context bundle. The classic
maintenance ritual is preserved: on the 1st of the month,
``distribute_month`` empties that month's folder into the day folders.

Honesty label: LOAD-BEARING — the mechanism (decouple capture from the
revisit trigger; resurface the artifact, not a ping) transfers nearly as-is.

Deny-closed inputs: empty titles, malformed dates, filing in the past,
unknown item ids, and folder operations are all rejected with ValueError.
Fail-safe surfacing: any item whose revisit date has passed is reported by
``open_today`` even if its folder was never distributed — nothing is
silently lost.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Optional, Union

__all__ = [
    "TicklerItem",
    "TicklerFile",
    "DateLike",
    "default_store_path",
]

DateLike = Union[date, str]


def _parse_date(value: DateLike, field_name: str = "date") -> date:
    """Strictly parse a date or ISO 'YYYY-MM-DD' string; reject everything else."""
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            y, m, d = value.split("-")
            return date(int(y), int(m), int(d))
        except (ValueError, AttributeError):
            pass
    raise ValueError(
        f"{field_name}: expected datetime.date or 'YYYY-MM-DD', got {value!r}"
    )


def default_store_path() -> Path:
    """Default on-disk store (owner-only dir under the user's home)."""
    return Path(os.path.expanduser("~")) / ".levi" / "methods" / "tickler.json"


@dataclass
class TicklerItem:
    """One filed item: the artifact plus why it should resurface."""

    id: str
    title: str
    revisit: str  # ISO date the item becomes relevant
    filed_on: str  # ISO date it was filed
    folder: str  # "day:DD" or "month:MM"
    body: str = ""
    reason: str = ""
    overdue: bool = False  # set transiently by open_today; persisted as filed


class TicklerFile:
    """The 43 folders: 31 day slots + 12 month slots, cycling forever."""

    def __init__(
        self, path: Optional[Union[str, Path]] = None, today: Optional[DateLike] = None
    ):
        self._path = Path(path) if path is not None else None
        self._today = _parse_date(today) if today is not None else None
        self._items: dict[str, TicklerItem] = {}
        if self._path is not None and self._path.exists():
            self._load()

    # -- time -----------------------------------------------------------
    def _now(self) -> date:
        return self._today if self._today is not None else date.today()

    # -- persistence ----------------------------------------------------
    def _load(self) -> None:
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError(
                f"tickler store is corrupt: expected a list in {self._path}"
            )
        for entry in raw:
            item = TicklerItem(
                **{
                    k: entry[k]
                    for k in ("id", "title", "revisit", "filed_on", "folder")
                }
            )
            item.body = entry.get("body", "")
            item.reason = entry.get("reason", "")
            self._items[item.id] = item

    def save(self) -> None:
        if self._path is None:
            raise ValueError(
                "no store path configured; construct with path= to persist"
            )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = []
        for item in self._items.values():
            d = asdict(item)
            d.pop("overdue", None)
            payload.append(d)
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # -- filing ----------------------------------------------------------
    @staticmethod
    def _folder_for(filed_on: date, revisit: date) -> str:
        if revisit.year == filed_on.year and revisit.month == filed_on.month:
            return f"day:{revisit.day:02d}"
        return f"month:{revisit.month:02d}"

    def file(
        self, title: str, revisit: DateLike, body: str = "", reason: str = ""
    ) -> TicklerItem:
        """File an item to resurface on ``revisit``. Returns the stored item."""
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title must be a non-empty string")
        rev = _parse_date(revisit, "revisit")
        filed = self._now()
        if rev < filed:
            raise ValueError(f"cannot file in the past: revisit {rev} < today {filed}")
        item = TicklerItem(
            id=uuid.uuid4().hex[:12],
            title=title.strip(),
            revisit=rev.isoformat(),
            filed_on=filed.isoformat(),
            folder=self._folder_for(filed, rev),
            body=body or "",
            reason=reason or "",
        )
        self._items[item.id] = item
        return item

    def get(self, item_id: str) -> TicklerItem:
        try:
            return self._items[item_id]
        except KeyError:
            raise ValueError(f"unknown tickler item: {item_id!r}") from None

    def dismiss(self, item_id: str) -> TicklerItem:
        """Remove a filed item (it was handled). Returns the removed item."""
        item = self.get(item_id)
        del self._items[item_id]
        return item

    def tickle_again(self, item_id: str, new_revisit: DateLike) -> TicklerItem:
        """Re-file an item for a later date (the classic 'tickle it forward')."""
        item = self.get(item_id)
        rev = _parse_date(new_revisit, "new_revisit")
        filed = self._now()
        if rev < filed:
            raise ValueError(f"cannot re-file in the past: {rev} < {filed}")
        item.revisit = rev.isoformat()
        item.folder = self._folder_for(filed, rev)
        item.overdue = False
        return item

    # -- the morning ritual ----------------------------------------------
    def distribute_month(self, on_date: DateLike) -> int:
        """On the 1st: move this month's folder contents into day folders.

        Only items whose revisit actually falls in the given month are moved;
        anything else is left alone (defensive). Returns the count moved.
        """
        on = _parse_date(on_date, "on_date")
        moved = 0
        for item in self._items.values():
            rev = _parse_date(item.revisit, "revisit")
            if item.folder == f"month:{on.month:02d}" and (rev.year, rev.month) == (
                on.year,
                on.month,
            ):
                item.folder = f"day:{rev.day:02d}"
                moved += 1
        return moved

    def open_today(self, on_date: DateLike) -> list[TicklerItem]:
        """Open today's folder: due items with their full context bundles.

        Fail-safe: any item whose revisit date has passed is surfaced even if
        its folder was never distributed (flagged ``overdue=True``).
        """
        on = _parse_date(on_date, "on_date")
        due: list[TicklerItem] = []
        for item in self._items.values():
            rev = _parse_date(item.revisit, "revisit")
            if rev <= on:
                item.overdue = rev < on
                due.append(item)
        due.sort(key=lambda i: (i.revisit, i.title))
        return due

    def pending(self) -> list[TicklerItem]:
        """All filed items, soonest first."""
        return sorted(self._items.values(), key=lambda i: (i.revisit, i.title))
