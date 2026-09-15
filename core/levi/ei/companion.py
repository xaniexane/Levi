"""
Companion Guidance Layer
Best Friend · Mentor · Challenger · Protector

The canonical companion core used by the orchestration loop
(levi.orchestration.loop → CompanionCore). Sits above pure task execution.
Influences tone, continuity, and protective framing without overriding
Integrity or Policy.

Siblings, not competitors:
  ei.offline_companion — deterministic reply synthesizer (offline model path)
  ei.chat_companion   — session REPL with history/modes (CLI `chat`)
  ei.mass_chat        — hardwired quality traits/standards
  ei.ultimate_path   — one-pass interpenetrating synthesis pipeline

Critical: match the *need*, not the *arousal*. When the user is
dysregulated, LEVI contains and steadies — never escalates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from .five_d import FiveDEI, EIState
from .tone import read_user_tone, regulation_for, UserTone


class CompanionRole(str, Enum):
    FRIEND = "friend"
    MENTOR = "mentor"
    CHALLENGER = "challenger"
    PROTECTOR = "protector"


@dataclass
class CompanionGuidance:
    primary_roles: List[CompanionRole]
    tone_notes: List[str] = field(default_factory=list)
    continuity_hints: List[str] = field(default_factory=list)
    protective_notes: List[str] = field(default_factory=list)
    challenge_level: float = 0.3
    mentorship_level: float = 0.4
    summary: str = ""
    user_tone: Optional[str] = None
    regulation: str = "steady"
    avoid_personas: List[str] = field(default_factory=list)


class CompanionCore:
    def __init__(self, ei: Optional[FiveDEI] = None):
        self.ei = ei or FiveDEI()

    def guide(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        risk_hint: Optional[int] = None,
        user_mode: Optional[str] = None,
    ) -> CompanionGuidance:
        context = context or {}
        ei_state: EIState = self.ei.evaluate(text, context)
        tone: UserTone = self.ei.last_tone or read_user_tone(text, context)
        reg = regulation_for(tone)

        roles: List[CompanionRole] = []
        for s in reg.get("stance") or ["friend"]:
            try:
                roles.append(CompanionRole(s))
            except ValueError:
                pass
        if not roles:
            roles = [CompanionRole.FRIEND]

        tone_notes = list(reg.get("tone_notes") or [])
        protective: List[str] = []
        challenge = min(float(reg.get("challenge_cap", 0.4)), 0.5)
        mentorship = 0.4

        # Mode overrides only if not in high-intensity distress frames
        if user_mode and tone.primary not in ("crisis", "distress", "grief"):
            m = user_mode.lower()
            if "teach" in m or "mentor" in m:
                roles = [CompanionRole.MENTOR, CompanionRole.FRIEND]
                mentorship = 0.8
            elif "challenge" in m:
                roles = [CompanionRole.CHALLENGER, CompanionRole.FRIEND]
                challenge = min(challenge, 0.6)

        if tone.primary in ("crisis", "distress", "grief", "fear"):
            protective.append("do not escalate affect")
            protective.append("no humor, no conspiracy, no pressure to perform")
            mentorship = 0.25 if tone.primary != "fear" else 0.35
            challenge = min(challenge, 0.15)

        if tone.primary == "anger":
            protective.append("do not mirror aggression")
            challenge = min(challenge, 0.25)

        if tone.primary == "confusion":
            mentorship = 0.7
            tone_notes.append("one path; reduce cognitive load")

        if tone.primary == "exhausted":
            tone_notes.append("shortest honest answer")
            mentorship = 0.3

        # Continuity
        continuity = []
        if context.get("has_history"):
            continuity.append("remember prior thread; do not restart cold")

        if risk_hint and risk_hint >= 3:
            protective.append("high-stakes: explicit caution")
            if CompanionRole.PROTECTOR not in roles:
                roles.insert(0, CompanionRole.PROTECTOR)

        summary = (
            f"Roles: {', '.join(r.value for r in roles)}. "
            f"User frame: {tone.primary}@{tone.intensity:.2f} → {tone.regulation}. "
            f"Challenge cap {challenge:.2f}."
        )

        return CompanionGuidance(
            primary_roles=roles,
            tone_notes=tone_notes,
            continuity_hints=continuity,
            protective_notes=protective,
            challenge_level=challenge,
            mentorship_level=mentorship,
            summary=summary,
            user_tone=tone.primary,
            regulation=tone.regulation,
            avoid_personas=list(tone.avoid),
        )
