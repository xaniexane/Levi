"""Ford Mk 1-style fire control: tachymetric prediction with feedback.

Studied from: pre-digital-computation-20260916 report.md
[Beat B #12, LOAD-BEARING] — tachymetric + synthetic: internal target
model integrated forward, discrepancy fed back — a mechanical Kalman
filter.

The director keeps an *internal model* of the target and integrates it
forward in time (the synthetic part). Each fresh observation
(tachymetric rate measurement) is compared against the model's
prediction; the discrepancy is fed back through a gain to correct the
model (the feedback part). Predict-then-correct, every cycle — the
mechanical ancestor of the Kalman filter, implemented here as a fixed
gain. The module says so plainly: a fixed gain is not a covariance
update, but it is the same loop shape.

``gun_orders`` turns the corrected track into firing data: time of
flight, lead (where the target will be), ballistic drop, and
deflection for a crossing target.

Honest limits: constant-velocity internal model — a maneuvering target
outruns the model and the residual shows it; the gain is fixed, so the
filter cannot widen its uncertainty when observations go noisy.
``track_quality`` reports the recent residual so the operator knows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple


ORIGIN = "levi-revival/fire-control"

GRAVITY = 9.80665


@dataclass
class TrackState:
    """Internal target model: position and velocity in the plane."""

    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0

    def predict(self, dt: float) -> "TrackState":
        """Integrate the model forward (synthetic part)."""
        return TrackState(
            self.x + self.vx * dt, self.y + self.vy * dt, self.vx, self.vy
        )

    def position(self) -> Tuple[float, float]:
        return (self.x, self.y)


class TachymetricTracker:
    """Predict-then-correct tracker with a fixed feedback gain."""

    def __init__(self, gain: float = 0.35, initial: TrackState | None = None) -> None:
        if not 0.0 < gain <= 1.0:
            raise ValueError("gain must be in (0, 1]")
        self.gain = gain
        self.state = initial or TrackState()
        self.residuals: List[float] = []

    def update(self, observed: Tuple[float, float], dt: float) -> TrackState:
        """One director cycle: predict forward, compare, feed back."""
        predicted = self.state.predict(dt)
        ox, oy = observed
        rx, ry = ox - predicted.x, oy - predicted.y
        self.residuals.append(math.hypot(rx, ry))
        self.state = TrackState(
            predicted.x + self.gain * rx,
            predicted.y + self.gain * ry,
            # Velocity follows from the corrected position history:
            # blend old velocity toward the implied new velocity.
            self.state.vx + self.gain * (rx / dt) if dt > 0 else self.state.vx,
            self.state.vy + self.gain * (ry / dt) if dt > 0 else self.state.vy,
        )
        return self.state

    def track_quality(self, window: int = 10) -> Dict[str, float]:
        """Recent residual statistics — the operator's honesty gauge."""
        recent = self.residuals[-window:] if window > 0 else self.residuals
        if not recent:
            return {"mean_residual": 0.0, "max_residual": 0.0, "samples": 0.0}
        return {
            "mean_residual": sum(recent) / len(recent),
            "max_residual": max(recent),
            "samples": float(len(recent)),
        }


@dataclass
class GunDirector:
    """Turns a corrected track into firing orders."""

    shell_speed: float  # muzzle velocity, m/s
    mount: Tuple[float, float] = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.shell_speed <= 0:
            raise ValueError("shell_speed must be positive")

    def orders(self, track: TrackState) -> Dict[str, float]:
        """Firing solution against the predicted target position."""
        mx, my = self.mount
        dx, dy = track.x - mx, track.y - my
        rng = math.hypot(dx, dy)
        if rng < 1e-9:
            raise ValueError("target is at the mount: no solution")
        tof = rng / self.shell_speed  # flat-fire approximation, honest
        # Lead: aim where the target will be when the shell arrives.
        lead_x = track.x + track.vx * tof
        lead_y = track.y + track.vy * tof
        aim_dx, aim_dy = lead_x - mx, lead_y - my
        bearing = math.degrees(math.atan2(aim_dy, aim_dx))
        drop = 0.5 * GRAVITY * tof * tof
        # Deflection: lateral offset of the lead point from the line
        # of sight, in angular mils (6400 mils per circle).
        los = math.degrees(math.atan2(dy, dx))
        deflection_mils = (bearing - los) * (6400.0 / 360.0)
        return {
            "range_m": rng,
            "time_of_flight_s": tof,
            "bearing_deg": bearing,
            "lead_distance_m": math.hypot(track.vx * tof, track.vy * tof),
            "ballistic_drop_m": drop,
            "deflection_mils": deflection_mils,
        }


def run_engagement(
    truth: List[Tuple[float, float]], dt: float, gain: float = 0.35, noise: float = 0.0
) -> Dict[str, object]:
    """Drive a tracker through a true track with optional observation
    noise (deterministic wobble, not random — reproducible). Returns
    the final state and quality report."""
    tracker = TachymetricTracker(
        gain=gain, initial=TrackState(truth[0][0], truth[0][1])
    )
    for i, (tx, ty) in enumerate(truth[1:], start=1):
        wobble = noise * math.sin(i * 1.7)
        tracker.update((tx + wobble, ty + wobble * 0.6), dt)
    return {
        "final": tracker.state,
        "quality": tracker.track_quality(),
        "truth_end": truth[-1],
    }
