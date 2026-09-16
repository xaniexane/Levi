"""Active-hours gate — when the signal plane may speak.

Default window: 08:00–22:00 local time. Outside the window only ESCALATE
passes; everything else waits for morning. The window is configurable;
overnight windows (e.g. 22:00–06:00) are supported.

``now`` is injectable for tests. Naive datetimes are treated as local
time; aware datetimes are converted to local time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

from levi.signals.grades import Signal, SignalGrade

__all__ = ["ActiveHours", "DEFAULT_ACTIVE_HOURS"]

DEFAULT_START: Tuple[int, int] = (8, 0)
DEFAULT_END: Tuple[int, int] = (22, 0)


@dataclass(frozen=True)
class ActiveHours:
    """A daily local-time window in which non-escalated signals may speak."""

    start: Tuple[int, int] = DEFAULT_START  # (hour, minute), inclusive
    end: Tuple[int, int] = DEFAULT_END  # (hour, minute), exclusive

    def __post_init__(self) -> None:
        for label, part in (("start", self.start), ("end", self.end)):
            if (
                not isinstance(part, tuple)
                or len(part) != 2
                or not (0 <= part[0] <= 23)
                or not (0 <= part[1] <= 59)
            ):
                raise ValueError(
                    "%s must be an (hour, minute) tuple, got %r" % (label, part)
                )

    @classmethod
    def from_strings(cls, start: str, end: str) -> "ActiveHours":
        """Parse ``"08:00"``-style strings."""

        def parse(text: str) -> Tuple[int, int]:
            hour_s, _, minute_s = text.strip().partition(":")
            return int(hour_s), int(minute_s or 0)

        return cls(start=parse(start), end=parse(end))

    def _local(self, now: Optional[datetime]) -> datetime:
        if now is None:
            return datetime.now().astimezone()
        if now.tzinfo is None:
            return now.astimezone()
        return now.astimezone()

    def in_window(self, now: Optional[datetime] = None) -> bool:
        """True when ``now`` falls inside the active window (local time)."""
        local = self._local(now)
        mark = (local.hour, local.minute)
        if self.start <= self.end:
            return self.start <= mark < self.end
        # Overnight window, e.g. 22:00–06:00.
        return mark >= self.start or mark < self.end

    def should_deliver(self, signal: Signal, now: Optional[datetime] = None) -> bool:
        """Gate predicate: outside the window, only ESCALATE speaks."""
        if signal.grade is SignalGrade.ESCALATE:
            return True
        return self.in_window(now)


DEFAULT_ACTIVE_HOURS = ActiveHours()
