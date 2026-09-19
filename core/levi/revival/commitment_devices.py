"""Opt-in commitment devices — streak mechanics with user-set goals.

Studied from: giant-patterns-hunt-20260916-0016/report.md [Additions 17].

The mechanism under study: streak-style habit mechanics where the user
sets the goal and the terms, entirely local. The design law here is
explicit: no guilt engineering (status language stays neutral and factual)
and no paid restores — a broken streak can only be rebuilt by doing the
thing, never by paying or by editing history. This is an original,
from-scratch implementation for LEVI.

A commitment tracks daily check-ins against a user-set target (e.g.
"30 minutes of reading"). Streaks count consecutive days meeting the
target; rest days (weekday-based, user-configured) are neutral — they
neither extend nor break a streak. Misses break the streak and are
reported plainly, without shaming copy.

Public surface:
- ``Commitment``: check_in / streak / total / best_streak / status.
- ``CommitmentStore``: create/get/list/archive commitments.

stdlib-only. No network. Dates are ISO "YYYY-MM-DD" strings supplied by
the caller; the module never touches the clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional

ORIGIN = "levi-revival/commitment-devices"


class CommitmentError(ValueError):
    """Raised when a commitment operation is invalid."""


def _parse_day(day: str) -> date:
    try:
        return date.fromisoformat(day)
    except ValueError:
        raise CommitmentError(f"day must be ISO YYYY-MM-DD, got {day!r}") from None


@dataclass
class Commitment:
    name: str
    target: float
    unit: str = "session"
    rest_weekdays: List[int] = field(default_factory=list)  # 0=Mon..6=Sun
    archived: bool = False
    _log: Dict[str, float] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not self.name:
            raise CommitmentError("name must not be empty")
        if self.target <= 0:
            raise CommitmentError("target must be positive")
        if any(not 0 <= w <= 6 for w in self.rest_weekdays):
            raise CommitmentError("rest_weekdays must be 0..6")

    def check_in(self, day: str, amount: float = 1.0) -> float:
        """Record work done on a day. Returns the day's accumulated total."""
        _parse_day(day)  # validate format
        if amount < 0:
            raise CommitmentError("amount must not be negative")
        # History is append-accumulate only: no editing, no paid restores.
        self._log[day] = self._log.get(day, 0.0) + amount
        return self._log[day]

    def day_total(self, day: str) -> float:
        return self._log.get(day, 0.0)

    def met(self, day: str) -> Optional[bool]:
        """True if target met, False if missed, None if day is a rest day."""
        d = _parse_day(day)
        if d.weekday() in self.rest_weekdays:
            return None
        return self._log.get(day, 0.0) >= self.target

    def streak(self, through: str) -> int:
        """Consecutive target-meeting days up to `through`.

        Rest days are neutral (skipped, not counted, not breaking).
        A miss resets to zero. Never consults the future.
        """
        cursor = _parse_day(through)
        count = 0
        while True:
            state = self.met(cursor.isoformat())
            if state is None:
                cursor -= timedelta(days=1)
                continue
            if state:
                count += 1
                cursor -= timedelta(days=1)
                continue
            return count

    def best_streak(self) -> int:
        best = 0
        for day in sorted(self._log):
            s = self.streak(day)
            best = max(best, s)
        return best

    def total(self) -> float:
        return sum(self._log.values())

    def days_logged(self) -> int:
        return len(self._log)

    def status(self, through: str) -> str:
        """Neutral, factual status line — no guilt copy, by design."""
        s = self.streak(through)
        met_today = self.met(through)
        if met_today is None:
            today = "rest day"
        elif met_today:
            today = "target met"
        else:
            today = "target not yet met"
        return (
            f"{self.name}: streak {s} day(s), {today}, "
            f"{self.total():g} {self.unit} total over "
            f"{self.days_logged()} logged day(s)."
        )


class CommitmentStore:
    """Owns the user's commitments."""

    def __init__(self) -> None:
        self._items: Dict[str, Commitment] = {}

    def create(
        self,
        name: str,
        target: float,
        unit: str = "session",
        rest_weekdays: Optional[List[int]] = None,
    ) -> Commitment:
        if name in self._items:
            raise CommitmentError(f"commitment {name!r} already exists")
        item = Commitment(name, target, unit, rest_weekdays or [])
        self._items[name] = item
        return item

    def get(self, name: str) -> Commitment:
        try:
            return self._items[name]
        except KeyError:
            raise CommitmentError(f"no commitment named {name!r}") from None

    def archive(self, name: str) -> None:
        self.get(name).archived = True

    def list_active(self) -> List[str]:
        return sorted(n for n, c in self._items.items() if not c.archived)

    def summary(self, through: str) -> List[str]:
        return [self._items[n].status(through) for n in self.list_active()]
