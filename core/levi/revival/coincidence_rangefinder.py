"""Coincidence rangefinder — absolute measurement as null-matching work.

Studied from: pre-digital-computation-20260916, report.md [Beat B #14,
USEFUL PATTERN] — Barr & Stroud coincidence rangefinder.

The mechanism, functionally: an operator looks through a fixed-baseline
instrument and sees the target as two half-images split by a prism.
Turning a knob shifts one half-image until the two halves *coincide*
— the operator's eye acts as a null detector, and reading the knob at
coincidence turns an absolute range measurement into a matching task.
Geometry does the rest: the convergence angle satisfies
``tan(alpha) = baseline / range``, so the knob reading at coincidence
maps directly to range.

This module models the pattern in software: a ``Rangefinder`` with a
fixed baseline and an eyepiece magnification (real instruments magnify
the split field so the eye can work the null); ``view()`` renders the
two half-views for a target at a true range; ``coincide()`` searches
the knob parameter until the mismatch between the half-views is
minimal (the human-operator step, done here by a coarse scan plus
golden-section refinement); ``measure()`` runs the whole loop and
converts the knob reading back to range. No fitted model anywhere —
the geometry is exact, and error comes only from sampling and search
tolerance. One honest instrument limit: the sub-sample shift uses
linear interpolation, so sharp step edges read about 1% off (the
instrument's accuracy class); smooth targets null to ~1e-5.

Honesty: pure geometry and a numeric search — no optics, no eyes, no
hardware. It only converges when the parallax fits inside the view
width (very close targets exceed the knob travel); that limit is
stated, not hidden.
"""

from __future__ import annotations

import math
from typing import Callable, List, Tuple

ORIGIN = "levi-revival/coincidence-rangefinder"

# Profile of a "half-view": a sampled brightness edge, e.g. a hull line.
Profile = List[float]


def knob_from_range(distance: float, baseline: float, magnify: float) -> float:
    """Knob reading (view units) that coincides at a known range."""
    if distance <= 0:
        raise ValueError("distance must be positive")
    if baseline <= 0 or magnify <= 0:
        raise ValueError("baseline and magnify must be positive")
    return magnify * baseline / distance


def range_from_knob(knob: float, baseline: float, magnify: float) -> float:
    """Range estimate from a knob reading taken at coincidence."""
    if knob <= 0:
        raise ValueError("knob must be positive at coincidence")
    if baseline <= 0 or magnify <= 0:
        raise ValueError("baseline and magnify must be positive")
    return baseline * magnify / knob


def _shift_profile(profile: Profile, shift_samples: float) -> Profile:
    """Sub-sample linear-interpolated shift of a profile."""
    n = len(profile)
    out: List[float] = []
    for i in range(n):
        x = i - shift_samples
        lo = math.floor(x)
        if lo < 0:
            out.append(profile[0])
        elif lo >= n - 1:
            out.append(profile[-1])
        else:
            frac = x - lo
            out.append(profile[lo] * (1.0 - frac) + profile[lo + 1] * frac)
    return out


def mismatch(a: Profile, b: Profile) -> float:
    """Sum of squared differences between two half-views."""
    if len(a) != len(b) or not a:
        raise ValueError("profiles must be non-empty and the same length")
    return sum((x - y) ** 2 for x, y in zip(a, b, strict=True))


class Rangefinder:
    """A fixed-baseline coincidence rangefinder.

    ``baseline`` is the window separation in range units; ``magnify``
    is the eyepiece magnification applied to the split field;
    ``half_len`` is the samples per half-view over the [-1, 1] field.
    """

    def __init__(self, baseline: float, magnify: float = 32.0, half_len: int = 64):
        if baseline <= 0:
            raise ValueError("baseline must be positive")
        if magnify <= 0:
            raise ValueError("magnify must be positive")
        if half_len < 16:
            raise ValueError("half_len must be at least 16")
        self.baseline = baseline
        self.magnify = magnify
        self.half_len = half_len
        self.dx = 2.0 / (half_len - 1)  # view units per sample

    def view(
        self, target: Callable[[float], float], true_range: float
    ) -> Tuple[Profile, Profile]:
        """Render the split field for a target edge function.

        ``target(x)`` is brightness along the sight line; the halves
        are offset by the magnified parallax (the range signal).
        """
        parallax = knob_from_range(true_range, self.baseline, self.magnify)
        n = self.half_len
        upper = [target(-1.0 + 2.0 * i / (n - 1) - parallax / 2.0) for i in range(n)]
        lower = [target(-1.0 + 2.0 * i / (n - 1) + parallax / 2.0) for i in range(n)]
        return upper, lower

    def coincide(
        self, upper: Profile, lower: Profile, tol: float = 1e-6, max_steps: int = 500
    ) -> Tuple[float, float, int]:
        """Find the knob reading that minimizes half-view mismatch.

        The operator's eye, as a deterministic search: coarse scan over
        the field to bracket the null, then golden-section refinement.
        Returns ``(knob, residual, steps_used)``.
        """
        n = len(upper)
        if len(lower) != n or n < 16:
            raise ValueError("half-views must match in length (>= 16)")

        def cost(knob: float) -> float:
            return mismatch(_shift_profile(lower, knob / self.dx), upper)

        # Coarse scan across the field at one-sample spacing: the null
        # must be bracketed before refinement can find it.
        step = self.dx
        k = -1.5
        best_k, best_c = k, cost(k)
        steps = 1
        k += step
        while k <= 1.5 and steps < max_steps:
            c = cost(k)
            steps += 1
            if c < best_c:
                best_k, best_c = k, c
            k += step

        # Golden-section refinement around the bracket.
        lo, hi = best_k - step, best_k + step
        invphi = (math.sqrt(5.0) - 1.0) / 2.0
        c = hi - (hi - lo) * invphi
        d = lo + (hi - lo) * invphi
        fc, fd = cost(c), cost(d)
        steps += 2
        while (hi - lo) > tol and steps < max_steps:
            if fc < fd:
                hi, d, fd = d, c, fc
                c = hi - (hi - lo) * invphi
                fc = cost(c)
            else:
                lo, c, fc = c, d, fd
                d = lo + (hi - lo) * invphi
                fd = cost(d)
            steps += 1
        knob = (lo + hi) / 2.0
        return knob, cost(knob), steps

    def measure(
        self, target: Callable[[float], float], true_range: float
    ) -> Tuple[float, float, int]:
        """Full loop: render views at ``true_range``, null them, estimate.

        Returns ``(estimated_range, residual, steps_used)``. Error comes
        only from sampling and search tolerance — the geometry is exact.
        """
        upper, lower = self.view(target, true_range)
        knob, residual, steps = self.coincide(upper, lower)
        return range_from_knob(knob, self.baseline, self.magnify), residual, steps


def demo() -> Tuple[float, float]:
    """Measure a synthetic step-edge target at 500 range units."""
    rf = Rangefinder(baseline=2.0)

    def edge(x: float) -> float:
        return 1.0 if x > 0.1 else 0.0

    est, residual, steps = rf.measure(edge, 500.0)
    return est, residual
