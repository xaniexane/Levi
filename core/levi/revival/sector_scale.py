"""The sector: proportional computation in engraved scale spacing.

Studied from: pre-digital-computation-20260916 / report.md (Beat A #7)

The mechanism: two straight legs joined by a hinge, with scales engraved
outward from the hinge — a line of equal parts (linear), a line of
squares (spacings proportional to square roots), a line of cubes
(spacings proportional to cube roots). There are no moving parts beyond
the hinge itself; the mathematics lives in the spacing.

Proportional work uses similar triangles. Open the legs until the
transverse distance between the two ``a`` marks equals some length ``b``
(taken with dividers); then the transverse distance between the two
``c`` marks is the fourth proportional ``x`` in a:b :: c:x, because
transverse spans scale with the engraved distances from the hinge.

What this module models:
- ``Scale``: engraved lines (linear / square / cube); ``mark(v)`` gives
  the distance of value ``v`` from the hinge.
- ``Sector.open_for(a, span_b)``: hinge angle set so the transverse span
  at mark ``a`` equals ``span_b`` — raises if the span is wider than the
  legs can open (a genuine hardware limit: the legs stop at 180°).
- ``Sector.transverse(c)``: the span between the ``c`` marks at the
  current opening, i.e. the computed fourth proportional.

Honest limits: exact floating-point geometry, not brass and friction —
a real sector resolves a few significant figures at best, and this
module does not model parallax, hinge wear, or divider slop. No
network, stdlib only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal


ORIGIN = "levi-revival/sector-scale"

ScaleKind = Literal["linear", "square", "cube"]


@dataclass(frozen=True)
class Scale:
    """One engraved line on a sector leg, measured from the hinge.

    - ``linear``: mark distance proportional to the value itself.
    - ``square``: distance proportional to sqrt(value), so equal
      transverse spans compare areas.
    - ``cube``: distance proportional to cbrt(value), for volumes.
    """

    kind: ScaleKind = "linear"

    def mark(self, value: float) -> float:
        """Distance from the hinge to the engraved mark for ``value``."""
        if value <= 0.0:
            raise ValueError("sector marks are defined for positive values")
        if self.kind == "linear":
            return value
        if self.kind == "square":
            return math.sqrt(value)
        return value ** (1.0 / 3.0)


class Sector:
    """A hinged pair of legs carrying engraved scales.

    The sector is used, never moved, during a computation: set the
    opening once with ``open_for``, then read answers with
    ``transverse``. ``scale`` selects which engraved line the marks are
    read from.
    """

    def __init__(self, scale: Scale | None = None) -> None:
        self.scale = scale or Scale("linear")
        self._half_angle: float | None = None

    # -- setting the opening -------------------------------------------
    def open_for(self, a: float, span_b: float) -> float:
        """Open the legs so the transverse span at mark ``a`` is ``span_b``.

        Returns the full hinge angle in radians. Raises ``ValueError``
        if ``span_b`` exceeds twice the mark distance — the legs cannot
        open past flat (180°), so some proportions are simply out of
        reach of the instrument.
        """
        mark_a = self.scale.mark(a)
        if span_b < 0.0:
            raise ValueError("span must be non-negative")
        if span_b > 2.0 * mark_a:
            raise ValueError(
                "span wider than the legs can open: choose a larger reference mark"
            )
        # Transverse span = 2 * mark_a * sin(half_angle).
        self._half_angle = math.asin(span_b / (2.0 * mark_a))
        return 2.0 * self._half_angle

    # -- reading answers -------------------------------------------------
    def transverse(self, c: float) -> float:
        """Span between the ``c`` marks at the current opening.

        With the opening set by ``open_for(a, span_b)``, this returns
        the fourth proportional x in a:b :: c:x — the computation the
        sector exists to perform.
        """
        if self._half_angle is None:
            raise ValueError("sector opening not set: call open_for first")
        return 2.0 * self.scale.mark(c) * math.sin(self._half_angle)

    def proportion(self, a: float, b: float, c: float) -> float:
        """Solve a:b :: c:x directly, via the transverse geometry."""
        self.open_for(a, b)
        return self.transverse(c)

    # -- scale utilities --------------------------------------------------
    def double_area_side(self, side: float) -> float:
        """Side of the square with twice the area, via the square line.

        On the square scale the transverse span at the doubled-area mark
        is found without any arithmetic on areas themselves.
        """
        square = Scale("square")
        # Area of the first square in "square-line" terms is side**2;
        # the mark for the doubled area sits at sqrt(2 * side**2).
        return square.mark(2.0 * side * side)
