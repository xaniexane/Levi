"""Norden-style gyro-stabilized bombsight: geometry plus the lab-field gap.

Studied from: pre-digital-computation-20260916 report.md
[Beat B #13, INSPIRATIONAL] — gyro-stabilized sight flies the plane;
the lab-vs-field gap as the lesson.

The sight solves the release triangle: from altitude ``h`` and ground
speed ``v``, time of fall is ``sqrt(2h/g)`` and bomb range is
``v * t`` minus trail (drag — a heuristic quadratic term the module
labels as such). The sighting angle is ``atan(range / altitude)``;
crosswind adds a drift angle the gyro platform must hold. The
``GyroStabilizer`` keeps the sight line steady against platform motion
with drift compensation — a toy integrator model, labeled as such.

The load-bearing lesson is ``lab_vs_field``: the same geometry solved
perfectly in test conditions degrades under combat factors (wind
mis-estimate, release timing error, evasive maneuver). Each factor is
an explicit, named multiplier — illustrative, not empirical — and the
report shows test CEP beside field CEP so the gap is visible instead
of hidden.

Honest limits: trail is a heuristic, not a drag table; CEP factors are
illustrative multipliers; the stabilizer models drift as a constant
rate, not a real gyro's error dynamics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List


ORIGIN = "levi-revival/gyro-sight"

GRAVITY = 9.80665
TRAIL_FACTOR = 0.02  # heuristic drag: trail = factor * t_fall^2 * v


@dataclass
class BombRun:
    """One bomb run's conditions."""

    altitude_m: float
    true_airspeed_ms: float
    headwind_ms: float = 0.0  # positive = headwind
    crosswind_ms: float = 0.0  # positive = from the left

    def __post_init__(self) -> None:
        if self.altitude_m <= 0:
            raise ValueError("altitude must be positive")
        if self.true_airspeed_ms <= 0:
            raise ValueError("airspeed must be positive")

    def time_of_fall(self) -> float:
        return math.sqrt(2.0 * self.altitude_m / GRAVITY)

    def ground_speed(self) -> float:
        return self.true_airspeed_ms - self.headwind_ms

    def trail(self) -> float:
        """Heuristic drag retardation — labeled heuristic, not a table."""
        t = self.time_of_fall()
        return TRAIL_FACTOR * t * t * self.ground_speed()

    def bomb_range(self) -> float:
        """Horizontal distance the bomb travels after release."""
        return self.ground_speed() * self.time_of_fall() - self.trail()

    def sighting_angle_deg(self) -> float:
        """Depression angle of the sight at the release point."""
        return math.degrees(math.atan2(self.bomb_range(), self.altitude_m))

    def drift_angle_deg(self) -> float:
        """Crab angle needed to hold track against crosswind."""
        gs = self.ground_speed()
        if gs <= 0:
            raise ValueError("ground speed is not positive: cannot hold track")
        return math.degrees(math.atan2(self.crosswind_ms, gs))

    def release_point(self) -> Dict[str, float]:
        return {
            "time_of_fall_s": self.time_of_fall(),
            "ground_speed_ms": self.ground_speed(),
            "bomb_range_m": self.bomb_range(),
            "trail_m": self.trail(),
            "sighting_angle_deg": self.sighting_angle_deg(),
            "drift_angle_deg": self.drift_angle_deg(),
        }


@dataclass
class GyroStabilizer:
    """Toy gyro platform: holds a sight angle against base motion.

    ``drift_rate`` is the gyro's constant wander (toy model); each
    ``correct`` step integrates base motion minus the compensation the
    operator dials in. ``pointing_error`` is what the bombardier sees.
    """

    sight_angle_deg: float = 0.0
    drift_rate_dps: float = 0.01
    pointing_error: float = 0.0

    def correct(
        self, base_rate_dps: float, compensation_dps: float, dt: float
    ) -> float:
        """One stabilization step; returns the pointing error."""
        if dt <= 0:
            raise ValueError("dt must be positive")
        residual = base_rate_dps - compensation_dps + self.drift_rate_dps
        self.pointing_error += residual * dt
        return self.pointing_error

    def re_cage(self) -> None:
        """Re-cage the gyro: zero the accumulated error (and admit it)."""
        self.pointing_error = 0.0


def cep(miss_distances: List[float]) -> float:
    """Circular error probable from radial miss distances.

    Heuristic: CEP ≈ 1.1774 * RMS / sqrt(2) for near-circular scatter.
    Needs at least 3 samples; fewer is a guess, and the module refuses.
    """
    if len(miss_distances) < 3:
        raise ValueError("CEP needs at least 3 miss distances")
    if any(d < 0 for d in miss_distances):
        raise ValueError("miss distances cannot be negative")
    rms = math.sqrt(sum(d * d for d in miss_distances) / len(miss_distances))
    return 1.1774 * rms / math.sqrt(2.0)


# Illustrative degradation factors: named, explicit, not empirical.
FIELD_FACTORS = {
    "wind_misestimate": 3.0,
    "release_timing_error": 2.5,
    "evasive_maneuver": 2.0,
    "sight_misalignment": 1.5,
}


def lab_vs_field(
    test_cep_m: float, factors: Dict[str, float] | None = None
) -> Dict[str, object]:
    """Apply the lab-to-field degradation stack to a test CEP.

    The factors are illustrative multipliers that name *where* the
    accuracy goes, not measured values. The lesson is the gap itself:
    a sight that is superb on the range can be ordinary over the
    target, and any plan that budgets the test number is budgeting a
    fiction.
    """
    if test_cep_m <= 0:
        raise ValueError("test CEP must be positive")
    applied = factors if factors is not None else FIELD_FACTORS
    field_cep = test_cep_m
    breakdown = {}
    for name, factor in applied.items():
        if factor < 1.0:
            raise ValueError(f"factor {name!r} must be >= 1")
        field_cep *= factor
        breakdown[name] = factor
    return {
        "test_cep_m": test_cep_m,
        "field_cep_m": field_cep,
        "degradation_ratio": field_cep / test_cep_m,
        "factors": breakdown,
        "lesson": (
            "Budget the field number, not the test number. "
            "Every factor above is a place where reality "
            "collects its tax."
        ),
    }
