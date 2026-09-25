"""Split-screen local play: one screen, one copy, N viewports.

Studied from: games-deadmechanics-20260916/findings.jsonl
[arch-games-splitscreen] (Split-screen local play: one screen, one copy, N
viewports; one-purchase-four-player economics plus physical proximity as
social glue).

This is an original, from-scratch implementation for LEVI. ``ViewportLayout``
divides one logical screen into non-overlapping viewports, one per local
player. The layouts are the classic honest geometries:

- 1 player: the full screen.
- 2 players: side-by-side halves (vertical split) or stacked halves.
- 3 players: one wide top strip + two bottom quadrants.
- 4 players: four quadrants.

Each ``Viewport`` carries its rectangle (x, y, width, height in pixels), the
player it belongs to, and a focus flag. ``set_focus(player)`` is the
"one screen follows one player" move: it can optionally re-weight a viewport
larger while keeping all viewports non-overlapping (a *focus mode* with a
configurable emphasis factor). ``ViewportLayout.validate()`` proves the two
hard invariants: every viewport is inside the screen, and no two viewports
overlap.

Public surface:
- ``ViewportLayout.for_players(n, width, height, split="vertical")``.
- ``Viewport``: ``rect``, ``player``, ``area``, ``contains(x, y)``.
- ``set_focus(player, emphasis=1.5)``, ``clear_focus()``,
  ``viewport_for(player)``, ``validate()``.

Honest limits: this is a layout manager, not a renderer — it computes
rectangles; drawing pixels is the game's job. Focus emphasis keeps the
4-player invariant (nobody's viewport disappears) by clamping emphasis so
every viewport keeps at least a quarter of its original area.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


ORIGIN = "levi-revival/splitscreen"

Rect = Tuple[int, int, int, int]  # (x, y, width, height)


class SplitscreenError(ValueError):
    """Raised for invalid layouts or focus requests."""


@dataclass(frozen=True)
class Viewport:
    """One player's rectangle on the shared screen."""

    player: int
    rect: Rect
    focused: bool = False

    @property
    def area(self) -> int:
        _, _, w, h = self.rect
        return w * h

    def contains(self, x: int, y: int) -> bool:
        rx, ry, rw, rh = self.rect
        return rx <= x < rx + rw and ry <= y < ry + rh

    def shrink_to(self, rect: Rect) -> "Viewport":
        return Viewport(player=self.player, rect=rect, focused=self.focused)


