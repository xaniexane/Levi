"""Hatter behaviors — chaos routing for the under-credited engine.

Hatter is the chaotic identity generator of the keeper's cosmology:
chaos routing, diagonal/cross movement, paradox held live. These are its
working organs — not metaphors, mechanisms:

- diagonal_search: non-local jumps across the search space (the diagonal
  move — never adjacent, always across).
- NoiseInjector: seeded, reproducible chaos. Same seed, same storm —
  chaos you can replay is a tool, not an accident.
- paradox_holder: re-exported from cuttlefish — two contradictory plans
  live at once until evidence resolves them.
"""

from __future__ import annotations

import random
from typing import Callable, List, Tuple

from levi.intelligence.behaviors.cuttlefish import ParadoxHolder

__all__ = ["ParadoxHolder", "diagonal_search", "NoiseInjector"]


def diagonal_search(
    space: List[int],
    fitness: Callable[[int], float],
    jumps: int = 20,
    seed: int = 0,
) -> Tuple[int, float, List[float]]:
    """Search by diagonal leaps: each jump lands far from the last.

    Picks a random distant index (>= len/4 away), keeps the best seen.
    Returns (best_index, best_fitness, history).
    """
    rng = random.Random(seed)
    n = len(space)
    assert n >= 4
    best_i = 0
    best_f = fitness(space[0])
    history = [best_f]
    current = 0
    for _ in range(jumps):
        # the diagonal: never a neighbor, always across the board
        lo = (current + n // 4) % n
        hi = (current + 3 * n // 4) % n
        if lo <= hi:
            nxt = rng.randint(lo, hi)
        else:  # wrapped range
            nxt = rng.choice(list(range(lo, n)) + list(range(0, hi + 1)))
        f = fitness(space[nxt])
        if f > best_f:
            best_f, best_i = f, nxt
        current = nxt
        history.append(best_f)
    return best_i, best_f, history


class NoiseInjector:
    """Seeded chaos stream. Same seed -> same storm, every replay."""

    def __init__(self, seed: int = 0, amplitude: float = 1.0) -> None:
        self.rng = random.Random(seed)
        self.amplitude = amplitude
        self.seed = seed

    def gust(self) -> float:
        """One signed chaotic gust in [-amplitude, +amplitude]."""
        return (self.rng.random() * 2.0 - 1.0) * self.amplitude

    def perturb(self, values: List[float]) -> List[float]:
        """Shake a signal without destroying its shape."""
        return [v + self.gust() * 0.1 for v in values]

    def reset(self) -> None:
        """Rewind the storm to its first gust."""
        self.rng = random.Random(self.seed)
