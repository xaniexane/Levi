"""LEVI's concentric memory wheels: N image-keyed rings whose rotations align concepts.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #3)

The old mechanism: concentric wheels, each ring carrying a sequence of
images or concepts around its rim; rotate the wheels against each other and
the columns that line up at any moment are the combinations worth
contemplating. The mechanism is rotation + alignment — a fixed rotation
procedure generates an ordered series of configurations, and *alignment*
is the query: at rotation r, which concepts stand together?

``Wheels`` holds N rings of equal length (pad or trim at construction —
the builder is honest about that). ``rotate`` sets the global rotation
count; each ring's offset at rotation r is r × ring.step slots (default
step 1). ``alignment(r)`` returns the one concept per ring lined up at the
reference spoke for rotation r. ``sweep`` walks every distinct rotation in
order and returns the full configuration series. ``query(concept)`` answers
the inverse: at which rotations does this concept align with another given
concept on a different ring — the proximity-by-alignment question.

All arithmetic is modular and deterministic. Same rings, same rotation ⇒
same alignment, forever.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

ORIGIN = "levi-revival/wheels"


class WheelError(Exception):
    """Base class for wheel failures."""


class EmptyRing(WheelError):
    """A ring was given no concepts."""


@dataclass
class Ring:
    """One concentric ring: ordered concepts and a per-rotation step size."""

    name: str
    concepts: List[Any]
    step: int = 1

    def __post_init__(self):
        if not self.concepts:
            raise EmptyRing(f"ring {self.name!r} has no concepts")

    def __len__(self) -> int:
        return len(self.concepts)


class Wheels:
    """N concentric rings of concepts, queried by rotation."""

    def __init__(self, rings: List[Ring]):
        if not rings:
            raise WheelError("need at least one ring")
        sizes = {len(r) for r in rings}
        if len(sizes) != 1:
            raise WheelError(
                f"rings must be equal length for clean alignment, got sizes {sorted(sizes)}"
            )
        self.rings = rings
        self.size = len(rings[0])

    @classmethod
    def build(cls, ring_specs: List[Tuple[str, List[Any], int]]) -> "Wheels":
        """Build from (name, concepts, step) specs."""
        return cls([Ring(name=n, concepts=list(c), step=s) for n, c, s in ring_specs])

    # -- rotation -----------------------------------------------------------
    def spoke_index(self, ring: Ring, rotation: int) -> int:
        """Which slot of the ring sits at the reference spoke at rotation r."""
        return (rotation * ring.step) % len(ring)

    def alignment(self, rotation: int) -> Dict[str, Any]:
        """The concepts aligned at the reference spoke for rotation r."""
        return {
            ring.name: ring.concepts[self.spoke_index(ring, rotation)]
            for ring in self.rings
        }

    def sweep(self) -> List[Dict[str, Any]]:
        """Every distinct rotation in order: the full configuration series."""
        return [self.alignment(r) for r in range(self.size)]

    # -- proximity by alignment ----------------------------------------------
    def query(self, concept: Any, ring_name: str, partner_ring: str) -> List[int]:
        """At which rotations does `concept` (on `ring_name`) align with any
        concept on `partner_ring`? Returns the rotation indices plus, for
        each, which partner concept stood with it."""
        self._ring(ring_name)  # validate ring names
        self._ring(partner_ring)
        return [r for r in range(self.size) if self.alignment(r)[ring_name] == concept]

    def coaligned(self, concept: Any, ring_name: str, rotation: int) -> Optional[Any]:
        """What the partner alignment was at one rotation, or None if the
        concept isn't at the reference spoke then."""
        if self.alignment(rotation)[ring_name] != concept:
            return None
        return {
            r.name: self.alignment(rotation)[r.name]
            for r in self.rings
            if r.name != ring_name
        }

    def partners_of(self, concept: Any, ring_name: str, partner_ring: str) -> List[Any]:
        """Every concept on partner_ring that ever aligns with this concept,
        in rotation order — the full co-occurrence set."""
        seen: List[Any] = []
        for r in range(self.size):
            if self.alignment(r)[ring_name] == concept:
                other = self.alignment(r)[partner_ring]
                if other not in seen:
                    seen.append(other)
        return seen

    def configuration_at(self, rotation: int) -> Tuple[Any, ...]:
        """The raw ordered tuple of aligned concepts at rotation r."""
        return tuple(self.alignment(rotation)[r.name] for r in self.rings)

    # -- internals ----------------------------------------------------------
    def _ring(self, name: str) -> Ring:
        for ring in self.rings:
            if ring.name == name:
                return ring
        raise KeyError(f"no ring named {name!r}")

    def __len__(self) -> int:
        return len(self.rings)
