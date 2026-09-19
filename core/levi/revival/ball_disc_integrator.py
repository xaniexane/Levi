"""The ball-and-disc integrator: integration in rolling contact.

Studied from: pre-digital-computation-20260916 / report.md (Beat B #4)

The mechanism: a disc turns at a rate proportional to dx — the variable
being integrated *with respect to*. A small ball rides on the disc,
its distance from the disc's center set proportional to y — the
variable being integrated. The ball's spin rate is therefore
proportional to y times the disc's rate; the ball's axle drives an
output shaft whose total revolutions equal the integral of y dx. Change
what turns the disc and you integrate with respect to any variable at
all — time, angle, anything with a shaft.

What this module models:
- ``BallDiscIntegrator``: ``step(dx, y)`` advances the mechanism one
  increment — the disc turns by dx, the ball sits at radius y, and the
  output shaft accumulates y*dx worth of revolutions.
- ``integrate``: drive the mechanism with a sampled function.
- ``integral`` / ``revolutions``: the accumulated result, as the raw
  integral and as output-shaft turns.
- Physical limits, honestly kept: the ball cannot ride past the disc's
  edge (y is clamped to the disc radius, and the clamp is reported);
  an optional ``slip`` factor models imperfect rolling contact.

Honest limits: the arithmetic here is exact — this module does not
simulate the ~0.1%-class accuracy of the brass instrument (friction,
slip, and machining tolerances were the physical machine's error
budget, and a ``slip`` knob is only a crude stand-in). What it does
model faithfully is the mechanism's mathematics: output proportional
to the integral of y with respect to x. No network, stdlib only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable


ORIGIN = "levi-revival/ball-disc-integrator"


@dataclass
class BallDiscIntegrator:
    """A disc, a ball, and an output shaft.

    ``disc_radius`` is the farthest the ball may ride from the disc's
    center; ``ball_radius`` converts contact motion into ball spin;
    ``slip`` in [0, 1) is the fraction of contact motion lost to
    imperfect rolling (0 = ideal grip).
    """

    disc_radius: float = 1.0
    ball_radius: float = 0.1
    slip: float = 0.0
    _integral: float = field(default=0.0, init=False, repr=False)
    _clamped_steps: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.disc_radius <= 0.0 or self.ball_radius <= 0.0:
            raise ValueError("radii must be positive")
        if not 0.0 <= self.slip < 1.0:
            raise ValueError("slip must lie in [0, 1)")

    # -- the mechanism ----------------------------------------------------
    def step(self, dx: float, y: float) -> float:
        """Advance one increment: disc turns by ``dx``, ball rides at ``y``.

        Returns the output shaft's accumulated revolutions after the
        step. A ``y`` beyond the disc's edge is clamped to the edge
        (the ball physically cannot ride there) and counted in
        ``clamped_steps``.
        """
        radius = y
        if abs(y) > self.disc_radius:
            radius = math.copysign(self.disc_radius, y)
            self._clamped_steps += 1
        # Contact velocity at the ball = radius * disc_rate; the ball's
        # spin (and the output shaft) loses `slip` to imperfect grip,
        # while _integral keeps the ideal mathematics of the machine.
        self._integral += radius * dx
        return self.revolutions

    def integrate(
        self, func: Callable[[float], float], a: float, b: float, steps: int = 1000
    ) -> float:
        """Integrate ``func`` from ``a`` to ``b`` by driving the mechanism.

        The disc is turned in ``steps`` equal increments of x; the ball
        is set to func(x) at each increment. Returns the accumulated
        integral.
        """
        if steps < 1:
            raise ValueError("steps must be >= 1")
        dx = (b - a) / steps
        x = a
        for _ in range(steps):
            self.step(dx, func(x + dx / 2.0))  # midpoint sampling
            x += dx
        return self.integral

    # -- reading the output --------------------------------------------------
    @property
    def integral(self) -> float:
        """Accumulated integral of y dx (the mathematics of the machine)."""
        return self._integral

    @property
    def revolutions(self) -> float:
        """Output-shaft revolutions: integral scaled by ball geometry and grip."""
        return self._integral * (1.0 - self.slip) / (2.0 * math.pi * self.ball_radius)

    @property
    def clamped_steps(self) -> int:
        """Steps where the ball was held at the disc's edge."""
        return self._clamped_steps

    def reset(self) -> None:
        """Zero the output shaft and the clamp counter."""
        self._integral = 0.0
        self._clamped_steps = 0
