"""LEVI's knotted-cord ledger: positional, tactile, hierarchical data.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #38)

The old mechanism: information tied into cord. A cord carries four
dimensions at once — *knot type* (what kind of thing), *position* (which
digit: units, tens, hundreds), *color* (which category), and *level* (daily
cords knot into weekly cords, weekly into monthly). The data has a body:
you can hold a number in your hand and feel where it sits.

This module implements all four dimensions and the load-bearing trick,
the *roll-up*: child cords report their totals upward, and a parent cord's
value is the sum of its children — computed automatically, never typed.
Numbers encode as knot sequences per position (a base-10 digit per knot
cluster); decode reads them back. Colors mark categories; knot types mark
meaning; levels form the hierarchy.

A ``Quipu`` is a small forest of cords. ``roll_up`` walks it bottom-up and
fills every parent's ``rolled_value`` from its children. ``encode_number``
/ ``decode_number`` handle the knot↔digit mapping.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

ORIGIN = "levi-revival/quipu"


class KnotType(Enum):
    """What kind of mark the knot is: meaning lives in the shape."""

    SINGLE = "single"  # unit counter knot
    LONG = "long"  # multi-turn knot, higher magnitudes
    FIGURE8 = "figure8"  # the ones digit (the anchor knot)
    TALLY = "tally"  # simple tick, non-numeric mark


class CordLevel(Enum):
    """Hierarchy: daily knots into weekly, weekly into monthly."""

    DAILY = 0
    WEEKLY = 1
    MONTHLY = 2
    YEARLY = 3


@dataclass
class Knot:
    """One knot: type × position (digit place) × count of turns/clusters."""

    knot_type: KnotType
    position: int  # 0 = ones, 1 = tens, 2 = hundreds, ...
    turns: int  # how many loops/ticks: the digit value (0-9)

    def __post_init__(self) -> None:
        if self.position < 0:
            raise ValueError("knot position must be >= 0")
        if not 0 <= self.turns <= 9:
            raise ValueError("knot turns must be a single digit 0-9")


@dataclass
class Cord:
    """One cord: colored, leveled, knotted, optionally parenting children."""

    name: str
    color: str
    level: CordLevel
    knots: List[Knot] = field(default_factory=list)
    children: List["Cord"] = field(default_factory=list)
    rolled_value: Optional[int] = None  # filled by roll_up on parents

    # -- the cord's own value, read straight from its knots ---------------

    @property
    def own_value(self) -> int:
        """Sum over knot clusters: turns × 10**position."""
        return sum(k.turns * (10**k.position) for k in self.knots)

    def knot(self, knot_type: KnotType, position: int, turns: int) -> "Cord":
        self.knots.append(Knot(knot_type, position, turns))
        return self

    def tie_child(self, child: "Cord") -> "Cord":
        """Knot a child cord into this one. Child must be exactly one level down."""
        if child.level.value != self.level.value - 1:
            raise ValueError(
                f"cannot tie {child.level.name} cord into {self.level.name} cord: "
                "children must be exactly one level below"
            )
        self.children.append(child)
        return self


def encode_number(value: int, figure8_for_ones: bool = True) -> List[Knot]:
    """Encode a non-negative integer as a knot sequence, ones closest to the end.

    Knot types carry the old shape: figure-8 for the ones place, long knots
    for higher places. A zero digit is an empty position (a gap, not a knot).
    """
    if value < 0:
        raise ValueError("quipu encodes non-negative integers")
    knots: List[Knot] = []
    digits = [int(d) for d in str(value)] or [0]
    for position, digit in enumerate(reversed(digits)):
        if digit == 0:
            continue  # zero is a gap between knots
        ktype = (
            KnotType.FIGURE8 if (position == 0 and figure8_for_ones) else KnotType.LONG
        )
        knots.append(Knot(ktype, position, digit))
    return knots


def decode_number(knots: List[Knot]) -> int:
    """Read a knot sequence back into an integer."""
    return sum(k.turns * (10**k.position) for k in knots)


@dataclass
class Quipu:
    """A forest of cords with automatic bottom-up roll-up."""

    cords: List[Cord] = field(default_factory=list)

    def add(self, cord: Cord) -> "Quipu":
        self.cords.append(cord)
        return self

    def roll_up(self) -> Dict[str, int]:
        """Aggregate child totals upward. Returns {cord_name: rolled_value}.

        A parent's rolled value is the sum of its children's *effective*
        values (their own rolled values if they have children, else their
        own knot values). Leaf cords keep their knot values untouched —
        roll-up never rewrites what the knots say.
        """
        results: Dict[str, int] = {}

        def effective(cord: Cord) -> int:
            if cord.children:
                total = sum(effective(c) for c in cord.children)
                cord.rolled_value = total
            else:
                total = cord.own_value
            results[cord.name] = (
                cord.rolled_value if cord.rolled_value is not None else total
            )
            return total

        for cord in self.cords:
            effective(cord)
        return results

    def level_totals(self) -> Dict[str, int]:
        """Sum of effective values per level across the whole quipu."""
        totals: Dict[str, int] = {}
        seen: Dict[int, Cord] = {}

        def visit(cord: Cord) -> None:
            seen[id(cord)] = cord
            for child in cord.children:
                visit(child)

        for cord in self.cords:
            visit(cord)
        for cord in seen.values():
            value = (
                cord.rolled_value if cord.rolled_value is not None else cord.own_value
            )
            totals[cord.level.name] = totals.get(cord.level.name, 0) + value
        return totals

    def census(self) -> Dict[str, int]:
        """Knot-type census: how many knots of each type across all cords."""
        counts: Dict[str, int] = {}

        def visit(cord: Cord) -> None:
            for k in cord.knots:
                counts[k.knot_type.value] = counts.get(k.knot_type.value, 0) + 1
            for child in cord.children:
                visit(child)

        for cord in self.cords:
            visit(cord)
        return counts


def demo() -> Dict[str, object]:
    """Three daily cords (grain harvest) roll into one weekly cord."""
    q = Quipu()
    monday = Cord("monday", "goldenrod", CordLevel.DAILY)
    for k in encode_number(132):
        monday.knots.append(k)
    tuesday = Cord("tuesday", "goldenrod", CordLevel.DAILY)
    for k in encode_number(98):
        tuesday.knots.append(k)
    wednesday = Cord("wednesday", "goldenrod", CordLevel.DAILY)
    for k in encode_number(210):
        wednesday.knots.append(k)
    week = Cord("harvest-week-1", "crimson", CordLevel.WEEKLY)
    week.tie_child(monday).tie_child(tuesday).tie_child(wednesday)
    q.add(week)
    rolled = q.roll_up()
    return {
        "rolled": rolled,  # weekly total = 440
        "level_totals": q.level_totals(),
        "roundtrip": decode_number(encode_number(2026)),
        "census": q.census(),
    }


if __name__ == "__main__":
    print(json.dumps(demo(), indent=2))
