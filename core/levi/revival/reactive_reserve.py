"""LEVI's reactive reserve: material that heals itself from a stored surplus.

Studied from: lost-crafts-20260916/report.md [Batch 3] (functional description
only; no historical claims).

The lesson, reborn as LEVI's own: leave *reactive reserve* inside the
material — pockets of unspent reactive clasts — and cracks stop being
permanent. Each weathering cycle, stress widens the cracks a little; then the
clasts nearest each crack dissolve in proportion to the crack's width and
recrystallize as sealant, spending the reserve. The mechanism is honest
bookkeeping: healing is capped by the reserve, and once the reserve is gone
the cracks grow unchecked. ``integrity()`` is the live health score.

Honesty: HEURISTIC MODEL. Crack growth, dissolution, and sealing are simple
proportional rules, not materials science. The model demonstrates the
*mechanism shape* — a finite reactive reserve that converts damage into
self-repair until it runs out — not any real material's behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

ORIGIN = "levi-revival/reactive-reserve"


@dataclass
class Slab:
    """A slab carrying cracks and the reactive reserve that seals them.

    ``cracks``: current crack widths (mm). ``clasts``: reactive reserve per
    pocket (mm of sealant each pocket can still release). ``failure_width``:
    total crack width at which the slab is considered failed.
    """

    cracks: List[float] = field(default_factory=list)
    clasts: List[float] = field(default_factory=list)
    failure_width: float = 10.0
    # Heuristic rates (documented as model parameters, not physics):
    growth_rate: float = 0.10  # crack growth per unit stress per cycle
    seal_efficiency: float = 0.9  # mm of crack sealed per mm of reserve spent

    def __post_init__(self) -> None:
        if any(c < 0 for c in self.cracks):
            raise ValueError("crack widths cannot be negative")
        if any(r < 0 for r in self.clasts):
            raise ValueError("reserve cannot be negative")
        if self.failure_width <= 0:
            raise ValueError("failure_width must be positive")

    # -- state ------------------------------------------------------------------
    def damage(self) -> float:
        """Total current crack width (mm)."""
        return sum(self.cracks)

    def heal_reserve(self) -> float:
        """Reactive reserve still available (mm of sealant)."""
        return sum(self.clasts)

    def integrity(self) -> float:
        """Health score in [0, 1]: 1 is pristine, 0 is failed."""
        return max(0.0, 1.0 - self.damage() / self.failure_width)

    # -- dynamics -----------------------------------------------------------------
    def stress_event(self, magnitude: float) -> None:
        """Open a new crack of ``magnitude`` mm (an impact, a frost heave)."""
        if magnitude < 0:
            raise ValueError("magnitude cannot be negative")
        self.cracks.append(magnitude)

    def cycle(self, stress: float = 1.0) -> float:
        """Run one weathering cycle: stress widens cracks, reserve seals them.

        Returns the net change in total crack width (negative = net healing).
        Each crack grows by ``stress * growth_rate``; then each crack draws
        from the nearest clast pocket, which releases up to the crack's width
        worth of sealant (capped by what the pocket still holds).
        """
        before = self.damage()
        # 1. Stress widens every crack.
        self.cracks = [c + stress * self.growth_rate for c in self.cracks]
        # 2. Reactive reserve answers: pair cracks to clast pockets in order.
        pockets = sorted(
            range(len(self.clasts)), key=lambda i: self.clasts[i], reverse=True
        )
        for ci, crack_idx in enumerate(range(len(self.cracks))):
            if ci >= len(pockets):
                break
            pocket = pockets[ci]
            available = self.clasts[pocket]
            if available <= 0:
                continue
            release = min(available, self.cracks[crack_idx])
            self.clasts[pocket] = available - release
            self.cracks[crack_idx] = max(
                0.0, self.cracks[crack_idx] - release * self.seal_efficiency
            )
        after = self.damage()
        return after - before

    def report(self) -> dict:
        return {
            "cracks": [round(c, 4) for c in self.cracks],
            "damage_mm": round(self.damage(), 4),
            "reserve_mm": round(self.heal_reserve(), 4),
            "integrity": round(self.integrity(), 4),
        }
