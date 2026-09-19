"""season_era — a battle pass that cannot FOMO.

Studied from: dead-game-genres-2026-09-16/report.md (Build shortlist — honest season).

The load-bearing idea: seasons in games are engineered urgency —
progress expires, streaks punish, the pass costs money. The honest
inversion keeps the *shape* people like (a themed arc, milestones,
celebration) and deletes the coercion: the player opens and closes
their own eras, progress never expires, streaks only celebrate, and
everything is free.

LEVI's take: an ``Era`` is a personal season with a name, an opening
moment, and an optional closing moment — the player decides both.
``Progress`` accumulates points that never decay and unlock
``Milestone`` rewards at thresholds; closing an era archives it with
everything earned intact, and milestones stay claimable forever.
``Streak`` tracks consecutive active days but only ever *adds*
celebration bonuses — ``miss_day`` records the gap and grants nothing,
taking nothing. There is no price field anywhere in the module.

Honest limits: "never expires" is a property of this data model, not
a promise about any company's servers — if a game operator deletes
your account, local honesty can't stop them. Export your eras.

This is an original, from-scratch implementation for LEVI.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/season-era"


@dataclass
class Milestone:
    """A reward threshold inside an era. Claimable forever."""

    name: str
    points_required: int
    reward: str
    claimed: bool = False


@dataclass
class Celebration:
    """A streak celebration. A bonus, never a penalty."""

    at_streak: int
    title: str
    bonus_points: int
    awarded: bool = False


@dataclass
class Era:
    """One personal season: opened by the player, closed by the player."""

    name: str
    theme: str = ""
    opened_at: float = field(default_factory=time.time)
    closed_at: Optional[float] = None
    points: int = 0
    milestones: List[Milestone] = field(default_factory=list)
    archived: bool = False

    @property
    def is_open(self) -> bool:
        return self.closed_at is None and not self.archived

    def add_milestone(self, milestone: Milestone) -> None:
        self.milestones.append(milestone)

    def earn(self, points: int, note: str = "") -> List[Milestone]:
        """Add progress. Points never decay; returns newly unlocked milestones."""
        if points < 0:
            raise ValueError("points cannot be negative")
        if not self.is_open:
            raise ValueError(f"era {self.name!r} is closed — open a new era")
        self.points += points
        unlocked = []
        for m in self.milestones:
            if not m.claimed and self.points >= m.points_required:
                m.claimed = True
                unlocked.append(m)
        return unlocked

    def close(self) -> Dict[str, object]:
        """Close the era yourself. Nothing expires; everything stays claimable."""
        if not self.is_open:
            raise ValueError(f"era {self.name!r} is already closed")
        self.closed_at = time.time()
        return self.summary()

    def summary(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "theme": self.theme,
            "open": self.is_open,
            "points": self.points,
            "milestones": [
                {
                    "name": m.name,
                    "required": m.points_required,
                    "reward": m.reward,
                    "claimed": m.claimed,
                }
                for m in self.milestones
            ],
        }


@dataclass
class Streak:
    """Consecutive active days. Celebrates; never punishes."""

    celebrations: List[Celebration] = field(default_factory=list)
    current: int = 0
    best: int = 0
    _last_active_day: Optional[int] = None

    @staticmethod
    def _day(ts: float) -> int:
        return int(ts // 86400)

    def active_day(self, ts: Optional[float] = None) -> List[Celebration]:
        """Record an active day. Consecutive days grow the streak."""
        ts = time.time() if ts is None else ts
        day = self._day(ts)
        if self._last_active_day == day:
            return []  # same day: no double count
        if self._last_active_day is not None and day == self._last_active_day + 1:
            self.current += 1
        else:
            self.current = 1  # a fresh start, not a punishment
        self._last_active_day = day
        self.best = max(self.best, self.current)
        newly: List[Celebration] = []
        for c in self.celebrations:
            if not c.awarded and self.current >= c.at_streak:
                c.awarded = True
                newly.append(c)
        return newly

    def miss_day(self) -> Dict[str, object]:
        """A missed day ends the streak quietly. Nothing is taken.

        Returns what was *kept* — the honest inversion of a punishment
        notice.
        """
        kept = {
            "streak_was": self.current,
            "best_kept": self.best,
            "points_lost": 0,
            "rewards_revoked": [],
        }
        self.current = 0
        self._last_active_day = None
        return kept

    def celebration_bonus(self) -> int:
        return sum(c.bonus_points for c in self.celebrations if c.awarded)


class SeasonJournal:
    """A player's shelf of eras: open, close, revisit — all free."""

    def __init__(self) -> None:
        self._eras: Dict[str, Era] = {}
        self.streak = Streak()

    def open_era(self, name: str, theme: str = "") -> Era:
        if name in self._eras and self._eras[name].is_open:
            raise ValueError(f"era {name!r} is already open")
        era = Era(name=name, theme=theme)
        self._eras[name] = era
        return era

    def get_era(self, name: str) -> Optional[Era]:
        return self._eras.get(name)

    def eras(self) -> List[Era]:
        return list(self._eras.values())

    def total_points_ever(self) -> int:
        """Progress across all eras, open or closed. Never expires."""
        return sum(e.points for e in self._eras.values())
