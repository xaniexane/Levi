"""Conjugation — bacterial horizontal gene transfer (class BCT, organ riem).

Real mechanism: bacteria share plasmids (small DNA rings) by direct
contact; a useful trait — e.g. resistance — spreads through the
population sideways, not just parent-to-child. The winners' genes get
promoted into the shared pool. Translated: top performers donate
solution-fragments (plasmids) to neighbors; beneficial fragments sweep
the population in a few rounds.
"""

from __future__ import annotations

import random
from typing import Callable, List, Tuple


class Carrier:
    """One agent carrying a genome plus a set of plasmids (fragments)."""

    def __init__(self, genome: List[int], plasmids: List[List[int]]) -> None:
        self.genome = list(genome)
        self.plasmids = [list(p) for p in plasmids]

    def effective(self) -> List[int]:
        """Genome with plasmids spliced in (later plasmids win)."""
        out = list(self.genome)
        for p in self.plasmids:
            for i, bit in enumerate(p):
                if i < len(out):
                    out[i] = bit
        return out


def conjugate(
    fitness: Callable[[List[int]], float],
    population: List[Carrier],
    rounds: int = 10,
    donors: int = 2,
    seed: int = 0,
) -> Tuple[List[Carrier], List[float]]:
    """Run horizontal transfer. Returns (population, best-fitness history)."""
    rng = random.Random(seed)
    history: List[float] = []
    for _ in range(rounds):
        scored = sorted(population, key=lambda c: fitness(c.effective()), reverse=True)
        history.append(fitness(scored[0].effective()))
        # top donors share one plasmid each with random recipients
        for donor in scored[:donors]:
            if not donor.plasmids:
                continue
            plasmid = rng.choice(donor.plasmids)
            recipient = rng.choice(population)
            if recipient is not donor:
                recipient.plasmids.append(list(plasmid))
                recipient.plasmids = recipient.plasmids[-4:]
    return population, history


def trait_frequency(population: List[Carrier], locus: int, value: int = 1) -> float:
    """Fraction of the population expressing `value` at `locus`."""
    eff = [c.effective() for c in population]
    return sum(g[locus] == value for g in eff) / len(eff)
