"""Pointing across window boundaries (transpointing).

Studied from: interfaces-hunt-20260915/report.md [1. Project Xanadu]

Functional description: each window owns its own local coordinate frame,
but the user sees one shared canvas. A *transpoint* is a link from an
anchor inside one window to a location inside another window — pointing
across the boundary between them. The module owns only this
cross-boundary interaction: window frames on a shared canvas, global<->local
coordinate translation, and transpoint links with honest resolution.

Care note: adjacent to ``levi.revival.xanadu``. This module does NOT rebuild
transclusion; it models pointing across window boundaries only.

Pure Python, stdlib only. No provider branding. Not artificial — synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/transpointing"


@dataclass
class Window:
    """A window: a local coordinate frame placed on the shared canvas."""

    id: str
    x: int
    y: int
    width: int
    height: int
    title: str = ""


@dataclass
class Transpoint:
    """A pointer from an anchor in one window to a spot in another."""

    id: int
    from_window: str
    from_point: Tuple[int, int]  # local coords in the source window
    to_window: str
    to_point: Tuple[int, int]  # local coords in the target window
    label: str = ""


class PointingSpace:
    """Shared canvas of windows with cross-boundary pointing links."""

    def __init__(self) -> None:
        self._windows: Dict[str, Window] = {}
        self._points: Dict[int, Transpoint] = {}
        self._next_id = 1

    # -- windows ---------------------------------------------------------
    def add_window(
        self, id: str, x: int, y: int, width: int, height: int, title: str = ""
    ) -> Window:
        if id in self._windows:
            raise ValueError(f"window already exists: {id!r}")
        if width <= 0 or height <= 0:
            raise ValueError("window dimensions must be positive")
        win = Window(id, x, y, width, height, title)
        self._windows[id] = win
        return win

    def remove_window(self, id: str) -> bool:
        if id not in self._windows:
            return False
        del self._windows[id]
        # transpoints touching a removed window no longer resolve
        self._points = {
            pid: p
            for pid, p in self._points.items()
            if p.from_window != id and p.to_window != id
        }
        return True

    def window_at(self, gx: int, gy: int) -> Optional[Window]:
        """Topmost window containing a global canvas point (last added wins)."""
        hit: Optional[Window] = None
        for win in self._windows.values():
            if win.x <= gx < win.x + win.width and win.y <= gy < win.y + win.height:
                hit = win
        return hit

    def to_global(self, window_id: str, lx: int, ly: int) -> Tuple[int, int]:
        win = self._windows[window_id]
        return (win.x + lx, win.y + ly)

    def to_local(self, window_id: str, gx: int, gy: int) -> Tuple[int, int]:
        win = self._windows[window_id]
        lx, ly = gx - win.x, gy - win.y
        if not (0 <= lx < win.width and 0 <= ly < win.height):
            raise ValueError(
                f"global point ({gx},{gy}) is outside window {window_id!r}"
            )
        return (lx, ly)

    def point(self, gx: int, gy: int) -> Tuple[Window, Tuple[int, int]]:
        """Point at the canvas: returns (window, local coords)."""
        win = self.window_at(gx, gy)
        if win is None:
            raise ValueError(f"no window at global point ({gx},{gy})")
        return win, self.to_local(win.id, gx, gy)

    # -- transpoints -----------------------------------------------------
    def transpoint(
        self,
        from_window: str,
        from_point: Tuple[int, int],
        to_window: str,
        to_point: Tuple[int, int],
        label: str = "",
    ) -> Transpoint:
        """Draw a pointer from an anchor in one window to another window."""
        if from_window not in self._windows or to_window not in self._windows:
            raise KeyError("both windows must exist")
        for wid, pt in ((from_window, from_point), (to_window, to_point)):
            win = self._windows[wid]
            if not (0 <= pt[0] < win.width and 0 <= pt[1] < win.height):
                raise ValueError(f"point {pt} is outside window {wid!r}")
        tp = Transpoint(
            self._next_id, from_window, from_point, to_window, to_point, label
        )
        self._next_id += 1
        self._points[tp.id] = tp
        return tp

    def remove_transpoint(self, tp_id: int) -> bool:
        return self._points.pop(tp_id, None) is not None

    def follow(self, tp_id: int) -> Tuple[str, Tuple[int, int], Tuple[int, int]]:
        """Resolve a transpoint: (target window, local point, global point)."""
        tp = self._points[tp_id]
        gx, gy = self.to_global(tp.to_window, *tp.to_point)
        return tp.to_window, tp.to_point, (gx, gy)

    def from_window(self, window_id: str) -> List[Transpoint]:
        return [p for p in self._points.values() if p.from_window == window_id]

    def into_window(self, window_id: str) -> List[Transpoint]:
        return [p for p in self._points.values() if p.to_window == window_id]

    def windows(self) -> List[Window]:
        return list(self._windows.values())


def demo_pointing() -> Dict[str, object]:
    space = PointingSpace()
    space.add_window("notes", 0, 0, 40, 20, "Notes")
    space.add_window("plan", 45, 5, 40, 20, "Plan")
    tp = space.transpoint("notes", (5, 5), "plan", (10, 2), label="see-also")
    win, local = space.point(50, 7)
    return {
        "pointed": {"window": win.id, "local": list(local)},
        "follow": space.follow(tp.id),
        "into_plan": [p.label for p in space.into_window("plan")],
    }


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(demo_pointing(), indent=2))
