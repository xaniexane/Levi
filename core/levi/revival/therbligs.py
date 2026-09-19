"""Therbligs — a finite motion vocabulary for finding waste.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #32).

The mechanism under study: any manual (here: any) task decomposes into
18 elemental motions — Search, Find, Select, Grasp, Transport Loaded,
Transport Empty, Position, Assemble, Use, Disassemble, Inspect,
Pre-Position, Release Load, Hold, Unavoidable Delay, Avoidable Delay,
Plan, Rest. Once motions have names, waste becomes visible: the task's
time budget breaks down by therblig, the waste therbligs (searching,
selecting, moving empty-handed, waiting avoidably) get flagged, and
elimination is concrete — name it, measure it, remove it.

This is an original, from-scratch implementation for LEVI. ``Therblig``
is the 18-element enum; a task is a ``MotionSequence`` of
``Motion(therblig, seconds)`` entries. ``analyze()`` returns the
per-therblig time budget, the waste fraction, and a flagged waste list
with elimination recommendations. ``optimize()`` produces a waste-free
sequence and a changelog of what was removed and why.

Public surface:
- ``Therblig``: the 18-element enum.
- ``Motion``: one elemental motion with an optional duration.
- ``MotionSequence``: ``add``, ``analyze() -> WasteReport``,
  ``optimize() -> (sequence, changelog)``.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/therbligs"


class TherbligError(Exception):
    """Bad motion data: negative time, empty sequence where one is required."""


class Therblig(Enum):
    """The 18 elemental motions. Every task is a sentence in these words."""

    SEARCH = auto()  # hunt for the object/information
    FIND = auto()  # locate it (the moment search ends)
    SELECT = auto()  # choose among alternatives
    GRASP = auto()  # take hold
    TRANSPORT_LOADED = auto()  # move while carrying the work
    TRANSPORT_EMPTY = auto()  # move while carrying nothing
    POSITION = auto()  # orient for the next operation
    ASSEMBLE = auto()  # put together
    USE = auto()  # the productive operation itself
    DISASSEMBLE = auto()  # take apart
    INSPECT = auto()  # check quality / conformance
    PRE_POSITION = auto()  # stage for the *next* cycle
    RELEASE_LOAD = auto()  # let go
    HOLD = auto()  # detained by the process, waiting
    UNAVOIDABLE_DELAY = auto()  # waiting the task genuinely needs
    AVOIDABLE_DELAY = auto()  # waiting the task does not need — waste
    PLAN = auto()  # decide the next move
    REST = auto()  # recover from fatigue


# Therbligs that add no value to the task: pure waste, candidates for elimination.
WASTE = {
    Therblig.SEARCH,
    Therblig.SELECT,
    Therblig.TRANSPORT_EMPTY,
    Therblig.HOLD,
    Therblig.AVOIDABLE_DELAY,
}

_RECOMMENDATIONS = {
    Therblig.SEARCH: "eliminate by staging: place what is needed within reach before the task starts",
    Therblig.SELECT: "eliminate by deciding once: make the choice a rule, not a per-cycle decision",
    Therblig.TRANSPORT_EMPTY: "eliminate by combining: carry work on the return leg (loaded both ways)",
    Therblig.HOLD: "eliminate by jigging: the process should hold the work, not the worker",
    Therblig.AVOIDABLE_DELAY: "eliminate outright: it is waiting the task never needed",
}


@dataclass
class Motion:
    therblig: Therblig
    seconds: float = 0.0
    note: str = ""

    def __post_init__(self) -> None:
        if self.seconds < 0:
            raise TherbligError("a motion cannot take negative time")


@dataclass
class FlaggedWaste:
    index: int
    therblig: Therblig
    seconds: float
    recommendation: str


@dataclass
class WasteReport:
    total_seconds: float
    waste_seconds: float
    waste_fraction: float
    budget: Dict[str, float]  # therblig name -> seconds, sorted desc
    waste_motions: List[FlaggedWaste]


class MotionSequence:
    """A task described as a sequence of elemental motions."""

    def __init__(self, name: str = "task") -> None:
        self.name = name
        self._motions: List[Motion] = []

    def add(
        self, therblig: Therblig, seconds: float = 0.0, note: str = ""
    ) -> "MotionSequence":
        self._motions.append(Motion(therblig, float(seconds), note))
        return self

    def __len__(self) -> int:
        return len(self._motions)

    def motions(self) -> List[Motion]:
        return list(self._motions)

    def analyze(self) -> WasteReport:
        """Name the waste: per-therblig time budget, flagged motions, waste fraction."""
        if not self._motions:
            raise TherbligError("cannot analyze an empty motion sequence")
        budget: Dict[str, float] = {}
        flagged: List[FlaggedWaste] = []
        total = 0.0
        waste = 0.0
        for index, motion in enumerate(self._motions):
            total += motion.seconds
            budget[motion.therblig.name] = (
                budget.get(motion.therblig.name, 0.0) + motion.seconds
            )
            if motion.therblig in WASTE:
                waste += motion.seconds
                flagged.append(
                    FlaggedWaste(
                        index=index,
                        therblig=motion.therblig,
                        seconds=motion.seconds,
                        recommendation=_RECOMMENDATIONS[motion.therblig],
                    )
                )
        budget = dict(sorted(budget.items(), key=lambda kv: kv[1], reverse=True))
        return WasteReport(
            total_seconds=round(total, 3),
            waste_seconds=round(waste, 3),
            waste_fraction=round(waste / total, 3) if total else 0.0,
            budget=budget,
            waste_motions=flagged,
        )

    def optimize(self) -> Tuple["MotionSequence", List[str]]:
        """Return the sequence with waste motions eliminated, plus a changelog."""
        optimized = MotionSequence(f"{self.name} (optimized)")
        changelog: List[str] = []
        for index, motion in enumerate(self._motions):
            if motion.therblig in WASTE:
                changelog.append(
                    f"removed #{index} {motion.therblig.name} "
                    f"({motion.seconds}s): {_RECOMMENDATIONS[motion.therblig]}"
                )
            else:
                optimized._motions.append(
                    Motion(motion.therblig, motion.seconds, motion.note)
                )
        return optimized, changelog

    def summary(self) -> str:
        """One-paragraph motion-study report: budget, waste, and the ask."""
        report = self.analyze()
        lines = [
            f"Motion study: '{self.name}' — {len(self._motions)} motions, "
            f"{report.total_seconds}s total, waste {report.waste_fraction:.0%} "
            f"({report.waste_seconds}s)",
        ]
        for flagged in report.waste_motions:
            lines.append(
                f"  #{flagged.index} {flagged.therblig.name} {flagged.seconds}s — "
                f"{flagged.recommendation}"
            )
        return "\n".join(lines)
