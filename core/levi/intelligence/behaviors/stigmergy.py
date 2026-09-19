"""Stigmergy — ant-colony pheromone coordination (class ANT, organ mandella).

Real mechanism: ants deposit pheromone as they walk; pheromone evaporates;
ants probabilistically follow the strongest local gradient. No ant knows
the plan. The trail IS the plan. Translated: a shared pheromone field over
a grid that lets dumb walkers converge on a target under fog.

Reference behavior: Deneubourg-style trail formation — deposit on success,
evaporate always, follow uphill.
"""

from __future__ import annotations

import random
from typing import List, Tuple


class PheromoneField:
    """A 2D pheromone field with deposit / evaporate / follow."""

    def __init__(
        self, width: int, height: int, evaporation: float = 0.05, seed: int = 0
    ) -> None:
        assert 0.0 < evaporation < 1.0
        self.width = width
        self.height = height
        self.evaporation = evaporation
        self.rng = random.Random(seed)
        self.grid: List[List[float]] = [[0.0] * width for _ in range(height)]

    def deposit(self, x: int, y: int, amount: float) -> None:
        self.grid[y % self.height][x % self.width] += amount

    def evaporate(self) -> None:
        keep = 1.0 - self.evaporation
        for row in self.grid:
            for i, v in enumerate(row):
                row[i] = v * keep

    def sense(self, x: int, y: int) -> float:
        return self.grid[y % self.height][x % self.width]

    def follow(self, x: int, y: int) -> Tuple[int, int]:
        """Step to the neighboring cell with the strongest pheromone.

        Ties and flat fields resolve randomly (seeded) — the fog is real.
        """
        best = (x, y)
        best_v = self.sense(x, y)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = (x + dx) % self.width, (y + dy) % self.height
                v = self.sense(nx, ny)
                if v > best_v or (v == best_v and self.rng.random() < 0.25):
                    best, best_v = (nx, ny), v
        return best


def lay_trail(
    field: PheromoneField, path: List[Tuple[int, int]], amount: float = 1.0
) -> None:
    """An ant walking home deposits pheromone along its whole path."""
    for x, y in path:
        field.deposit(x, y, amount)
