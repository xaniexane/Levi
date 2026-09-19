"""Keyboard-only link jumping over a two-dimensional layout.

Studied from: desktop-casualties-20260916/report.md [1. Opera]

The studied shape: spatial navigation moves keyboard focus through
links and controls by direction — Shift+arrows jump to the nearest
element *up/down/left/right* of the current one — so a page is fully
operable without a pointer.

LEVI-native re-expression: a geometric focus engine. A **SpatialMap**
holds focusable elements as rectangles; ``move(focus, direction)``
picks the best candidate in that direction using an angle-plus-distance
score, and incremental label typing jumps straight to a named element.

Operations:

* ``SpatialMap.add(id, label, x, y, w, h)`` — register a focusable rect
* ``SpatialMap.move(focus_id, direction)`` — best neighbor
  (``"up"|"down"|"left"|"right"``); ``None`` if nothing lies that way
* ``SpatialMap.jump(label_prefix)`` — first element whose label starts
  with the typed prefix (case-insensitive)
* ``SpatialMap.nearest(x, y)`` — element whose center is closest to a point

Honest limits: "best neighbor" is a heuristic — it scores candidates
by angular deviation from the requested direction weighted against
distance, which matches human expectation most of the time but can
surprise on dense or overlapping layouts. Wrap-around is opt-in.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, hypot, pi
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/spatial-nav"

_DIRS = {"up", "down", "left", "right"}
# Ideal bearing for each direction, measured clockwise from north.
_IDEAL = {"up": 0.0, "right": pi / 2, "down": pi, "left": 3 * pi / 2}


@dataclass
class Element:
    id: str
    label: str
    x: float
    y: float
    w: float
    h: float

    def center(self) -> Tuple[float, float]:
        return (self.x + self.w / 2.0, self.y + self.h / 2.0)


class SpatialMap:
    """Focusable elements on a plane, navigable by direction."""

    def __init__(self, wrap: bool = False) -> None:
        self.elements: Dict[str, Element] = {}
        self.order: List[str] = []
        self.wrap = wrap

    def add(
        self, id: str, label: str, x: float, y: float, w: float, h: float
    ) -> Element:
        el = Element(id=id, label=label, x=x, y=y, w=w, h=h)
        self.elements[id] = el
        if id not in self.order:
            self.order.append(id)
        return el

    def remove(self, id: str) -> None:
        self.elements.pop(id, None)
        if id in self.order:
            self.order.remove(id)

    @staticmethod
    def _bearing(frm: Tuple[float, float], to: Tuple[float, float]) -> float:
        cx0, cy0 = frm
        cx1, cy1 = to
        return atan2(cx1 - cx0, -(cy1 - cy0)) % (2 * pi)

    def _score(
        self, frm: Tuple[float, float], to: Tuple[float, float], direction: str
    ) -> Optional[float]:
        """Heuristic score; higher is better. None if the candidate is
        behind the requested direction (more than 90° off bearing)."""
        bx, by = frm, to
        bearing = self._bearing(bx, by)
        dev = abs((bearing - _IDEAL[direction] + pi) % (2 * pi) - pi)
        if dev >= pi / 2:
            return None
        d = hypot(to[0] - frm[0], to[1] - frm[1])
        if d == 0:
            return None
        # Angular alignment dominates; distance breaks ties.
        return (1.0 - dev / (pi / 2)) * 1000.0 / (1.0 + d)

    def move(self, focus_id: str, direction: str) -> Optional[str]:
        """Best element from ``focus_id`` in ``direction``.

        Returns ``None`` when nothing lies that way (or when
        ``wrap`` is off and the current element is unknown).
        """
        if direction not in _DIRS:
            raise ValueError(f"direction must be one of {sorted(_DIRS)}")
        cur = self.elements.get(focus_id)
        if cur is None:
            return None
        c0 = cur.center()
        best: Optional[Tuple[float, str]] = None
        for eid, el in self.elements.items():
            if eid == focus_id:
                continue
            s = self._score(c0, el.center(), direction)
            if s is not None and (best is None or s > best[0]):
                best = (s, eid)
        if best is not None:
            return best[1]
        if self.wrap and self.order:
            # Wrap to the farthest element in the requested direction.
            axis = 0 if direction in ("left", "right") else 1
            rev = direction in ("left", "up")  # wrap to the far edge
            key = lambda e: self.elements[e].center()[axis]  # noqa: E731
            return sorted(self.order, key=key, reverse=rev)[0]
        return None

    def jump(self, label_prefix: str) -> Optional[str]:
        """First element (registration order) whose label starts with
        ``label_prefix``, case-insensitive. Returns ``None`` on no match."""
        p = label_prefix.lower()
        for eid in self.order:
            if self.elements[eid].label.lower().startswith(p):
                return eid
        return None

    def nearest(self, x: float, y: float) -> Optional[str]:
        best: Optional[Tuple[float, str]] = None
        for eid, el in self.elements.items():
            cx, cy = el.center()
            d = hypot(cx - x, cy - y)
            if best is None or d < best[0]:
                best = (d, eid)
        return best[1] if best else None
