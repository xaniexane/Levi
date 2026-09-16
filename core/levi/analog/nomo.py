"""Nomograph engine — d'Ocagne's paper computers, LEVI-native.

A Z-chart (parallel-scale) nomograph solves equations of the family

    X(u) + Y(v) = Z(w)

with one straight line: pick u on the left scale and v on the middle
scale, draw the line through both, read w where it crosses the right
scale. Zero energy, survives any outage, and it teaches the *shape* of an
equation — something a calculator never shows.

LEVI's remix: the same chart is drawn twice — once as ASCII for the
terminal, once as SVG for printing — and the accuracy note is *computed*
(the bisection residual over the chart's own isopleths), never promised.
Solves are bounded bisection; an unbracketed target raises instead of
guessing.

Classic example: X(u) = log10(u), Y(v) = log10(v), Z(w) = log10(w) turns
u * v = w into a slide-rule chart (the wire-gauge style the old radio
handbooks carried).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple


@dataclass
class Nomograph:
    """One Z-chart nomograph for X(u) + Y(v) = Z(w).

    X, Y, Z are user-supplied *monotone* scale functions (callables); the
    ranges are (lo, hi) tuples for the underlying variables.
    """

    X: Callable[[float], float]
    Y: Callable[[float], float]
    Z: Callable[[float], float]
    u_range: Tuple[float, float]
    v_range: Tuple[float, float]
    w_range: Tuple[float, float]
    u_name: str = "u"
    v_name: str = "v"
    w_name: str = "w"
    tol: float = 1e-12
    max_iter: int = 200

    # -- solving ---------------------------------------------------------
    def solve(self, u: float, v: float) -> float:
        """Find w with Z(w) = X(u) + Y(v) by bounded bisection.

        Raises ValueError when the target is not bracketed by Z over
        w_range — an unbracketed solve is a guess, and we do not guess.
        """
        target = self.X(u) + self.Y(v)
        lo, hi = self.w_range
        flo, fhi = self.Z(lo) - target, self.Z(hi) - target
        bracket_lo = min(flo, fhi)
        bracket_hi = max(flo, fhi)
        if not (bracket_lo <= 0.0 <= bracket_hi):
            raise ValueError(
                "target %r (X(%r)+Y(%r)) not bracketed by Z over w_range %r; "
                "widen the range or check the scale functions"
                % (target, u, v, self.w_range)
            )
        for _ in range(self.max_iter):
            mid = 0.5 * (lo + hi)
            fm = self.Z(mid) - target
            if fm == 0.0 or (hi - lo) <= self.tol * max(1.0, abs(mid)):
                return mid
            if (flo < 0.0) == (fm < 0.0):
                lo, flo = mid, fm
            else:
                hi = mid
        return 0.5 * (lo + hi)  # bounded: at most max_iter iterations

    # -- honesty ----------------------------------------------------------
    def max_inversion_residual(self, samples: List[Tuple[float, float]]) -> float:
        """Honest accuracy note: worst |Z(solve(u,v)) - (X(u)+Y(v))| over
        the given (u, v) sample pairs. Bisection guarantees this stays at
        the tolerance — reported, not promised."""
        worst = 0.0
        for u, v in samples:
            w = self.solve(u, v)
            residual = abs(self.Z(w) - (self.X(u) + self.Y(v)))
            worst = max(worst, residual)
        return worst

    # -- geometry ----------------------------------------------------------
    def _scale_points(self, height: int):
        """Map each scale's function values to canvas rows."""
        top, bottom = 2, height - 4

        def rows(f, rng):
            flo, fhi = f(rng[0]), f(rng[1])
            lo, hi = (flo, fhi) if flo < fhi else (fhi, flo)
            span = hi - lo if hi != lo else 1.0

            def row(x):
                frac = (f(x) - lo) / span
                return int(round(top + (1.0 - frac) * (bottom - top)))

            return row, lo, hi

        return (
            rows(self.X, self.u_range),
            rows(self.Y, self.v_range),
            rows(self.Z, self.w_range),
        )

    def _sample_pairs(self, n_lines: int) -> List[Tuple[float, float]]:
        (ulo, uhi), (vlo, vhi) = self.u_range, self.v_range
        pairs = []
        for i in range(n_lines):
            frac = i / (n_lines - 1) if n_lines > 1 else 0.5
            pairs.append((ulo + frac * (uhi - ulo), vhi - frac * (vhi - vlo)))
        return pairs

    # -- ASCII --------------------------------------------------------------
    def chart_ascii(
        self,
        n_lines: int = 9,
        width: int = 61,
        height: int = 21,
        sample_uv: Optional[Tuple[float, float]] = None,
        n_ticks: int = 5,
    ) -> str:
        """ASCII nomograph: three labeled scales plus isopleths.

        The highlighted isopleth (marked with '#') is the sample (u, v)
        pair; others are '.'. Footer carries the computed accuracy note.
        """
        (urow, _xlo, _xhi), (vrow, _ylo, _yhi), (zrow, _zlo, _zhi) = self._scale_points(
            height
        )
        col_u, col_v, col_w = 6, width // 2, width - 7

        grid = [[" " for _ in range(width)] for _ in range(height)]

        def vline(col, char="|"):
            for r in range(2, height - 3):
                grid[r][col] = char

        vline(col_u)
        vline(col_v)
        vline(col_w)

        # tick labels: parameter values along each scale
        def label_scale(col, row_fn, rng, name, side: int):
            for i in range(n_ticks):
                frac = i / (n_ticks - 1) if n_ticks > 1 else 0.5
                x = rng[0] + frac * (rng[1] - rng[0])
                r = row_fn(x)
                grid[r][col] = "+"
                txt = "%.4g" % (x,)
                start = col + side if side > 0 else col + side - len(txt) + 1
                for k, ch in enumerate(txt):
                    cc = start + k
                    if 0 <= cc < width:
                        grid[r][cc] = ch

        label_scale(col_u, urow, self.u_range, self.u_name, +2)
        label_scale(col_v, vrow, self.v_range, self.v_name, +2)
        label_scale(col_w, zrow, self.w_range, self.w_name, -2)

        # headers
        for col, name in (
            (col_u, self.u_name),
            (col_v, self.v_name),
            (col_w, self.w_name),
        ):
            for k, ch in enumerate(name):
                if col + k < width:
                    grid[0][col + k] = ch

        # isopleths: straight lines u -> v -> w(solved)
        def draw_line(r0, c0, r1, c1, char):
            n = max(abs(r1 - r0), abs(c1 - c0), 1)
            for i in range(n + 1):
                r = int(round(r0 + (r1 - r0) * i / n))
                c = int(round(c0 + (c1 - c0) * i / n))
                if 0 <= r < height and 0 <= c < width and grid[r][c] == " ":
                    grid[r][c] = char

        pairs = self._sample_pairs(n_lines)
        if sample_uv is None:
            sample_uv = pairs[len(pairs) // 2]
        for u, v in pairs:
            w = self.solve(u, v)
            char = "#" if (u, v) == sample_uv else "."
            draw_line(urow(u), col_u, zrow(w), col_w, char)

        # highlight the sample crossing point on the w scale
        ws = self.solve(*sample_uv)
        rw = zrow(ws)
        if 0 <= rw < height:
            grid[rw][col_w] = "@"

        residual = self.max_inversion_residual(pairs)
        lines = ["".join(row).rstrip() for row in grid]
        lines.append("")
        lines.append(
            "isopleth # : %s=%.4g, %s=%.4g  ->  %s=%.6g"
            % (self.u_name, sample_uv[0], self.v_name, sample_uv[1], self.w_name, ws)
        )
        lines.append(
            "accuracy: max scale-inversion residual over %d isopleths = %.3g "
            "(bisection tol %.0e; reading a printed scale adds human error)"
            % (n_lines, residual, self.tol)
        )
        return "\n".join(lines)

    # -- SVG -----------------------------------------------------------------
    def svg(
        self,
        width_px: int = 640,
        height_px: int = 460,
        n_lines: int = 9,
        sample_uv: Optional[Tuple[float, float]] = None,
        n_ticks: int = 6,
    ) -> str:
        """SVG string of the same chart — printable, stdlib string building
        only (no XML library)."""
        margin = 60
        top, bottom = 50, height_px - 60
        x_u, x_v, x_w = 110, width_px // 2, width_px - 110

        def row_fn(f, rng):
            flo, fhi = f(rng[0]), f(rng[1])
            lo, hi = (flo, fhi) if flo < fhi else (fhi, flo)
            span = hi - lo if hi != lo else 1.0

            def row(x):
                frac = (f(x) - lo) / span
                return top + (1.0 - frac) * (bottom - top)

            return row

        urow = row_fn(self.X, self.u_range)
        vrow = row_fn(self.Y, self.v_range)
        zrow = row_fn(self.Z, self.w_range)

        parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'width="%d" height="%d" viewBox="0 0 %d %d">'
            % (width_px, height_px, width_px, height_px),
            '<rect width="100%%" height="100%%" fill="#0d0d12"/>',
            '<text x="%d" y="26" fill="#e8e8f0" font-size="16" '
            'text-anchor="middle" font-family="monospace">'
            "X(%s) + Y(%s) = Z(%s)</text>"
            % (width_px // 2, self.u_name, self.v_name, self.w_name),
        ]

        def scale(x, row, rng, name, color):
            s = [
                '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" '
                'stroke-width="2"/>' % (x, top, x, bottom, color)
            ]
            s.append(
                '<text x="%d" y="%d" fill="%s" font-size="14" text-anchor='
                '"middle" font-family="monospace">%s</text>'
                % (x, top - 14, color, name)
            )
            for i in range(n_ticks):
                frac = i / (n_ticks - 1) if n_ticks > 1 else 0.5
                xv = rng[0] + frac * (rng[1] - rng[0])
                r = row(xv)
                s.append(
                    '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s"/>'
                    % (x - 6, r, x + 6, r, color)
                )
                s.append(
                    '<text x="%d" y="%.1f" fill="#a8a8b8" font-size="11" '
                    'text-anchor="end" font-family="monospace">%.4g</text>'
                    % (x - 10, r + 4, xv)
                )
            return "".join(s)

        parts.append(scale(x_u, urow, self.u_range, self.u_name, "#7fd4ff"))
        parts.append(scale(x_v, vrow, self.v_range, self.v_name, "#ffd47f"))
        parts.append(scale(x_w, zrow, self.w_range, self.w_name, "#9dff7f"))

        pairs = self._sample_pairs(n_lines)
        if sample_uv is None:
            sample_uv = pairs[len(pairs) // 2]
        for u, v in pairs:
            w = self.solve(u, v)
            hot = (u, v) == sample_uv
            parts.append(
                '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" '
                'stroke="%s" stroke-width="%s" opacity="0.75"/>'
                % (
                    x_u,
                    urow(u),
                    x_w,
                    zrow(w),
                    "#ffffff" if hot else "#555566",
                    "2.5" if hot else "1",
                )
            )
        ws = self.solve(*sample_uv)
        parts.append(
            '<circle cx="%d" cy="%.1f" r="6" fill="none" stroke="#ffffff" '
            'stroke-width="2"/>' % (x_w, zrow(ws))
        )
        parts.append(
            '<text x="%d" y="%d" fill="#a8a8b8" font-size="12" '
            'font-family="monospace">%s=%.6g (solved; residual %.2g)</text>'
            % (
                margin,
                height_px - 24,
                self.w_name,
                ws,
                self.max_inversion_residual(pairs),
            )
        )
        parts.append("</svg>")
        return "".join(parts)


def multiply_nomograph(
    u_range=(0.5, 10.0), v_range=(0.5, 10.0), w_range=(0.25, 100.0)
) -> Nomograph:
    """The classic slide-rule chart: log10 scales turn u * v = w into a
    straight-line nomograph, wire-gauge style."""
    log = math.log10
    return Nomograph(
        X=log,
        Y=log,
        Z=log,
        u_range=u_range,
        v_range=v_range,
        w_range=w_range,
        u_name="u",
        v_name="v",
        w_name="w (=u*v)",
    )
