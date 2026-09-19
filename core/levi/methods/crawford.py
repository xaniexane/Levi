"""The Crawford slip method: anonymous slip rounds for fast group input.

Origin: invented by Professor C. C. Crawford (University of Southern
California, education) in 1925–1926; he used it actively and continuously
for the next 66 years. The facilitator states the problem; every
participant silently writes one idea per slip of paper; slips are
collected; contents go up on the board; the group runs another round on
the posted ideas; slips are sorted into categories and the most frequent
rise to the top.

The load-bearing parts: (1) the slip as unit of anonymity — collection
before display breaks attribution, so by the time an idea reaches the
board its author is unrecoverable; (2) one idea per slip forces
decomposition — no rambling paragraphs, no "and-also" smuggling; (3) the
sort-into-categories step is affinity clustering by hand, and the
frequency ranking is a popularity signal earned in silence rather than
performed in public.

What killed it as a protocol: post-it brainstorming kept the slips and
dropped the discipline — no enforced rounds, no anonymity (color-coded
authorship), no categorization ritual. Apps digitized the board and
monetized the template per seat. NGT (methods/ngt.py) is arguably
Crawford's formalism grown up; Crawford stays the lighter tool for when
there is no time to discuss.

What it is in LEVI: slip rounds for fast anonymous input — e.g.,
collecting a crew's concerns before a build wave. A round collects all
slips before any are shown; the refusal to show early is the entire
value. Sorting is a first-class step with category counts; the report
leads with frequency.

Honesty label: USEFUL PATTERN — the mechanism is narrow (collection
before display + one idea per slip), genuinely simple, and easy to
dismiss as "just writing things down." The 66-year continuous use by its
inventor is testimony, not evidence; treated accordingly.

Deny-closed inputs: empty slips, writing to a collected round, sorting
before collection, and naming categories with empty titles are all
rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

__all__ = ["CrawfordSession", "Slip"]


@dataclass
class Slip:
    round_no: int
    text: str
    category: str = ""


@dataclass
class CrawfordSession:
    """One or more anonymous slip rounds over a stated target question."""

    target: str = ""
    _round_no: int = field(default=0, init=False, repr=False)
    _open: bool = field(default=False, init=False, repr=False)
    _slips: List[Slip] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        if not self.target:
            raise ValueError("crawford: target question must not be empty")

    # -- rounds ------------------------------------------------------------
    def open_round(self) -> int:
        """Start a new slip round; returns the round number."""
        if self._open:
            raise ValueError(
                "crawford: round %d still open; collect it first" % self._round_no
            )
        self._round_no += 1
        self._open = True
        return self._round_no

    def write(self, text: str) -> Slip:
        """Write one idea on one slip. One idea per slip is the rule."""
        if not self._open:
            raise ValueError("crawford: no round open; call open_round() first")
        text = (text or "").strip()
        if not text:
            raise ValueError("crawford: empty slip refused")
        slip = Slip(round_no=self._round_no, text=text)
        self._slips.append(slip)
        return slip

    def collect(self) -> List[Slip]:
        """Collect the round: locks writing, returns this round's slips."""
        if not self._open:
            raise ValueError("crawford: no round open to collect")
        self._open = False
        return [s for s in self._slips if s.round_no == self._round_no]

    # -- sorting -----------------------------------------------------------
    def sort(self, categories: Dict[str, List[int]]) -> Dict[str, int]:
        """Assign slips to categories by slip index (0-based over all slips).

        Returns the category counts, most frequent first.
        """
        if self._open:
            raise ValueError("crawford: collect the open round before sorting")
        if not categories:
            raise ValueError("crawford: no categories given")
        for name in categories:
            if not name.strip():
                raise ValueError("crawford: empty category name refused")
        assigned: Dict[int, str] = {}
        for name, idxs in categories.items():
            for idx in idxs:
                if not 0 <= idx < len(self._slips):
                    raise ValueError("crawford: slip index %d out of range" % idx)
                if idx in assigned:
                    raise ValueError(
                        "crawford: slip %d assigned to two categories" % idx
                    )
                assigned[idx] = name.strip()
        for idx, name in assigned.items():
            self._slips[idx].category = name
        counts: Dict[str, int] = {}
        for s in self._slips:
            key = s.category or "(uncategorized)"
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    def report(self) -> List[Dict[str, object]]:
        """Category report, most frequent first, with the slips inside."""
        if self._open:
            raise ValueError("crawford: collect the open round before reporting")
        groups: Dict[str, List[str]] = {}
        for s in self._slips:
            key = s.category or "(uncategorized)"
            groups.setdefault(key, []).append(s.text)
        ordered = sorted(groups.items(), key=lambda kv: -len(kv[1]))
        return [
            {"category": name, "count": len(texts), "slips": texts}
            for name, texts in ordered
        ]

    def round_count(self) -> int:
        return self._round_no
