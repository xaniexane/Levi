"""Analysis of Competing Hypotheses: rank by disconfirmation, not belief.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #18)

The mechanism is a discipline for the analyst's own mind: lay the
hypotheses down as columns, the evidence down as rows, and score each
cell for consistency. Then — the load-bearing rule — rank hypotheses by
*how little evidence disconfirms them*, most-consistent first, rather
than by how much you like them.

Two extra mechanisms make it more than a scoreboard:

* **Sensitivity analysis.** For every evidence item, re-run the ranking
  with that item removed. If removing one item flips the winner, the
  analysis is fragile at exactly that point — and now you know where.
* **Diagnosticity.** Evidence that is consistent with every hypothesis
  tells you nothing; the matrix tells you which rows are noise.

Consistency scores are plain floats in ``[-1.0, 1.0]``:

* ``+1.0`` — evidence strongly consistent with the hypothesis
* `` 0.0`` — neutral / irrelevant to the hypothesis
* ``-1.0`` — evidence inconsistent (disconfirming)

Any float in between is allowed; a score below 0 counts as a
disconfirmation for ranking purposes (threshold is exact: ``< 0``).

stdlib-only. No network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


ORIGIN = "levi-revival/ach"


@dataclass
class ACH:
    """A hypothesis x evidence consistency matrix."""

    hypotheses: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    scores: Dict[Tuple[int, int], float] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Building the matrix
    # ------------------------------------------------------------------
    def add_hypothesis(self, name: str) -> int:
        if not name or not name.strip():
            raise ValueError("hypothesis name must be non-empty")
        if name in self.hypotheses:
            raise ValueError(f"duplicate hypothesis: {name!r}")
        self.hypotheses.append(name)
        return len(self.hypotheses) - 1

    def add_evidence(self, name: str) -> int:
        if not name or not name.strip():
            raise ValueError("evidence name must be non-empty")
        if name in self.evidence:
            raise ValueError(f"duplicate evidence: {name!r}")
        self.evidence.append(name)
        return len(self.evidence) - 1

    def score(self, evidence: int | str, hypothesis: int | str, value: float) -> None:
        """Set the consistency score for one cell in ``[-1.0, 1.0]``."""
        if not isinstance(value, (int, float)) or not -1.0 <= value <= 1.0:
            raise ValueError("consistency score must be a float in [-1.0, 1.0]")
        e = self._evidence_index(evidence)
        h = self._hypothesis_index(hypothesis)
        self.scores[(e, h)] = float(value)

    def _evidence_index(self, evidence: int | str) -> int:
        return self._resolve(evidence, self.evidence, "evidence")

    def _hypothesis_index(self, hypothesis: int | str) -> int:
        return self._resolve(hypothesis, self.hypotheses, "hypothesis")

    @staticmethod
    def _resolve(ref: int | str, items: List[str], kind: str) -> int:
        if isinstance(ref, int):
            if 0 <= ref < len(items):
                return ref
            raise ValueError(f"{kind} index out of range: {ref}")
        try:
            return items.index(ref)
        except ValueError:
            raise ValueError(f"unknown {kind}: {ref!r}") from None

    # ------------------------------------------------------------------
    # Ranking by disconfirmation
    # ------------------------------------------------------------------
    def ranking(self, exclude: Optional[List[int]] = None) -> List[Dict]:
        """Rank hypotheses: fewest disconfirmations first.

        ``exclude`` lists evidence indices to leave out of the count
        (used by sensitivity analysis). Ties break on total support —
        the sum of all consistency scores — so a hypothesis that is
        consistent with more evidence still wins a clean tie.
        """
        excluded = set(exclude or [])
        rows = []
        for h, name in enumerate(self.hypotheses):
            disconfirmed = 0
            support = 0.0
            for e in range(len(self.evidence)):
                if e in excluded:
                    continue
                value = self.scores.get((e, h), 0.0)
                if value < 0:
                    disconfirmed += 1
                support += value
            rows.append(
                {
                    "hypothesis": name,
                    "disconfirmations": disconfirmed,
                    "support": round(support, 4),
                }
            )
        rows.sort(key=lambda r: (r["disconfirmations"], -r["support"]))
        for place, row in enumerate(rows, start=1):
            row["rank"] = place
        return rows

    def winner(self, exclude: Optional[List[int]] = None) -> Optional[str]:
        ranked = self.ranking(exclude=exclude)
        return ranked[0]["hypothesis"] if ranked else None

    # ------------------------------------------------------------------
    # Sensitivity analysis: which single item flips the verdict?
    # ------------------------------------------------------------------
    def sensitivity(self) -> Dict[str, object]:
        """For each evidence item, drop it and re-rank.

        Returns the baseline winner plus a list of "flips": evidence
        items whose removal changes the winner. An empty ``flips`` list
        means the ranking is robust to any single-item removal.
        """
        baseline = self.winner()
        flips = []
        for e, name in enumerate(self.evidence):
            new_winner = self.winner(exclude=[e])
            if new_winner != baseline:
                flips.append(
                    {
                        "evidence": name,
                        "baseline_winner": baseline,
                        "new_winner": new_winner,
                    }
                )
        return {"baseline_winner": baseline, "flips": flips, "fragile": bool(flips)}

    # ------------------------------------------------------------------
    # Diagnosticity: which evidence actually discriminates?
    # ------------------------------------------------------------------
    def diagnosticity(self) -> List[Dict]:
        """Per evidence item: how spread are its scores across hypotheses.

        Items with all-equal scores (all consistent, or all neutral)
        carry zero diagnosticity — they agree with everything, so they
        tell you nothing. Items whose scores span consistent and
        inconsistent are the load-bearing ones.
        """
        rows = []
        for e, name in enumerate(self.evidence):
            values = [self.scores.get((e, h), 0.0) for h in range(len(self.hypotheses))]
            spread = max(values) - min(values) if values else 0.0
            disconfirms_any = any(v < 0 for v in values)
            consistent_with_all = all(v >= 0 for v in values)
            rows.append(
                {
                    "evidence": name,
                    "diagnosticity": round(spread, 4),
                    "disconfirms_any": disconfirms_any,
                    "agrees_with_all": consistent_with_all,
                }
            )
        rows.sort(key=lambda r: -r["diagnosticity"])
        return rows
