"""Intensity scale for the level-up training layer.

Harder / deeper work is worth more EXP. The scale is fixed and
documented here so scoring is legible to Chauncey and to Nanobit.

| Level | Name      | What it means                                  | Multiplier |
|-------|-----------|------------------------------------------------|------------|
| 1     | spark     | single-step recall: "What is 47 + 58?"         | 1.0x       |
| 2     | ember     | single-step applied: light reasoning, one hop  | 1.25x      |
| 3     | flame     | multi-step (2-3 steps), worked trace           | 1.5x       |
| 4     | blaze     | multi-step (4+ steps) or deep reasoning trace  | 2.0x       |
| 5     | supernova | synthesis: cross-subject, novel combination    | 3.0x       |

Intensity never multiplies the *daily-complete* bonus — the bonus is a
flat +50 for finishing the day's quota, not a score.
"""

from __future__ import annotations

INTENSITY_MULTIPLIERS: dict[int, float] = {
    1: 1.0,
    2: 1.25,
    3: 1.5,
    4: 2.0,
    5: 3.0,
}

INTENSITY_NAMES: dict[int, str] = {
    1: "spark",
    2: "ember",
    3: "flame",
    4: "blaze",
    5: "supernova",
}


def multiplier(intensity: int) -> float:
    """EXP multiplier for an intensity level. Raises on out-of-range (L5)."""
    if not isinstance(intensity, int) or intensity not in INTENSITY_MULTIPLIERS:
        raise ValueError(
            "intensity must be an int in 1..5, got %r" % (intensity,)
        )
    return INTENSITY_MULTIPLIERS[intensity]


def name(intensity: int) -> str:
    """Human name for an intensity level. Raises on out-of-range (L5)."""
    if not isinstance(intensity, int) or intensity not in INTENSITY_NAMES:
        raise ValueError(
            "intensity must be an int in 1..5, got %r" % (intensity,)
        )
    return INTENSITY_NAMES[intensity]
