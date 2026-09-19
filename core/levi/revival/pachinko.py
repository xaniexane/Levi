"""LEVI's pachinko machine: a computer with no processor.

Studied from: pre-digital-computation-20260916/report.md [Beat C #15, USEFUL PATTERN].

The shape being studied: mechanical pachinko as computation. Read it as a
machine and the parts line up exactly:

- *input*: the launch velocity of the ball;
- *program*: the pin layout it falls through;
- *memory*: the ball inventory — balls are both the data and the currency;
- *output*: the payout in balls.

``pachinko`` rebuilds that shape from scratch, LEVI-native:

- ``PinLayout`` — the program: rows of staggered pins plus the pocket
  bins at the bottom, each with a payout multiplier.
- ``BallBank`` — the memory: an inventory of balls you spend to launch
  and refill from payouts. It cannot go negative; the machine refuses to
  launch on an empty bank instead of inventing credit.
- ``Machine`` — runs the program: ``launch(velocity)`` spends one ball,
  walks it through the pin field (deflection jitter grows with velocity —
  a harder launch is a noisier computation), lands it in a pocket, and
  pays out.

Honest limits: the "physics" is a pseudo-random walk
(``random.Random``), reproducible from the seed, not a simulation of any
real machine. Payouts are rounded to whole balls; multipliers below 1 are
allowed (the house edge, stated openly).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Tuple


ORIGIN = "levi-revival/pachinko"


class PachinkoError(Exception):
    """Base class for pachinko failures."""


@dataclass
class Pocket:
    """One payout bin at the bottom of the field."""

    label: str
    multiplier: float  # balls paid per ball launched
    share: float = 1.0  # relative width of this pocket

    def __post_init__(self):
        if self.multiplier < 0:
            raise PachinkoError("pocket multiplier cannot be negative")
        if self.share <= 0:
            raise PachinkoError("pocket share must be positive")


@dataclass
class PinLayout:
    """The program: pin rows over payout pockets.

    ``stagger`` alternates each row's pin offset by half a spacing, the
    classic arrangement that forces the ball to choose at every pin.
    """

    rows: int
    pins_per_row: int
    pockets: List[Pocket]
    stagger: bool = True
    width: float = 12.0

    def __post_init__(self):
        if self.rows < 1 or self.pins_per_row < 1:
            raise PachinkoError("layout needs at least one row and one pin per row")
        if not self.pockets:
            raise PachinkoError("layout needs at least one pocket")
        if self.width <= 0:
            raise PachinkoError("width must be positive")

    @classmethod
    def standard(cls) -> "PinLayout":
        return cls(
            rows=10,
            pins_per_row=9,
            pockets=[
                Pocket("dud", 0.0, share=2.0),
                Pocket("small", 2.0),
                Pocket("jackpot", 15.0, share=0.5),
                Pocket("small", 2.0),
                Pocket("dud", 0.0, share=2.0),
            ],
        )


@dataclass
class LaunchResult:
    velocity: float
    path: List[Tuple[int, float]]
    pocket: str
    multiplier: float
    payout: int
    bank_after: int


class BallBank:
    """The memory: a plain inventory of balls. Never negative."""

    def __init__(self, balls: int = 0):
        if balls < 0:
            raise PachinkoError("bank cannot start negative")
        self.balls = balls

    def insert(self, n: int) -> int:
        if n < 0:
            raise PachinkoError("cannot insert a negative number of balls")
        self.balls += n
        return self.balls

    def spend(self) -> None:
        if self.balls < 1:
            raise PachinkoError("bank is empty — insert balls before launching")
        self.balls -= 1

    def collect(self, n: int) -> int:
        if n < 0:
            raise PachinkoError("cannot collect a negative payout")
        self.balls += n
        return self.balls


class Machine:
    """Runs the pin program against launch-velocity input."""

    def __init__(
        self,
        layout: PinLayout,
        bank: Optional[BallBank] = None,
        seed: Optional[int] = None,
    ):
        self.layout = layout
        self.bank = bank or BallBank()
        self.rng = random.Random(seed)
        self.launches = 0
        self.total_paid = 0

    def _pocket_edges(self) -> List[Tuple[float, float, Pocket]]:
        total = sum(p.share for p in self.layout.pockets)
        edges = []
        x = 0.0
        for p in self.layout.pockets:
            w = p.share / total * self.layout.width
            edges.append((x, x + w, p))
            x += w
        return edges

    def launch(self, velocity: float) -> LaunchResult:
        """Spend one ball, run it through the pins, pay the pocket.

        ``velocity`` in [0, 1]: harder launches deflect more violently, so
        the landing distribution widens — a noisier computation.
        """
        if not 0.0 <= velocity <= 1.0:
            raise PachinkoError(f"velocity {velocity} out of range [0, 1]")
        self.bank.spend()

        width = self.layout.width
        x = width / 2.0  # balls enter at the top center
        drift = 0.0
        path: List[Tuple[int, float]] = []
        spacing = width / self.layout.pins_per_row

        for r in range(self.layout.rows):
            offset = (0.5 * (r % 2)) if self.layout.stagger else 0.0
            pins = [
                ((i + 0.5 + offset) % self.layout.pins_per_row) * spacing
                for i in range(self.layout.pins_per_row)
            ]
            nearest = min(pins, key=lambda p: abs(p - x))
            lean = (x - nearest) + drift * 0.4
            # Harder launch, wilder bounce: jitter scales with velocity.
            jitter = self.rng.uniform(-1.0, 1.0) * (0.25 + 0.75 * velocity)
            direction = 1.0 if lean + jitter * spacing * 0.5 >= 0 else -1.0
            kick = abs(self.rng.gauss(0, 1)) * (0.3 + 0.9 * velocity)
            x += direction * kick * spacing * 0.5
            if x < 0:
                x = -x
            elif x > width:
                x = 2 * width - x
            drift = direction * kick
            path.append((r, round(x, 4)))

        pocket = self.layout.pockets[-1]
        for lo, hi, p in self._pocket_edges():
            if lo <= x < hi or (p is self.layout.pockets[-1] and x >= lo):
                pocket = p
                break

        payout = int(round(pocket.multiplier))  # 1 ball in, multiplier out
        self.bank.collect(payout)
        self.launches += 1
        self.total_paid += payout
        return LaunchResult(
            velocity=velocity,
            path=path,
            pocket=pocket.label,
            multiplier=pocket.multiplier,
            payout=payout,
            bank_after=self.bank.balls,
        )

    def expected_value(self, velocity: float, balls: int = 2000) -> float:
        """Empirical mean payout per ball at this velocity.

        The honest readout of the machine's generosity: run it, don't
        trust the layout diagram.
        """
        if balls < 1:
            raise PachinkoError("balls must be >= 1")
        saved = (self.bank.balls, self.launches, self.total_paid)
        self.bank.insert(balls)
        paid = 0
        for _ in range(balls):
            paid += self.launch(velocity).payout
        self.bank.balls, self.launches, self.total_paid = saved
        return paid / balls
