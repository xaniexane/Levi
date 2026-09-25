"""Nomographic computation: equations compiled into paper scales.

Studied from: precompute-hunt-20260915 report.md [Find 2, LOAD-BEARING]
(functional shape only: multi-variable equations frozen into scales;
a straightedge laid across known values reads the unknown).

A nomograph compiles an equation into *scales* — value-to-position
mappings printed on paper — so that solving the equation becomes a
geometric act: lay a straightedge across two known values, read the
third where the edge crosses its scale. LEVI's version keeps the idea
and the honest analog limit: reading a printed scale is quantized to
the finest tick division, so every reading carries a graphical error
the digital solve does not.

Supported chart shapes (all "type N": three parallel scales, relation
sum of scale-functions = 0):

- addition:       u + v - w = 0
- product:        log(u) + log(v) - log(w) = 0  (u, v, w > 0)
- harmonic:       1/u + 1/v - 1/w = 0            (parallel resistors)
- custom:         caller supplies forward/inverse functions per scale

Every scale is invertible, so solving is exact arithmetic on the
compiled functions. ``read()`` then simulates the analog reading:
the position of the true answer is snapped to the nearest tick of a
scale divided into ``divisions`` ticks, and the quantized position is
mapped back to a value. The gap between the digital solve and the
tick reading is the machine's honest error.

This is a heuristic reading simulation, not a physical instrument.
stdlib-only, no network.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple


ORIGIN = "levi-revival/nomography"


@dataclass
class Scale:
    """One printed scale: a name plus a value<->position mapping."""

    name: str
    forward: Callable[[float], float]
    inverse: Callable[[float], float]
    lo: float
    hi: float

    def position(self, value: float, length: float = 1.0) -> float:
        """Paper position of ``value`` on a scale of ``length``."""
        if not (self.lo <= value <= self.hi):
            raise ValueError(f"{value!r} outside scale {self.name} range")
        span = self.forward(self.hi) - self.forward(self.lo)
        if span == 0:
            raise ValueError(f"degenerate scale {self.name}")
        return length * (self.forward(value) - self.forward(self.lo)) / span

    def value_at(self, position: float, length: float = 1.0) -> float:
        """Value whose paper position is ``position``."""
        if not (0.0 <= position <= length):
            raise ValueError(f"position {position!r} off scale {self.name}")
        span = self.forward(self.hi) - self.forward(self.lo)
        return self.inverse(self.forward(self.lo) + span * (position / length))


@dataclass
class Reading:
    """Result of solving plus its simulated analog read."""

    unknown: str
    exact: float
    read_value: float
    read_error: float
    positions: Dict[str, float]


class ParallelNomograph:
    """Three parallel scales with relation f1 + f2 + f3 = 0 (signed per scale).

    Each scale contributes its forward function with a sign; the
    straightedge alignment is exactly the constraint that the three
    paper positions lie on one straight line across parallel scales,
    which for a type-N chart is equivalent to the signed sum being
    zero. Solve any one unknown from the other two.
    """

    def __init__(self, scales: List[Tuple[Scale, float]], length: float = 1.0):
        if len(scales) != 3:
            raise ValueError("type-N chart needs exactly three scales")
        self.scales = scales
        self.length = length
        self._by_name = {s.name: (s, sign) for s, sign in scales}

    def _position_pair(self, scale: Scale, value: float) -> float:
        return scale.position(value, self.length)

    def solve(
        self, known: Dict[str, float], unknown: str, divisions: int = 100
    ) -> Reading:
        """Solve for ``unknown`` and simulate reading it off the ticks.

        ``known`` maps the other two scale names to values. ``divisions``
        is the tick resolution of the printed unknown scale — the
        coarser the ticks, the larger the honest read error.
        """
        if unknown not in self._by_name:
            raise KeyError(f"no scale named {unknown!r}")
        names = [s.name for s, _ in self.scales]
        if set(known) != set(names) - {unknown}:
            raise ValueError(f"need exactly the two knowns {set(names) - {unknown}}")
        # Straightedge alignment: signed sum of forward values is zero.
        total = 0.0
        positions: Dict[str, float] = {}
        for scale, sign in self.scales:
            if scale.name in known:
                total += sign * scale.forward(known[scale.name])
                positions[scale.name] = self._position_pair(scale, known[scale.name])
        uscale, usign = self._by_name[unknown]
        exact = uscale.inverse(-total / usign)
        # Analog reading: snap position to nearest tick.
        raw_pos = self._position_pair(uscale, exact)
        tick = self.length / divisions
        snapped = round(raw_pos / tick) * tick
        snapped = min(max(snapped, 0.0), self.length)
        read_value = uscale.value_at(snapped, self.length)
        positions[unknown] = snapped
        return Reading(
            unknown=unknown,
            exact=exact,
            read_value=read_value,
            read_error=abs(read_value - exact),
            positions=positions,
        )


def addition_chart(
    lo: float = 0.0, hi: float = 100.0, length: float = 1.0
) -> ParallelNomograph:
    """Nomograph for u + v = w."""
    ident = (lambda x: x, lambda x: x)
    scales = [
        (Scale("u", *ident, lo, hi), 1.0),
        (Scale("v", *ident, lo, hi), 1.0),
        (Scale("w", *ident, lo, hi + hi), -1.0),
    ]
    return ParallelNomograph(scales, length)


def product_chart(
    lo: float = 1.0, hi: float = 100.0, length: float = 1.0
) -> ParallelNomograph:
    """Nomograph for u * v = w (log scales; all values > 0)."""
    fwd = (math.log10, lambda x: 10.0**x)
    scales = [
        (Scale("u", *fwd, lo, hi), 1.0),
        (Scale("v", *fwd, lo, hi), 1.0),
        (Scale("w", *fwd, lo * lo, hi * hi), -1.0),
    ]
    return ParallelNomograph(scales, length)


def harmonic_chart(
    lo: float = 1.0, hi: float = 100.0, length: float = 1.0
) -> ParallelNomograph:
    """Nomograph for 1/u + 1/v = 1/w (parallel-resistor form)."""
    fwd = (lambda x: 1.0 / x, lambda x: 1.0 / x)
    # 1/w = 1/u + 1/v ranges over 2/hi..2/lo, so w ranges over lo/2..hi/2.
    w_scale = Scale("w", *fwd, lo / 2.0, hi / 2.0)
    scales = [
        (Scale("u", *fwd, lo, hi), 1.0),
        (Scale("v", *fwd, lo, hi), 1.0),
        (w_scale, -1.0),
    ]
    return ParallelNomograph(scales, length)
