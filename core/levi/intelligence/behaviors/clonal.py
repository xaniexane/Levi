"""Clonal selection — immune affinity maturation (class IMM, organ riem).

Real mechanism (Burnet 1957): a diverse B-cell repertoire exists; an
antigen selects the cells that bind it; the chosen clone and multiply
(clonal expansion); offspring undergo somatic hypermutation — mutation
rate inversely proportional to affinity — and the best binders win
(affinity maturation). Memory cells keep the winners: selection promoted
into the genome. Translated: generate-mutate-select loop where the best
solutions clone the most and mutate the least.
"""

from __future__ import annotations

import random
from typing import Callable, List, Tuple


def clonal_select(
    fitness: Callable[[List[int]], float],
    genome_length: int,
    population: int = 20,
    generations: int = 30,
    clones: int = 5,
    base_mutation: float = 0.3,
    seed: int = 0,
) -> Tuple[List[int], float, List[float]]:
    """Run clonal selection. Returns (best genome, best fitness, history).

    fitness: higher is better. Genomes are bitstrings.
    """
    rng = random.Random(seed)
    pop = [[rng.randint(0, 1) for _ in range(genome_length)] for _ in range(population)]
    history: List[float] = []
    for _ in range(generations):
        scored = sorted(
            ((fitness(g), g) for g in pop),
            key=lambda t: t[0],
            reverse=True,
        )
        history.append(scored[0][0])
        elites = [g for _, g in scored[:clones]]
        new_pop: List[List[int]] = []
        for rank, genome in enumerate(elites):
            # better rank -> more clones, less mutation (affinity maturation)
            n_clones = clones - rank
            mut_rate = base_mutation / (rank + 1)
            for _ in range(n_clones):
                child = [bit if rng.random() > mut_rate else 1 - bit for bit in genome]
                new_pop.append(child)
        while len(new_pop) < population:  # fresh diversity, like marrow
            new_pop.append([rng.randint(0, 1) for _ in range(genome_length)])
        pop = new_pop[:population]
    best_fit, best = max(((fitness(g), g) for g in pop), key=lambda t: t[0])
    history.append(best_fit)
    return best, best_fit, history
