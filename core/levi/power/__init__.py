"""LEVI power layer — organism-wide signal primitives.

Generic, non-narrative building blocks generalized from L.W.P.'s power
concepts: signal conversion (transform), amplification (boost/gain),
decay resistance (repeat), load balancing across consumers (rail), and
fault isolation (circuit breakers). Any organ imports these directly;
L.W.P.-specific bindings live in levi.power.lwp.
"""

from levi.power.amplifier import Booster, GainStage, StepAmplifier
from levi.power.breaker import BreakerOpen, BreakerState, CircuitBreaker
from levi.power.lwp import (
    IMMORTAL_REPEATER,
    LWP_POWER_PROFILES,
    SCAR_REPEATER,
    WORD_STEP_AMP,
    PowerProfile,
    finale_surge,
    power_repeats,
    power_step,
    profile,
)
from levi.power.rail import (
    Consumer,
    Delivery,
    Direction,
    DistributionReport,
    PowerRail,
    RouteReport,
)
from levi.power.repeater import Repeater, RepeaterLog
from levi.power.signal import Signal, attenuate, degraded, signal_to_noise
from levi.power.transformer import TransformChain, Transformer

__all__ = [
    "Signal",
    "attenuate",
    "degraded",
    "signal_to_noise",
    "Transformer",
    "TransformChain",
    "Booster",
    "GainStage",
    "StepAmplifier",
    "Repeater",
    "RepeaterLog",
    "CircuitBreaker",
    "BreakerState",
    "BreakerOpen",
    "PowerRail",
    "Consumer",
    "Delivery",
    "Direction",
    "DistributionReport",
    "RouteReport",
    "PowerProfile",
    "LWP_POWER_PROFILES",
    "WORD_STEP_AMP",
    "SCAR_REPEATER",
    "IMMORTAL_REPEATER",
    "profile",
    "power_step",
    "power_repeats",
    "finale_surge",
]
