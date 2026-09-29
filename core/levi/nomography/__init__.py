"""nomography — printable SVG alignment charts (nomograms), stdlib-only.

Clean-room LEVI-native revival of d'Ocagne's nomography (1880s;
perpetual-hunt daily 2026-09-27, record
``arch-method-nomography-alignment-charts``): compile an equation into
*geometry* — parallel scales with deliberately transformed graduations, so
that a straightedge (the index line / isopleth) laid across two known
values crosses the third scale at the answer. No power, no arithmetic,
workshop-grade precision. This is NOT any product's code; the construction
math is public domain (d'Ocagne d. 1938), reimplemented from first
principles.

The supported form is the classic three-parallel-scale alignment chart for
equations of the shape::

    f1(u) + f2(v) = f3(w)

which also covers products (log scales: log a + log b = log c), ratios
(reciprocal scales), and plain sums. The three axes sit at x = 0, m, 2m;
the outer axes carry scales f1 and f2, the middle axis carries f3/2 —
because a straight line through (0, f1(u)) and (2m, f2(v)) crosses x = m
at exactly (f1(u) + f2(v)) / 2.

LAWS (declared first, proved by tests/test_nomography.py):
  L1 collinearity — for any u, v with w solving f3(w) = f1(u)+f2(v), the
     isopleth through the u and v points crosses the middle axis exactly
     at the w point. Geometry IS the equation.
  L2 honest solving — ``solve_w`` returns None (not a guess) when the
     target lies outside the w scale's range; it requires f3 monotonic.
  L3 tick fidelity — the first and last ticks sit exactly at lo and hi.

Public API:
    addition_nomogram(f1, f2, f3, r1, r2, r3, labels, title="",
                      isopleth_uv=None, width=640, height=800) -> str (SVG)
    parallel_nomogram(scales, title="", isopleth=None, ...) -> str (SVG)
    solve_w(f3, target, lo, hi, tol=1e-9) -> float | None
    Scale  (dataclass: x, y_of, lo, hi, label, ticks)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape as _escape

__all__ = [
    "Scale",
    "addition_nomogram",
    "parallel_nomogram",
    "solve_w",
    "isopleth_points",
]

_YOf = Callable[[float], float]


@dataclass
class Scale:
    """One vertical axis of the chart.

    x:      horizontal position as a fraction of the plot width (0..1)
    y_of:   scale function mapping a value to chart-y units (must be
            monotonic over [lo, hi]; e.g. ``lambda v: v`` or ``math.log10``)
    lo/hi:  value range; ticks: number of graduations (>= 2)
    label:  axis caption
    """
    x: float
    y_of: _YOf
    lo: float
    hi: float
    label: str
    ticks: int = 11


def solve_w(f3: _YOf, target: float, lo: float, hi: float,
            tol: float = 1e-9) -> Optional[float]:
    """Invert f3 by bisection: find w with f3(w) == target. L2.

    Returns None when the target is outside [f3(lo), f3(hi)] (either
    orientation) instead of guessing. Requires f3 monotonic on [lo, hi].
    """
    flo, fhi = f3(lo), f3(hi)
    increasing = fhi >= flo
    inside = (flo - tol <= target <= fhi + tol) if increasing else \
             (fhi - tol <= target <= flo + tol)
    if not inside:
        return None
    a, b = lo, hi
    fa = f3(a) - target
    for _ in range(200):
        m = 0.5 * (a + b)
        fm = f3(m) - target
        if abs(fm) <= tol or b - a <= tol:
            return m
        if (fa <= 0) == (fm <= 0):
            a, fa = m, fm
        else:
            b = m
    return 0.5 * (a + b)


def isopleth_points(scales: Sequence[Scale],
                    values: Sequence[float]) -> List[Tuple[float, float]]:
    """(x fraction, y units) for each scale at the given values. L1's stage."""
    return [(s.x, s.y_of(v)) for s, v in zip(scales, values)]


def _y_extent(scales: Sequence[Scale]) -> Tuple[float, float]:
    ymin, ymax = math.inf, -math.inf
    for s in scales:
        for i in range(51):
            v = s.lo + (s.hi - s.lo) * i / 50
            y = s.y_of(v)
            ymin, ymax = min(ymin, y), max(ymax, y)
    if not (ymax > ymin):
        raise ValueError("degenerate scale: y range is empty")
    return ymin, ymax


