"""odds_audit — drop tables with nothing to hide.

Studied from: dead-game-genres-2026-09-16/report.md (Build shortlist — anti-loot-box).

The load-bearing idea: a random reward is only honest when the player
can see the whole machine — every table published, the exact expected
value computed and shown, rolls free and unlimited, a visible pity
timer, and an empirical audit that replays thousands of rolls to
prove the published odds match reality.

LEVI's take: ``DropTable`` holds named outcomes with weights and
values. ``expected_value`` computes exact EV from the weights (no
simulation needed — it is arithmetic). ``roll`` is free and unlimited
by design: there is no currency argument anywhere. ``PityTimer``
guarantees the rarest outcome after N consecutive misses and always
shows its counter. ``prove`` runs N empirical rolls and compares
observed frequencies against published odds with a chi-square test,
reporting pass/fail plus the per-outcome deltas — the honest version
of "trust us".

Honest limits: ``prove`` is statistical, not a certificate — a small
sample can fail by luck, and passing does not prove the production
server uses the same table. EV is exact only for the declared table;
real games layer modifiers the table does not show.

This is an original, from-scratch implementation for LEVI.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional

ORIGIN = "levi-revival/odds-audit"


@dataclass(frozen=True)
class Outcome:
    """One row of a published drop table."""

    name: str
    weight: float  # relative probability weight; must be > 0
    value: float = 0.0  # expected in-game value, for EV math


class DropTable:
    """A fully published drop table: odds, EV, free rolls, pity, audit."""

    def __init__(
        self, name: str, outcomes: List[Outcome], pity_after: int = 90
    ) -> None:
        if not outcomes:
            raise ValueError("a drop table needs at least one outcome")
        if any(o.weight <= 0 for o in outcomes):
            raise ValueError("all weights must be positive")
        if pity_after < 1:
            raise ValueError("pity_after must be >= 1")
        self.name = name
        self.outcomes = list(outcomes)
        self.pity_after = pity_after
        self._pity_counter = 0
        self._rolls = 0

    # -- published math ------------------------------------------------
    def total_weight(self) -> float:
        return sum(o.weight for o in self.outcomes)

    def odds(self) -> Dict[str, float]:
        """Exact published probability per outcome. Sums to 1.0."""
        total = self.total_weight()
        return {o.name: o.weight / total for o in self.outcomes}

    def expected_value(self) -> float:
        """Exact EV per roll, from the published table. Arithmetic, not luck."""
        total = self.total_weight()
        return sum(o.value * o.weight / total for o in self.outcomes)

    def rarest(self) -> Outcome:
        return min(self.outcomes, key=lambda o: o.weight)

    # -- rolling: free, unlimited, pity-visible ------------------------
    def pity_status(self) -> Dict[str, object]:
        return {
            "misses_since_rarest": self._pity_counter,
            "guarantees_at": self.pity_after,
            "rolls_until_guarantee": self.pity_after - self._pity_counter,
        }

    def roll(self, rng: Optional[random.Random] = None) -> Outcome:
        """One roll. Free, unlimited — there is deliberately no cost argument."""
        rng = rng or random.Random()
        self._rolls += 1
        rarest = self.rarest()
        if self._pity_counter >= self.pity_after:
            self._pity_counter = 0
            return rarest
        total = self.total_weight()
        draw = rng.random() * total
        cumulative = 0.0
        for outcome in self.outcomes:
            cumulative += outcome.weight
            if draw < cumulative:
                if outcome.name == rarest.name:
                    self._pity_counter = 0
                else:
                    self._pity_counter += 1
                return outcome
        # float rounding fallback: last outcome
        if self.outcomes[-1].name == rarest.name:
            self._pity_counter = 0
        else:
            self._pity_counter += 1
        return self.outcomes[-1]

    @property
    def rolls_done(self) -> int:
        return self._rolls

    # -- empirical audit ------------------------------------------------
    def prove(self, trials: int = 10000, seed: int = 7) -> Dict[str, object]:
        """Replay ``trials`` rolls; chi-square test vs published odds.

        Returns pass/fail, the chi-square statistic, per-outcome
        observed-vs-expected deltas, and the pity triggers seen. A
        failure means the table as rolled does not match the table as
        published — investigate, don't ship.
        """
        if trials < 100:
            raise ValueError("prove needs at least 100 trials to mean anything")
        rng = random.Random(seed)
        # fresh table so the audit doesn't inherit live pity state
        audit_table = DropTable(self.name, self.outcomes, self.pity_after)
        counts: Dict[str, int] = {o.name: 0 for o in self.outcomes}
        pity_triggers = 0
        for _ in range(trials):
            before = audit_table._pity_counter
            outcome = audit_table.roll(rng)
            counts[outcome.name] += 1
            if before >= audit_table.pity_after:
                pity_triggers += 1
        published = self.odds()
        chi2 = 0.0
        deltas = {}
        for outcome in self.outcomes:
            expected = published[outcome.name] * trials
            observed = counts[outcome.name]
            deltas[outcome.name] = {
                "published": round(published[outcome.name], 6),
                "observed": round(observed / trials, 6),
                "delta": round(observed / trials - published[outcome.name], 6),
            }
            if expected > 0:
                chi2 += (observed - expected) ** 2 / expected
        # chi-square critical value, df = k-1, alpha = 0.01 (Wilson-Hilferty approx)
        df = len(self.outcomes) - 1
        critical = _chi2_critical_99(df)
        return {
            "table": self.name,
            "trials": trials,
            "chi_square": round(chi2, 3),
            "critical_99": round(critical, 3),
            "passed": chi2 < critical,
            "deltas": deltas,
            "pity_triggers": pity_triggers,
        }

    def publish(self) -> Dict[str, object]:
        """The whole machine, on paper: odds, EV, pity rule."""
        return {
            "table": self.name,
            "odds": {k: round(v, 6) for k, v in self.odds().items()},
            "expected_value_per_roll": round(self.expected_value(), 4),
            "pity": f"rarest outcome guaranteed after {self.pity_after} misses",
            "rolls_free_and_unlimited": True,
        }


def _chi2_critical_99(df: int) -> float:
    """Chi-square 99th percentile via the Wilson-Hilferty approximation.

    Good enough for an audit gate; exact tables would need scipy.
    """
    if df < 1:
        return float("inf")
    # 99th percentile of standard normal
    z = 2.32634787404084
    term = 1.0 - 2.0 / (9.0 * df) + z * math.sqrt(2.0 / (9.0 * df))
    return df * term**3
