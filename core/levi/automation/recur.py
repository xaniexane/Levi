"""Recurrence phrases -> schedules (LEVI-native automation timing).

Parses human schedule phrases into a :class:`Recurrence` and computes
upcoming run times. Pairs with :class:`levi.automation.watchers.TickWatcher`
(which takes raw seconds) and the automation engine's due-tick logic:
this module turns "every 6h" / "daily at 06:45" / "weekly on monday" into
concrete datetimes.

Pure stdlib, local-first. The clock is injectable (``now`` arguments) so
tests never depend on wall time.

Supported phrases (case-insensitive):

* ``every 30s`` / ``every 15m`` / ``every 6h`` / ``every 2d`` / ``every 3w``
* ``every hour`` / ``every day`` / ``every week`` / ``every month``
* ``hourly`` / ``daily`` / ``weekly`` / ``monthly``
* ``daily at 06:45`` / ``daily at 6:45pm``
* ``weekly on monday`` / ``weekly on fri at 09:00``
* ``monthly on the 3rd`` / ``monthly on the 31st at 10:00``

Interop (wired when the manifest is free — see queue note below):

.. code-block:: python

    "automation-recur": {
        "provides": ["automation.recur"],
        "requires": [],
    }

Until then, :func:`register_capabilities` registers this module against
any :class:`levi.interop.registry.Registry`.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional


class RecurError(ValueError):
    """Raised when a schedule phrase cannot be parsed."""


#: Capability wiring (see module docstring).
MODULE_NAME = "automation-recur"
PROVIDES = ["automation.recur"]
REQUIRES: List[str] = []


_UNIT_SECONDS = {
    "s": 1,
    "sec": 1,
    "secs": 1,
    "second": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "mins": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hrs": 3600,
    "hour": 3600,
    "hours": 3600,
    "d": 86400,
    "day": 86400,
    "days": 86400,
    "w": 604800,
    "week": 604800,
    "weeks": 604800,
}

_WEEKDAYS = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}

_EVERY_RE = re.compile(r"^every\s+(?:(\d+)\s*)?([a-z]+)\s*$")
_AT_RE = re.compile(r"^(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap]m?)?\s*$")
_MONTHDAY_RE = re.compile(r"^the\s+(\d{1,2})(?:st|nd|rd|th)?\s*$")


def _parse_clock(text: str) -> tuple:
    """Parse 'HH:MM' / 'H:MMpm' / '6pm' -> (hour, minute)."""
    m = _AT_RE.match(text.strip().lower())
    if not m:
        raise RecurError(f"bad clock time: {text!r} (want e.g. '06:45' or '6:45pm')")
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    meridiem = (m.group(3) or "").lower()
    if meridiem.startswith("p") and hour < 12:
        hour += 12
    if meridiem.startswith("a") and hour == 12:
        hour = 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise RecurError(f"clock time out of range: {text!r}")
    return hour, minute


@dataclass(frozen=True)
class Recurrence:
    """A parsed schedule. ``next_after`` is strictly after the given time."""

    kind: str  # interval | daily_at | weekly_on | monthly_on
    interval_seconds: Optional[int] = None
    hour: int = 0
    minute: int = 0
    weekday: Optional[int] = None  # 0=Monday
    monthday: Optional[int] = None
    anchor: Optional[datetime] = None  # interval origin (parse time by default)

    def next_after(self, when: datetime) -> datetime:
        if self.kind == "interval":
            assert self.interval_seconds and self.anchor is not None
            if when < self.anchor:
                return self.anchor
            step = timedelta(seconds=self.interval_seconds)
            elapsed = (when - self.anchor).total_seconds()
            k = int(elapsed // self.interval_seconds) + 1
            return self.anchor + k * step
        if self.kind == "daily_at":
            cand = when.replace(
                hour=self.hour, minute=self.minute, second=0, microsecond=0
            )
            if cand <= when:
                cand += timedelta(days=1)
            return cand
        if self.kind == "weekly_on":
            assert self.weekday is not None
            days_ahead = (self.weekday - when.weekday()) % 7
            cand = (when + timedelta(days=days_ahead)).replace(
                hour=self.hour, minute=self.minute, second=0, microsecond=0
            )
            if cand <= when:
                cand += timedelta(days=7)
            return cand
        if self.kind == "monthly_on":
            assert self.monthday is not None
            year, month = when.year, when.month
            for _ in range(3):  # at most one rollover needed
                last = calendar.monthrange(year, month)[1]
                day = min(self.monthday, last)
                cand = datetime(year, month, day, self.hour, self.minute)
                if cand > when:
                    return cand
                month += 1
                if month > 12:
                    month, year = 1, year + 1
            raise RecurError("monthly recurrence failed to advance")
        raise RecurError(f"unknown recurrence kind: {self.kind!r}")

    def next_n(self, when: datetime, n: int) -> List[datetime]:
        """Next ``n`` run times after ``when``, strictly increasing."""
        out: List[datetime] = []
        cursor = when
        for _ in range(max(0, n)):
            cursor = self.next_after(cursor)
            out.append(cursor)
        return out

    def to_interval_seconds(self) -> Optional[int]:
        """Fixed-second spacing, or None when the spacing varies (monthly)."""
        if self.kind == "interval":
            return self.interval_seconds
        if self.kind == "daily_at":
            return 86400
        if self.kind == "weekly_on":
            return 604800
        return None

    def describe(self) -> str:
        clock = f"{self.hour:02d}:{self.minute:02d}"
        if self.kind == "interval":
            secs = self.interval_seconds or 0
            for name, size in (
                ("week", 604800),
                ("day", 86400),
                ("hour", 3600),
                ("minute", 60),
                ("second", 1),
            ):
                if secs % size == 0:
                    n = secs // size
                    unit = name if n == 1 else name + "s"
                    return f"every {n} {unit}"
            return f"every {secs} seconds"
        if self.kind == "daily_at":
            return f"daily at {clock}"
        if self.kind == "weekly_on":
            day = calendar.day_name[self.weekday or 0]
            return f"weekly on {day} at {clock}"
        if self.kind == "monthly_on":
            return f"monthly on the {self.monthday} at {clock}"
        return self.kind


def parse(text: str, *, now: Optional[datetime] = None) -> Recurrence:
    """Parse a schedule phrase into a :class:`Recurrence`.

    ``now`` anchors fixed intervals (defaults to the current local time).
    Raises :class:`RecurError` on anything unparseable — never guesses.
    """
    raw = text
    text = text.strip().lower()
    anchor = now or datetime.now()

    m = _EVERY_RE.match(text)
    if m:
        n = int(m.group(1) or 1)
        unit = m.group(2)
        if unit.startswith("month"):
            if n != 1:
                raise RecurError(f"unsupported: {raw!r} (months are calendar-based)")
            return Recurrence(kind="monthly_on", monthday=1, anchor=anchor)
        if unit not in _UNIT_SECONDS:
            raise RecurError(f"unknown unit {unit!r} in {raw!r}")
        if n <= 0:
            raise RecurError(f"interval must be positive in {raw!r}")
        return Recurrence(
            kind="interval", interval_seconds=n * _UNIT_SECONDS[unit], anchor=anchor
        )

    if text in ("hourly", "daily", "weekly", "monthly"):
        table = {
            "hourly": Recurrence(kind="interval", interval_seconds=3600, anchor=anchor),
            "daily": Recurrence(kind="daily_at", anchor=anchor),
            "weekly": Recurrence(kind="weekly_on", weekday=0, anchor=anchor),
            "monthly": Recurrence(kind="monthly_on", monthday=1, anchor=anchor),
        }
        return table[text]

    if text.startswith("daily"):
        rest = text[len("daily") :].strip()
        hour, minute = (0, 0)
        if rest:
            if not rest.startswith("at "):
                raise RecurError(f"unsupported: {raw!r} (want 'daily at HH:MM')")
            hour, minute = _parse_clock(rest[3:])
        return Recurrence(kind="daily_at", hour=hour, minute=minute, anchor=anchor)

    if text.startswith("weekly on "):
        rest = text[len("weekly on ") :].strip()
        day_part, _, at_part = rest.partition(" at ")
        day_part = day_part.strip()
        if day_part not in _WEEKDAYS:
            raise RecurError(f"unknown weekday {day_part!r} in {raw!r}")
        hour, minute = (0, 0)
        if at_part.strip():
            hour, minute = _parse_clock("at " + at_part.strip())
        return Recurrence(
            kind="weekly_on",
            weekday=_WEEKDAYS[day_part],
            hour=hour,
            minute=minute,
            anchor=anchor,
        )

    if text.startswith("monthly on "):
        rest = text[len("monthly on ") :].strip()
        day_part, _, at_part = rest.partition(" at ")
        mm = _MONTHDAY_RE.match(day_part.strip())
        if not mm:
            raise RecurError(f"bad month day in {raw!r} (want 'monthly on the 3rd')")
        day = int(mm.group(1))
        if not 1 <= day <= 31:
            raise RecurError(f"month day out of range in {raw!r}")
        hour, minute = (0, 0)
        if at_part.strip():
            hour, minute = _parse_clock("at " + at_part.strip())
        return Recurrence(
            kind="monthly_on", monthday=day, hour=hour, minute=minute, anchor=anchor
        )

    raise RecurError(
        f"cannot parse schedule {raw!r} — try 'every 6h', 'daily at 06:45', "
        "'weekly on monday', or 'monthly on the 3rd'"
    )


def register_capabilities(reg) -> None:
    """Register this module's capabilities against an interop Registry."""
    reg.register(MODULE_NAME, provides=list(PROVIDES), requires=list(REQUIRES))
