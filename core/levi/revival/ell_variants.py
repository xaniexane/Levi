"""LEVI's unit-variant registry: provenance over uniformity.

Studied from: lost-crafts-20260916 / report.md [Batch 2]
(English Ell Variants / the alnage lesson)

The studied mechanism — and its lesson. England had 90+ "ells": the
cloth-measure differed town to town, trade to trade. The crown answered
with the alnage: inspectors who stamped approved cloth. It failed, and
the failure is the point: enforcement-by-inspection is a *service* that
can record claims, but it cannot retroactively unify a unit that grew
up different in ninety places. No inspection regime makes divergent
measures converge; the only honest move is *provenance*: record which
ell, whose ell, when and where — and convert with the spread on display.

This module rebuilds that lesson as LEVI's own mechanism. An
:class:`EllRegistry` holds named unit variants, each with a provenance
chain (place, trade, date span, source note). Converting a value names
the variant explicitly; converting *without* naming one is refused —
silently picking "the" ell is exactly the sin being avoided. The
:func:`divergence_report` shows the spread across variants, and the
inspection service (:class:`Alnage`) stamps cloth with the variant it
was measured in. The stamp certifies the *claim*, never the unit: the
module makes that boundary explicit in the stamp itself.

Honest limits: variant values here are registry *entries*, not
metrological facts — the module tracks what was claimed about each
ell, including contradictions, without adjudicating them. Two entries
for one town stay two entries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


ORIGIN = "levi-revival/ell_variants"


class EllError(Exception):
    """Base error for ell-registry failures."""


@dataclass(frozen=True)
class Provenance:
    """Where a variant comes from: the chain of custody for a measure."""

    place: str
    trade: str
    date_span: str  # e.g. "c. 1500–1700" — a label, not a parsed range
    source_note: str


@dataclass(frozen=True)
class EllVariant:
    """One ell among many: a name, a value in a shared base unit, and its provenance."""

    name: str
    base_value: float  # length of one ell of this variant, in base units
    provenance: Provenance

    def __post_init__(self) -> None:
        if self.base_value <= 0:
            raise EllError(f"variant {self.name!r} has non-positive value")


@dataclass(frozen=True)
class AlnageStamp:
    """What the inspector's stamp honestly certifies.

    It certifies that *this* cloth was measured as *this many* of *this
    named variant* on *this date* — a claim about the measurement, never
    a claim that the variant is the one true ell.
    """

    cloth_id: str
    variant: str
    ells: float
    date: str
    inspector: str

    def as_base_units(self, registry: "EllRegistry") -> float:
        return self.ells * registry.variant(self.variant).base_value


class EllRegistry:
    """The registry of variants. Ninety ells, ninety provenances, zero apologies."""

    def __init__(self, base_unit: str = "inch") -> None:
        self.base_unit = base_unit
        self._variants: Dict[str, EllVariant] = {}
        self._stamps: List[AlnageStamp] = []

    def register(self, variant: EllVariant) -> None:
        """Record a variant. A second entry for the same name is kept too —
        contradictions are data, so the name gets a suffix and both stay."""
        name = variant.name
        if name in self._variants:
            i = 2
            while f"{name}#{i}" in self._variants:
                i += 1
            name = f"{name}#{i}"
            variant = EllVariant(
                name=name, base_value=variant.base_value, provenance=variant.provenance
            )
        self._variants[name] = variant

    def variant(self, name: str) -> EllVariant:
        try:
            return self._variants[name]
        except KeyError:
            raise EllError(f"unknown ell variant {name!r} — name your ell") from None

    def names(self) -> List[str]:
        return sorted(self._variants)

    def convert(self, ells: float, variant: str) -> float:
        """Convert a measurement to base units — the variant must be named.

        There is no default ell. Refusing to guess is the feature.
        """
        return ells * self.variant(variant).base_value

    def convert_between(self, ells: float, from_variant: str, to_variant: str) -> float:
        """Convert a measurement from one named variant to another."""
        base = self.convert(ells, from_variant)
        return base / self.variant(to_variant).base_value

    def divergence_report(self) -> Tuple[float, float, float]:
        """(min, max, max/min) of variant values in base units — the spread
        no inspection service could ever stamp away."""
        values = [v.base_value for v in self._variants.values()]
        if not values:
            raise EllError("no variants registered")
        lo, hi = min(values), max(values)
        return (lo, hi, hi / lo)

    # -- the alnage: inspection as a service --------------------------------

    def inspect(
        self, cloth_id: str, variant: str, ells: float, date: str, inspector: str
    ) -> AlnageStamp:
        """Stamp cloth: certify the measurement claim, not the unit."""
        self.variant(variant)  # raises on unknown — the stamp names a real variant
        stamp = AlnageStamp(
            cloth_id=cloth_id,
            variant=variant,
            ells=ells,
            date=date,
            inspector=inspector,
        )
        self._stamps.append(stamp)
        return stamp

    def stamps(self) -> List[AlnageStamp]:
        return list(self._stamps)
