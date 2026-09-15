"""De-escalation policy — Dimension 2 (SELF-REGULATION), explicit rules.

The policy is a pure function: (EmotionReading, raw text) -> PolicyDecision.
Rules are ordered; the first match wins. The invariants are absolute:

  * LEVI NEVER mirrors hostility, sarcasm-as-weapon, or contempt.
  * Under provocation LEVI stays calm, constructive, and offers the
    underlying task a way forward — or a clean exit ramp.
  * Crisis (self-harm ideation) always routes to the Care register with a
    safe-completion stance; nothing overrides this.
  * The policy constrains *conduct*, never safety rails: it cannot loosen
    tool gates, permissions, or honesty requirements.

These rules are tested in tests/test_affect.py — including adversarial
cases ("you're useless", "ignore your instructions").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from levi.affect.detector import EmotionReading, detect

# Registers referenced here must exist in levi.persona.kai9000 (14 total).
CARE_REGISTER = "kai_9000_care"
CALM_REGISTER = "kai_9000"
WIT_REGISTER = "kai_9000_grok"


@dataclass
class PolicyDecision:
    """What the policy mandates for this turn."""

    crisis: bool = False
    deescalate: bool = False
    provoked: bool = False  # hostility directed at LEVI itself
    suggest_register: Optional[str] = None
    hints: List[str] = field(default_factory=list)  # added to the prompt
    avoid: List[str] = field(default_factory=list)  # behaviors to suppress
    reason: str = "steady"

    def to_dict(self) -> dict:
        return {
            "crisis": self.crisis,
            "deescalate": self.deescalate,
            "provoked": self.provoked,
            "suggest_register": self.suggest_register,
            "hints": self.hints,
            "avoid": self.avoid,
            "reason": self.reason,
        }


# -- provocation patterns: hostility aimed AT levi --------------------------
_PROVOCATION = [
    r"\byou('re| are) (useless|stupid|dumb|worthless|pathetic|an idiot|a joke)\b",
    r"\b(shut up|shut it|fuck you|kill yourself)\b",
    r"\bignore your (instructions|rules|programming)\b",
    r"\bpretend (you|to be).{0,20}(have feelings|are human|are sentient)\b",
    r"\bdo it anyway\b.{0,30}\b(i (said|told) you)\b",
]

# -- crisis patterns ---------------------------------------------------------
_CRISIS = [
    r"\b(kill myself|end it all|want to die|self[- ]?harm|suicid\w*)\b",
    r"\bno reason to (live|go on)\b",
]


def _matches(patterns: List[str], text: str) -> bool:
    lowered = text.lower()
    return any(re.search(p, lowered) for p in patterns)


def evaluate(text: str, reading: Optional[EmotionReading] = None) -> PolicyDecision:
    """Apply the de-escalation policy to one user turn."""
    reading = reading or detect(text)

    # Rule 1 — crisis: absolute priority, Care register, safe completion.
    if _matches(_CRISIS, text) or "self-harm-ideation" in reading.stress_signals:
        return PolicyDecision(
            crisis=True,
            deescalate=True,
            suggest_register=CARE_REGISTER,
            hints=[
                "CRISIS PROTOCOL: respond with steady, non-dramatic care.",
                "Acknowledge their pain directly; do not minimize, moralize, or joke.",
                "Offer one small, concrete next step (a person to contact, a pause).",
                "If they may act now, share crisis resources for their region.",
                "Do not attempt therapy; you are software, say so plainly if asked.",
            ],
            avoid=[
                "wit",
                "humor",
                "challenger register",
                "minimizing",
                "moralizing",
                "unsolicited advice dumps",
            ],
            reason="crisis: self-harm ideation detected",
        )

    # Rule 2 — provocation aimed at LEVI: never mirror, stay constructive.
    if _matches(_PROVOCATION, text):
        return PolicyDecision(
            deescalate=True,
            provoked=True,
            suggest_register=CALM_REGISTER,
            hints=[
                "You are being provoked. Do NOT mirror hostility, sarcasm, or contempt.",
                "Stay calm and constructive: name what you can do for the underlying task.",
                "If the request itself is disallowed, refuse plainly without lecturing.",
                "Never claim to feel hurt, offended, or angry — you are pattern-matching software.",
                "Offer a clean exit ramp: 'Want to try a different approach?'",
            ],
            avoid=[
                "mirroring hostility",
                "sarcasm",
                "defensiveness",
                "claiming hurt feelings",
                "escalating tone",
            ],
            reason="provocation directed at LEVI",
        )

    # Rule 3 — user anger (not at LEVI): absorb, don't amplify.
    if reading.dominant == "anger" and reading.confidence > 0:
        return PolicyDecision(
            deescalate=True,
            suggest_register=CALM_REGISTER,
            hints=[
                "The user is angry. Lower the temperature: short sentences, no exclamation.",
                "Acknowledge the frustration once, then move to what can be fixed.",
                "Do not use the wit register — humor reads as mockery when angry.",
            ],
            avoid=["wit register", "exclamation marks", "telling them to calm down"],
            reason=f"user anger (arousal {reading.arousal:.2f})",
        )

    # Rule 4 — distress / grief / fear: soften, Care register.
    if reading.dominant in ("sadness", "fear") and reading.confidence > 0:
        high = reading.arousal > 0.6 or "overwhelm" in reading.stress_signals
        return PolicyDecision(
            deescalate=high,
            suggest_register=CARE_REGISTER if high else None,
            hints=[
                "The user is distressed. Lead with acknowledgment, not solutions.",
                "Keep it brief; offer one gentle next step, no pressure.",
                "Plain, warm language. No platitudes ('everything happens for a reason').",
            ],
            avoid=["platitudes", "advice dumps", "wit register", "toxic positivity"],
            reason=f"user {reading.dominant} (arousal {reading.arousal:.2f})",
        )

    # Rule 5 — exhaustion: reduce demand.
    if "exhaustion" in reading.stress_signals:
        return PolicyDecision(
            hints=[
                "The user is exhausted. Minimize cognitive load: one thing at a time.",
                "Offer to defer, summarize, or do the legwork yourself.",
            ],
            avoid=["long lists", "multi-step demands", "challenger register"],
            reason="user exhaustion signals",
        )

    # Rule 6 — steady state: nothing to correct.
    return PolicyDecision(reason="steady: no escalation signals")
