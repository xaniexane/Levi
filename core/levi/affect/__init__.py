"""LEVI affect engine — Goleman's 5-dimension emotional intelligence.

Pattern-based affect modeling for conduct shaping. NOT felt emotion;
no sentience or subjective-experience claims anywhere in this package.
See docs/AFFECT.md for the full spec.
"""

from levi.affect.detector import EmotionReading, detect, EMOTIONS
from levi.affect.state import DIMENSIONS, SelfModel, SessionEI, honesty_check
from levi.affect.policy import PolicyDecision, evaluate
from levi.affect.registers import (
    REGISTERS,
    RegisterSuggestion,
    check_wit_safety,
    detect_rapport,
    detect_repair,
    rapport_note,
    suggest_register,
)
from levi.affect.modulation import (
    affect_hint,
    growth_signals,
    modulate,
    record_signal,
)

__all__ = [
    "EmotionReading",
    "detect",
    "EMOTIONS",
    "DIMENSIONS",
    "SelfModel",
    "SessionEI",
    "honesty_check",
    "PolicyDecision",
    "evaluate",
    "REGISTERS",
    "RegisterSuggestion",
    "check_wit_safety",
    "detect_rapport",
    "detect_repair",
    "rapport_note",
    "suggest_register",
    "affect_hint",
    "growth_signals",
    "modulate",
    "record_signal",
]
