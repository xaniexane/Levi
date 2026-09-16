"""Opt-in commitment devices — honest streak mechanics, local only.

A commitment is a user-defined habit with a user-defined target:

    {name, unit, target_per: day|week, rest_days_per_week,
     mulligans_per_month, start_date, checkins: [{date, value}]}

Check-ins record values; :func:`streak` counts consecutive successful
periods where "successful" is defined *by the user's own rules*:
- a day counts as hit when value >= target (for per-day commitments),
- rest days the user configured never break a streak,
- mulligans (user-configured count per month) forgive misses explicitly.

COPY LAW (binding): every user-facing string in this module was reviewed
for guilt engineering. There is no shaming copy, no "you're letting
yourself down", no loss-framed urgency, no paid restores, no streak
freezes sold back to you. A missed day is reported neutrally:
"no check-in recorded for 2026-09-14." A mulligan is applied when the
user asks, never sold. Snap monetizes the addiction; this is the honest
version: the mechanics belong to the user, including the right to pause
or delete without penalty copy.

All state in ``~/.levi/commitments/commitments.json``; home resolved at
call time.
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

ENC = "utf-8"


def commitments_home(home: "str | os.PathLike[str] | None" = None) -> Path:
    base = Path(home) if home is not None else Path(os.path.expanduser("~"))
    return base / ".levi" / "commitments"


class CommitmentError(Exception):
    pass


# -- neutral copy -------------------------------------------------------------
# Every string the user sees. Rule: describe facts, never judge the user.

_COPY = {
    "missed": "no check-in recorded for {day}.",
    "mulligan_applied": "mulligan applied for {day} ({left} remaining this month).",
    "streak": "{n}-period streak. Current: {state}.",
    "paused": "commitment paused on {day}; streak is held, not broken.",
}


def _today() -> date:
    return date.today()


def _parse_day(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise CommitmentError("bad date %r — use YYYY-MM-DD" % s) from None


class CommitmentStore:
    def __init__(self, home: "str | os.PathLike[str] | None" = None) -> None:
        self.root = commitments_home(home)
        self.root.mkdir(parents=True, exist_ok=True)
        self._path = self.root / "commitments.json"

    def _load(self) -> Dict[str, Any]:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text(encoding=ENC))

    def _save(self, data: Dict[str, Any]) -> None:
        self._path.write_text(json.dumps(data, indent=2), encoding=ENC)

    # -- definitions ----------------------------------------------------------
    def define(
        self,
        name: str,
        unit: str = "times",
        target: float = 1.0,
        per: str = "day",
        rest_days_per_week: int = 0,
        mulligans_per_month: int = 0,
        start: Optional[str] = None,
    ) -> Dict[str, Any]:
        data = self._load()
        if name in data:
            raise CommitmentError("commitment already exists: %s" % name)
        if per not in ("day", "week"):
            raise CommitmentError("per must be 'day' or 'week'")
        if target <= 0:
            raise CommitmentError("target must be positive")
        if not 0 <= rest_days_per_week <= 6:
            raise CommitmentError("rest_days_per_week must be 0-6")
        if mulligans_per_month < 0:
            raise CommitmentError("mulligans_per_month must be >= 0")
        start_day = _parse_day(start) if start else _today()
        data[name] = {
            "name": name,
            "unit": unit,
            "target": target,
            "per": per,
            "rest_days_per_week": rest_days_per_week,
            "mulligans_per_month": mulligans_per_month,
            "start": start_day.isoformat(),
            "paused": False,
            "checkins": {},  # YYYY-MM-DD -> value
            "mulligans_used": {},  # YYYY-MM -> count
        }
        self._save(data)
        return data[name]

    def get(self, name: str) -> Dict[str, Any]:
        data = self._load()
        if name not in data:
            raise CommitmentError("no such commitment: %s" % name)
        return data[name]

    def list(self) -> List[Dict[str, Any]]:
        return [self._load()[k] for k in sorted(self._load())]

    def edit(self, name: str, **fields) -> Dict[str, Any]:
        data = self._load()
        c = self.get(name)
        for key in (
            "unit",
            "target",
            "per",
            "rest_days_per_week",
            "mulligans_per_month",
            "paused",
        ):
            if key in fields and fields[key] is not None:
                c[key] = fields[key]
        if c["per"] not in ("day", "week"):
            raise CommitmentError("per must be 'day' or 'week'")
        data[name] = c
        self._save(data)
        return c

    def delete(self, name: str) -> None:
        data = self._load()
        if name not in data:
            raise CommitmentError("no such commitment: %s" % name)
        del data[name]
        self._save(data)

    # -- check-ins ------------------------------------------------------------
    def checkin(
        self, name: str, value: float = 1.0, day: Optional[str] = None
    ) -> Dict[str, Any]:
        data = self._load()
        c = self.get(name)
        d = _parse_day(day) if day else _today()
        if d < _parse_day(c["start"]):
            raise CommitmentError("check-in is before the start date")
        c["checkins"][d.isoformat()] = c["checkins"].get(d.isoformat(), 0) + value
        data[name] = c
        self._save(data)
        return {
            "name": name,
            "day": d.isoformat(),
            "total": c["checkins"][d.isoformat()],
        }

    def mulligan(self, name: str, day: Optional[str] = None) -> Dict[str, Any]:
        """Forgive a missed day using one of the user's monthly mulligans."""
        data = self._load()
        c = self.get(name)
        d = _parse_day(day) if day else _today()
        month = d.strftime("%Y-%m")
        used = c["mulligans_used"].get(month, 0)
        if used >= c["mulligans_per_month"]:
            raise CommitmentError(
                "no mulligans remaining for %s (configured: %d/month)"
                % (month, c["mulligans_per_month"])
            )
        c["mulligans_used"][month] = used + 1
        c["checkins"][d.isoformat()] = c["checkins"].get(d.isoformat(), 0)
        # mark forgiven: a mulligan day counts as hit regardless of value
        c.setdefault("mulligan_days", []).append(d.isoformat())
        data[name] = c
        self._save(data)
        return {
            "name": name,
            "day": d.isoformat(),
            "message": _COPY["mulligan_applied"].format(
                day=d.isoformat(), left=c["mulligans_per_month"] - used - 1
            ),
        }

    # -- streaks --------------------------------------------------------------
    def _periods(self, c: Dict[str, Any], until: date) -> List[date]:
        start = _parse_day(c["start"])
        if c["per"] == "day":
            days = []
            d = start
            while d <= until:
                days.append(d)
                d += timedelta(days=1)
            return days
        # week: weeks starting Monday from the start week
        weeks = []
        d = start - timedelta(days=start.weekday())
        while d <= until:
            weeks.append(d)
            d += timedelta(weeks=1)
        return weeks

    def _period_hit(self, c: Dict[str, Any], period_start: date) -> bool:
        iso = period_start.isoformat()
        if iso in c.get("mulligan_days", []):
            return True
        if c["per"] == "day":
            if (
                period_start.weekday() >= 7 - c["rest_days_per_week"]
                and c["rest_days_per_week"]
            ):
                # rest days are the last N days of the week (Sat/Sun first)
                return True
            return c["checkins"].get(iso, 0) >= c["target"]
        # week: sum the 7 days
        total = sum(
            c["checkins"].get((period_start + timedelta(days=i)).isoformat(), 0)
            for i in range(7)
        )
        return total >= c["target"]

    def status(self, name: str, as_of: Optional[str] = None) -> Dict[str, Any]:
        c = self.get(name)
        until = _parse_day(as_of) if as_of else _today()
        periods = self._periods(c, until)
        hits = [self._period_hit(c, p) for p in periods]
        # current streak: consecutive hits at the end. An in-progress period
        # (today, for per-day) never breaks the streak — only a completed
        # missed period does.
        if c["per"] == "day" and periods and periods[-1] == _today() and not hits[-1]:
            hits = hits[:-1]
            periods = periods[:-1]
        streak = 0
        for h in reversed(hits):
            if h:
                streak += 1
            else:
                break
        # longest streak
        longest, run = 0, 0
        for h in hits:
            run = run + 1 if h else 0
            longest = max(longest, run)
        total_hits = sum(hits)
        state = "on track" if (not hits or hits[-1]) else "missed last period"
        if c.get("paused"):
            state = "paused"
        missed = [p.isoformat() for p, h in zip(periods, hits) if not h]
        return {
            "name": name,
            "per": c["per"],
            "target": c["target"],
            "unit": c["unit"],
            "streak": streak,
            "longest": longest,
            "periods": len(periods),
            "hits": total_hits,
            "state": state,
            "missed": missed[-10:],
            "message": _COPY["streak"].format(n=streak, state=state),
        }
