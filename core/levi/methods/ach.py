"""Analysis of Competing Hypotheses (ACH): the disconfirmation matrix.

Origin: Richards Heuer's CIA-developed structured analytic technique. List
all hypotheses *and* all evidence in a matrix; mark each evidence item
consistent / inconsistent / irrelevant with each hypothesis; then rank
hypotheses by the evidence *against* them, not for them — deliberately
fighting confirmation bias. The matrix, not the analyst's gut, does the
weighing. Sensitivity analysis asks which single evidence item, if wrong,
would flip the ranking.

What it is in LEVI: a native debiasing engine for high-stakes judgment.
The assistant builds the matrix from elicited hypotheses and evidence,
ranks by disconfirmation, flags unexplained or non-diagnostic evidence, and
runs the sensitivity check automatically — then argues against the leading
hypothesis.

Honesty label: LOAD-BEARING as a discipline — but flag the evidence gap: a
2026 review found only ~8 direct empirical tests of ACH. Well-theorized,
thinly tested. Sell it as the best available discipline, not proven
debiasing.

Deny-closed inputs: marks against unknown hypotheses/evidence, invalid mark
codes, empty names, and duplicate names are rejected with ValueError. An
unmarked cell is *unknown*, never assumed consistent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

__all__ = [
    "CONSISTENT",
    "INCONSISTENT",
    "IRRELEVANT",
    "MARKS",
    "ACH",
    "Ranking",
]

CONSISTENT = "C"  # evidence is consistent with the hypothesis
INCONSISTENT = "I"  # evidence is inconsistent with (argues against) the hypothesis
IRRELEVANT = "NA"  # evidence is irrelevant to the hypothesis
MARKS = (CONSISTENT, INCONSISTENT, IRRELEVANT)


@dataclass
class Ranking:
    hypothesis: str
    against: int  # inconsistent marks — the disconfirmation score (lower wins)
    supporting: int  # consistent marks
    unknown: int  # unmarked cells


class ACH:
    """Hypothesis x evidence matrix, ranked by disconfirmation."""

    def __init__(self, question: str = ""):
        if not isinstance(question, str):
            raise ValueError("question must be a string")
        self.question = question
        self.hypotheses: list[str] = []
        self.evidence: dict[str, str] = {}  # name -> description
        self._marks: dict[tuple[str, str], str] = {}  # (evidence, hypothesis) -> mark

    # -- building the matrix -------------------------------------------------
    @staticmethod
    def _clean_name(name: str, kind: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{kind} name must be a non-empty string")
        return name.strip()

    def add_hypothesis(self, name: str) -> str:
        name = self._clean_name(name, "hypothesis")
        if name in self.hypotheses:
            raise ValueError(f"duplicate hypothesis: {name!r}")
        self.hypotheses.append(name)
        return name

    def add_evidence(self, name: str, description: str = "") -> str:
        name = self._clean_name(name, "evidence")
        if name in self.evidence:
            raise ValueError(f"duplicate evidence: {name!r}")
        self.evidence[name] = description or ""
        return name

    def mark(self, evidence: str, hypothesis: str, mark: str) -> None:
        """Record how one evidence item bears on one hypothesis."""
        if evidence not in self.evidence:
            raise ValueError(f"unknown evidence: {evidence!r}")
        if hypothesis not in self.hypotheses:
            raise ValueError(f"unknown hypothesis: {hypothesis!r}")
        if mark not in MARKS:
            raise ValueError(f"mark must be one of {MARKS}, got {mark!r}")
        self._marks[(evidence, hypothesis)] = mark

    def get_mark(self, evidence: str, hypothesis: str) -> Optional[str]:
        return self._marks.get((evidence, hypothesis))

    # -- the disconfirmation ranking -------------------------------------------
    def _score(self, exclude_evidence: Optional[str] = None) -> list[Ranking]:
        rows: list[Ranking] = []
        for h in self.hypotheses:
            against = supporting = unknown = 0
            for e in self.evidence:
                if e == exclude_evidence:
                    continue
                m = self._marks.get((e, h))
                if m == INCONSISTENT:
                    against += 1
                elif m == CONSISTENT:
                    supporting += 1
                elif m == IRRELEVANT:
                    pass
                else:
                    unknown += 1
            rows.append(Ranking(h, against, supporting, unknown))
        # Fewest inconsistencies wins; ties broken by fewest supporting marks
        # (a hypothesis "supported" by everything explained nothing away —
        # Heuer's rule: focus on refutation, not confirmation).
        rows.sort(key=lambda r: (r.against, r.supporting))
        return rows

    def rank(self) -> list[Ranking]:
        """Hypotheses ordered by evidence against them (least refuted first)."""
        if not self.hypotheses:
            raise ValueError("no hypotheses to rank")
        return self._score()

    def leader(self) -> Ranking:
        return self.rank()[0]

    # -- diagnosticity & flags ---------------------------------------------------
    def diagnosticity(self, evidence: str) -> float:
        """How well an evidence item discriminates between hypotheses.

        1.0 = perfectly diagnostic (marks split across hypotheses);
        0.0 = non-diagnostic (same mark — or no marks — everywhere).
        """
        if evidence not in self.evidence:
            raise ValueError(f"unknown evidence: {evidence!r}")
        marks = [self._marks.get((evidence, h)) for h in self.hypotheses]
        marks = [m for m in marks if m in (CONSISTENT, INCONSISTENT)]
        if len(marks) < 2:
            return 0.0
        # Normalized Shannon entropy of the C/I split.
        from math import log2

        p = sum(1 for m in marks if m == CONSISTENT) / len(marks)
        if p in (0.0, 1.0):
            return 0.0
        return -p * log2(p) - (1 - p) * log2(1 - p)

    def flags(self) -> list[dict]:
        """Inconsistency flags: problems the matrix itself reveals."""
        out: list[dict] = []
        for e in self.evidence:
            marks = [self._marks.get((e, h)) for h in self.hypotheses]
            known = [m for m in marks if m is not None]
            if (
                known
                and all(m == INCONSISTENT for m in known)
                and len(known) == len(self.hypotheses)
            ):
                out.append(
                    {
                        "type": "unexplained",
                        "evidence": e,
                        "message": f"{e!r} is inconsistent with EVERY hypothesis — "
                        "the hypothesis set may be incomplete",
                    }
                )
            elif known and len(set(known)) == 1 and len(known) == len(self.hypotheses):
                out.append(
                    {
                        "type": "non_diagnostic",
                        "evidence": e,
                        "message": f"{e!r} bears the same way on all hypotheses — "
                        "it cannot discriminate between them",
                    }
                )
        for h in self.hypotheses:
            if not any((e, h) in self._marks for e in self.evidence):
                out.append(
                    {
                        "type": "unevaluated",
                        "hypothesis": h,
                        "message": f"{h!r} has no evidence marked against it at all",
                    }
                )
        return out

    # -- sensitivity: what would change your mind? ---------------------------------
    def sensitivity(self) -> list[dict]:
        """For each evidence item: the leader if that item were wrong/removed.

        Items whose removal flips the leader are the load-bearing facts —
        verify those first.
        """
        if not self.hypotheses or not self.evidence:
            return []
        base_leader = self.leader().hypothesis
        out: list[dict] = []
        for e in self.evidence:
            alt = self._score(exclude_evidence=e)[0].hypothesis
            out.append(
                {
                    "evidence": e,
                    "leader_without_it": alt,
                    "flips_leader": alt != base_leader,
                }
            )
        return out

    def argue_against(self, hypothesis: Optional[str] = None) -> dict:
        """The steelman against the leader (or a named hypothesis): every
        inconsistent item plus every unknown cell that must be resolved."""
        target = hypothesis or self.leader().hypothesis
        if target not in self.hypotheses:
            raise ValueError(f"unknown hypothesis: {target!r}")
        inconsistent = [
            e for e in self.evidence if self._marks.get((e, target)) == INCONSISTENT
        ]
        unresolved = [e for e in self.evidence if (e, target) not in self._marks]
        return {
            "hypothesis": target,
            "inconsistent_evidence": inconsistent,
            "unresolved_evidence": unresolved,
            "case_against": (
                f"Against {target!r}: {len(inconsistent)} evidence item(s) are "
                f"inconsistent with it ({', '.join(inconsistent) or 'none'}), and "
                f"{len(unresolved)} item(s) are unmarked "
                f"({', '.join(unresolved) or 'none'})."
            ),
        }
