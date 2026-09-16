"""LEVI signal plane — grades, instincts, focus mute, active-hours gate.

Every daemon speaks through four grades (SILENT / NUDGE / CARD /
ESCALATE); instincts fire on evidence with cooldowns and grade caps;
focus mode and active hours decide what may actually reach the user.
"""

from levi.signals.defaults import (
    EVIDENCE_KEYS,
    accountability_evidence,
    register_default_instincts,
)
from levi.signals.focus import (
    Mode,
    get_mode,
    set_mode,
    should_deliver as focus_delivers,
)
from levi.signals.grades import Delivery, Signal, SignalGrade, render, route
from levi.signals.hours import ActiveHours, DEFAULT_ACTIVE_HOURS
from levi.signals.instincts import (
    Instinct,
    InstinctRegistry,
    levi_home,
    matches_evidence,
)
from levi.signals.wiring import (
    default_registry,
    deliver,
    gather_evidence,
    graded_digest,
    heartbeat_to_signals,
    pulse_with_signals,
    signals_for_supervisor,
)

__all__ = [
    "ActiveHours",
    "DEFAULT_ACTIVE_HOURS",
    "Delivery",
    "EVIDENCE_KEYS",
    "Instinct",
    "InstinctRegistry",
    "Mode",
    "Signal",
    "SignalGrade",
    "accountability_evidence",
    "default_registry",
    "deliver",
    "focus_delivers",
    "gather_evidence",
    "get_mode",
    "graded_digest",
    "heartbeat_to_signals",
    "levi_home",
    "matches_evidence",
    "pulse_with_signals",
    "register_default_instincts",
    "render",
    "route",
    "set_mode",
    "signals_for_supervisor",
]
