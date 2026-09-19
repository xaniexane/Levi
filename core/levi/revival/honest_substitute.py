"""Honest-substitute board-making: say what it is, make it well.

Studied from: lost-crafts-20260916/report.md [Games standing theme]
(Kaya goban)

The studied shape: when the canonical material (kaya wood) is gone,
craftspeople don't fake it — they build from local softwoods and say
so, drawing the grid by hand at the true 21.5 x 23 mm spacing. The
honesty is part of the craft: the substitute is labeled as a
substitute, and the geometry is still exact.

LEVI-native re-expression: a board-planning system with two honest
mechanisms.

**1. Material substitution.** A catalog lists the canonical material
and available substitutes. ``pick_substitute`` scores candidates on
honest criteria — local availability, dimensional stability, and a
*declared difference* penalty: a substitute that pretends to be kaya
scores worse than one that admits what it is. The winner's label
states the substitution plainly.

**2. Grid geometry.** ``BoardPlan`` generates the line coordinates for
a 19x19 grid at the canonical 21.5 x 23 mm spacing (or any spacing),
plus ``hand_drawn`` mode: seeded, reproducible jitter on each line, so
the plan admits the human hand instead of hiding behind perfect CAD
lines.

Operations:

* ``MaterialCatalog.pick_substitute(requirements)`` — ranked honest picks
* ``BoardPlan.generate_grid()`` — (vertical lines, horizontal lines) in mm
* ``BoardPlan.hand_drawn(seed)`` — jittered lines, reproducible
* ``BoardPlan.label()`` — the honest plaque text

Honest limits: stability scores are comparative heuristics over
declared material properties, not lab measurements. Hand-drawn jitter
is a reproducible pseudo-random stand-in, not a scan of a real board.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


ORIGIN = "levi-revival/honest-substitute"

CANONICAL_SPACING = (21.5, 23.0)  # mm: (x, y) line spacing for a 19-line grid
GRID_LINES = 19


@dataclass
class Material:
    """One candidate board wood, declared as it is."""

    name: str
    canonical: bool = False
    available: bool = True
    local: bool = False
    stability: float = 0.5  # 0..1 dimensional stability (declared)
    declares_itself: bool = True  # admits it is a substitute, not kaya

    def __post_init__(self) -> None:
        if not (0.0 <= self.stability <= 1.0):
            raise ValueError("stability must be within 0..1")


@dataclass
class MaterialCatalog:
    """The shelf: canonical (gone) plus the honest substitutes."""

    materials: List[Material] = field(default_factory=list)

    def add(self, material: Material) -> None:
        if any(m.name == material.name for m in self.materials):
            raise ValueError(f"duplicate material {material.name!r}")
        self.materials.append(material)

    def canonical(self) -> List[Material]:
        return [m for m in self.materials if m.canonical]

    # -- honest substitution ----------------------------------------------------------
    def score(
        self, m: Material, require_local: bool = False
    ) -> Tuple[float, List[str]]:
        """Honest score 0..1 + the reasons. Pretenders score worse."""
        notes: List[str] = []
        if not m.available:
            return 0.0, ["not available"]
        s = 0.0
        s += 0.40 * m.stability
        notes.append(f"stability {m.stability:.2f}")
        if m.local:
            s += 0.25
            notes.append("locally sourced")
        elif require_local:
            s -= 0.25
            notes.append("fails the local-only requirement")
        if m.declares_itself and not m.canonical:
            s += 0.35
            notes.append("honestly declared as substitute")
        elif not m.declares_itself:
            s -= 0.35
            notes.append("pretends to be the canonical material — penalized")
        if m.canonical:
            notes.append("canonical material (unavailable by definition of the task)")
        return round(max(0.0, min(1.0, s)), 3), notes

    def pick_substitute(
        self, require_local: bool = False
    ) -> List[Tuple[Material, float, List[str]]]:
        """Rank non-canonical, available materials by honest score."""
        ranked = [
            (m, *self.score(m, require_local))
            for m in self.materials
            if not m.canonical
        ]
        ranked.sort(key=lambda t: t[1], reverse=True)
        return ranked


@dataclass
class BoardPlan:
    """The grid, drawn at true spacing — by machine or by hand."""

    material: Material
    spacing: Tuple[float, float] = CANONICAL_SPACING
    lines: int = GRID_LINES
    drawn_by: str = "hand"

    def __post_init__(self) -> None:
        sx, sy = self.spacing
        if sx <= 0 or sy <= 0:
            raise ValueError("spacing must be positive")
        if self.lines < 2:
            raise ValueError("grid needs at least 2 lines")

    # -- grid geometry -------------------------------------------------------------------
    def generate_grid(self) -> Tuple[List[float], List[float]]:
        """(vertical x-coords, horizontal y-coords) in mm from the origin."""
        sx, sy = self.spacing
        verticals = [round(i * sx, 3) for i in range(self.lines)]
        horizontals = [round(i * sy, 3) for i in range(self.lines)]
        return verticals, horizontals

    def board_size(self) -> Tuple[float, float]:
        """Finished board footprint in mm."""
        v, h = self.generate_grid()
        return v[-1], h[-1]

    def hand_drawn(
        self, seed: int = 0, wobble: float = 0.3
    ) -> Tuple[List[float], List[float]]:
        """The same grid with a human hand in it: seeded, reproducible
        jitter (mm) per line, so the plan admits imperfection instead
        of pretending to be machine-perfect."""
        if wobble < 0:
            raise ValueError("wobble must be >= 0")
        rng = random.Random(seed)
        v, h = self.generate_grid()

        def jitter() -> float:
            return round(rng.uniform(-wobble, wobble), 3)

        return [round(x + jitter(), 3) for x in v], [round(y + jitter(), 3) for y in h]

    def star_points(self) -> List[Tuple[int, int]]:
        """Grid indices of the star (hoshi) points for the line count.

        Standard 19x19: 3-3 / 3-9 / 3-15 pattern on the 4-4, 10-10,
        16-16 lines (0-based). Smaller boards get the center only.
        """
        if self.lines == GRID_LINES:
            pts = (3, 9, 15)
            return [(r, c) for r in pts for c in pts]
        mid = self.lines // 2
        return [(mid, mid)]

    # -- the honest plaque ------------------------------------------------------------------
    def label(self) -> str:
        canon = "kaya (unavailable)"
        status = (
            f"Substitute board in {self.material.name} — "
            f"the canonical {canon} is extinct in this workshop. "
            f"Grid drawn {self.drawn_by} at {self.spacing[0]}x{self.spacing[1]} mm spacing."
        )
        return status

    def summary(self) -> Dict[str, object]:
        w, d = self.board_size()
        return {
            "material": self.material.name,
            "canonical_substitute": not self.material.canonical,
            "grid": f"{self.lines}x{self.lines}",
            "spacing_mm": self.spacing,
            "footprint_mm": (w, d),
            "label": self.label(),
        }
