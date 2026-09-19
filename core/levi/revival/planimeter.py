"""Amsler-style polar planimeter: integration in brass.

Studied from: precompute-hunt-20260915 report.md [Find 4, INSPIRATIONAL]
(functional shape only: trace a boundary; a constrained measuring
wheel rolls only perpendicular to the tracer arm; wheel travel times
arm length equals enclosed area).

The mechanism, faithfully simulated:

- A pivot is fixed outside the figure. A pole arm (length ``pole``)
  runs from the pivot to an elbow; a tracer arm (length ``arm``) runs
  from the elbow to the tracer point you drag around the boundary.
- A measuring wheel rides on the tracer arm at distance ``wheel_d``
  from the elbow. Its axle is aligned with the arm, so it can only
  roll perpendicular to the arm — pure rolling, no slip, no sideways
  skid.
- As the tracer traces the closed boundary, the wheel's rim travel
  ``w`` accumulates. The instrument's theorem: enclosed area
  ``A = arm * w`` (counterclockwise traces read positive).

The module integrates this motion directly: at each step the elbow is
re-solved as the continuous branch of the two-circle intersection,
the wheel contact point is advanced, and its velocity is projected
onto the arm-perpendicular. No closed-form area formula is used to
produce the reading — ``shoelace_area`` exists only as the reference
the tests compare against.

Honest limits:

- The pivot must sit *outside* the traced figure. With the pivot
  inside, the pole arm winds a full turn and the reading gains an
  instrument constant the simple ``A = arm * w`` form does not cover;
  the module raises ``GeometryError`` rather than misread.
- Every tracer point must stay within reach
  (``|pole - arm| < dist < pole + arm``) and off the pivot itself.
- Accuracy is set by ``subdivisions`` per edge (default 1200; error
  is well under 1% on ordinary polygons). This is a numerical
  simulation of the mechanism, not the brass itself.

stdlib-only, no network.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple


ORIGIN = "levi-revival/planimeter"

Point = Tuple[float, float]


class GeometryError(ValueError):
    """The tracer path cannot be reached by this instrument setup."""


@dataclass
class Measurement:
    """One full trace of a boundary."""

    wheel_travel: float
    measured_area: float
    reference_area: float
    relative_error: float
    steps: int


def shoelace_area(vertices: List[Point]) -> float:
    """Signed polygon area (reference only; counterclockwise positive)."""
    total = 0.0
    n = len(vertices)
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return total / 2.0


class PolarPlanimeter:
    """A polar planimeter with fixed geometry.

    ``pivot`` is the fixed pole position (must lie outside any figure
    you trace). ``pole`` and ``arm`` are the two arm lengths;
    ``wheel_d`` is the wheel's distance from the elbow along the
    tracer arm.
    """

    def __init__(
        self,
        pivot: Point = (-5.0, 0.0),
        pole: float = 6.0,
        arm: float = 4.0,
        wheel_d: float = 2.0,
        subdivisions: int = 1200,
    ) -> None:
        if pole <= 0 or arm <= 0:
            raise ValueError("arm lengths must be positive")
        if not (0.0 < wheel_d < arm):
            raise ValueError("wheel must ride on the tracer arm")
        if subdivisions < 1:
            raise ValueError("subdivisions must be positive")
        self.pivot = pivot
        self.pole = pole
        self.arm = arm
        self.wheel_d = wheel_d
        self.subdivisions = subdivisions

    def _check_reachable(self, tx: float, ty: float) -> None:
        ox, oy = self.pivot
        dist = math.hypot(tx - ox, ty - oy)
        if dist < 1e-9:
            raise GeometryError("tracer point sits on the pivot")
        if not (abs(self.pole - self.arm) < dist < self.pole + self.arm):
            raise GeometryError(
                f"tracer point {(tx, ty)} out of reach (dist {dist:.3f})"
            )

    def _elbow(self, tx: float, ty: float, prev: Point | None) -> Point:
        """Elbow = continuous branch of the two-circle intersection."""
        ox, oy = self.pivot
        dx, dy = tx - ox, ty - oy
        dist = math.hypot(dx, dy)
        a = (self.pole**2 - self.arm**2 + dist**2) / (2.0 * dist)
        h = math.sqrt(max(self.pole**2 - a * a, 0.0))
        mx, my = ox + a * dx / dist, oy + a * dy / dist
        off_x, off_y = -h * dy / dist, h * dx / dist
        e1 = (mx + off_x, my + off_y)
        e2 = (mx - off_x, my - off_y)
        if prev is None:
            return e1
        return e1 if math.dist(e1, prev) < math.dist(e2, prev) else e2

    def trace(self, vertices: List[Point]) -> Measurement:
        """Trace a closed boundary; return the wheel's area reading."""
        if len(vertices) < 3:
            raise ValueError("need at least 3 vertices")
        for vx, vy in vertices:
            self._check_reachable(vx, vy)

        # Pivot-inside check: the pole arm must not wind a full turn.
        # Approximate by sampling the pivot-to-tracer angle around the
        # loop; a net winding of ~+/-2pi means the pivot is enclosed.
        ox, oy = self.pivot
        angles = [math.atan2(vy - oy, vx - ox) for vx, vy in vertices]
        winding = 0.0
        for i in range(len(angles)):
            da = angles[(i + 1) % len(angles)] - angles[i]
            while da > math.pi:
                da -= 2 * math.pi
            while da < -math.pi:
                da += 2 * math.pi
            winding += da
        if abs(winding) > math.pi:
            raise GeometryError(
                "pivot lies inside the traced figure; "
                "A = arm * wheel_travel does not apply"
            )

        travel = 0.0
        steps = 0
        elbow_prev: Point | None = None
        wheel_prev: Point | None = None
        loop = list(vertices) + [vertices[0]]
        for i in range(len(loop) - 1):
            ax, ay = loop[i]
            bx, by = loop[i + 1]
            for s in range(self.subdivisions):
                t = (s + 1) / self.subdivisions
                tx = ax + (bx - ax) * t
                ty = ay + (by - ay) * t
                elbow_prev = self._elbow(tx, ty, elbow_prev)
                ex, ey = elbow_prev
                ux, uy = (tx - ex) / self.arm, (ty - ey) / self.arm
                wx = ex + self.wheel_d * ux
                wy = ey + self.wheel_d * uy
                # Wheel rolls only perpendicular to the arm.
                nx, ny = -uy, ux
                if wheel_prev is not None:
                    travel += (wx - wheel_prev[0]) * nx + (wy - wheel_prev[1]) * ny
                wheel_prev = (wx, wy)
                steps += 1

        measured = self.arm * travel
        reference = shoelace_area(vertices)
        rel = (
            abs(measured - reference) / abs(reference)
            if reference != 0
            else abs(measured)
        )
        return Measurement(
            wheel_travel=travel,
            measured_area=measured,
            reference_area=reference,
            relative_error=rel,
            steps=steps,
        )
