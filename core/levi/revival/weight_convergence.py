"""LEVI's merchant consensus: a standard nobody owns, everybody checks.

Studied from: lost-crafts-20260916/report.md [Batch 2] (functional description
only; no historical claims).

The lesson, reborn as LEVI's own: a shared unit of weight can emerge without
any central authority when merchants repeatedly *cross-check* each other's
weight-stones and nudge their own standard toward the ones that check out.
Each merchant carries a local standard (grams per shekel) plus a trust score
for every peer. Each round, pairs weigh one another's stones; a merchant moves
its standard toward peers it trusts, and trust itself rises for peers whose
standards agree and falls for outliers. The group statistic — the shrinking
spread of the standards — is the convergence signal.

Honesty: HEURISTIC MODEL. This is adaptive weighted averaging (DeGroot-style
consensus with trust-adaptive weights), not a historical simulation. It shows
the *mechanism shape* — cross-checking drives variance down — not any claim
about how real merchants behaved. All randomness is seedable.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Sequence

ORIGIN = "levi-revival/weight-convergence"


@dataclass
class ConvergenceReport:
    """What happened over the rounds."""

    rounds: int
    initial_spread: float  # std of standards at round 0
    final_spread: float  # std of standards at the end
    consensus: float  # mean standard at the end
    converged: bool  # final_spread <= tolerance
    history: List[float] = field(default_factory=list)  # spread per round
    final_trust: Dict[str, Dict[str, float]] = field(default_factory=dict)


def _std(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return math.sqrt(sum((v - mean) ** 2 for v in values) / n)


def cross_check(
    standards: Dict[str, float],
    rounds: int = 50,
    seed: int = 7,
    nudge: float = 0.5,
    tolerance: float = 0.02,
    trust_learning: float = 0.15,
) -> ConvergenceReport:
    """Run the cross-checking protocol and report convergence.

    ``standards`` maps merchant name -> its local grams-per-shekel. Each
    round, merchants are shuffled into pairs; each merchant moves its
    standard a fraction ``nudge`` toward its partner's, weighted by trust.
    Trust in a peer grows when the two standards agree within ``tolerance``
    and shrinks otherwise. Returns a report with the spread history.
    """
    if not standards:
        raise ValueError("need at least one merchant")
    if not 0.0 < nudge <= 1.0:
        raise ValueError("nudge must be in (0, 1]")

    rng = random.Random(seed)
    names = list(standards)
    current = dict(standards)
    trust: Dict[str, Dict[str, float]] = {
        a: {b: 0.5 for b in names if b != a} for a in names
    }

    history = [_std(list(current.values()))]
    for _ in range(rounds):
        order = names[:]
        rng.shuffle(order)
        # Pair off (a leftover merchant sits the round out).
        pairs = [(order[i], order[i + 1]) for i in range(0, len(order) - 1, 2)]
        proposed: Dict[str, float] = {}
        for a, b in pairs:
            sa, sb = current[a], current[b]
            agree = abs(sa - sb) <= tolerance * max(sa, sb, 1e-9)
            # Trust update: agreement earns trust, disagreement spends it.
            for x, y in ((a, b), (b, a)):
                t = trust[x][y] + (trust_learning if agree else -trust_learning)
                trust[x][y] = min(1.0, max(0.0, t))
            wa = trust[a][b]
            wb = trust[b][a]
            # Each merchant nudges toward the peer, weighted by its trust.
            proposed[a] = sa + nudge * wa * (sb - sa)
            proposed[b] = sb + nudge * wb * (sa - sb)
        current.update(proposed)
        history.append(_std(list(current.values())))

    final_values = list(current.values())
    final_spread = history[-1]
    return ConvergenceReport(
        rounds=rounds,
        initial_spread=history[0],
        final_spread=final_spread,
        consensus=sum(final_values) / len(final_values),
        converged=final_spread
        <= tolerance * max(abs(sum(final_values) / len(final_values)), 1e-9),
        history=history,
        final_trust={a: dict(row) for a, row in trust.items()},
    )


def trusted_peers(trust_row: Dict[str, float], threshold: float = 0.6) -> List[str]:
    """Peers in one merchant's trust row above ``threshold``, highest first."""
    return sorted(
        (p for p, t in trust_row.items() if t >= threshold),
        key=lambda p: trust_row[p],
        reverse=True,
    )
