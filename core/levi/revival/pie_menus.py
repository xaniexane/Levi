"""Circular menus: equal travel for every item, wedge targets.

Studied from: interfaces-hunt-20260915/report.md [4. Pie and marking menus]

The studied shape: items arranged in a circle around the cursor —
every item is the same distance from the pointer, and wedge-shaped
targets are far larger than rows in a linear menu. Direction does
the selecting, distance barely matters.

LEVI-native re-expression: pure menu geometry. A **PieMenu** holds
items on equal angular sectors; ``select(dx, dy)`` maps a pointer
offset to the item under that angle, honoring a dead-zone radius
at the center. Sectors, neighbors, and angles are all queryable so
a host UI can draw them.

Operations:

* ``PieMenu(items, dead_radius=24.0)`` — items spaced evenly, first
  item centered on north, clockwise
* ``select(dx, dy)`` — item for a pointer offset, or ``None`` inside
  the dead zone
* ``angle_of(item)`` / ``sector_of(item)`` — center angle (degrees,
  clockwise from north) and ``(start, end)`` wedge bounds
* ``neighbor(item, step=1)`` — rotate selection without a pointer

Honest limits: geometry only — this module draws nothing and reads
no real pointer. Item order is fixed at construction; dynamic
reordering is the host's job.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, pi
from typing import Generic, List, Optional, Tuple, TypeVar

ORIGIN = "levi-revival/pie-menus"

T = TypeVar("T")


@dataclass
class Sector:
    item: object
    index: int
    start_deg: float  # wedge start, clockwise from north
    end_deg: float  # wedge end, clockwise from north
    center_deg: float


class PieMenu(Generic[T]):
    """Items on a circle; angle selects, distance is (almost) irrelevant."""

    def __init__(self, items: List[T], dead_radius: float = 24.0) -> None:
        if not items:
            raise ValueError("a pie menu needs at least one item")
        self.items: List[T] = list(items)
        self.dead_radius = dead_radius
        self._sweep = 360.0 / len(items)
        # First item centered on north (0°); wedges span ±sweep/2.
        self._sectors: List[Sector] = [
            Sector(
                item=item,
                index=i,
                start_deg=(i * self._sweep - self._sweep / 2) % 360.0,
                end_deg=(i * self._sweep + self._sweep / 2) % 360.0,
                center_deg=(i * self._sweep) % 360.0,
            )
            for i, item in enumerate(self.items)
        ]

    def __len__(self) -> int:  # noqa: D105
        return len(self.items)

    @staticmethod
    def _angle_deg(dx: float, dy: float) -> float:
        """Pointer angle in degrees, clockwise from north (y grows down)."""
        return (atan2(dx, -dy) * 180.0 / pi) % 360.0

    def _sector_at(self, angle: float) -> Sector:
        for s in self._sectors:
            if s.start_deg <= s.end_deg:
                if s.start_deg <= angle < s.end_deg:
                    return s
            else:  # wedge wraps 360°
                if angle >= s.start_deg or angle < s.end_deg:
                    return s
        return self._sectors[0]  # unreachable for angle in [0, 360)

    def select(self, dx: float, dy: float) -> Optional[T]:
        """Item under the pointer offset; ``None`` inside the dead zone."""
        if dx * dx + dy * dy < self.dead_radius * self.dead_radius:
            return None
        return self._sector_at(self._angle_deg(dx, dy)).item  # type: ignore[return-value]

    def angle_of(self, item: T) -> float:
        for s in self._sectors:
            if s.item == item:
                return s.center_deg
        raise KeyError(item)

    def sector_of(self, item: T) -> Tuple[float, float]:
        for s in self._sectors:
            if s.item == item:
                return (s.start_deg, s.end_deg)
        raise KeyError(item)

    def neighbor(self, item: T, step: int = 1) -> T:
        idx = self.items.index(item)
        return self.items[(idx + step) % len(self.items)]
