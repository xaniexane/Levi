"""LEVI's trace dopant: a whisper of additive steering the whole structure.

Studied from: lost-crafts-20260916/report.md [Batch 3] (functional description
only; no historical claims).

The lesson, reborn as LEVI's own: a *trace* addition — parts per million,
not percent — can steer a material's macrostructure through microsegregation.
The model is a heuristic response surface: ``banding_index`` peaks near an
optimal dopant level (illustratively ~300 ppm) and falls off on both sides
(too little does nothing, too much coarsens), scaled by cooling rate. The
continuous index maps to a discrete macrostructure class, and ``recommend``
inverts the surface to find the smallest dopant addition that hits a target
structure without breaching the impurity ceiling.

Honesty: HEURISTIC MODEL. The response surface is a stylized log-Gaussian,
not metallurgy; the 300 ppm optimum and the class thresholds are chosen to
demonstrate the *mechanism shape* — outsized effect from a trace addition
with a sweet spot and a ceiling — not to describe any real alloy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

ORIGIN = "levi-revival/trace-dopants"

# Illustrative response-surface parameters (mechanism demonstration, not data).
OPTIMUM_PPM = 300.0  # dopant level where banding peaks
SPREAD = 0.8  # log-space width of the sweet spot


def banding_index(dopant_ppm: float, cooling_rate: float = 1.0) -> float:
    """Segregation index in [0, 1] for a dopant level and cooling rate.

    Peaks near ``OPTIMUM_PPM``; faster cooling (``cooling_rate`` > 1)
    amplifies the segregation, slower cooling damps it.
    """
    if dopant_ppm <= 0:
        return 0.0
    if cooling_rate <= 0:
        raise ValueError("cooling_rate must be positive")
    log_dist = (math.log(dopant_ppm) - math.log(OPTIMUM_PPM)) / SPREAD
    peak = math.exp(-log_dist * log_dist)
    cooling_gain = 1.0 - math.exp(-cooling_rate)
    return max(0.0, min(1.0, peak * cooling_gain / (1.0 - math.exp(-1.0))))


def macrostructure(dopant_ppm: float, cooling_rate: float = 1.0) -> str:
    """Discrete structure class from the continuous segregation index."""
    idx = banding_index(dopant_ppm, cooling_rate)
    if idx >= 0.6:
        return "banded"
    if idx >= 0.35:
        return "fine"
    if idx >= 0.15:
        return "coarse"
    return "dendritic"


@dataclass(frozen=True)
class DopantPlan:
    """A recommended addition: level, expected structure, headroom to ceiling."""

    dopant_ppm: float
    expected_index: float
    expected_structure: str
    headroom_ppm: float  # max_ppm - dopant_ppm


def recommend(
    target_index: float,
    cooling_rate: float = 1.0,
    max_ppm: float = 1000.0,
    step_ppm: float = 5.0,
) -> DopantPlan:
    """Find the smallest dopant addition hitting ``target_index``.

    Scans upward from a trace (``step_ppm``) so the recommendation is the
    *minimum effective dose*; never exceeds ``max_ppm``. Raises if the
    target is unreachable within the ceiling.
    """
    if not 0.0 <= target_index <= 1.0:
        raise ValueError("target_index must be in [0, 1]")
    if max_ppm <= 0:
        raise ValueError("max_ppm must be positive")
    best: Tuple[float, float] | None = None  # (error, ppm)
    ppm = step_ppm
    while ppm <= max_ppm:
        err = abs(banding_index(ppm, cooling_rate) - target_index)
        if best is None or err < best[0]:
            best = (err, ppm)
        ppm += step_ppm
    assert best is not None
    err, chosen = best
    if err > 0.05:
        raise ValueError(
            f"target {target_index} unreachable within {max_ppm} ppm ceiling"
        )
    return DopantPlan(
        dopant_ppm=chosen,
        expected_index=banding_index(chosen, cooling_rate),
        expected_structure=macrostructure(chosen, cooling_rate),
        headroom_ppm=max_ppm - chosen,
    )


def sweep(
    cooling_rate: float = 1.0, max_ppm: float = 1000.0, step_ppm: float = 50.0
) -> List[Tuple[float, float, str]]:
    """Response surface sample: (ppm, banding index, structure) rows."""
    rows = []
    ppm = step_ppm
    while ppm <= max_ppm:
        rows.append(
            (ppm, banding_index(ppm, cooling_rate), macrostructure(ppm, cooling_rate))
        )
        ppm += step_ppm
    return rows
