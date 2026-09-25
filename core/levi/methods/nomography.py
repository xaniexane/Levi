"""Nomography: computation compiled into the artifact.

Origin: invented 1884 (some sources 1880) by Maurice d'Ocagne for
earth-moving volume equations; used daily by engineers into the 1970s. A
nomogram is three or more straight or curved scales on paper: lay a
straightedge across the known values and read the unknown where it crosses
its scale. The parallel-resistor chart was the electrical engineer's daily
tool. Multi-variable equations worked via concatenated charts and
translucent overlays of additional scale arrangements.

What it is in LEVI: a CompiledTable. Precompute a function over a grid
into lookup scales (the compilation step), then evaluate by interpolation
— the straightedge laid across the scales — at zero compute cost per
lookup. ``chain`` concatenates charts for multi-variable work (evaluate
the second chart at the first chart's reading); ``CompiledTable2D``
compiles a two-variable function into one chart with bilinear lookup.

Honesty label: LOAD-BEARING — precompute-then-interpolate is the actual
nomography mechanism: the function frozen into the artifact, read back
with a straightedge.

Deny-closed inputs: non-callable functions, fewer than 2 grid points,
inverted or empty ranges, non-finite values produced during compilation,
and evaluations outside the compiled range all raise ValueError.
"""

from __future__ import annotations

import math
from typing import Callable

__all__ = ["CompiledTable", "CompiledTable2D", "chain"]


def _check_func(func: Callable[[float], float], where: str) -> None:
    if not callable(func):
        raise ValueError(f"{where}: func must be callable")


def _check_grid(n: int, lo: float, hi: float, where: str) -> None:
    if n < 2:
        raise ValueError(f"{where}: need at least 2 grid points")
    if not (math.isfinite(lo) and math.isfinite(hi)):
        raise ValueError(f"{where}: range bounds must be finite")
    if lo >= hi:
        raise ValueError(f"{where}: need lo < hi, got {lo} >= {hi}")


class CompiledTable:
    """A function compiled into lookup scales; the straightedge is
    linear interpolation between the two bracketing grid points."""

    def __init__(
        self, func: Callable[[float], float], lo: float, hi: float, n: int = 101
    ) -> None:
        _check_func(func, "CompiledTable")
        _check_grid(n, lo, hi, "CompiledTable")
        self.lo = lo
        self.hi = hi
        self.n = n
        xs = [lo + (hi - lo) * i / (n - 1) for i in range(n)]
        ys: list[float] = []
        for x in xs:
            try:
                y = func(x)
            except Exception as exc:
                raise ValueError(f"func failed at x={x}: {exc}") from exc
            if not isinstance(y, (int, float)) or not math.isfinite(y):
                raise ValueError(f"func produced non-finite value at x={x}")
            ys.append(float(y))
        self._xs = xs
        self._ys = ys

    def evaluate(self, x: float) -> float:
        """Lay the straightedge: interpolate between bracketing scales."""
        if not isinstance(x, (int, float)) or not math.isfinite(x):
            raise ValueError(f"evaluate: x must be finite, got {x!r}")
        if not self.lo <= x <= self.hi:
            raise ValueError(f"x={x} outside compiled range [{self.lo}, {self.hi}]")
        # binary search for the bracketing interval
        lo_i, hi_i = 0, self.n - 1
        while hi_i - lo_i > 1:
            mid = (lo_i + hi_i) // 2
            if self._xs[mid] <= x:
                lo_i = mid
            else:
                hi_i = mid
        x0, x1 = self._xs[lo_i], self._xs[hi_i]
        y0, y1 = self._ys[lo_i], self._ys[hi_i]
        if x1 == x0:
            return y0
        t = (x - x0) / (x1 - x0)
        return y0 + t * (y1 - y0)

    def grid(self) -> list[tuple[float, float]]:
        return list(zip(self._xs, self._ys, strict=True))


def chain(first: CompiledTable, second: CompiledTable) -> Callable[[float], float]:
    """Concatenated charts: read the first chart, lay the straightedge on
    the second chart at that reading. Returns f(x) = second(first(x))."""
    if not isinstance(first, CompiledTable) or not isinstance(second, CompiledTable):
        raise ValueError("chain needs two CompiledTables")

    def chained(x: float) -> float:
        return second.evaluate(first.evaluate(x))

    return chained


class CompiledTable2D:
    """A two-variable function compiled into one chart; bilinear lookup."""

    def __init__(
        self,
        func: Callable[[float, float], float],
        x_lo: float,
        x_hi: float,
        nx: int,
        y_lo: float,
        y_hi: float,
        ny: int,
    ) -> None:
        _check_func(func, "CompiledTable2D")
        _check_grid(nx, x_lo, x_hi, "CompiledTable2D(x)")
        _check_grid(ny, y_lo, y_hi, "CompiledTable2D(y)")
        self.x_lo, self.x_hi, self.nx = x_lo, x_hi, nx
        self.y_lo, self.y_hi, self.ny = y_lo, y_hi, ny
        self._xs = [x_lo + (x_hi - x_lo) * i / (nx - 1) for i in range(nx)]
        self._ys = [y_lo + (y_hi - y_lo) * j / (ny - 1) for j in range(ny)]
        self._grid: list[list[float]] = []
        for x in self._xs:
            row: list[float] = []
            for y in self._ys:
                try:
                    v = func(x, y)
                except Exception as exc:
                    raise ValueError(f"func failed at ({x}, {y}): {exc}") from exc
                if not isinstance(v, (int, float)) or not math.isfinite(v):
                    raise ValueError(f"func produced non-finite value at ({x}, {y})")
                row.append(float(v))
            self._grid.append(row)

    def _bracket(self, v: float, pts: list[float], name: str) -> tuple[int, float]:
        lo_i, hi_i = 0, len(pts) - 1
        while hi_i - lo_i > 1:
            mid = (lo_i + hi_i) // 2
            if pts[mid] <= v:
                lo_i = mid
            else:
                hi_i = mid
        p0, p1 = pts[lo_i], pts[hi_i]
        t = 0.0 if p1 == p0 else (v - p0) / (p1 - p0)
        return lo_i, t

    def evaluate(self, x: float, y: float) -> float:
        for v, lo, hi, name in (
            (x, self.x_lo, self.x_hi, "x"),
            (y, self.y_lo, self.y_hi, "y"),
        ):
            if not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f"evaluate: {name} must be finite")
            if not lo <= v <= hi:
                raise ValueError(f"{name}={v} outside compiled range [{lo}, {hi}]")
        ix, tx = self._bracket(x, self._xs, "x")
        iy, ty = self._bracket(y, self._ys, "y")
        g = self._grid
        return (
            g[ix][iy] * (1 - tx) * (1 - ty)
            + g[ix + 1][iy] * tx * (1 - ty)
            + g[ix][iy + 1] * (1 - tx) * ty
            + g[ix + 1][iy + 1] * tx * ty
        )
