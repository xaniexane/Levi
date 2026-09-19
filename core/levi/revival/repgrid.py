"""Kelly's repertory grid: elicit the latent model behind someone's words.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #19)

The mechanism: you cannot ask people for their mental model directly —
they don't have words for it. So you *elicit* it with triads. Pick three
elements (people, options, situations), ask "how are two of these alike
and different from the third?", and write down the answer as a *bipolar
construct*: a dimension with two poles ("warm --- distant",
"spontaneous --- planned").

Then the grid: rate every element on every construct. The resulting
element x construct matrix IS the latent model — a coordinate map of
how the person construes that corner of the world, built entirely from
their own distinctions rather than the analyst's categories.

Module flow:

1. ``RepGrid(elements=[...])`` — the things being construed.
2. ``elicit(triple, like_pair, emergent, implicit)`` — record a
   construct from a triad: which two were alike (the emergent pole is
   what they share) and what the third had (the implicit pole is its
   contrast).
3. ``rate(element, construct, value)`` — rate every element on every
   construct, 1..7 by default (1 = emergent pole, 7 = implicit pole).
4. ``matrix()`` / ``similarity()`` — the element x construct grid and a
   read-out of which elements the subject construes as alike.

Validation is strict: every element must be rated on every construct
before the matrix is considered complete — a grid with holes is not a
model, it's a questionnaire draft. ``matrix(strict=False)`` tolerates
gaps for partial reads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


ORIGIN = "levi-revival/repgrid"

DEFAULT_SCALE = 7


@dataclass
class Construct:
    """One bipolar distinction, elicited from a triad."""

    emergent: str  # the pole the "alike" pair shares ("warm")
    implicit: str  # the contrast pole the odd one out had ("distant")
    triple: Tuple[str, str, str] = ("", "", "")
    note: str = ""

    def label(self) -> str:
        return f"{self.emergent} --- {self.implicit}"


@dataclass
class RepGrid:
    elements: List[str] = field(default_factory=list)
    constructs: List[Construct] = field(default_factory=list)
    ratings: Dict[Tuple[int, int], int] = field(default_factory=dict)
    scale: int = DEFAULT_SCALE

    def __post_init__(self) -> None:
        if self.scale < 2:
            raise ValueError("scale must be at least 2")
        if len(set(self.elements)) != len(self.elements):
            raise ValueError("elements must be unique")
        for label in self.elements:
            if not label or not label.strip():
                raise ValueError("element labels must be non-empty")

    # ------------------------------------------------------------------
    # Triadic elicitation
    # ------------------------------------------------------------------
    def elicit(
        self,
        triple: Tuple[str, str, str],
        like_pair: Tuple[str, str],
        emergent: str,
        implicit: str,
        note: str = "",
    ) -> int:
        """Record one construct from a triad.

        ``triple`` holds three element labels; ``like_pair`` holds the
        two the subject said were alike (the third is the odd one out).
        ``emergent`` names what the alike pair shares; ``implicit`` names
        the contrast the odd one out carried. Returns the construct
        index.
        """
        if len(set(triple)) != 3:
            raise ValueError("a triad needs three distinct elements")
        for label in triple:
            if label not in self.elements:
                raise ValueError(f"triad element not in grid: {label!r}")
        if len(set(like_pair)) != 2 or not set(like_pair) <= set(triple):
            raise ValueError("like_pair must be two distinct members of the triad")
        if not emergent.strip() or not implicit.strip():
            raise ValueError("both poles of the construct must be non-empty")
        self.constructs.append(
            Construct(
                emergent=emergent.strip(),
                implicit=implicit.strip(),
                triple=tuple(triple),
                note=note,
            )
        )
        return len(self.constructs) - 1

    # ------------------------------------------------------------------
    # Rating
    # ------------------------------------------------------------------
    def rate(self, element: int | str, construct: int, value: int) -> None:
        e = self._element_index(element)
        if not 0 <= construct < len(self.constructs):
            raise ValueError(f"construct index out of range: {construct}")
        if not isinstance(value, int) or not 1 <= value <= self.scale:
            raise ValueError(f"rating must be an int in 1..{self.scale}")
        self.ratings[(e, construct)] = value

    def _element_index(self, element: int | str) -> int:
        if isinstance(element, int):
            if 0 <= element < len(self.elements):
                return element
            raise ValueError(f"element index out of range: {element}")
        try:
            return self.elements.index(element)
        except ValueError:
            raise ValueError(f"unknown element: {element!r}") from None

    # ------------------------------------------------------------------
    # The latent model map
    # ------------------------------------------------------------------
    def missing(self) -> List[Tuple[str, str]]:
        """All (element, construct) cells not yet rated."""
        return [
            (self.elements[e], self.constructs[c].label())
            for e in range(len(self.elements))
            for c in range(len(self.constructs))
            if (e, c) not in self.ratings
        ]

    def is_complete(self) -> bool:
        return not self.missing()

    def matrix(self, strict: bool = True) -> List[List]:
        """The element x construct grid: header + one row per element.

        ``strict=True`` (default) refuses to build the map from a grid
        with holes; pass ``strict=False`` for a partial read with gaps
        shown as ``None``.
        """
        gaps = self.missing()
        if strict and gaps:
            raise ValueError(
                f"grid incomplete: {len(gaps)} unrated cells, "
                "e.g. " + ", ".join(f"{e}/{c}" for e, c in gaps[:3])
            )
        header = ["element"] + [c.label() for c in self.constructs]
        rows = [header]
        for e, name in enumerate(self.elements):
            rows.append(
                [name] + [self.ratings.get((e, c)) for c in range(len(self.constructs))]
            )
        return rows

    def element_vector(
        self, element: int | str, strict: bool = True
    ) -> List[int | None]:
        e = self._element_index(element)
        if strict and any(
            (e, c) not in self.ratings for c in range(len(self.constructs))
        ):
            raise ValueError(f"element {self.elements[e]!r} has unrated constructs")
        return [self.ratings.get((e, c)) for c in range(len(self.constructs))]

    def similarity(self, a: int | str, b: int | str, strict: bool = True) -> float:
        """How alike the subject construes two elements (0..1).

        1.0 means rated identically on every construct; 0.0 means rated
        at opposite poles everywhere. Needs rated cells for both
        elements; unrated cells are skipped, not imputed.
        """
        va = self.element_vector(a, strict=strict)
        vb = self.element_vector(b, strict=strict)
        pairs = [
            (x, y)
            for x, y in zip(va, vb, strict=True)
            if x is not None and y is not None
        ]
        if not pairs:
            raise ValueError("no rated constructs shared by both elements")
        total = sum(1 - abs(x - y) / (self.scale - 1) for x, y in pairs)
        return round(total / len(pairs), 4)

    def most_alike_pairs(self, strict: bool = True) -> List[Dict]:
        """Every element pair, sorted by construed similarity."""
        pairs = []
        for i in range(len(self.elements)):
            for j in range(i + 1, len(self.elements)):
                pairs.append(
                    {
                        "a": self.elements[i],
                        "b": self.elements[j],
                        "similarity": self.similarity(i, j, strict=strict),
                    }
                )
        pairs.sort(key=lambda p: -p["similarity"])
        return pairs