@dataclass
class ViewportLayout:
    """N non-overlapping viewports on one screen of (width x height)."""

    width: int
    height: int
    viewports: Tuple[Viewport, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise SplitscreenError("screen dimensions must be positive")
        if not self.viewports:
            raise SplitscreenError("a layout needs at least one viewport")

    # -- construction --------------------------------------------------
    @classmethod
    def for_players(
        cls, n: int, width: int, height: int, split: str = "vertical"
    ) -> "ViewportLayout":
        """Build the classic layout for 1–4 players."""
        if not 1 <= n <= 4:
            raise SplitscreenError("split-screen supports 1 to 4 players")
        if split not in ("vertical", "horizontal"):
            raise SplitscreenError("split must be 'vertical' or 'horizontal'")

        def vp(player: int, rect: Rect) -> Viewport:
            return Viewport(player=player, rect=rect)

        hw, hh = width // 2, height // 2
        if n == 1:
            rects = [(0, 0, width, height)]
        elif n == 2:
            if split == "vertical":
                rects = [(0, 0, hw, height), (hw, 0, width - hw, height)]
            else:
                rects = [(0, 0, width, hh), (0, hh, width, height - hh)]
        elif n == 3:
            rects = [
                (0, 0, width, hh),
                (0, hh, hw, height - hh),
                (hw, hh, width - hw, height - hh),
            ]
        else:
            rects = [
                (0, 0, hw, hh),
                (hw, 0, width - hw, hh),
                (0, hh, hw, height - hh),
                (hw, hh, width - hw, height - hh),
            ]
        return cls(
            width=width,
            height=height,
            viewports=tuple(vp(i, r) for i, r in enumerate(rects)),
        )

    # -- queries -------------------------------------------------------
    def viewport_for(self, player: int) -> Viewport:
        for v in self.viewports:
            if v.player == player:
                return v
        raise SplitscreenError(f"no viewport for player {player}")

    def viewport_at(self, x: int, y: int) -> Optional[Viewport]:
        """Which player's viewport owns this pixel (None if outside screen)."""
        for v in self.viewports:
            if v.contains(x, y):
                return v
        return None

    def validate(self) -> List[str]:
        """Return a list of invariant violations (empty = layout is sound)."""
        problems: List[str] = []
        for v in self.viewports:
            x, y, w, h = v.rect
            if w <= 0 or h <= 0:
                problems.append(f"player {v.player}: degenerate rect {v.rect}")
            if x < 0 or y < 0 or x + w > self.width or y + h > self.height:
                problems.append(f"player {v.player}: rect {v.rect} outside screen")
        for i, a in enumerate(self.viewports):
            for b in self.viewports[i + 1 :]:
                if self._overlap(a.rect, b.rect):
                    problems.append(
                        f"players {a.player} and {b.player}: viewports overlap"
                    )
        return problems

    @staticmethod
    def _overlap(a: Rect, b: Rect) -> bool:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah

    # -- focus ---------------------------------------------------------
    def set_focus(self, player: int, emphasis: float = 1.5) -> "ViewportLayout":
        """Grow one viewport at the others' expense; nobody disappears.

        Emphasis is clamped so every viewport keeps at least a quarter of
        its original area — the 4-player social contract holds even in
        focus mode.
        """
        self.viewport_for(player)  # raises if unknown
        if emphasis < 1.0:
            raise SplitscreenError("emphasis must be >= 1.0")
        # Re-layout: focused viewport takes a bigger share of the long axis.
        # Simplest honest approach: re-split the screen with weighted shares.
        n = len(self.viewports)
        weights = [emphasis if v.player == player else 1.0 for v in self.viewports]
        total = sum(weights)
        rects = self._weighted_row(weights, total)
        if n in (3, 4):
            # Keep the classic 2-row geometry, weighted within each row.
            rects = self._weighted_grid(player, emphasis)
        new_viewports = tuple(
            Viewport(player=v.player, rect=r, focused=(v.player == player))
            for v, r in zip(self.viewports, rects, strict=True)
        )
        layout = ViewportLayout(
            width=self.width, height=self.height, viewports=new_viewports
        )
        # Enforce the nobody-disappears invariant; fall back to unfocused.
        for v, orig in zip(new_viewports, self.viewports, strict=True):
            if v.area * 4 < orig.area:
                return self.clear_focus()
        return layout

    def _weighted_row(self, weights: List[float], total: float) -> List[Rect]:
        """Split the full screen into one horizontal row of weighted rects."""
        rects: List[Rect] = []
        x = 0
        for i, w in enumerate(weights):
            share = int(round(self.width * w / total))
            if i == len(weights) - 1:
                share = self.width - x  # absorb rounding on the last rect
            rects.append((x, 0, max(1, share), self.height))
            x += share
        return rects

    def _weighted_grid(self, focus_player: int, emphasis: float) -> List[Rect]:
        """Two-row grid (3 or 4 players) with the focused viewport weighted."""
        hh = self.height // 2
        rows: Dict[int, List[Viewport]] = {0: [], 1: []}
        for v in self.viewports:
            _, y, _, _ = v.rect
            rows[0 if y < hh else 1].append(v)
        rects: List[Rect] = [None] * len(self.viewports)  # type: ignore[list-item]
        for row_idx, row_vps in rows.items():
            y = 0 if row_idx == 0 else hh
            h = hh if row_idx == 0 else self.height - hh
            weights = [emphasis if v.player == focus_player else 1.0 for v in row_vps]
            total = sum(weights)
            x = 0
            for i, v in enumerate(row_vps):
                share = int(round(self.width * weights[i] / total))
                if i == len(row_vps) - 1:
                    share = self.width - x
                rects[v.player] = (x, y, max(1, share), h)
                x += share
        return rects

    def clear_focus(self) -> "ViewportLayout":
        """Back to the even split."""
        return ViewportLayout.for_players(len(self.viewports), self.width, self.height)
