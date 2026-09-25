"""The perpetual future-attention queue: 31 daily folders + 12 monthly folders.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #15)

The load-bearing mechanism: decouple *capture* from *scheduling*. You
don't need a date — you need a *revisit trigger*. File anything for a
future date; each day, :meth:`TicklerFile.today` opens that day's folder
and resurfaces the full material with its context (why you filed it,
what you attached), not just a ping.

The 43 folders rotate forever: items filed within the next 31 days go
into daily folders; anything further out rests in a monthly folder and
rolls into daily folders when its month arrives (:meth:`advance`
handles the rotation, including skipped days — missed day-folders
resurface as overdue, nothing is silently dropped).

This is an original, from-scratch LEVI implementation — no historical
code is used or copied. Stdlib only, no network.

Honesty: the mechanism revived is the perpetual 43-folder rotation with
context-carrying resurfacing. Not revived: fixed-time nagging — the
tickler resurfaces *material*, and it waits for you to open the folder.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path


ORIGIN = "levi-revival/tickler"

_DAILY_WINDOW = 31  # days filed ahead go straight into daily folders


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TicklerError(Exception):
    """Base class for tickler failures."""


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


@dataclass
class TicklerItem:
    """One filed item: the material, its revisit date, and its context."""

    item_id: str
    text: str
    for_date: str  # ISO date
    context: str = ""
    filed_on: str = field(default_factory=lambda: date.today().isoformat())

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "text": self.text,
            "for_date": self.for_date,
            "context": self.context,
            "filed_on": self.filed_on,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TicklerItem":
        return cls(
            data["item_id"],
            data["text"],
            data["for_date"],
            data.get("context", ""),
            data.get("filed_on", ""),
        )


# ---------------------------------------------------------------------------
# The 43 folders
# ---------------------------------------------------------------------------


class TicklerFile:
    """A rotating file of 31 daily + 12 monthly folders.

    ``today`` is virtual and settable (defaults to the real date) so the
    rotation is testable and resumable.
    """

    def __init__(self, path: str | Path | None = None, today: date | None = None):
        self.path = Path(path) if path else None
        self.today_date: date = today or date.today()
        self._daily: dict[str, list[TicklerItem]] = {}  # ISO date -> items
        self._monthly: dict[str, list[TicklerItem]] = {}  # YYYY-MM -> items
        self._counter = 0
        if self.path is not None:
            self._load()

    # -- persistence ------------------------------------------------------
    def _file(self) -> Path:
        assert self.path is not None
        return self.path / "tickler.json"

    def _load(self) -> None:
        f = self._file()
        if not f.exists():
            return
        data = json.loads(f.read_text(encoding="utf-8"))
        self.today_date = date.fromisoformat(
            data.get("today", self.today_date.isoformat())
        )
        self._counter = int(data.get("counter", 0))
        self._daily = {
            k: [TicklerItem.from_dict(d) for d in v]
            for k, v in data.get("daily", {}).items()
        }
        self._monthly = {
            k: [TicklerItem.from_dict(d) for d in v]
            for k, v in data.get("monthly", {}).items()
        }

    def save(self) -> Path:
        """Persist the file. Only meaningful when constructed with a path."""
        if self.path is None:
            raise TicklerError("no path: this file is in-memory only")
        self.path.mkdir(parents=True, exist_ok=True)
        target = self._file()
        tmp = target.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "today": self.today_date.isoformat(),
                    "counter": self._counter,
                    "daily": {
                        k: [i.to_dict() for i in v] for k, v in self._daily.items()
                    },
                    "monthly": {
                        k: [i.to_dict() for i in v] for k, v in self._monthly.items()
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        tmp.replace(target)
        return target

    # -- filing ---------------------------------------------------------------
    def file(self, text: str, for_date: date, context: str = "") -> TicklerItem:
        """File an item for a future date. Within the daily window it goes
        straight into a day folder; further out it rests in the monthly
        folder until its month arrives."""
        if not text or not text.strip():
            raise ValueError("text must be non-empty")
        if for_date < self.today_date:
            raise ValueError("cannot file for a past date — use today or later")
        self._counter += 1
        item = TicklerItem(
            item_id=f"t{self._counter}",
            text=text.strip(),
            for_date=for_date.isoformat(),
            context=context,
            filed_on=self.today_date.isoformat(),
        )
        if (for_date - self.today_date).days <= _DAILY_WINDOW:
            self._daily.setdefault(item.for_date, []).append(item)
        else:
            month = for_date.strftime("%Y-%m")
            self._monthly.setdefault(month, []).append(item)
        return item

    # -- the daily opening -------------------------------------------------------
    def peek_today(self) -> list[dict]:
        """Look inside today's folder (and any missed day-folders) without
        emptying them."""
        return self._collect_due(clear=False)

    def today(self) -> list[dict]:
        """Open today's folder: resurface every due item with its full
        context, then empty the folder. Missed day-folders come up marked
        overdue — nothing is silently dropped."""
        return self._collect_due(clear=True)

    def _collect_due(self, clear: bool) -> list[dict]:
        due = []
        for folder in sorted(self._daily):
            if folder <= self.today_date.isoformat():
                for item in self._daily[folder]:
                    due.append(
                        {
                            "item_id": item.item_id,
                            "text": item.text,
                            "context": item.context,
                            "filed_on": item.filed_on,
                            "folder": folder,
                            "overdue": folder < self.today_date.isoformat(),
                        }
                    )
                if clear:
                    del self._daily[folder]
        return due

    # -- the rotation -------------------------------------------------------------
    def advance(self, days: int = 1) -> date:
        """Move the tickler forward. Monthly folders roll their items into
        daily folders as their month arrives; the rotation never ends."""
        if days < 0:
            raise ValueError("advance moves forward only")
        for _ in range(days):
            self.today_date += timedelta(days=1)
            self._roll_month()
        return self.today_date

    def _roll_month(self) -> None:
        """A new month has arrived: its folder's items move into day
        folders (or stay if still beyond the daily window — the check is
        per item, not per folder)."""
        month = self.today_date.strftime("%Y-%m")
        items = self._monthly.pop(month, [])
        for item in items:
            target = date.fromisoformat(item.for_date)
            if (target - self.today_date).days <= _DAILY_WINDOW:
                self._daily.setdefault(item.for_date, []).append(item)
            else:  # pragma: no cover - defensive; filing routes these already
                self._monthly.setdefault(month, []).append(item)

    def set_today(self, today: date) -> None:
        """Reset the virtual date (for tests and for resuming)."""
        self.today_date = today

    # -- visibility -----------------------------------------------------------------
    def status(self) -> dict:
        """The whole rotation at a glance: upcoming daily folders and
        pending monthly folders."""
        upcoming = {
            folder: [i.text for i in items]
            for folder, items in sorted(self._daily.items())
            if folder >= self.today_date.isoformat()
        }
        pending = {
            month: [i.text for i in items]
            for month, items in sorted(self._monthly.items())
        }
        return {
            "today": self.today_date.isoformat(),
            "daily_folders": upcoming,
            "monthly_folders": pending,
        }

    def pending_count(self) -> int:
        return sum(len(v) for v in self._daily.values()) + sum(
            len(v) for v in self._monthly.values()
        )


__all__ = [
    "ORIGIN",
    "TicklerError",
    "TicklerItem",
    "TicklerFile",
]
