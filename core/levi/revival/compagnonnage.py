"""Forced rotation across workshops so no single master's blind spots persist.

Studied from: lost-crafts-20260916/report.md [Batch 1] (the compagnonnage:
journeymen rotate across workshops — the tour — so no one master or shop
shapes their whole craft).

This is an original, from-scratch implementation for LEVI. A ``Tour`` moves a
journeyman through a sequence of ``Placement``s, one per workshop, with three
honest invariants enforced by the scheduler:

1. **Full coverage first**: a journeyman cannot repeat any workshop until
   every workshop on the circuit has been visited once.
2. **Handoff record**: each placement records what was studied and what the
   receiving master certified — the rotation produces a documented lineage,
   not just a travel log.
3. **Cooling-off on return**: when the circuit restarts, the journeyman does
   not return to the immediately-previous workshop first (rotation order is
   shuffled deterministically by a seed, and the starting workshop is forced
   to differ from the last visited one).

Placement durations are nominal "seasons" (integers) — the module tracks
ordering and coverage, not calendar time. It never claims to model real
apprenticeship law; it is a rotation scheduler with auditable handoffs.

Public surface:
- ``Tour``: ``begin()``, ``complete_placement(studies, certified_by)``,
  ``current`` / ``placements()`` / ``coverage()`` / ``done``.
- ``Workshop``, ``Placement``, ``RotationError`` for embedding.

stdlib-only. No network. Deterministic (seeded shuffle, no random module).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import List, Optional, Sequence

ORIGIN = "levi-revival/compagnonnage"


class RotationError(ValueError):
    """Raised when a rotation step violates the tour's invariants."""


@dataclass(frozen=True)
class Workshop:
    name: str
    specialty: str
    master: str


@dataclass
class Placement:
    workshop: Workshop
    season: int
    studies: str = ""
    certified_by: str = ""
    complete: bool = False


class Tour:
    """A forced-rotation tour across a circuit of workshops."""

    def __init__(
        self,
        journeyman: str,
        workshops: Sequence[Workshop],
        rounds: int = 1,
        seed: str = "levi-tour",
    ) -> None:
        if not journeyman:
            raise RotationError("journeyman must be named")
        workshops = list(workshops)
        if len(workshops) < 2:
            raise RotationError("a tour needs at least 2 workshops")
        names = [w.name for w in workshops]
        if len(set(names)) != len(names):
            raise RotationError("workshop names must be unique")
        if rounds < 1:
            raise RotationError("rounds must be >= 1")
        self.journeyman = journeyman
        self.rounds = rounds
        self.seed = seed
        # Deterministic per-round order: sort by hash of (seed, round, name).
        self._circuit: List[List[Workshop]] = [
            sorted(
                workshops,
                key=lambda w, r=r: hashlib.sha256(
                    f"{seed}|{r}|{w.name}".encode()
                ).hexdigest(),
            )
            for r in range(rounds)
        ]
        # Invariant 3: never start a new round where the last one ended.
        for r in range(1, rounds):
            if (
                self._circuit[r][0].name == self._circuit[r - 1][-1].name
                and len(workshops) > 1
            ):
                self._circuit[r] = self._circuit[r][1:] + self._circuit[r][:1]
        self._placements: List[Placement] = []
        self._cursor = 0  # index into flattened circuit

    def _flat(self) -> List[Workshop]:
        return [w for round_ in self._circuit for w in round_]

    def begin(self) -> Placement:
        """Start the tour; returns the first placement."""
        if self._placements:
            raise RotationError("tour already begun")
        flat = self._flat()
        placement = Placement(workshop=flat[0], season=1)
        self._placements.append(placement)
        return placement

    @property
    def current(self) -> Optional[Placement]:
        if not self._placements:
            return None
        return self._placements[-1]

    @property
    def done(self) -> bool:
        return (
            self._cursor >= len(self._flat())
            and bool(self._placements)
            and self._placements[-1].complete
        )

    def complete_placement(self, studies: str, certified_by: str) -> Placement:
        """Close the current placement and advance to the next workshop.

        Invariant 1 is structural: the circuit itself contains each workshop
        exactly once per round, so repeats are impossible before full coverage.
        """
        cur = self.current
        if cur is None:
            raise RotationError("tour has not begun; call begin() first")
        if cur.complete:
            raise RotationError("current placement already completed")
        if certified_by != cur.workshop.master:
            raise RotationError(
                f"placement must be certified by the workshop master {cur.workshop.master!r}"
            )
        cur.studies = studies
        cur.certified_by = certified_by
        cur.complete = True
        self._cursor += 1
        flat = self._flat()
        if self._cursor < len(flat):
            nxt = Placement(workshop=flat[self._cursor], season=self._cursor + 1)
            self._placements.append(nxt)
            return nxt
        return cur

    def placements(self) -> List[Placement]:
        return list(self._placements)

    def coverage(self) -> List[str]:
        """Workshop names visited so far, in order (completed ones only)."""
        return [p.workshop.name for p in self._placements if p.complete]

    def full_circuit_names(self) -> List[str]:
        """The scheduled visit order for the whole tour."""
        return [w.name for w in self._flat()]
