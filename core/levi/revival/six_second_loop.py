"""The six-second loop: setup, twist, payoff — then it repeats.

Studied from: fallen-platforms-hunt-20260916/report.md [2. Vine's six-second loop]

The studied shape: a hard six-second cap that forces a whole arc —
setup, twist, payoff — inside one seamless loop, where the *repeat
itself* is a compositional element: the joke lands harder the second
time because the end pours back into the beginning.

LEVI-native re-expression: a loop-clip model made of timed beats
(setup/twist/payoff plus optional grace beats), with the cap
enforced as a real invariant, a seam check that verifies the last
frame hands off to the first (modeled as beat descriptions matching
across the join), and a play simulator that unrolls N loops so the
author can read the arc repeated and check the payoff still lands.

Honest limits: there is no video here — beats are text descriptions
with timestamps; the "seamless repeat" is checked as narrative
continuity across the join, not frame interpolation; the six-second
cap is enforced numerically, not by a media pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

ORIGIN = "levi-revival/six-second-loop"

#: The hard cap, in seconds. Everything must fit inside it.
LOOP_CAP = 6.0

#: The canonical arc phases, in order.
ARC = ("setup", "twist", "payoff")


class LoopError(Exception):
    """Raised when a clip breaks the cap, the arc, or the seam."""


@dataclass
class Beat:
    """One moment inside the loop."""

    at: float  # seconds from loop start
    phase: str  # "setup" | "twist" | "payoff" | "grace"
    description: str

    def __post_init__(self) -> None:
        if not 0 <= self.at <= LOOP_CAP:
            raise LoopError(f"beat at {self.at}s is outside the {LOOP_CAP}s loop")
        if self.phase not in ARC + ("grace",):
            raise LoopError(f"unknown phase: {self.phase!r}")
        self.description = self.description.strip()
        if not self.description:
            raise LoopError("beat description may not be blank")


@dataclass
class LoopClip:
    """A six-second clip with its arc and its seam."""

    title: str
    beats: List[Beat] = field(default_factory=list)
    seam_note: str = ""  # how the end pours back into the start

    def add_beat(self, at: float, phase: str, description: str) -> Beat:
        beat = Beat(at=at, phase=phase, description=description)
        self.beats.append(beat)
        self.beats.sort(key=lambda b: b.at)
        return beat

    def phases_present(self) -> List[str]:
        return [p for p in ARC if any(b.phase == p for b in self.beats)]

    def arc_complete(self) -> bool:
        """Setup, twist, AND payoff all present, in order."""
        order = [b.phase for b in self.beats if b.phase in ARC]
        seen: List[str] = []
        for p in order:
            if not seen or seen[-1] != p:
                seen.append(p)
        return seen == list(ARC)

    def duration(self) -> float:
        if not self.beats:
            return 0.0
        return max(b.at for b in self.beats)

    def check_seam(self) -> str:
        """Verify the loop can repeat: the author must say how it joins.

        Returns the seam note when arc and note are both sound.
        """
        if not self.arc_complete():
            raise LoopError("arc incomplete: need setup -> twist -> payoff in order")
        if not self.seam_note.strip():
            raise LoopError("a loop needs a seam note: how the end pours back in")
        return self.seam_note.strip()

    def play(self, loops: int = 3) -> str:
        """Unroll N repeats so the author can read the arc looping."""
        if loops < 1:
            raise LoopError("play at least one loop")
        self.check_seam()
        lines = [f"▶ {self.title} ({self.duration():.1f}s loop)"]
        for n in range(1, loops + 1):
            lines.append(f"-- loop {n} --")
            for b in self.beats:
                lines.append(f"  {b.at:4.1f}s [{b.phase:6}] {b.description}")
            lines.append(f"  ↺ seam: {self.seam_note.strip()}")
        return "\n".join(lines)

    def tighten(self) -> "LoopClip":
        """Return a copy with grace beats dropped — the lean six seconds.

        A heuristic edit suggestion, labeled as such: it only removes
        grace beats; the author still owns setup/twist/payoff.
        """
        lean = LoopClip(title=self.title, seam_note=self.seam_note)
        lean.beats = [b for b in self.beats if b.phase != "grace"]
        return lean
