"""Franklin's moral-perfection ledger: the black-spot habit grid.

Origin: Benjamin Franklin's *Autobiography* project — 13 virtues, each with
a short precept, tracked in a ruled ledger: one column per day, one row per
virtue; each evening a black spot for every fault. He worked on one virtue
per week, cycling through all 13 four times a year — and cheerfully admits
perfection eluded him.

What it is in LEVI: a low-friction behavior log. The grid makes patterns
visible (which virtue, which days) without narrative journaling; the weekly
focus virtue gets attention while the rest are merely monitored. The
assistant's addition is pattern detection: spots clustered on travel days,
weekdays, or around the focus virtue.

Honesty label: USEFUL PATTERN — this is self-experimentation by a genius
amateur, not moral science. Present it as behavior logging with a good UI,
not a validated path to virtue.

Deny-closed inputs: unknown virtues, malformed dates, and duplicate marks
for the same virtue/day are rejected with ValueError. Custom virtue lists
(up to 13, Franklin's number) are accepted; the 13 defaults carry
Franklin's own precepts, abbreviated from the public-domain *Autobiography*.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, Union

__all__ = [
    "FRANKLIN_VIRTUES",
    "FranklinLedger",
    "default_store_path",
]

DateLike = Union[date, str]

# Franklin's 13 virtues with his precepts (Autobiography, public domain).
FRANKLIN_VIRTUES: tuple[tuple[str, str], ...] = (
    ("Temperance", "Eat not to dullness; drink not to elevation."),
    (
        "Silence",
        "Speak not but what may benefit others or yourself; avoid trifling conversation.",
    ),
    (
        "Order",
        "Let all your things have their places; let each part of your business have its time.",
    ),
    (
        "Resolution",
        "Resolve to perform what you ought; perform without fail what you resolve.",
    ),
    (
        "Frugality",
        "Make no expense but to do good to others or yourself; i.e., waste nothing.",
    ),
    (
        "Industry",
        "Lose no time; be always employ'd in something useful; cut off all unnecessary actions.",
    ),
    (
        "Sincerity",
        "Use no hurtful deceit; think innocently and justly, and, if you speak, speak accordingly.",
    ),
    (
        "Justice",
        "Wrong none by doing injuries, or omitting the benefits that are your duty.",
    ),
    (
        "Moderation",
        "Avoid extremes; forbear resenting injuries so much as you think they deserve.",
    ),
    ("Cleanliness", "Tolerate no uncleanliness in body, cloaths, or habitation."),
    (
        "Tranquillity",
        "Be not disturbed at trifles, or at accidents common or unavoidable.",
    ),
    (
        "Chastity",
        "Rarely use venery but for health or offspring, never to dullness or weakness.",
    ),
    ("Humility", "Imitate Jesus and Socrates."),
)

MAX_VIRTUES = 13


def _parse_date(value: DateLike, field_name: str = "date") -> date:
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
    return Path(os.path.expanduser("~")) / ".levi" / "methods" / "franklin.json"


class FranklinLedger:
    """The ruled ledger: rows = virtues, columns = days, black spots = faults."""

    def __init__(
        self,
        virtues: Optional[list[tuple[str, str]]] = None,
        path: Optional[Union[str, Path]] = None,
        start: Optional[DateLike] = None,
    ):
        vlist = list(virtues) if virtues is not None else list(FRANKLIN_VIRTUES)
        if not vlist or len(vlist) > MAX_VIRTUES:
            raise ValueError(f"virtues: need 1..{MAX_VIRTUES}, got {len(vlist)}")
        names = [n for n, _ in vlist]
        if any(not n or not n.strip() for n in names):
            raise ValueError("virtue names must be non-empty strings")
        if len({n.strip().lower() for n in names}) != len(names):
            raise ValueError("virtue names must be unique")
        self.virtues: list[tuple[str, str]] = [(n.strip(), p) for n, p in vlist]
        self._names = [n for n, _ in self.virtues]
        self.start = _parse_date(start) if start is not None else date.today()
        self._spots: dict[str, set[str]] = {
            n: set() for n in self._names
        }  # virtue -> ISO dates
        self._path = Path(path) if path is not None else None
        if self._path is not None and self._path.exists():
            self._load()

    # -- persistence ------------------------------------------------------
    def _load(self) -> None:
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or "spots" not in raw:
            raise ValueError(f"franklin store is corrupt: {self._path}")
        for name, days in raw["spots"].items():
            if name in self._spots:
                self._spots[name] = set(days)

    def save(self) -> None:
        if self._path is None:
            raise ValueError(
                "no store path configured; construct with path= to persist"
            )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "virtues": self.virtues,
            "start": self.start.isoformat(),
            "spots": {n: sorted(s) for n, s in self._spots.items()},
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # -- the nightly ritual --------------------------------------------------
    def _check_virtue(self, virtue: str) -> str:
        match = next(
            (n for n in self._names if n.lower() == virtue.strip().lower()), None
        )
        if match is None:
            raise ValueError(
                f"unknown virtue: {virtue!r} (known: {', '.join(self._names)})"
            )
        return match

    def mark(self, virtue: str, on_date: Optional[DateLike] = None) -> None:
        """Record a black spot: a fault against ``virtue`` on ``on_date``."""
        name = self._check_virtue(virtue)
        day = _parse_date(on_date) if on_date is not None else date.today()
        iso = day.isoformat()
        if iso in self._spots[name]:
            raise ValueError(f"already marked: {name} on {iso}")
        self._spots[name].add(iso)

    def clear(self, virtue: str, on_date: DateLike) -> None:
        """Remove a mark entered in error."""
        name = self._check_virtue(virtue)
        iso = _parse_date(on_date, "on_date").isoformat()
        self._spots[name].discard(iso)

    # -- the weekly rotation ---------------------------------------------------
    def week_index(self, on_date: Optional[DateLike] = None) -> int:
        """Weeks since the ledger started (Franklin cycled 13 virtues x4/year)."""
        day = _parse_date(on_date) if on_date is not None else date.today()
        if day < self.start:
            raise ValueError("on_date is before the ledger start")
        return (day - self.start).days // 7

    def focus_virtue(self, on_date: Optional[DateLike] = None) -> str:
        """This week's virtue of focus: attention here, monitoring elsewhere."""
        return self._names[self.week_index(on_date) % len(self._names)]

    # -- reading the grid --------------------------------------------------------
    def grid(
        self, start: Optional[DateLike] = None, days: int = 7
    ) -> dict[str, list[bool]]:
        """Black-spot matrix: virtue -> [spotted?] for ``days`` from ``start``."""
        if days < 1:
            raise ValueError("days must be >= 1")
        s = _parse_date(start) if start is not None else self.start
        out: dict[str, list[bool]] = {}
        for name in self._names:
            out[name] = [
                (s + timedelta(days=i)).isoformat() in self._spots[name]
                for i in range(days)
            ]
        return out

    def report(self) -> dict:
        """Totals per virtue, the focus virtue, and where the spots cluster."""
        totals = {n: len(s) for n, s in self._spots.items()}
        weekday_hits: Counter[int] = Counter()
        for spots in self._spots.values():
            for iso in spots:
                y, m, d = (int(x) for x in iso.split("-"))
                weekday_hits[date(y, m, d).weekday()] += 1
        focus = self.focus_virtue()
        return {
            "virtues": len(self._names),
            "total_spots": sum(totals.values()),
            "spots_per_virtue": totals,
            "worst_virtue": max(totals, key=totals.get) if totals else None,
            "focus_virtue": focus,
            "focus_spots": totals.get(focus, 0),
            "spots_by_weekday": {str(k): v for k, v in sorted(weekday_hits.items())},
        }
