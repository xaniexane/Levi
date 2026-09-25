"""Multi-step question scoring with partial credit (L8).

A question is a chain of steps; each step gets its own correctness
score in 0..1 (0 = wrong, 1 = right, fractions for partial work).
Honest grading: partial effort gets partial credit, never zeroed,
never rounded up to full.

Math per question:
    step_award_i = round(STEP_BASE * correctness_i)      # STEP_BASE = 10
    subtotal     = sum(step_award_i) * intensity_multiplier
    bonus        = round(0.20 * subtotal) if all steps >= 0.8 else 0
    total        = int(round(subtotal + bonus))

Examples (intensity 1):
    3 steps, all correct: 30 + 6 bonus = 36 EXP
    3 steps, correctness [1, 0.5, 0]: 10 + 5 + 0 = 15 EXP, no bonus
    3 steps, all wrong: 0 EXP
"""

from __future__ import annotations

from . import intensity as _intensity
from .receipts import award_exp

STEP_BASE = 10
CHAIN_BONUS = 0.20
BONUS_FLOOR = 0.8


def _check_steps(correctness: object) -> list[float]:
    if not isinstance(correctness, (list, tuple)) or not correctness:
        raise ValueError(
            "correctness must be a non-empty list of 0..1 floats, got %r"
            % (correctness,)
        )
    out: list[float] = []
    for i, c in enumerate(correctness):
        if isinstance(c, bool) or not isinstance(c, (int, float)):
            raise ValueError("step %d: correctness must be a number 0..1" % i)
        c = float(c)
        if c < 0.0 or c > 1.0:
            raise ValueError("step %d: correctness must be 0..1, got %r" % (i, c))
        out.append(c)
    return out


def question_exp(correctness: list[float], intensity_level: int = 1) -> int:
    """EXP for one answered question (L5, L8)."""
    steps = _check_steps(correctness)
    mult = _intensity.multiplier(intensity_level)
    per_step = [round(STEP_BASE * c) for c in steps]
    subtotal = sum(per_step) * mult
    bonus = round(CHAIN_BONUS * subtotal) if all(c >= BONUS_FLOOR for c in steps) else 0
    return int(round(subtotal + bonus))


def award_question(
    entity: str,
    correctness: list[float],
    intensity_level: int = 1,
    meta: dict | None = None,
) -> dict:
    """Score one answered question and append the EXP receipt."""
    exp = question_exp(correctness, intensity_level)
    m = dict(meta or {})
    m.update(
        {
            "steps": len(_check_steps(correctness)),
            "intensity": intensity_level,
            "intensity_name": _intensity.name(intensity_level),
        }
    )
    return award_exp(entity, "question", exp, m)
