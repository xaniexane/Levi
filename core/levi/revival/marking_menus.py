"""One stroke vocabulary for novice and expert: marking menus.

Studied from: interfaces-hunt-20260915/report.md [4. Pie and marking menus]

The studied shape: the *same* gesture selects for both the novice
and the expert. The novice presses, waits — the pie pops up, they
steer into a wedge. The expert presses and strokes without waiting —
"mouse-ahead" — and the same stroke fires the same item with no
popup. One vocabulary, no separate accelerator keys to learn.

LEVI-native re-expression: a stroke-driven hierarchical menu. Each
item owns a direction path (e.g. ``["E", "S"]`` = east then south).
A **StrokeRecorder** turns a pointer trail into a direction string;
``MarkingMenu.recognize`` matches it against the menu tree. The
novice/expert difference is only whether the popup was shown — both
paths call the same matcher.

Operations:

* ``MarkingMenu(items)`` — items as ``(name, path)`` or ``MenuItem``;
  paths use N/NE/E/SE/S/SW/W/NW
* ``recognize(stroke)`` — ``"exact"`` (one full match),
  ``"prefix"`` (stroke is a prefix of deeper items → show the popup
  submenu), or ``"none"``
* ``popup_options(stroke)`` — submenu items valid after a partial stroke
* ``novice_select(stroke)`` / ``expert_select(stroke)`` — same
  matching; novice returns the submenu when the stroke is a prefix,
  expert resolves to the unique exact match or ``None``

Honest limits: stroke recognition reuses the same compass
quantization heuristics as ``mouse_gestures`` — ambiguous trails can
land on prefix matches. Menus deeper than the recorded stroke depth
are unreachable until the stroke continues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, hypot
from typing import List, Optional, Tuple

ORIGIN = "levi-revival/marking-menus"

_COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def quantize(trail: List[Tuple[float, float]]) -> List[str]:
    """Compress a pointer trail into direction tokens (N/NE/E/...).

    Consecutive duplicates collapse; sub-10px jitter is dropped.
    """
    out: List[str] = []
    for (x0, y0), (x1, y1) in zip(trail, trail[1:], strict=False):
        dx, dy = x1 - x0, y1 - y0
        if hypot(dx, dy) < 10.0:
            continue
        idx = int(round(atan2(dx, -dy) / (3.141592653589793 / 4))) % 8
        d = _COMPASS[idx]
        if not out or out[-1] != d:
            out.append(d)
    return out


@dataclass
class MenuItem:
    name: str
    path: List[str] = field(default_factory=list)  # direction tokens
    action: str = ""

    def __post_init__(self) -> None:
        for d in self.path:
            if d not in _COMPASS:
                raise ValueError(f"bad direction token {d!r} in {self.name!r}")


class MarkingMenu:
    """Hierarchical menu where a stroke *is* the selection."""

    def __init__(self, items: List[MenuItem]) -> None:
        self.items = list(items)
        seen = set()
        for it in self.items:
            key = tuple(it.path)
            if key in seen:
                raise ValueError(f"duplicate stroke path {key}")
            seen.add(key)

    def recognize(self, stroke: List[str]) -> str:
        """``"exact"`` / ``"prefix"`` / ``"none"`` for ``stroke``."""
        s = tuple(stroke)
        exact = any(tuple(it.path) == s for it in self.items)
        if exact:
            return "exact"
        if any(
            tuple(it.path)[: len(s)] == s and len(it.path) > len(s) for it in self.items
        ):
            return "prefix"
        return "none"

    def popup_options(self, stroke: List[str]) -> List[MenuItem]:
        """Submenu items reachable by continuing ``stroke`` one step."""
        s = tuple(stroke)
        out = []
        for it in self.items:
            p = tuple(it.path)
            if len(p) == len(s) + 1 and p[: len(s)] == s:
                out.append(it)
        return out

    def _exact(self, stroke: List[str]) -> Optional[MenuItem]:
        s = tuple(stroke)
        for it in self.items:
            if tuple(it.path) == s:
                return it
        return None

    def novice_select(
        self, stroke: List[str]
    ) -> Tuple[Optional[MenuItem], List[MenuItem]]:
        """Novice flow: popup appears. Returns (selected, submenu-shown).

        A full stroke selects immediately; a prefix stroke shows the
        submenu options; a dead stroke shows the top-level options.
        """
        state = self.recognize(stroke)
        if state == "exact":
            return (self._exact(stroke), [])
        if state == "prefix":
            return (None, self.popup_options(stroke))
        return (None, self.popup_options([]))

    def expert_select(self, stroke: List[str]) -> Optional[MenuItem]:
        """Expert flow: mouse-ahead, no popup. Same matcher, no submenu."""
        if self.recognize(stroke) == "exact":
            return self._exact(stroke)
        return None

    def learn_path(self, name: str) -> Optional[List[str]]:
        """Stroke path for ``name`` — what the novice sees in the popup
        and internalizes into expert muscle memory."""
        for it in self.items:
            if it.name == name:
                return list(it.path)
        return None