def _fmt(v: float) -> str:
    if v == int(v) and abs(v) < 1e12:
        return str(int(v))
    return "%g" % v


def parallel_nomogram(scales: Sequence[Scale], title: str = "",
                      isopleth: Optional[Sequence[float]] = None,
                      width: int = 640, height: int = 800,
                      margin: int = 70) -> str:
    """Emit the chart as an SVG string.

    ``isopleth``: one value per scale — the straight index line is drawn
    through the corresponding points.
    """
    scales = list(scales)
    if len(scales) < 2:
        raise ValueError("need at least two scales")
    ymin, ymax = _y_extent(scales)
    pw, ph = width - 2 * margin, height - 2 * margin

    def px(xf: float) -> float:
        return margin + xf * pw

    def py(y: float) -> float:
        return margin + ph - (y - ymin) / (ymax - ymin) * ph

    parts: List[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d" font-family="serif">' % (width, height, width, height),
    ]
    if title:
        parts.append(
            '<text x="%d" y="36" text-anchor="middle" font-size="20">%s</text>'
            % (width // 2, _escape(title)))
    for s in scales:
        x = px(s.x)
        y_top, y_bot = py(s.y_of(s.hi)), py(s.y_of(s.lo))
        # L3: ticks span exactly [lo, hi]
        parts.append(
            '<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="black" '
            'stroke-width="2"/>' % (x, y_top, x, y_bot))
        n = max(2, s.ticks)
        for i in range(n):
            v = s.lo + (s.hi - s.lo) * i / (n - 1)
            yy = py(s.y_of(v))
            parts.append(
                '<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="black"/>'
                % (x - 6, yy, x + 6, yy))
            parts.append(
                '<text x="%.2f" y="%.2f" text-anchor="end" font-size="11" '
                'dominant-baseline="middle">%s</text>'
                % (x - 10, yy, _escape(_fmt(v))))
        parts.append(
            '<text x="%.2f" y="%.2f" text-anchor="middle" font-size="14" '
            'font-style="italic">%s</text>' % (x, height - 24, _escape(s.label)))
    if isopleth is not None:
        if len(isopleth) != len(scales):
            raise ValueError("isopleth needs one value per scale")
        pts = ["%.2f,%.2f" % (px(s.x), py(s.y_of(v)))
               for s, v in zip(scales, isopleth)]
        parts.append(
            '<polyline points="%s" fill="none" stroke="crimson" '
            'stroke-width="2"/>' % " ".join(pts))
        for pt in pts:
            x_s, y_s = pt.split(",")
            parts.append(
                '<circle cx="%s" cy="%s" r="4" fill="crimson"/>' % (x_s, y_s))
    parts.append("</svg>")
    return "\n".join(parts)


def addition_nomogram(f1: _YOf, f2: _YOf, f3: _YOf,
                      r1: Tuple[float, float], r2: Tuple[float, float],
                      r3: Tuple[float, float], labels: Tuple[str, str, str],
                      title: str = "",
                      isopleth_uv: Optional[Tuple[float, float]] = None,
                      width: int = 640, height: int = 800,
                      ticks: int = 11) -> str:
    """Build the classic 3-parallel-scale chart for f1(u)+f2(v)=f3(w).

    Middle axis carries f3/2 at x = 0.5 (the collinearity construction).
    ``isopleth_uv``: draw the index line for known (u, v); w is solved
    honestly via ``solve_w`` — no line is drawn when it is out of range.
    """
    mid = lambda w: f3(w) / 2.0  # noqa: E731
    scales = [
        Scale(0.0, f1, r1[0], r1[1], labels[0], ticks),
        Scale(0.5, mid, r3[0], r3[1], labels[2], ticks),
        Scale(1.0, f2, r2[0], r2[1], labels[1], ticks),
    ]
    iso = None
    if isopleth_uv is not None:
        u, v = isopleth_uv
        w = solve_w(f3, f1(u) + f2(v), r3[0], r3[1])
        if w is not None:
            iso = [u, w, v]
    return parallel_nomogram(scales, title=title, isopleth=iso,
                             width=width, height=height)
