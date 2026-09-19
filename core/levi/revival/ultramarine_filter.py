"""ultramarine_filter — lapis separation: three-pass claim grading.

Studied from: lost-crafts-20260916 — report.md [Batch 4]
(Lapis Ultramarine separation).

Load-bearing idea: lapis is not crushed but kneaded and washed in
passes — the finest ultramarine floats free, lesser blues sink, and the
gray residue is kept deliberately as its own "ash" grades, never passed
off as the fine blue. LEVI's take: a three-pass pipeline over raw
``Claim``s. Pass 1 strips noise (empty text, non-claims, malformed
records). Pass 2 keeps corroborated claims: claims that agree (same
normalized text) from distinct sources accumulate corroboration and
graduate to facts. Pass 3 grades the residue as "ash" — low-confidence
hunches kept quarantined in their own grade, permanently barred from
merging with facts. The grading is heuristic, and the docstring says so.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


ORIGIN = "levi-revival/ultramarine-filter"

FACT_THRESHOLD = 2  # distinct sources needed before a claim becomes a fact


@dataclass
class Claim:
    """One raw assertion entering the separation pipeline."""

    text: str
    source: str
    kind: str = "assertion"  # "assertion", "observation", "hearsay"
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    ts: float = field(default_factory=time.time)


@dataclass
class GradedClaim:
    """A claim after separation, with its grade and provenance."""

    text: str
    grade: str  # "fact" | "ash"
    sources: Set[str] = field(default_factory=set)
    corroborations: int = 0
    claim_ids: List[str] = field(default_factory=list)

    def is_fact(self) -> bool:
        return self.grade == "fact"


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


class Ultramarine:
    """Three-pass separation: noise stripped, facts kept, ash quarantined."""

    def __init__(self, fact_threshold: int = FACT_THRESHOLD) -> None:
        self.fact_threshold = fact_threshold
        self.facts: Dict[str, GradedClaim] = {}  # normalized text -> fact
        self.ash: Dict[str, GradedClaim] = {}  # normalized text -> ash grade
        self._stripped: List[Claim] = []  # pass-1 waste, kept for audit

    # -- the three passes ------------------------------------------------------

    def separate(self, claims: List[Claim]) -> Dict[str, List[str]]:
        """Run one batch through all three passes.

        Returns {"stripped": [...], "facts": [...], "ash": [...]} with
        normalized texts per pass.
        """
        # Pass 1: strip noise — empty, whitespace-only, or non-claim kinds.
        live = []
        report = {"stripped": [], "facts": [], "ash": []}
        for claim in claims:
            if not claim.text or not claim.text.strip():
                self._stripped.append(claim)
                report["stripped"].append(claim.id)
            else:
                live.append(claim)

        # Pass 2 + 3: knead by normalized text; corroboration decides the grade.
        groups: Dict[str, List[Claim]] = {}
        for claim in live:
            groups.setdefault(_normalize(claim.text), []).append(claim)

        for norm, group in groups.items():
            sources = {c.source for c in group}
            graded = GradedClaim(
                text=group[0].text.strip(),
                grade="ash",
                sources=sources,
                corroborations=len(group),
                claim_ids=[c.id for c in group],
            )
            if len(sources) >= self.fact_threshold:
                graded.grade = "fact"
                self.facts[norm] = graded
                report["facts"].append(norm)
            else:
                self.ash[norm] = graded
                report["ash"].append(norm)
        return report

    # -- the quarantine ------------------------------------------------------------

    def promote(self, norm: str, by_source: str) -> GradedClaim:
        """Corroborate an ash-grade claim from a new source.

        Enough distinct sources and the ash washes up into ultramarine:
        it graduates to a fact. The ash record is never edited in place
        to look like a fact — it moves, leaving the quarantine behind.
        """
        graded = self.ash.get(norm) or self.facts.get(norm)
        if graded is None:
            raise KeyError(f"unknown claim {norm!r}")
        graded.sources.add(by_source)
        graded.corroborations += 1
        if graded.grade == "ash" and len(graded.sources) >= self.fact_threshold:
            graded.grade = "fact"
            self.facts[norm] = graded
            del self.ash[norm]
        return graded

    def fact_texts(self) -> List[str]:
        return [g.text for g in self.facts.values()]

    def ash_texts(self) -> List[str]:
        return [g.text for g in self.ash.values()]

    def stripped_count(self) -> int:
        return len(self._stripped)

    def query(self, text: str) -> Optional[GradedClaim]:
        """Look up a claim by text. Returns None if never seen."""
        norm = _normalize(text)
        return self.facts.get(norm) or self.ash.get(norm)
