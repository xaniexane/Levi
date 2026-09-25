"""L.W.P. power semantics, expressed on the generic signal layer.

L.W.P.'s powers began as narrative controls in the model engine. The
mechanics underneath are generic signal operations, and this module binds
each L.W.P. power name to its primitive composition so the whole organism
speaks one power language:

- repeater    -> Repeater: re-inject the kept scar so length does not rot
- booster     -> short intensity amp: fixed step, spends itself fast
- transformer -> Transformer: convert energy, isolate noise
- gain        -> step-up toward the band: fixed step per round
- immortal    -> rare multi-sequence: bigger step + cycling essences
- finale      -> PowerRail.surge: endgame surge under breakers

Nothing here is narrative. The story sentences stay in model_engine;
this module owns the numbers and the engagement rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .amplifier import StepAmplifier
from .rail import PowerRail
from .repeater import Repeater


@dataclass(frozen=True)
class PowerProfile:
    """What a named power *does*, in primitive terms."""

    name: str
    amp_step: int = 0  # fixed step added per round (booster/gain/immortal)
    repeats: bool = False  # re-injects essence over distance (repeater)
    multi_sequence: bool = False  # cycles essences (immortal)
    converts: bool = False  # convert energy + isolate noise (transformer)


LWP_POWER_PROFILES: Dict[str, PowerProfile] = {
    "repeater": PowerProfile(name="repeater", repeats=True),
    "booster": PowerProfile(name="booster", amp_step=30),
    "transformer": PowerProfile(name="transformer", converts=True),
    "gain": PowerProfile(name="gain", amp_step=70),
    "immortal": PowerProfile(name="immortal", amp_step=120, multi_sequence=True),
}

# The word-target steps model_engine used to hard-code per power.
WORD_STEP_AMP = StepAmplifier(
    {name: profile.amp_step for name, profile in LWP_POWER_PROFILES.items()}
)

# The scar liturgy, re-injected so the distance would not rot.
SCAR_REPEATER = Repeater(essence="scar liturgy", interval=1, decay=1.0, restore=1.0)

# Immortal's rare multi-sequence: a different essence per re-injection.
IMMORTAL_REPEATER = Repeater.multi(
    ["sequence/alpha", "sequence/omega", "sequence/echo"],
    interval=7,
    decay=0.95,
)


def profile(power: str) -> PowerProfile:
    """Primitive composition of a named L.W.P. power (unknown -> inert)."""
    return LWP_POWER_PROFILES.get(power, PowerProfile(name=power))


def power_step(power: str) -> int:
    """Fixed amplification step for a power name; 0 when it has none."""
    return int(WORD_STEP_AMP.step(power))


def power_repeats(power: str) -> bool:
    """True when the power re-injects essence over distance."""
    return profile(power).repeats


def finale_surge(rail: PowerRail, factor: float = 2.0, rounds: int = 1) -> None:
    """Endgame surge under breakers: arm a rail surge, faults still isolate."""
    rail.surge(factor=factor, rounds=rounds)
