"""LEVI's pricing measure: the ruler is a pricing instrument, not just a length.

Studied from: lost-crafts-20260916/report.md [Batch 2] (functional description
only; no historical claims).

The lesson, reborn as LEVI's own: a measure can carry *policy metadata* —
which commodity it applies to, which authority set it, and therefore what
price a quoted length really means. Give silk a shorter arm than wool in the
same market and the measure itself becomes a pricing instrument: the same
quoted price per "braccio" is a higher price per true meter for silk. The
``MeasuresGraph`` holds every measure as a node with its policy metadata and
answers the questions that matter at the stall: what does this length really
cost, which measure favors whom, and who decreed the difference.

Honesty: the lengths and prices in the demo graph are illustrative figures
for demonstrating the mechanism, not claims about any historical market.
``add_measure`` accepts any local figures.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/measure-pricing"


@dataclass(frozen=True)
class Measure:
    """One measure: its true length plus the policy metadata around it."""

    name: str
    city: str
    commodity: Optional[str]  # None = generic, applies to everything
    length_m: float  # the true length behind the name
    authority: str  # who set / enforces this measure
    note: str = ""


class MeasuresGraph:
    """Measures as policy-laden nodes; pricing derived from true length."""

    def __init__(self) -> None:
        self._measures: Dict[str, Measure] = {}

    def add_measure(self, measure: Measure) -> Measure:
        if measure.length_m <= 0:
            raise ValueError("length must be positive")
        self._measures[measure.name] = measure
        return measure

    def get(self, name: str) -> Measure:
        return self._measures[name]

    def for_commodity(self, commodity: str) -> List[Measure]:
        """Measures applying to ``commodity`` (generic ones included)."""
        return [m for m in self._measures.values() if m.commodity in (None, commodity)]

    # -- pricing --------------------------------------------------------------
    def price_per_meter(self, quoted_per_measure: float, measure_name: str) -> float:
        """True price per meter behind a quote in this measure's units."""
        m = self._measures[measure_name]
        return quoted_per_measure / m.length_m

    def compare(
        self, commodity: str, quoted_per_measure: float
    ) -> List[Tuple[str, float, float]]:
        """Every applicable measure: (name, true length, price per true meter).

        Sorted cheapest-first by true price per meter — the measure as a
        pricing instrument made visible.
        """
        rows = [
            (m.name, m.length_m, quoted_per_measure / m.length_m)
            for m in self.for_commodity(commodity)
        ]
        return sorted(rows, key=lambda r: r[2])

    def pricing_edge(self, measure_a: str, measure_b: str) -> Dict[str, float]:
        """How much shorter ``a`` is than ``b``, and the price premium that buys.

        At the same quoted price per measure, the shorter measure charges
        more per true meter. Returns the length ratio and the premium factor.
        """
        a = self._measures[measure_a]
        b = self._measures[measure_b]
        ratio = a.length_m / b.length_m
        return {
            "length_ratio_a_to_b": ratio,
            "shorter_by_pct": (1.0 - ratio) * 100.0 if ratio < 1 else 0.0,
            "price_premium_factor": 1.0 / ratio,
        }

    def authority_of(self, measure_name: str) -> str:
        """Who decreed this measure — the policy metadata, on demand."""
        return self._measures[measure_name].authority


def cloth_market() -> MeasuresGraph:
    """Demo graph: one city, a shorter arm for silk than for wool.

    Illustrative lengths only; they demonstrate the pricing mechanism.
    """
    g = MeasuresGraph()
    g.add_measure(
        Measure(
            name="silk_braccio",
            city="florence",
            commodity="silk",
            length_m=0.583,
            authority="silk_guild",
            note="shorter arm: the measure prices silk by policy",
        )
    )
    g.add_measure(
        Measure(
            name="wool_braccio",
            city="florence",
            commodity="wool",
            length_m=0.680,
            authority="wool_guild",
            note="longer arm for the coarser trade",
        )
    )
    g.add_measure(
        Measure(
            name="generic_braccio",
            city="florence",
            commodity=None,
            length_m=0.620,
            authority="city_council",
            note="fallback for unregulated goods",
        )
    )
    return g
