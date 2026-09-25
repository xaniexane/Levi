"""The tide predictor: mechanical Fourier synthesis.

Studied from: pre-digital-computation-20260916 / report.md (Beat B #3)

The mechanism: a set of shafts, each turning at the period of one
astronomical tide constituent (the moon's transit, the sun's transit,
and their harmonics). Each shaft drives a crank whose throw is the
constituent's amplitude; a single wire threaded over-and-under all the
crank pulleys sums the motions into one vertical displacement — the
predicted tide. It is Fourier synthesis in brass: the tide is treated
as a sum of sinusoids and the machine adds them continuously.

What this module models:
- ``TidePredictor``: named constituents (period in hours, amplitude,
  phase); ``predict(t)`` sums the harmonics; ``series`` samples a
  window; ``high_low_waters`` finds extrema by derivative sign change.
- ``CLASSIC_CONSTITUENTS``: the standard astronomical periods. Periods
  are astronomy; amplitudes and phases are site-specific and default to
  1.0 / 0.0 until the operator sets them.

Honest limits: this is the synthesis half of the machine — the
analysis half (deriving amplitudes and phases from observed tide
records) is not modelled; without fitted constituents the output is a
demonstration of the synthesis geometry, not a tide table. Extrema are
resolved to the sampling step. No network, stdlib only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


ORIGIN = "levi-revival/tide-predictor"

# Standard astronomical periods in hours (public domain astronomy).
# Amplitudes/phases are deliberately NOT included: they belong to a
# specific harbor's observations, not to the mechanism.
CLASSIC_CONSTITUENTS: Dict[str, float] = {
    "M2": 12.4206,  # principal lunar semidiurnal
    "S2": 12.0000,  # principal solar semidiurnal
    "N2": 12.6583,  # larger lunar elliptic semidiurnal
    "M4": 6.2103,  # shallow-water overtide of M2
    "K1": 23.9345,  # lunisolar diurnal
    "O1": 25.8193,  # lunar diurnal
}


@dataclass
class Constituent:
    """One harmonic shaft: period, crank throw (amplitude), phase."""

    name: str
    period_hours: float
    amplitude: float = 1.0
    phase_radians: float = 0.0

    def __post_init__(self) -> None:
        if self.period_hours <= 0.0:
            raise ValueError("period must be positive")

    def height(self, t_hours: float) -> float:
        """This shaft's contribution at hour ``t_hours``."""
        return self.amplitude * math.cos(
            2.0 * math.pi * t_hours / self.period_hours + self.phase_radians
        )


@dataclass
class TidePredictor:
    """The summation wire: adds every constituent's motion."""

    constituents: List[Constituent] = field(default_factory=list)

    def add(self, constituent: Constituent) -> None:
        """Mount another shaft on the machine."""
        if any(c.name == constituent.name for c in self.constituents):
            raise ValueError(f"constituent {constituent.name!r} already mounted")
        self.constituents.append(constituent)

    def add_classic(
        self, name: str, amplitude: float = 1.0, phase_radians: float = 0.0
    ) -> None:
        """Mount a standard constituent by name with the operator's amplitude."""
        if name not in CLASSIC_CONSTITUENTS:
            raise ValueError(f"unknown constituent {name!r}")
        self.add(
            Constituent(name, CLASSIC_CONSTITUENTS[name], amplitude, phase_radians)
        )

    def predict(self, t_hours: float) -> float:
        """The wire's total displacement at hour ``t_hours``."""
        return sum(c.height(t_hours) for c in self.constituents)

    def series(
        self, start: float, end: float, step: float
    ) -> List[Tuple[float, float]]:
        """Sampled predictions over [start, end] at ``step``-hour intervals."""
        if step <= 0.0:
            raise ValueError("step must be positive")
        if end < start:
            raise ValueError("end must not precede start")
        points = []
        t = start
        while t <= end + 1e-9:
            points.append((t, self.predict(t)))
            t += step
        return points

    def high_low_waters(
        self, start: float, end: float, step: float = 0.1
    ) -> List[Tuple[float, float, str]]:
        """Find high and low waters by derivative sign change.

        Returns (time, height, "high"|"low"). Resolution is limited by
        ``step`` — the machine's pen draws a continuous curve, but this
        reading samples it, so times are approximate to the step size.
        """
        points = self.series(start, end, step)
        if len(points) < 3:
            return []
        events = []
        for i in range(1, len(points) - 1):
            prev_d = points[i][1] - points[i - 1][1]
            next_d = points[i + 1][1] - points[i][1]
            if prev_d > 0.0 and next_d <= 0.0:
                events.append((points[i][0], points[i][1], "high"))
            elif prev_d < 0.0 and next_d >= 0.0:
                events.append((points[i][0], points[i][1], "low"))
        return events
