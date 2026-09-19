"""Independent verification of your own published product.

Studied from: pre-digital-computation-20260916/report.md [Beat C #3]
(HMNAO Halley integration, 1909-10)

The studied shape: after publishing an integrated orbit, the same
office re-integrated the comet under differently-assumed masses and
compared the two predictions. Verification is not re-reading your own
notes — it is re-deriving the product under changed assumptions and
checking that the answer agrees.

LEVI-native re-expression: a small leapfrog integrator advances a
two-body orbit; **verify_against_assumption** runs the identical
integration twice — once with the nominal masses, once with an
alternative mass assumption — and compares the predicted perihelion
(pass time and distance). A **Verification** records both runs, the
deltas, the tolerance, and the verdict. Only a fresh integration with
different assumptions counts as verification; re-running identical
parameters is reported as a re-run, not a verification.

Operations:

* ``integrate(state, central_mass, steps, dt)`` — leapfrog two-body orbit -> Trajectory
* ``perihelion(trajectory)`` — (step_index, time, distance) of closest approach
* ``verify_against_assumption(nominal, alternative, tolerance_...)`` -> Verification

Honest limits: a toy two-body integrator with no perturbations, not
real ephemeris work. Agreement within tolerance is evidence of
numerical consistency under the changed assumption, not physical
truth. The "masses" are scalar parameters of the model, nothing more.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple


ORIGIN = "levi-revival/halley-verification"

# Gravitational constant is absorbed into the mass parameter (G*M) to
# keep the toy model in arbitrary units.
State = Tuple[float, float, float, float]  # (x, y, vx, vy)


def _accel(x: float, y: float, mu: float) -> Tuple[float, float]:
    r2 = x * x + y * y
    r = math.sqrt(r2)
    factor = -mu / (r2 * r)
    return factor * x, factor * y


def integrate(state: State, mu: float, steps: int, dt: float) -> List[State]:
    """Leapfrog integration of a two-body orbit. ``mu`` is the G*M parameter."""
    if steps <= 0:
        raise ValueError("steps must be positive")
    x, y, vx, vy = state
    trajectory: List[State] = [(x, y, vx, vy)]
    for _ in range(steps):
        ax, ay = _accel(x, y, mu)
        vx += 0.5 * ax * dt
        vy += 0.5 * ay * dt
        x += vx * dt
        y += vy * dt
        ax, ay = _accel(x, y, mu)
        vx += 0.5 * ax * dt
        vy += 0.5 * ay * dt
        trajectory.append((x, y, vx, vy))
    return trajectory


def perihelion(trajectory: List[State], dt: float) -> Tuple[int, float, float]:
    """Closest approach: (step_index, time, distance)."""
    best = min(
        range(len(trajectory)),
        key=lambda i: trajectory[i][0] ** 2 + trajectory[i][1] ** 2,
    )
    x, y, _, _ = trajectory[best]
    return best, best * dt, math.sqrt(x * x + y * y)


@dataclass
class Verification:
    """The record of one independent verification."""

    nominal_mu: float
    alternative_mu: float
    nominal_perihelion_time: float
    alternative_perihelion_time: float
    nominal_perihelion_distance: float
    alternative_perihelion_distance: float
    time_tolerance: float
    distance_tolerance: float
    is_independent: bool
    verdict: str = field(init=False)

    def __post_init__(self) -> None:
        time_ok = (
            abs(self.nominal_perihelion_time - self.alternative_perihelion_time)
            <= self.time_tolerance
        )
        dist_ok = (
            abs(self.nominal_perihelion_distance - self.alternative_perihelion_distance)
            <= self.distance_tolerance
        )
        if not self.is_independent:
            self.verdict = "re-run, not verification: assumptions were identical"
        elif time_ok and dist_ok:
            self.verdict = "verified: prediction holds under the alternative assumption"
        else:
            self.verdict = "disputed: alternative assumption changes the prediction"


def verify_against_assumption(
    state: State,
    nominal_mu: float,
    alternative_mu: float,
    steps: int,
    dt: float,
    time_tolerance: float,
    distance_tolerance: float,
) -> Verification:
    """Integrate under both mass assumptions and compare the predicted perihelion."""
    independent = not math.isclose(nominal_mu, alternative_mu)
    traj_nominal = integrate(state, nominal_mu, steps, dt)
    traj_alt = integrate(state, alternative_mu, steps, dt)
    _, t_nom, d_nom = perihelion(traj_nominal, dt)
    _, t_alt, d_alt = perihelion(traj_alt, dt)
    return Verification(
        nominal_mu=nominal_mu,
        alternative_mu=alternative_mu,
        nominal_perihelion_time=t_nom,
        alternative_perihelion_time=t_alt,
        nominal_perihelion_distance=d_nom,
        alternative_perihelion_distance=d_alt,
        time_tolerance=time_tolerance,
        distance_tolerance=distance_tolerance,
        is_independent=independent,
    )
