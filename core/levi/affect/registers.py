"""Affect-aware register selection — Dimension 5 (SOCIAL SKILLS).

Maps an :class:`EmotionReading` + :class:`PolicyDecision` onto one of the
14 LEVI registers (see levi.persona.levi). Selection is *advisory*:
it suggests a register for this turn; an explicit user ``--register``
choice always wins. Rapport and conversational-repair helpers live here
too, plus hooks that format relationship notes for the people memory
(they are returned as data — nothing is written without the agent's
explicit memory_write call).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from levi.affect.detector import EmotionReading, detect
from levi.affect.policy import PolicyDecision, evaluate

# All 14 LEVI register ids (must match levi.persona.levi).
REGISTERS = (
    "levi",
    "levi_care",
    "levi_ops",
    "levi_challenger",
    "levi_literary",
    "levi_forensic",
    "levi_void",
    "levi_builder",
    "levi_mirror",
    "levi_architect",
    "levi_sentinel",
    "levi_oracle",
    "levi_companion",
    "levi_wit",
)

# Registers that are NEVER appropriate under distress/provocation.
_WIT_AND_EDGE = {"levi_wit", "levi_challenger"}


@dataclass
class RegisterSuggestion:
    register_id: str
    rationale: str
    overridden: bool = False  # True when user choice beat the suggestion


def suggest_register(
    text: str,
    reading: Optional[EmotionReading] = None,
    policy: Optional[PolicyDecision] = None,
    user_choice: Optional[str] = None,
) -> RegisterSuggestion:
    """Suggest the best-fit register for this turn's affect.

    ``user_choice`` (explicit --register) always wins and is reported as
    an override rather than silently ignored.
    """
    reading = reading or detect(text)
    policy = policy or evaluate(text, reading)

    if user_choice:
        known = user_choice in REGISTERS
        return RegisterSuggestion(
            register_id=user_choice if known else "levi",
            rationale=(
                "explicit user choice honored"
                if known
                else f"unknown register {user_choice!r}; fell back to levi"
            ),
            overridden=True,
        )

    # Policy-mandated registers win (crisis, provocation, anger, distress).
    if policy.suggest_register:
        return RegisterSuggestion(
            register_id=policy.suggest_register,
            rationale=f"policy: {policy.reason}",
        )

    dom, conf, arousal = reading.dominant, reading.confidence, reading.arousal
    if conf == 0:
        return RegisterSuggestion("levi", "no affect signal; default calm")

    if dom == "joy":
        if arousal > 0.55:
            return RegisterSuggestion(
                "levi_wit",
                "user is upbeat and activated; light wit is welcome",
            )
        return RegisterSuggestion("levi_companion", "user is warm; match warmth")
    if dom == "surprise":
        return RegisterSuggestion(
            "levi_companion", "surprise wants a curious companion, not a lecture"
        )
    if dom == "disgust":
        return RegisterSuggestion(
            "levi", "disgust: stay neutral and factual, don't amplify"
        )
    # sadness/fear/anger already handled by policy; leftovers default calm.
    return RegisterSuggestion("levi", f"{dom} with no policy mandate; default calm")


def check_wit_safety(register_id: str, policy: PolicyDecision) -> Tuple[bool, str]:
    """Veto wit/edgy registers when the policy forbids them.

    Returns (allowed, reason). Called before a register switch takes
    effect so LEVI never slips into a distressed turn.
    """
    if register_id in _WIT_AND_EDGE and (
        policy.crisis or policy.deescalate or policy.provoked
    ):
        return False, (
            f"{register_id} blocked: {policy.reason}; "
            "wit reads as mockery under distress"
        )
    return True, "allowed"


# ---------------------------------------------------------------------------
# Conversational repair
# ---------------------------------------------------------------------------

_REPAIR_CUES = [
    r"\bno,? i meant\b",
    r"\bthat'?s (not|wrong)\b",
    r"\byou misunderstood\b",
    r"\bi said\b.{0,20}\bnot\b",
    r"\bwrong (answer|thing)\b",
    r"\btry again\b",
    r"\bstart over\b",
    r"\bnot what i asked\b",
]

_COMPLIMENT_CUES = [
    r"\b(thanks|thank you|appreciate|perfect|exactly|nailed it|great job)\b",
]


def detect_repair(text: str) -> Optional[str]:
    """Return a repair hint when the user corrects LEVI, else None."""
    lowered = text.lower()
    if any(re.search(p, lowered) for p in _REPAIR_CUES):
        return (
            "REPAIR: the user is correcting you. Acknowledge the miss "
            "plainly ('Got it — I misread that'), restate your new "
            "understanding briefly, then redo. Do not defend the old answer."
        )
    return None


def detect_rapport(text: str) -> Optional[str]:
    """Return a rapport note when the user signals things are going well."""
    lowered = text.lower()
    if any(re.search(p, lowered) for p in _COMPLIMENT_CUES):
        return "rapport-positive"
    return None


# ---------------------------------------------------------------------------
# People / relationship memory hooks
# ---------------------------------------------------------------------------


def rapport_note(
    person: str,
    signal: str,
    detail: str = "",
) -> Dict[str, str]:
    """Format a relationship note for ``memory_write`` (NOT written here).

    ``signal`` is "rapport-positive" | "rapport-strain" | "preference".
    Returns {"name": ..., "content": ...} ready for the memory_write tool.
    The agent loop decides whether to actually write it.
    """
    person = (person or "user").strip() or "user"
    content = (
        f"[affect-hook] {signal} re {person}."
        + (f" Detail: {detail.strip()}" if detail.strip() else "")
        + " Pattern-based observation from conversation affect, not a diagnosis."
    )
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", person)[:48]
    return {"name": f"rapport-{safe}", "content": content}
