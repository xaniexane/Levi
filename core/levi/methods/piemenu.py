"""Radial marking menus: one gesture for novices and experts.

Origin: pie menus — Callahan, Hopkins, Weiser & Shneiderman (1988). Items in
a circle around the cursor: equal travel distance for every item, wedge
targets larger than linear rows, faster selection by Fitts' law. Marking
menus (Kurtenbach & Buxton) add the killer property: the SAME gesture selects
for the novice (the popup appears) and the expert (mouse-ahead, no popup).
One vocabulary, no separate accelerator keys — every novice selection
rehearses the expert gesture.

What it is in LEVI: ``RadialMenu``. Items sit on a circle; selection takes an
angle (a direction) and resolves it to an item. ``novice_select`` shows the
label popup first, ``expert_select`` takes the bare gesture — both resolve
through the identical angle-to-item path, so the rehearsal property holds by
construction, not by convention.

Honesty label: LOAD-BEARING — the angle-to-item geometry is a concrete
mechanism, identical in both modes.

Deny-closed inputs: fewer than two items, empty item names, duplicate item
names, and angles that are not finite numbers are all rejected with
ValueError.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = ["PieItem", "RadialMenu"]


@dataclass
class PieItem:
    """One wedge of the pie: a name and its center angle in degrees."""

    name: str
    center_degrees: float


class RadialMenu:
    """Items on a circle, selected by direction. Novices see the popup;
    experts draw the bare gesture; both resolve through one path."""

    def __init__(self, names: list[str]) -> None:
        if not isinstance(names, list) or len(names) < 2:
            raise ValueError("a radial menu needs at least two items")
        seen: set[str] = set()
        for name in names:
            if not isinstance(name, str) or not name.strip():
                raise ValueError("menu item names must be non-empty strings")
            name = name.strip()
            if name in seen:
                raise ValueError(f"duplicate menu item: {name!r}")
            seen.add(name)
        step = 360.0 / len(names)
        self._items = [
            PieItem(name=name.strip(), center_degrees=i * step)
            for i, name in enumerate(names)
        ]

    def __len__(self) -> int:
        return len(self._items)

    def labels(self) -> dict[str, float]:
        """What the novice's popup shows: every item and its center angle."""
        return {item.name: item.center_degrees for item in self._items}

    def _resolve(self, angle_degrees: float) -> PieItem:
        """The single angle->item path both modes share. Each item owns the
        wedge [center - step/2, center + step/2); a gesture exactly on a
        boundary belongs to the wedge that starts there."""
        if (
            isinstance(angle_degrees, bool)
            or not isinstance(angle_degrees, (int, float))
            or not math.isfinite(angle_degrees)
        ):
            raise ValueError(f"angle must be a finite number, got {angle_degrees!r}")
        n = len(self._items)
        step = 360.0 / n
        angle = float(angle_degrees) % 360.0
        index = int((angle + step / 2.0) // step) % n
        return self._items[index]

    def novice_select(self, angle_degrees: float) -> tuple[PieItem, dict[str, float]]:
        """The popup appears (labels shown), then the gesture resolves."""
        return self._resolve(angle_degrees), self.labels()

    def expert_select(self, angle_degrees: float) -> PieItem:
        """The bare gesture, no popup — same resolution as the novice's."""
        return self._resolve(angle_degrees)
