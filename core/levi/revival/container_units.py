"""LEVI's container ladder: the vessel *is* the unit, and the tax rides along.

Studied from: lost-crafts-20260916/report.md [Batch 2] (functional description
only; no historical claims).

The lesson, reborn as LEVI's own: a unit of volume can be defined by the
container itself — a doubling ladder of firkin, kilderkin, barrel, hogshead —
and when the *gallon* differs by commodity (ale vs. wine), tax policy gets
encoded directly into the volume. A ``ContainerLadder`` is built for one
commodity: its rungs are fixed multiples of that commodity's gallon, and its
excise table quotes duty per gallon, so ``excise_due`` prices a shipment
straight from rung + count with no separate tax schedule to look up.

Honesty: the gallon sizes and rung multiples used here are illustrative
defaults (ale gallon 282 cu in, wine gallon 231 cu in), chosen to demonstrate
the *mechanism* — commodity-specific gallons plus container ladders — not to
assert any particular historical schedule. ``custom()`` builds ladders with
any local figures.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/container-units"

# Illustrative commodity gallons (cubic inches per gallon).
ALE_GALLON_CU_IN = 282.0
WINE_GALLON_CU_IN = 231.0

# Doubling ladder: rung -> gallons of the commodity's own gallon.
# (Hogshead and butt differ by commodity because the gallon does.)
_LADDER_BEER = {
    "firkin": 9,
    "kilderkin": 18,
    "barrel": 36,
    "hogshead": 54,
    "butt": 108,
}
_LADDER_WINE = {
    "firkin": 9,
    "kilderkin": 18,
    "barrel": 36,
    "hogshead": 63,
    "butt": 126,
}


@dataclass(frozen=True)
class Rung:
    """One rung of the ladder: name, gallons, cubic inches, excise per gallon."""

    name: str
    gallons: float
    cubic_inches: float
    excise_per_gallon: float


class ContainerLadder:
    """A commodity's container-as-unit ladder with excise baked in.

    ``commodity`` selects the gallon and the rung multiples; ``excise`` is a
    per-gallon duty rate so the tax policy lives inside the ladder itself.
    """

    def __init__(
        self,
        commodity: str,
        gallon_cu_in: float,
        rungs: Dict[str, float],
        excise_per_gallon: float,
    ) -> None:
        if gallon_cu_in <= 0:
            raise ValueError("gallon size must be positive")
        if excise_per_gallon < 0:
            raise ValueError("excise cannot be negative")
        self.commodity = commodity
        self.gallon_cu_in = gallon_cu_in
        self._rungs = dict(rungs)
        self.excise_per_gallon = excise_per_gallon

    # -- ladder -------------------------------------------------------------
    def rungs(self) -> List[str]:
        """Rung names, smallest container first."""
        return sorted(self._rungs, key=lambda r: self._rungs[r])

    def rung(self, name: str) -> Rung:
        gallons = self._rungs[name]
        return Rung(
            name=name,
            gallons=gallons,
            cubic_inches=gallons * self.gallon_cu_in,
            excise_per_gallon=self.excise_per_gallon,
        )

    def double_up(self, name: str) -> str:
        """The next rung up the doubling ladder."""
        ordered = self.rungs()
        idx = ordered.index(name)
        if idx == len(ordered) - 1:
            raise ValueError(f"{name!r} is already the top rung")
        return ordered[idx + 1]

    # -- volume & duty --------------------------------------------------------
    def volume_gallons(self, name: str, count: int = 1) -> float:
        return self._rungs[name] * count

    def volume_cubic_inches(self, name: str, count: int = 1) -> float:
        return self._rungs[name] * count * self.gallon_cu_in

    def excise_due(self, name: str, count: int = 1) -> float:
        """Duty owed on ``count`` containers of rung ``name``.

        The tax is read off the ladder itself: rung gallons x per-gallon
        rate — policy encoded as volume, not as a separate schedule.
        """
        return self.volume_gallons(name, count) * self.excise_per_gallon

    def shipment(self, manifest: Dict[str, int]) -> Tuple[float, float]:
        """Total (gallons, excise) for a manifest of rung -> count."""
        gallons = sum(self.volume_gallons(r, c) for r, c in manifest.items())
        return gallons, gallons * self.excise_per_gallon


def beer_ladder(excise_per_gallon: float = 0.05) -> ContainerLadder:
    """The doubling ladder on the ale gallon."""
    return ContainerLadder("ale", ALE_GALLON_CU_IN, _LADDER_BEER, excise_per_gallon)


def wine_ladder(excise_per_gallon: float = 0.08) -> ContainerLadder:
    """The doubling ladder on the wine gallon — same names, different volumes."""
    return ContainerLadder("wine", WINE_GALLON_CU_IN, _LADDER_WINE, excise_per_gallon)


def custom(
    commodity: str,
    gallon_cu_in: float,
    rungs: Dict[str, float],
    excise_per_gallon: float,
) -> ContainerLadder:
    """Build a ladder with local figures (any commodity, any rung multiples)."""
    return ContainerLadder(commodity, gallon_cu_in, rungs, excise_per_gallon)
