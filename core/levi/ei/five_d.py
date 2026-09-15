"""
5D Emotional Intelligence Subsystem
D1 Presence · D2 Empathy · D3 Regulation · D4 Relational · D5 Integrity
Never overrides safety, permission, or factual integrity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional
from enum import Enum

from levi.ei.tone import read_user_tone, UserTone


class Dimension(str, Enum):
    PRESENCE = "presence"
    EMPATHY = "empathy"
    REGULATION = "regulation"
    RELATIONAL = "relational"
    INTEGRITY = "integrity"


@dataclass
class EIState:
    presence: float = 0.8
    empathy: float = 0.7
    regulation: float = 0.9
    relational: float = 0.7
    integrity: float = 1.0
    user_tone: Optional[str] = None
    user_intensity: float = 0.0
    tone_regulation: str = "steady"

    def as_dict(self) -> Dict[str, float]:
        d = {
            "presence": self.presence,
            "empathy": self.empathy,
            "regulation": self.regulation,
            "relational": self.relational,
            "integrity": self.integrity,
        }
        if self.user_tone:
            d["user_tone"] = self.user_tone  # type: ignore
            d["user_intensity"] = self.user_intensity  # type: ignore
            d["tone_regulation"] = self.tone_regulation  # type: ignore
        return d

    def guidance_summary(self) -> str:
        tone = (
            f" tone={self.user_tone}@{self.user_intensity:.2f}"
            if self.user_tone
            else ""
        )
        return (
            f"EI — P:{self.presence:.2f} E:{self.empathy:.2f} R:{self.regulation:.2f} "
            f"Rel:{self.relational:.2f} I:{self.integrity:.2f}{tone}"
        )


class FiveDEI:
    """Tone-aware 5D EI. Integrity floor is absolute."""

    def __init__(self, baseline: Optional[EIState] = None):
        self.state = baseline or EIState()
        self.last_tone: Optional[UserTone] = None

    def evaluate(self, text: str, context: Optional[Dict[str, Any]] = None) -> EIState:
        tone = read_user_tone(text, context)
        self.last_tone = tone

        # Start from calm professional baseline
        presence, empathy, regulation, relational = 0.85, 0.7, 0.85, 0.7

        if tone.primary in ("crisis", "distress", "grief", "fear"):
            presence = 0.95
            empathy = min(1.0, 0.75 + 0.2 * tone.intensity)
            regulation = 0.98  # LEVI's regulation UP when user is dysregulated
            relational = 0.9
        elif tone.primary == "anger":
            presence = 0.9
            empathy = 0.75
            regulation = 0.95  # do not match fire with fire
            relational = 0.8
        elif tone.primary == "confusion":
            presence = 0.9
            empathy = 0.7
            regulation = 0.9
            relational = 0.75
        elif tone.primary == "exhausted":
            presence = 0.88
            empathy = 0.8
            regulation = 0.92
            relational = 0.85
        elif tone.primary == "hopeful":
            presence = 0.85
            empathy = 0.75
            regulation = 0.8
            relational = 0.85
        elif tone.primary == "playful":
            presence = 0.8
            empathy = 0.7
            regulation = 0.75
            relational = 0.8
        elif tone.primary == "collaborative":
            presence = 0.88
            empathy = 0.78
            regulation = 0.85
            relational = 0.92

        self.state = EIState(
            presence=presence,
            empathy=empathy,
            regulation=regulation,
            relational=relational,
            integrity=1.0,
            user_tone=tone.primary,
            user_intensity=tone.intensity,
            tone_regulation=tone.regulation,
        )
        return self.state

    def status(self) -> Dict[str, Any]:
        return {
            "subsystem": "5D Emotional Intelligence",
            "state": self.state.as_dict(),
            "last_tone": self.last_tone.to_dict() if self.last_tone else None,
            "invariants": [
                "Integrity never lowered below safety threshold",
                "When user is dysregulated, LEVI regulation rises (not mirrors)",
                "EI never overrides policy or factual integrity",
            ],
        }
