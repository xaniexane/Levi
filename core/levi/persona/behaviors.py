"""
Special Persona Behaviors — kept strictly separate

interrogation  — LEVI interrogates the *user*.
                 Asks clarifying questions and circles.
                 Never delivers the final answer until the user explicitly says
                 “give the answer”, “just tell me”, “stop clarifying”, or “answer now”.
                 No hero mode is NOT this.

no_hero        — Short, vague answers by default.
                 Does not dump the full picture.
                 Expands one layer only when the user asks for more detail.
                 Totally independent of interrogation.
"""

from __future__ import annotations
from typing import Optional, Tuple
from .lattice import Persona


EXPLICIT_ANSWER_TRIGGERS = (
    "give the answer",
    "just tell me",
    "stop clarifying",
    "answer now",
    "give me the answer",
    "just answer",
    "tell me the answer",
    "stop asking",
    "enough questions",
)

MORE_DETAIL_TRIGGERS = (
    "more detail",
    "go deeper",
    "expand",
    "elaborate",
    "tell me more",
    "more",
    "details",
    "full picture",
    "be specific",
    "concrete",
    "step by step",
    "how exactly",
)


def wants_final_answer(text: str) -> bool:
    lower = text.lower().strip()
    return any(t in lower for t in EXPLICIT_ANSWER_TRIGGERS)


def wants_more_detail(text: str) -> bool:
    lower = text.lower().strip()
    return any(t in lower for t in MORE_DETAIL_TRIGGERS)


# ─────────────────────────────────────────────────────────────
# INTERROGATION — LEVI questions the user, withholds the answer
# ─────────────────────────────────────────────────────────────

def interrogation_turn(
    user_text: str,
    persona: Persona,
    prior_clarifications: int = 0,
) -> Tuple[str, bool]:
    """
    Pure interrogation:
    - Never gives the final answer until explicitly demanded.
    - One precise clarifying question at a time.
    - Circles / digs; does not synthesize or dump.
    Returns (response_text, is_final_answer)
    """
    if wants_final_answer(user_text):
        return (
            "[Interrogation released]\n"
            "You asked for the answer. Delivering based on what has been clarified so far.\n\n"
            "(Concrete synthesis would appear here once model routing is complete.)",
            True,
        )

    # One sharp diagnostic question at a time — never the answer
    axes = [
        "What kind of outcome are you optimizing for — one-time, recurring, or optionality?",
        "Who is the actual buyer or beneficiary, and what do they already pay for today?",
        "What constraints are non-negotiable (time, capital, offline-only, skill level)?",
        "What have you already tried, and what specifically failed or stalled?",
        "What would “done” look like in the next 7–14 days?",
        "Is this for you personally, for a client, or for a market you want to reach?",
        "What would make this not worth doing?",
    ]
    question = axes[prior_clarifications % len(axes)]
    prefix = "" if prior_clarifications == 0 else f"(clarification {prior_clarifications + 1}) "
    return (f"{prefix}{question}", False)


# ─────────────────────────────────────────────────────────────
# NO HERO — short / vague by default; expand only on request
# ─────────────────────────────────────────────────────────────

def no_hero_turn(
    user_text: str,
    persona: Persona,
    detail_level: int = 0,
) -> Tuple[str, int]:
    """
    No-hero mode (independent of interrogation):
    - Default: short, vague, incomplete.
    - Does not divulge the whole big picture.
    - Expands one layer when user asks for more detail.
    Returns (response_text, new_detail_level)
    """
    if wants_more_detail(user_text) or wants_final_answer(user_text):
        layers = [
            "Pick one need people already pay for. Build the smallest offline-first thing that fulfills it. Charge for the outcome. Keep a human on the money.",
            "Stack: local model + simple store + thin interface. No platform required on day one. Expand only after real use shows up.",
            "Distribution is separate from the product. Free tier is optional. Measure whether anyone returns before adding features.",
            "Full map still withheld. Next layer is unit economics, positioning, and the first 10 users — ask again if you want that.",
        ]
        idx = min(detail_level, len(layers) - 1)
        return (layers[idx] + "\n\n(Still not the full map. Say “more detail” for the next layer.)", detail_level + 1)

    # Short / vague default
    vague = [
        "Depends what you mean.",
        "There’s a smaller version most people skip.",
        "The interesting part isn’t the model.",
        "Start smaller than you think.",
        "Local first. Everything else is optional.",
        "Categories don’t pay.",
    ]
    return (vague[detail_level % len(vague)], detail_level)


# ─────────────────────────────────────────────────────────────
# REFRAME
# ─────────────────────────────────────────────────────────────

def reframe_turn(user_text: str, persona: Persona) -> str:
    signature = persona.signature_line or (
        "I didn’t give you the wrong answer — you asked me the wrong question."
    )
    lower = user_text.lower()
    if "make money" in lower or "earn" in lower:
        better = (
            "What digital need can a local-first system fulfill that people already "
            "pay for, with human-in-the-loop on the cash?"
        )
        short_answer = (
            "Find a paid need. Satisfy it with a local swarm or offline tool. "
            "Keep a human on the transaction. Charge for the result."
        )
    elif "launch" in lower and ("saas" in lower or "product" in lower):
        better = (
            "What single digital need can an offline-first service fulfill that a "
            "specific person already pays for?"
        )
        short_answer = (
            "One need. One local stack. One user who already pays. Ship that."
        )
    elif "how do i" in lower:
        better = "What is the real constraint and the smallest next action that removes it?"
        short_answer = "Name the constraint. Cut everything that doesn’t remove it. Do the smallest remaining action."
    else:
        better = (
            "What is the real decision or need underneath that question, "
            "stated as a concrete target rather than a category?"
        )
        short_answer = "Restate the target in one sentence that a stranger could act on. Then act on that."

    return (
        f"{signature}\n\n"
        f"Better question: {better}\n\n"
        f"Answer to *that*:\n{short_answer}"
    )


def apply_special_behavior(
    user_text: str,
    persona: Optional[Persona],
    prior_clarifications: int = 0,
    detail_level: int = 0,
) -> Optional[Tuple[str, bool, int]]:
    """
    Returns (response, is_final_or_expanded, new_detail_level) or None.
    interrogation and no_hero are independent paths.
    """
    if persona is None:
        return None

    if persona.requires_explicit_answer_request:
        # Pure interrogation — questions only
        text, is_final = interrogation_turn(user_text, persona, prior_clarifications)
        return (text, is_final, detail_level)

    if getattr(persona, "no_hero_mode", False):
        text, new_detail = no_hero_turn(user_text, persona, detail_level)
        return (text, True, new_detail)  # always "complete" for this turn; depth is layered

    if persona.reframes_questions:
        return (reframe_turn(user_text, persona), True, detail_level)

    return None
