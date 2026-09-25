"""LEVI's heuristic discovery engine for the growth loop (DISPUTED history).

Inspired by Eurisko (Douglas Lenat, 1976–1982 — the AM successor; the
1981 Traveller TCS naval-wargame story: Eurisko allegedly won the
tournament twice with "cheesy" fleets, after which the rules were changed
to exclude it). The ahead-of-its-time mechanisms: heuristics as first-
class objects that suggest concepts, *credit assignment* (which
heuristics earned the win), and meta-heuristics that propose new
heuristics — automated discovery, not just automated search.

Remix delta: Eurisko's discovery loop reimagined for LEVI's *growth loop*
("raise baby Levi") — not a game-playing clone. Heuristics are scorable
objects competing over judged rounds (e.g. triaging the morning feed);
credit assignment tracks who earned the win; meta-heuristics breed
variants that enter a probationary pool and must earn their place or be
culled. The improvement over the original framing is honesty by
construction: the module warns that credit is only as good as the judge
you supply, and the historical claims stay labeled disputed.

**Honesty — read this first.** The historical claims around Eurisko are
DISPUTED. Contemporary accounts conflict on how much of the Traveller
story is legend versus documented tournament record; Lenat's own later
accounts and independent retellings disagree on details, and the
available sources are thin. Treat the framing above as lore, not settled
history. What survives scrutiny is the *mechanism* — heuristics as
scorable, composable objects with credit assignment and meta-heuristics
— and that mechanism is all this module revives.

This is an original, from-scratch reimplementation for LEVI — no Eurisko
code is used. ``Heuristic`` objects propose candidate solutions to a
problem and carry a track record (wins/uses → score). ``CreditAssigner``
runs a round: every heuristic proposes, a judge scores the proposals,
credit flows back to the winners proportional to their contribution.
``MetaHeuristic`` objects propose *new* heuristics (mutating or combining
existing ones), which enter a probationary pool and must earn their place
— discoveries are scored, never trusted on arrival.

The LEVI application: "raise baby Levi" — heuristics for triaging the
morning feed, for example, compete over weeks; the ones that actually
surface useful items earn credit and breed variants; meta-heuristics
propose the variants. A small, honest discovery engine.

Honesty: USEFUL PATTERN — the discovery loop is genuinely useful; the
historical framing is explicitly disputed. Credit is only as good as the
judge you supply: garbage judging produces confident garbage — the
module says so in :meth:`CreditAssigner.run_round`.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DiscoveryError(Exception):
    """Base class for discovery failures."""


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------

Proposer = Callable[[Any], Any]  # problem -> candidate solution
Judge = Callable[[Any, Any], float]  # (problem, candidate) -> score in [0, 1]


@dataclass
class Heuristic:
    """A heuristic: proposes candidate solutions, keeps a scored track
    record. ``score`` is the credit-weighted win rate with a small prior
    so new heuristics start at 0.5 (neutral), not 0 (dead)."""

    name: str
    propose: Proposer
    wins: float = 0.0
    uses: float = 0.0
    prior: float = 0.5

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("heuristic name must be non-empty")

    @property
    def score(self) -> float:
        total = self.uses + 1.0  # the prior counts as one pseudo-observation
        return (self.wins + self.prior) / total

    def record(self, credit: float) -> None:
        """Credit assignment: ``credit`` in [0, 1] for this round."""
        if not 0.0 <= credit <= 1.0:
            raise ValueError("credit must be in [0, 1]")
        self.uses += 1.0
        self.wins += credit

    def candidate(self, problem: Any) -> Any:
        return self.propose(problem)


# ---------------------------------------------------------------------------
# Credit assignment
# ---------------------------------------------------------------------------


class CreditAssigner:
    """Runs discovery rounds: every heuristic proposes, the judge scores,
    credit flows back proportional to contribution."""

    def __init__(
        self,
        heuristics: Optional[list[Heuristic]] = None,
        judge: Optional[Judge] = None,
    ):
        self.heuristics: list[Heuristic] = list(heuristics or [])
        self.judge = judge
        self.rounds = 0
        self.history: list[dict] = []

    def add(self, heuristic: Heuristic) -> None:
        if any(h.name == heuristic.name for h in self.heuristics):
            raise ValueError(f"heuristic {heuristic.name!r} already registered")
        self.heuristics.append(heuristic)

    def run_round(self, problem: Any) -> dict:
        """One round. Returns the round record: proposals, scores, credits.

        Honest warning: credit is only as good as ``judge``. A bad judge
        produces confident garbage — the scores will look rigorous and
        mean nothing. Vet the judge, not the loop.
        """
        if self.judge is None:
            raise DiscoveryError("no judge supplied: cannot score proposals")
        if not self.heuristics:
            raise DiscoveryError("no heuristics registered")
        scored: list[tuple[Heuristic, Any, float]] = []
        for h in self.heuristics:
            try:
                cand = h.candidate(problem)
            except Exception:
                cand = None  # a crashing heuristic proposes nothing
            try:
                s = float(self.judge(problem, cand)) if cand is not None else 0.0
            except Exception:
                s = 0.0
            s = max(0.0, min(1.0, s))
            scored.append((h, cand, s))
        best = max(s for _, _, s in scored)
        # Credit: full credit to the best, proportional credit to the rest
        # (relative contribution — Lenat's "who earned the win").
        for h, _, s in scored:
            credit = (
                1.0
                if (best > 0 and math.isclose(s, best))
                else (s / best if best > 0 else 0.0)
            )
            h.record(credit)
        self.rounds += 1
        record = {
            "round": self.rounds,
            "best_score": best,
            "results": [(h.name, s) for h, _, s in scored],
        }
        self.history.append(record)
        return record

    def leaderboard(self) -> list[tuple[str, float, float]]:
        """``(name, score, uses)`` sorted by score — who earned their keep."""
        return sorted(
            ((h.name, h.score, h.uses) for h in self.heuristics),
            key=lambda row: row[1],
            reverse=True,
        )


# ---------------------------------------------------------------------------
# Meta-heuristics: heuristics that propose new heuristics
# ---------------------------------------------------------------------------


@dataclass
class MetaHeuristic:
    """Proposes new heuristics from existing ones. The two built-ins:
    *mutate* (perturb a heuristic's proposer) and *combine* (blend two
    proposers). Custom ``breed`` callables receive the parent pool."""

    name: str
    kind: str = "mutate"  # mutate | combine | custom
    breed: Optional[Callable[[list[Heuristic], random.Random], Optional[Heuristic]]] = (
        None
    )

    def __post_init__(self) -> None:
        if self.kind not in ("mutate", "combine", "custom"):
            raise ValueError(f"unknown meta-heuristic kind {self.kind!r}")
        if self.kind == "custom" and self.breed is None:
            raise ValueError("custom meta-heuristics need a breed callable")

    def propose(
        self, pool: list[Heuristic], rng: Optional[random.Random] = None
    ) -> Optional[Heuristic]:
        rng = rng or random.Random()
        if self.kind == "custom":
            assert self.breed is not None
            return self.breed(pool, rng)
        if not pool:
            return None
        if self.kind == "mutate":
            parent = rng.choice(pool)
            child_propose = _mutate_proposer(parent.propose, rng)
            return Heuristic(f"{parent.name}+m{len(pool)}", child_propose)
        # combine
        if len(pool) < 2:
            return None
        a, b = rng.sample(pool, 2)
        child_propose = _combine_proposers(a.propose, b.propose, rng)
        return Heuristic(f"{a.name}x{b.name}", child_propose)


def _mutate_proposer(propose: Proposer, rng: random.Random) -> Proposer:
    """A mutated proposer: usually behaves like the parent, occasionally
    perturbs numeric candidates (the honest, minimal "mutation")."""

    def mutated(problem: Any) -> Any:
        cand = propose(problem)
        if isinstance(cand, (int, float)) and not isinstance(cand, bool):
            if rng.random() < 0.3:
                return cand + rng.uniform(-0.5, 0.5) * (abs(cand) or 1.0)
        return cand

    return mutated


def _combine_proposers(pa: Proposer, pb: Proposer, rng: random.Random) -> Proposer:
    """A combined proposer: picks a parent's candidate at random per call
    (recombination of *behavior*, honestly labeled — not a real crossover)."""

    def combined(problem: Any) -> Any:
        return pa(problem) if rng.random() < 0.5 else pb(problem)

    return combined


class DiscoveryPool:
    """The full loop: a probationary pool where meta-heuristics propose
    children, children must earn their place over ``probation_rounds``
    judged rounds, and the weak are culled."""

    def __init__(self, judge: Judge, seed: Optional[int] = None):
        self.assigner = CreditAssigner(judge=judge)
        self.metas: list[MetaHeuristic] = []
        self.rng = random.Random(seed)
        self.probation_rounds = 3

    def seed_heuristic(self, heuristic: Heuristic) -> None:
        self.assigner.add(heuristic)

    def add_meta(self, meta: MetaHeuristic) -> None:
        self.metas.append(meta)

    def evolve(self, problem: Any, generations: int = 1) -> dict:
        """Run ``generations`` discovery generations. Each generation:
        meta-heuristics propose children → children enter probation →
        ``probation_rounds`` judged rounds → cull heuristics scoring below
        0.5 with at least one use. Returns the final leaderboard."""
        if generations < 1:
            raise ValueError("generations must be >= 1")
        for _ in range(generations):
            for meta in self.metas:
                child = meta.propose(self.assigner.heuristics, self.rng)
                if child is not None:
                    try:
                        self.assigner.add(child)
                    except ValueError:
                        pass  # name collision: the child doesn't get born
            for _ in range(self.probation_rounds):
                self.assigner.run_round(problem)
            self.assigner.heuristics = [
                h
                for h in self.assigner.heuristics
                if not (h.uses >= 1.0 and h.score < 0.5)
            ]
        return {
            "leaderboard": self.assigner.leaderboard(),
            "rounds": self.assigner.rounds,
        }


__all__ = [
    "DiscoveryError",
    "Heuristic",
    "CreditAssigner",
    "MetaHeuristic",
    "DiscoveryPool",
]
