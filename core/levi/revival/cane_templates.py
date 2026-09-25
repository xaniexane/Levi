"""Cross-sectional encoding: one master drawn into many identical instances.

Studied from: lost-crafts-20260916/report.md [Batch 4] (Millefiori / Murrine)

The studied shape: a glassmaker composes one cross-sectional pattern
(the cane's face), then draws the whole cane out so the single master
becomes many identical slices. The pattern is designed once and
multiplied losslessly. Millefiori bundles several canes into one
composite face ("a thousand flowers").

LEVI-native re-expression: a template system. A **Cane** holds one
master pattern (a 2D grid of cell codes — the cross-section). Drawing
the cane *compresses* a repetitive layout into `master + slice count`
instead of spelling out every slice; decoding regenerates every slice
bit-for-bit. **Bundling** fuses several canes into a composite master
pattern. Compression ratio is reported honestly: pattern bytes vs
expanded bytes.

Cell codes are single characters or short tokens; the only rule is that
the alphabet is consistent within a cane.

Operations:

* ``Cane.draw(pattern)`` — record the master cross-section
* ``Cane.slice(n)`` — draw out n identical instances (lossless)
* ``Cane.encode() / Cane.decode(payload)`` — serialize the master +
  draw count as compact text; decode reproduces the master exactly
* ``millefiori(canes, layout)`` — bundle canes into a composite master
* ``compression_ratio(n)`` — expanded size / encoded size

Honest limits: the "compression" is exact only for identical slices —
patterns that vary slice-to-slice don't fit the model and LEVI says
so. This is a template-multiplication mechanism, not a general
compressor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple


ORIGIN = "levi-revival/cane-templates"


def _validate_grid(grid: Sequence[Sequence[str]]) -> Tuple[Tuple[str, ...], ...]:
    if not grid:
        raise ValueError("pattern must have at least one row")
    width = len(grid[0])
    if width == 0:
        raise ValueError("pattern rows must be non-empty")
    for i, row in enumerate(grid):
        if len(row) != width:
            raise ValueError(
                f"row {i} has width {len(row)}, expected {width} — cross-section must be rectangular"
            )
        for cell in row:
            if not isinstance(cell, str) or not cell:
                raise ValueError("every cell must be a non-empty string code")
    return tuple(tuple(r) for r in grid)


@dataclass
class Cane:
    """One master cross-section that draws out into identical slices."""

    name: str = "cane"
    master: Tuple[Tuple[str, ...], ...] = field(default_factory=tuple)

    def draw(self, pattern: Sequence[Sequence[str]]) -> "Cane":
        """Compose the master face. Returns self for chaining."""
        self.master = _validate_grid(pattern)
        return self

    # -- the draw: one master, many identical instances ---------------------------
    @property
    def shape(self) -> Tuple[int, int]:
        if not self.master:
            raise ValueError("cane has no master pattern — call draw() first")
        return len(self.master), len(self.master[0])

    def slice(self, n: int) -> List[Tuple[Tuple[str, ...], ...]]:
        """Draw out n identical slices of the master cross-section."""
        if n <= 0:
            raise ValueError("slice count must be >= 1")
        if not self.master:
            raise ValueError("cane has no master pattern — call draw() first")
        return [self.master for _ in range(n)]

    def is_identical(self, slices: Sequence[Tuple[Tuple[str, ...], ...]]) -> bool:
        """True if every slice matches the master exactly (lossless check)."""
        return all(s == self.master for s in slices)

    # -- compact encoding ----------------------------------------------------------
    def encode(self, draws: int) -> str:
        """master + draw count as compact text: the lossless shorthand."""
        if draws <= 0:
            raise ValueError("draw count must be >= 1")
        rows, cols = self.shape
        flat = "".join(cell for row in self.master for cell in row)
        return f"{self.name}|{rows}x{cols}|{draws}|{flat}"

    @classmethod
    def decode(cls, payload: str) -> Tuple["Cane", int]:
        """Rebuild the cane and draw count from an encoded payload.

        Raises ValueError if the payload is malformed or inconsistent.
        """
        try:
            name, dims, draws_s, flat = payload.split("|", 3)
            rows, cols = (int(x) for x in dims.split("x"))
            draws = int(draws_s)
        except ValueError as err:
            raise ValueError(f"malformed cane payload: {payload!r}") from err
        if rows <= 0 or cols <= 0 or draws <= 0:
            raise ValueError(f"invalid dimensions in payload: {payload!r}")
        if len(flat) != rows * cols:
            raise ValueError(
                f"payload body length {len(flat)} != declared {rows}x{cols}"
            )
        grid = tuple(tuple(flat[r * cols : (r + 1) * cols]) for r in range(rows))
        cane = cls(name=name)
        cane.draw(grid)
        return cane, draws

    # -- honest accounting ------------------------------------------------------------
    def compression_ratio(self, draws: int) -> float:
        """expanded bytes / encoded bytes for `draws` identical slices."""
        rows, cols = self.shape
        expanded = rows * cols * draws
        encoded = len(self.encode(draws))
        return round(expanded / max(1, encoded), 3)

    def expand(self, draws: int) -> List[str]:
        """Fully spell out `draws` slices as text rows (the expensive form)."""
        return ["".join("".join(row) for row in s) for s in self.slice(draws)]


def millefiori(canes: Sequence[Cane], name: str = "fiori") -> Cane:
    """Bundle several canes into one composite master cross-section.

    Canes tile side by side in a row (each drawn cane becomes a block
    of the composite face), like bundling rods before the final draw.
    """
    if not canes:
        raise ValueError("need at least one cane to bundle")
    heights = {c.shape[0] for c in canes}
    if len(heights) != 1:
        raise ValueError("all canes must have the same row count to bundle")
    composite = [list(row) for row in canes[0].master]
    for cane in canes[1:]:
        for r, row in enumerate(cane.master):
            composite[r].extend(row)
    return Cane(name=name).draw(composite)


def palette_usage(cane: Cane) -> Dict[str, int]:
    """Count of each cell code in the master — the pattern's palette."""
    counts: Dict[str, int] = {}
    for row in cane.master:
        for cell in row:
            counts[cell] = counts.get(cell, 0) + 1
    return counts
