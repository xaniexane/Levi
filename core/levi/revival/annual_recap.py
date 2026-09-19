"""Local annual recap — Wrapped-style shareable cards, computed on-device.

Studied from: giant-patterns-hunt-20260916-0016/report.md [Additions 18].

The mechanism under study: year-in-review cards computed locally from
data the user already owns — counts by category, top items, personal
firsts and bests — rendered as shareable text/Markdown cards. This is an
original, from-scratch implementation for LEVI. There is no cloud
aggregation step and no "share" button that phones home; rendering a card
is pure formatting of local aggregates.

Input is a plain event stream: (date, category, label, value). The recap
engine groups by year and produces cards:
- "by the numbers": total events, total value, active days per category;
- "top shelf": highest-value labels per category;
- "milestones": first-ever labels and personal-best single-day values;
- "rhythm": busiest weekday and busiest month.

Public surface:
- ``Recap``: add_event / recap(year) -> YearRecap / render_card(...).
- ``YearRecap`` holds the computed cards as plain data.

stdlib-only. No network. Dates are ISO strings.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

ORIGIN = "levi-revival/annual-recap"


@dataclass
class Event:
    day: str  # ISO YYYY-MM-DD
    category: str
    label: str
    value: float = 1.0


@dataclass
class Card:
    title: str
    lines: List[str] = field(default_factory=list)

    def render(self) -> str:
        bar = "=" * max(12, len(self.title) + 4)
        body = "\n".join(f"  {line}" for line in self.lines)
        return f"{bar}\n  {self.title}\n{bar}\n{body}\n"


@dataclass
class YearRecap:
    year: int
    cards: List[Card] = field(default_factory=list)

    def render(self) -> str:
        return "\n".join(card.render() for card in self.cards)


class Recap:
    """Collects user-owned events and computes yearly recap cards."""

    def __init__(self) -> None:
        self._events: List[Event] = []

    def add_event(
        self, day: str, category: str, label: str, value: float = 1.0
    ) -> Event:
        date.fromisoformat(day)  # validate
        if not category or not label:
            raise ValueError("category and label must not be empty")
        event = Event(day, category, label, value)
        self._events.append(event)
        return event

    def years(self) -> List[int]:
        return sorted({int(e.day[:4]) for e in self._events})

    def recap(self, year: int) -> YearRecap:
        events = [e for e in self._events if int(e.day[:4]) == year]
        cards: List[Card] = []
        if not events:
            return YearRecap(
                year, [Card(f"{year} in review", ["No events recorded this year."])]
            )

        # --- by the numbers ------------------------------------------------
        per_cat = Counter(e.category for e in events)
        totals: Dict[str, float] = defaultdict(float)
        active_days: Dict[str, set] = defaultdict(set)
        for e in events:
            totals[e.category] += e.value
            active_days[e.category].add(e.day)
        numbers = Card(f"{year} by the numbers", [f"{len(events)} moments logged"])
        for cat in sorted(per_cat):
            numbers.lines.append(
                f"{cat}: {per_cat[cat]} events, {totals[cat]:g} total, "
                f"{len(active_days[cat])} active days"
            )
        cards.append(numbers)

        # --- top shelf ------------------------------------------------------
        label_totals: Dict[str, Dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        for e in events:
            label_totals[e.category][e.label] += e.value
        top = Card(f"{year} top shelf")
        for cat in sorted(label_totals):
            ranked = sorted(
                label_totals[cat].items(), key=lambda kv: kv[1], reverse=True
            )[:3]
            for i, (label, val) in enumerate(ranked, 1):
                top.lines.append(f"{cat} #{i}: {label} ({val:g})")
        cards.append(top)

        # --- milestones: firsts and personal bests ---------------------------
        first_seen: Dict[str, str] = {}
        for e in sorted(events, key=lambda e: e.day):
            first_seen.setdefault((e.category, e.label), e.day)
        firsts = sorted(first_seen.items(), key=lambda kv: kv[1])[:5]
        best_day: Dict[str, tuple] = {}
        per_day: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for e in events:
            per_day[e.category][e.day] += e.value
        for cat, days in per_day.items():
            best = max(days.items(), key=lambda kv: kv[1])
            best_day[cat] = best
        miles = Card(f"{year} milestones")
        for (cat, label), day in firsts:
            miles.lines.append(f"first {cat} — {label} ({day})")
        for cat in sorted(best_day):
            day, val = best_day[cat]
            miles.lines.append(f"best {cat} day — {val:g} on {day}")
        cards.append(miles)

        # --- rhythm ----------------------------------------------------------
        weekdays = Counter(date.fromisoformat(e.day).strftime("%A") for e in events)
        months = Counter(date.fromisoformat(e.day).strftime("%B") for e in events)
        rhythm = Card(
            f"{year} rhythm",
            [
                f"busiest weekday: {weekdays.most_common(1)[0][0]}",
                f"busiest month: {months.most_common(1)[0][0]}",
            ],
        )
        cards.append(rhythm)

        return YearRecap(year, cards)

    def render_card(self, year: int, title: str) -> Optional[str]:
        for card in self.recap(year).cards:
            if card.title == title:
                return card.render()
        return None
