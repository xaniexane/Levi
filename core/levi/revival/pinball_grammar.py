"""LEVI's pinboard grammar: skill-modulated chaos on a field of pins.

Studied from: pre-digital-computation-20260916/report.md [Beat C #13, USEFUL PATTERN].

The shape being studied: bagatelle into pinball — a ball dropped through a
staggered field of pins is an *analog probability space*. The launch (aim
and power) is the skill; every pin strike re-rolls the outcome with a
nudge. Centuries before Monte Carlo, this was Monte Carlo you could touch:
skill doesn't determine the result, it *shapes the distribution*.

``pinball_grammar`` rebuilds that shape from scratch, LEVI-native:

- ``BoardSpec`` — the *grammar*: rows of pins (count + stagger per row),
  board width, and the scoring bins at the bottom. Different specs compose
  different boards from the same mechanic.
- ``Pinboard`` — plays a ball: at each row the ball strikes the nearest
  pin and deflects left or right, biased by its incoming angle, with a
  jitter the player's ``skill`` narrows but never removes.
- ``PlayResult`` — the full path (auditable), the landing bin, the score.

Honest limits: this is a pseudo-random simulation (``random.Random``),
not physics and not calibrated to any real table. ``skill`` in [0, 1]
modulates variance — 1.0 means tight, repeatable distributions, never a
guaranteed outcome. Outcomes are reproducible from the seed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


ORIGIN = "levi-revival/pinball-grammar"


class PinballError(Exception):
    """Base class for pinboard failures."""


@dataclass
class PinRow:
    """One horizontal row of pins: ``count`` pins, staggered by ``offset``."""

    count: int
    offset: float = 0.0  # fraction of pin spacing, 0..1


@dataclass
class BoardSpec:
    """The grammar of a board: pin rows, width, and scoring bins.

    ``bins`` holds the score for each bottom segment, left to right. The
    segments divide the board width evenly.
    """

    rows: List[PinRow]
    width: float = 10.0
    bins: List[int] = field(default_factory=lambda: [10, 50, 100, 50, 10])

    def __post_init__(self):
        if not self.rows:
            raise PinballError("a board needs at least one pin row")
        if any(r.count < 1 for r in self.rows):
            raise PinballError("every pin row needs at least one pin")
        if not self.bins:
            raise PinballError("a board needs at least one scoring bin")
        if self.width <= 0:
            raise PinballError("board width must be positive")

    @classmethod
    def classic(cls, rows: int = 8, pins: int = 7, width: float = 10.0) -> "BoardSpec":
        """A standard staggered board: alternating rows offset by half spacing."""
        return cls(
            rows=[PinRow(pins, offset=(i % 2) * 0.5) for i in range(rows)],
            width=width,
        )


@dataclass
class PlayResult:
    aim: float
    skill: float
    path: List[Tuple[int, float]]  # (row_index, x) after each row
    bin_index: int
    score: int


class Pinboard:
    """Plays balls through a ``BoardSpec`` with skill-modulated chaos."""

    def __init__(self, spec: BoardSpec, seed: Optional[int] = None):
        self.spec = spec
        self.rng = random.Random(seed)

    def _pin_xs(self, row: PinRow) -> List[float]:
        spacing = self.spec.width / row.count
        return [
            (i + 0.5 + row.offset) * spacing % self.spec.width for i in range(row.count)
        ]

    def play(self, aim: float, skill: float = 0.5) -> PlayResult:
        """Launch a ball. ``aim`` in [-1, 1] picks the drop point (left..right).

        ``skill`` in [0, 1]: higher skill narrows the deflection jitter at
        every pin, shaping the landing distribution without fixing it.
        """
        if not -1.0 <= aim <= 1.0:
            raise PinballError(f"aim {aim} out of range [-1, 1]")
        skill = max(0.0, min(1.0, skill))

        x = (aim * 0.5 + 0.5) * self.spec.width  # drop point
        incoming = 0.0  # lateral drift from the last deflection
        path: List[Tuple[int, float]] = []

        for ri, row in enumerate(self.spec.rows):
            pins = self._pin_xs(row)
            # Strike the nearest pin; deflection leans with incoming drift.
            nearest = min(pins, key=lambda p: abs(p - x))
            lean = (x - nearest) + incoming * 0.5
            # Jitter shrinks with skill: unskilled play is nearly a coin
            # flip per pin; masterful play keeps the ball on its line.
            jitter = self.rng.uniform(-1.0, 1.0) * (1.0 - 0.85 * skill)
            direction = 1.0 if lean + jitter * 0.6 >= 0 else -1.0
            step = 0.35 + 0.65 * abs(self.rng.gauss(0, 1)) * (1.0 - 0.5 * skill)
            spacing = self.spec.width / row.count
            x += direction * step * spacing * 0.5
            # Walls bounce the ball back in — the board contains the chaos.
            if x < 0:
                x = -x
            elif x > self.spec.width:
                x = 2 * self.spec.width - x
            incoming = direction * step
            path.append((ri, round(x, 4)))

        bin_width = self.spec.width / len(self.spec.bins)
        bin_index = min(int(x // bin_width), len(self.spec.bins) - 1)
        return PlayResult(
            aim=aim,
            skill=skill,
            path=path,
            bin_index=bin_index,
            score=self.spec.bins[bin_index],
        )

    def distribution(self, aim: float, skill: float, balls: int) -> List[int]:
        """Empirical landing-bin histogram over ``balls`` launches.

        The honest way to see what skill buys: run the board, don't trust
        one ball.
        """
        if balls < 1:
            raise PinballError("balls must be >= 1")
        hist = [0] * len(self.spec.bins)
        for _ in range(balls):
            hist[self.play(aim, skill).bin_index] += 1
        return hist
