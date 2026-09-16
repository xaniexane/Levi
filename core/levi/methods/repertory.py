"""Kelly's repertory grid: eliciting how someone actually thinks.

Origin: George Kelly's 1955 technique from Personal Construct Theory. To
elicit a person's real dimensions of judgment (not their claimed ones),
present elements in triads — "Alice, Bob, Carol: how are two alike and
different from the third?" — record the bipolar construct ("warm–distant"),
then rate all elements on all constructs. The grid maps a mental model,
including constructs the person would never articulate unprompted.

What it is in LEVI: a conversational interview instrument. The assistant
poses triads, records the elicited bipolar constructs with their
provenance, collects ratings, and analyzes the grid — which constructs
actually discriminate between the elements, and which constructs travel
together (the person's latent value structure).

Honesty label: LOAD-BEARING as an elicitation discipline — with the
caveat that repertory-grid psychometric validity varies by measure; use
it to surface revealed preferences, not as a validated personality test.

Deny-closed inputs: ratings for unknown elements/constructs, scores
outside the scale, malformed triads, and duplicate names are rejected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from typing import Optional

__all__ = ["Construct", "RepertoryGrid", "DEFAULT_SCALE"]

DEFAULT_SCALE = (1, 7)  # classic 7-point repertory-grid scale


@dataclass
class Construct:
    """A bipolar dimension of judgment, e.g. 'autonomous' vs 'directed'."""

    id: str
    pole_a: str
    pole_b: str
    triad: Optional[tuple[str, str, str]] = None  # (a, b, c) it was elicited from
    alike_pair: Optional[tuple[str, str]] = None  # the two judged alike


class RepertoryGrid:
    """Elements x constructs rating matrix with construct analysis."""

    def __init__(self, topic: str = "", scale: tuple[int, int] = DEFAULT_SCALE):
        if not isinstance(topic, str):
            raise ValueError("topic must be a string")
        lo, hi = scale
        if not (isinstance(lo, int) and isinstance(hi, int) and lo < hi):
            raise ValueError(f"scale must be (lo, hi) with lo < hi, got {scale!r}")
        self.topic = topic
        self.scale = (lo, hi)
        self.elements: list[str] = []
        self.constructs: dict[str, Construct] = {}
        self._ratings: dict[tuple[str, str], int] = {}  # (element, construct_id) -> score
        self._next_construct = 1

    # -- building the grid -----------------------------------------------------
    @staticmethod
    def _clean(name: str, kind: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{kind} name must be a non-empty string")
        return name.strip()

    def add_element(self, name: str) -> str:
        name = self._clean(name, "element")
        if name in self.elements:
            raise ValueError(f"duplicate element: {name!r}")
        self.elements.append(name)
        return name

    def elicit_construct(
        self,
        pole_a: str,
        pole_b: str,
        triad: Optional[tuple[str, str, str]] = None,
        alike_pair: Optional[tuple[str, str]] = None,
    ) -> Construct:
        """Record a bipolar construct from a triadic comparison.

        ``triad`` is the (a, b, c) presented; ``alike_pair`` the two judged
        alike on ``pole_a``, differing from the third on ``pole_b``.
        """
        pole_a = self._clean(pole_a, "construct pole")
        pole_b = self._clean(pole_b, "construct pole")
        if pole_a.lower() == pole_b.lower():
            raise ValueError("construct poles must differ")
        if triad is not None:
            if len(triad) != 3 or len(set(triad)) != 3:
                raise ValueError("triad must be three distinct elements")
            for el in triad:
                if el not in self.elements:
                    raise ValueError(f"triad element not in grid: {el!r}")
        if alike_pair is not None:
            if triad is None:
                raise ValueError("alike_pair requires its triad")
            if set(alike_pair) - set(triad) or len(set(alike_pair)) != 2:
                raise ValueError("alike_pair must be two members of the triad")
        cid = f"C{self._next_construct}"
        self._next_construct += 1
        construct = Construct(id=cid, pole_a=pole_a, pole_b=pole_b,
                              triad=triad, alike_pair=alike_pair)
        self.constructs[cid] = construct
        return construct

    def rate(self, element: str, construct_id: str, score: int) -> None:
        """Rate an element on a construct (low = pole_a, high = pole_b)."""
        if element not in self.elements:
            raise ValueError(f"unknown element: {element!r}")
        if construct_id not in self.constructs:
            raise ValueError(f"unknown construct: {construct_id!r}")
        lo, hi = self.scale
        if not isinstance(score, int) or not (lo <= score <= hi):
            raise ValueError(f"score must be an int in {self.scale}, got {score!r}")
        self._ratings[(element, construct_id)] = score

    def grid(self) -> dict[str, dict[str, Optional[int]]]:
        """The full construct x element matrix (None = unrated)."""
        return {
            cid: {el: self._ratings.get((el, cid)) for el in self.elements}
            for cid in self.constructs
        }

    def completeness(self) -> float:
        cells = len(self.elements) * len(self.constructs)
        return (len(self._ratings) / cells) if cells else 0.0

    # -- analysis ----------------------------------------------------------------
    @staticmethod
    def _pearson(xs: list[float], ys: list[float]) -> float:
        n = len(xs)
        if n < 2:
            return 0.0
        mx, my = sum(xs) / n, sum(ys) / n
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        den = sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
        return num / den if den else 0.0

    def analyze(self) -> dict:
        """Which constructs discriminate, and which travel together.

        - ``spread``: rating range per construct — the constructs that
          actually separate your elements (your live dimensions of judgment).
        - ``aligned_pairs``: construct pairs with |correlation| >= 0.7 over
          fully-rated elements — possibly the same latent dimension twice.
        """
        lo, hi = self.scale
        full = [el for el in self.elements
                if all((el, cid) in self._ratings for cid in self.constructs)]
        spreads: dict[str, dict] = {}
        for cid, c in self.constructs.items():
            scores = [self._ratings[(el, cid)] for el in self.elements
                      if (el, cid) in self._ratings]
            spreads[cid] = {
                "poles": (c.pole_a, c.pole_b),
                "rated": len(scores),
                "spread": (max(scores) - min(scores)) if scores else 0,
                "mean": round(sum(scores) / len(scores), 2) if scores else None,
            }
        aligned: list[dict] = []
        cids = list(self.constructs)
        for i in range(len(cids)):
            for j in range(i + 1, len(cids)):
                xs = [float(self._ratings[(el, cids[i])]) for el in full]
                ys = [float(self._ratings[(el, cids[j])]) for el in full]
                r = self._pearson(xs, ys)
                if abs(r) >= 0.7:
                    aligned.append({"constructs": (cids[i], cids[j]),
                                    "correlation": round(r, 3)})
        most_discriminating = sorted(spreads, key=lambda c: spreads[c]["spread"],
                                     reverse=True)
        return {
            "topic": self.topic,
            "elements": len(self.elements),
            "constructs": len(self.constructs),
            "completeness": round(self.completeness(), 3),
            "spreads": spreads,
            "most_discriminating": most_discriminating,
            "aligned_pairs": aligned,
        }

    def score_option(self, ratings: dict[str, int]) -> dict[str, float]:
        """Score a *new* option (not in the grid) on your elicited constructs.

        ``ratings`` maps construct_id -> score. Returns the option's mean
        position per construct — where it sits in *your* revealed space.
        """
        if set(ratings) != set(self.constructs):
            raise ValueError("ratings must cover every construct exactly once")
        lo, hi = self.scale
        for cid, s in ratings.items():
            if not isinstance(s, int) or not (lo <= s <= hi):
                raise ValueError(f"score for {cid} must be an int in {self.scale}")
        return {cid: float(s) for cid, s in ratings.items()}
