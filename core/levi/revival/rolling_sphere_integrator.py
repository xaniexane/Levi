"""Henrici–Coradi-style rolling-sphere integrator: area by rolling.

Studied from: pre-digital-computation-20260916 report.md
[Beat B #6, USEFUL PATTERN] — rolling-sphere integrator; five spheres
produce ten Fourier coefficients in one tracing pass.

A ball-and-disc integrator turns area into rotation: a sphere riding on
a disc at radius ``y`` from the disc's center advances its own
rotation by ``y * dx / R`` as the disc turns through ``dx`` — the
sphere's total rotation is the integral of ``y``. Trace a curve ``y(x)``
once and each sphere accumulates one coefficient:

    a_n = (2/T) * integral_0^T y(x) cos(2 pi n x / T) dx
    b_n = (2/T) * integral_0^T y(x) sin(2 pi n x / T) dx

so ``k`` spheres yield ``2k`` coefficients in a single pass.

Honest limits: this is a numerical emulation of the mechanical action
(stepwise rolling, Simpson quadrature), not a physical sphere. A
``slip`` parameter models the machine's real failure mode — imperfect
traction — as proportional leakage on every step.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict


ORIGIN = "levi-revival/rolling-sphere-integrator"


@dataclass
class SphereIntegrator:
    """One rolling sphere. ``radius`` R scales rotation; ``slip`` in
    [0, 1) bleeds a fraction of each step's advance, modeling imperfect
    traction between sphere and disc."""

    radius: float = 1.0
    slip: float = 0.0
    revolutions: float = 0.0
    steps: int = 0

    def __post_init__(self) -> None:
        if self.radius <= 0:
            raise ValueError("sphere radius must be positive")
        if not 0.0 <= self.slip < 1.0:
            raise ValueError("slip must be in [0, 1)")

    def step(self, y: float, dx: float) -> float:
        """Roll one step: disc radius ``y``, disc advance ``dx``."""
        advance = (y * dx / self.radius) * (1.0 - self.slip)
        self.revolutions += advance
        self.steps += 1
        return self.revolutions

    def reset(self) -> None:
        self.revolutions = 0.0
        self.steps = 0


@dataclass
class TracingPass:
    """One tracing of a curve ``y(x)`` over ``[0, period]`` with a bank
    of spheres, each integrating one Fourier product function."""

    curve: Callable[[float], float]
    period: float
    n_spheres: int = 5
    samples_per_pass: int = 2000
    slip: float = 0.0
    spheres: Dict[str, SphereIntegrator] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError("period must be positive")
        if self.n_spheres < 1:
            raise ValueError("need at least one sphere")
        for n in range(1, self.n_spheres + 1):
            self.spheres[f"a{n}"] = SphereIntegrator(slip=self.slip)
            self.spheres[f"b{n}"] = SphereIntegrator(slip=self.slip)
        self.spheres["a0"] = SphereIntegrator(slip=self.slip)

    def trace(self) -> Dict[str, float]:
        """Run the tracing pass; return the Fourier coefficients."""
        n = self.samples_per_pass
        if n < 8 or n % 2:
            raise ValueError("samples_per_pass must be an even number >= 8")
        dx = self.period / n
        omega = 2.0 * math.pi / self.period

        def integrand(x: float, kind: str) -> float:
            y = self.curve(x)
            if kind == "a0":
                return y
            m = kind[1:]
            harmonic = int(m)
            if kind.startswith("a"):
                return y * math.cos(harmonic * omega * x)
            return y * math.sin(harmonic * omega * x)

        # Trapezoid sub-steps delivered through the spheres: each sphere
        # integrates its product function step by step.
        results: Dict[str, float] = {}
        for name, sphere in self.spheres.items():
            sphere.reset()
            total = 0.0
            x = 0.0
            f_prev = integrand(0.0, name)
            for i in range(1, n + 1):
                x = i * dx
                f = integrand(x if x < self.period else 0.0, name)
                # Trapezoid sub-step through the rolling action.
                sphere.step(0.5 * (f_prev + f), dx)
                total = sphere.revolutions
                f_prev = f
            scale = 2.0 / self.period if name != "a0" else 1.0 / self.period
            results[name] = total * scale
        return results

    def reconstruct(self, coefficients: Dict[str, float], x: float) -> float:
        """Rebuild y(x) from a coefficient set (checks the pass)."""
        total = coefficients.get("a0", 0.0)
        omega = 2.0 * math.pi / self.period
        for n in range(1, self.n_spheres + 1):
            total += coefficients.get(f"a{n}", 0.0) * math.cos(n * omega * x)
            total += coefficients.get(f"b{n}", 0.0) * math.sin(n * omega * x)
        return total


def coefficient_count(n_spheres: int) -> int:
    """How many Fourier coefficients one pass yields: 2 per sphere + a0."""
    return 2 * n_spheres + 1
