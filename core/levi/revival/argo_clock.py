"""Argo clock — continuously integrated relative-motion fire control.

Studied from: pre-digital-computation-20260916, report.md [Beat B #15,
USEFUL PATTERN] — Pollen Argo Clock.

The mechanism, functionally: rather than re-solving the fire-control
triangle from scratch on every observation, keep a *running model* of
relative motion between own ship and target. Own course/speed and target
course/speed feed continuous integrators that advance the plot: range,
bearing, and the rate-of-change of each. A virtual-speed drive (the
ball-and-disk integrator) advances the clock faster than real time so
the crew can read off the *future* range and bearing at which shells
should land — i.e. the gun orders (train angle, elevation) are outputs
of an integrated model, not of a single snapshot.

This module is a software analog of that pattern: a ``Plot`` holds the
relative-motion state (range, bearing, range-rate, bearing-rate,
target course/speed, own course/speed); ``tick(dt)`` advances the
integrators exactly per the relative-velocity vector; ``clock_rate``
drives the model ahead of real time; ``gun_orders(shell_flight)``
projects to the predicted intercept point and returns train/elevation
offsets from current bearing/range; ``correct_range``/``correct_bearing``
let a fresh observation nudge the running model (closing the loop the
way range-takers fed the clock).

Honesty: exact 2-D vector kinematics, not physics of a mechanical
integrator; no shell ballistics — elevation is a linear range mapping
with a caller-supplied scale, stated openly. It models the *pattern*
of a continuously integrated fire-control model, at toy scale.
"""

from __future__ import annotations

import math
from typing import Tuple

ORIGIN = "levi-revival/argo-clock"


def _deg(rad: float) -> float:
    return math.degrees(rad)


def _rad(deg: float) -> float:
    return math.radians(deg)


class Plot:
    """Continuously integrated relative-motion plot.

    Positions are in arbitrary range units, angles in degrees, speeds in
    range-units per second. The state is *relative*: target motion minus
    own motion, integrated forward by the clock.
    """

    def __init__(
        self,
        initial_range: float,
        initial_bearing_deg: float,
        target_course_deg: float,
        target_speed: float,
        own_course_deg: float,
        own_speed: float,
        clock_rate: float = 1.0,
    ):
        if initial_range <= 0:
            raise ValueError("initial_range must be positive")
        if target_speed < 0 or own_speed < 0:
            raise ValueError("speeds must be non-negative")
        if clock_rate <= 0:
            raise ValueError("clock_rate must be positive")
        self.range = initial_range
        self.bearing_deg = initial_bearing_deg % 360.0
        self.target_course_deg = target_course_deg % 360.0
        self.target_speed = target_speed
        self.own_course_deg = own_course_deg % 360.0
        self.own_speed = own_speed
        self.clock_rate = clock_rate
        self.elapsed = 0.0  # clock seconds integrated
        self.corrections = 0

    # -- state derivation -------------------------------------------------

    def relative_velocity(self) -> Tuple[float, float]:
        """Relative velocity vector (east, north) of target vs own."""
        tc, ts = _rad(self.target_course_deg), self.target_speed
        oc, os_ = _rad(self.own_course_deg), self.own_speed
        east = ts * math.sin(tc) - os_ * math.sin(oc)
        north = ts * math.cos(tc) - os_ * math.cos(oc)
        return east, north

    def rates(self) -> Tuple[float, float]:
        """(range_rate, bearing_rate_deg_per_s) of the current geometry."""
        east, north = self.relative_velocity()
        br = _rad(self.bearing_deg)
        los_e, los_n = math.sin(br), math.cos(br)  # line-of-sight unit
        range_rate = east * los_e + north * los_n
        cross = east * los_n - north * los_e  # perpendicular component
        bearing_rate = _deg(cross / self.range) if self.range > 0 else 0.0
        return range_rate, bearing_rate

    # -- the clock: integrate ---------------------------------------------

    def tick(self, real_dt: float) -> None:
        """Advance the integrators by ``real_dt`` seconds of real time.

        The model advances ``real_dt * clock_rate``; a clock_rate above
        1 runs the plot ahead of reality (prediction), below 1 replays
        slower. Exact relative-vector stepping, not Euler drift: the
        position update is analytic in the relative frame.
        """
        if real_dt < 0:
            raise ValueError("real_dt must be non-negative")
        dt = real_dt * self.clock_rate
        east, north = self.relative_velocity()
        br = _rad(self.bearing_deg)
        x = self.range * math.sin(br) + east * dt
        y = self.range * math.cos(br) + north * dt
        self.range = math.hypot(x, y)
        self.bearing_deg = _deg(math.atan2(x, y)) % 360.0
        self.elapsed += dt

    # -- the loop: observations correct the model --------------------------

    def correct_range(self, observed_range: float, gain: float = 0.5) -> None:
        """Nudge the model range toward a fresh observation.

        ``gain`` in (0, 1]: fraction of the discrepancy absorbed. The
        clock keeps integrating from the corrected state.
        """
        if observed_range <= 0:
            raise ValueError("observed_range must be positive")
        if not 0.0 < gain <= 1.0:
            raise ValueError("gain must be in (0, 1]")
        self.range += gain * (observed_range - self.range)
        self.corrections += 1

    def correct_bearing(self, observed_bearing_deg: float, gain: float = 0.5) -> None:
        """Nudge the model bearing toward a fresh observation (wrap-aware)."""
        if not 0.0 < gain <= 1.0:
            raise ValueError("gain must be in (0, 1]")
        diff = (observed_bearing_deg - self.bearing_deg + 540.0) % 360.0 - 180.0
        self.bearing_deg = (self.bearing_deg + gain * diff) % 360.0
        self.corrections += 1

    def retarget(self, course_deg: float, speed: float) -> None:
        """Update the target motion hypothesis (e.g. target turns)."""
        if speed < 0:
            raise ValueError("speed must be non-negative")
        self.target_course_deg = course_deg % 360.0
        self.target_speed = speed

    # -- the output: gun orders --------------------------------------------

    def project(self, ahead_s: float) -> Tuple[float, float]:
        """Predicted (range, bearing_deg) ``ahead_s`` clock-seconds ahead."""
        east, north = self.relative_velocity()
        br = _rad(self.bearing_deg)
        x = self.range * math.sin(br) + east * ahead_s
        y = self.range * math.cos(br) + north * ahead_s
        return math.hypot(x, y), _deg(math.atan2(x, y)) % 360.0

    def gun_orders(
        self, shell_flight_s: float, elev_per_range: float = 0.01
    ) -> Tuple[float, float]:
        """Train and elevation orders for a shell fired *now*.

        The shell lands ``shell_flight_s`` seconds from now, so the guns
        are laid for the predicted position then. Returns
        ``(train_offset_deg, elevation_deg)``: train relative to the
        current bearing (positive = right), and elevation as a linear
        range mapping — the caller supplies the ballistic scale openly,
        since real ballistics are outside this model.
        """
        if shell_flight_s < 0:
            raise ValueError("shell_flight_s must be non-negative")
        pr, pb = self.project(shell_flight_s)
        train = ((pb - self.bearing_deg + 540.0) % 360.0) - 180.0
        return train, pr * elev_per_range


def demo() -> Tuple[float, float]:
    """Plot a crossing target, run the clock, read gun orders."""
    p = Plot(
        initial_range=8000.0,
        initial_bearing_deg=45.0,
        target_course_deg=270.0,
        target_speed=15.0,
        own_course_deg=0.0,
        own_speed=20.0,
    )
    p.tick(60.0)
    return p.gun_orders(30.0)
