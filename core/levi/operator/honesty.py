"""The honest-boundary law, baked into routing.

Standing law (Chauncey, 2026-09-22): for every turn, the SI declares
whether it can do the task honestly now or whether the task needs more
training — and never fakes the latter.

No-provider ruling (same night): "None — I'm fully training it." No
external AI provider is seated. The ai operator is Chauncey's own
trained brain (native training path, his machines, his records).
Self-sufficiency from the big providers: learn off them now, need
them never. So the boundary is not "offline vs. online" — it is
**"can do now" vs. "needs more training."**

Every routed turn carries its declaration: :func:`route_turn`
returns the operator name AND the :class:`BoundaryDeclaration`.
Callers (loop/chat) surface the declaration so the user always sees
which side of the boundary the turn fell on. The declaration is
heuristic, and it says so — uncertainty resolves toward honesty
("needs more training"), never toward faking.

Escalation rule (plain):

- trivial -> the nano-bit tier (XI-first: smallest, fastest, cheapest)
- normal  -> the seat's configured operator (offline default)
- high    -> the ai seat (his own trained brain) when the turn needs
  trained-brain depth AND the seat is healthy; otherwise the seat
  default. High-stakes deterministic work stays on the seat operator —
  the twin verifier, not the ai seat, is the high-stakes safety
  mechanism.

Offline stays the default; the ai seat engages by stakes and by need.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .ai_brain import AI_SEAT_NAME
from .contract import OperatorMessage
from .registry import assess_stakes, resolve_for_seat, tier_operator

__all__ = [
    "HONEST_BOUNDARY_LAW",
    "BoundaryDeclaration",
    "RoutedTurn",
    "declare_boundary",
    "route_turn",
]

#: The standing law, verbatim enough to be auditable.
HONEST_BOUNDARY_LAW = (
    "Standing law (Chauncey, 2026-09-22): for every turn, the SI "
    "declares whether it can do the task honestly now or whether the "
    "task needs more training — and never fakes the latter. "
    "No-provider ruling (same night): no external AI provider; the ai "
    "seat is Chauncey's own trained brain. The boundary is 'can do now' "
    "vs. 'needs more training', not 'offline vs. online'."
)

#: Verdicts a per-turn declaration can carry.
CAN_DO_NOW = "can-do-now"
NEEDS_MORE_TRAINING = "needs-more-training"

#: Heuristic patterns for tasks that need trained-brain depth — fluent
#: generation, nuanced understanding, broad reasoning. Heuristic, and
#: declared as such: uncertainty resolves toward honesty.
_NEEDS_TRAINED_DEPTH_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bwrite\b.{0,40}\b(essay|story|poem|song|speech|article|novel|book)\b",
        r"\b(essay|story|poem)\b.{0,20}\babout\b",
        r"\bexplain\b.{0,30}\b(nuanced|deeply|in depth|like i'm five)\b",
        r"\banalyze\b|\banalysis\b|\bcritique\b",
        r"\bsummarize\b.{0,30}\b(long|document|article|book|paper)\b",
        r"\btranslate\b.{0,20}\binto\b",
        r"\bprove\b|\bproof of\b",
        r"\bbrainstorm\b",
        r"\bwrite\b.{0,40}\b(code|function|program|script|app)\b.{0,20}\b(full|complete|complex|entire)\b",
    )
)


@dataclass
class BoundaryDeclaration:
    """Per-turn honesty declaration: which side of the boundary."""

    verdict: str  # "can-do-now" | "needs-more-training"
    reason: str
    stakes: str = "normal"
    routed_to: str = ""
    law: str = field(default=HONEST_BOUNDARY_LAW, repr=False)


@dataclass
class RoutedTurn:
    """A routed turn: the operator name plus its honesty declaration."""

    operator_name: str
    declaration: BoundaryDeclaration
    stakes: str


def _user_text(messages: List[OperatorMessage]) -> str:
    return " ".join(m.content or "" for m in messages if m.role == "user")


def declare_boundary(
    messages: List[OperatorMessage],
    tools: Optional[List[Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
    *,
    ai_healthy: bool = False,
) -> BoundaryDeclaration:
    """Declare, for this turn, "can do now" vs "needs more training".

    Never fakes: when the turn needs trained-brain depth the current
    brain cannot honestly supply, the verdict is "needs-more-training"
    with the reason stated, even though a (worse, offline) answer
    could have been attempted.
    """
    stakes = assess_stakes(messages, tools, context)
    text = _user_text(messages)
    needs_depth = any(p.search(text) for p in _NEEDS_TRAINED_DEPTH_PATTERNS)

    if stakes == "trivial":
        return BoundaryDeclaration(
            verdict=CAN_DO_NOW,
            reason=(
                "trivial turn — the nano-bit tier handles it honestly "
                "at near-zero cost"
            ),
            stakes=stakes,
        )
    if needs_depth:
        if ai_healthy:
            return BoundaryDeclaration(
                verdict=CAN_DO_NOW,
                reason=(
                    "needs trained-brain depth; the ai seat (his own "
                    "trained brain) takes it — the result carries the "
                    "training-envelope note"
                ),
                stakes=stakes,
            )
        return BoundaryDeclaration(
            verdict=NEEDS_MORE_TRAINING,
            reason=(
                "needs trained-brain depth the current brain cannot "
                "honestly supply yet — needs more training; not faked"
            ),
            stakes=stakes,
        )
    return BoundaryDeclaration(
        verdict=CAN_DO_NOW,
        reason=(
            "deterministic/structural work — honestly handled offline "
            "by the seat operator"
        ),
        stakes=stakes,
    )


def _ai_seat_healthy(registry: Any) -> bool:
    try:
        op = registry.resolve(AI_SEAT_NAME)
    except Exception:
        return False
    try:
        return bool(op.health().ok)
    except Exception:
        return False


def route_turn(
    seat_id: str,
    messages: List[OperatorMessage],
    tools: Optional[List[Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
    registry: Any = None,
    config: Optional[Dict[str, Any]] = None,
) -> RoutedTurn:
    """Route a turn to an operator name, declaration attached.

    Additive routing — :func:`resolve_for_task` is untouched. The
    escalation rule:

    - trivial -> nano-bit tier (XI-first)
    - normal  -> the seat's configured operator (offline default)
    - high    -> the ai seat when the turn needs trained-brain depth
      and the seat is healthy; otherwise the seat default. The
      declaration always says which side of the boundary the turn
      fell on.

    ``registry`` may be None (declaration-only routing); then the ai
    seat counts as unhealthy and high-depth turns declare
    "needs-more-training".
    """
    config = config or {}
    stakes = assess_stakes(messages, tools, context)
    ai_healthy = _ai_seat_healthy(registry) if registry is not None else False
    declaration = declare_boundary(
        messages, tools, context, ai_healthy=ai_healthy
    )

    if stakes == "trivial":
        picked = tier_operator("nano_bit", config)
    elif stakes == "high":
        text = _user_text(messages)
        needs_depth = any(
            p.search(text) for p in _NEEDS_TRAINED_DEPTH_PATTERNS
        )
        if needs_depth and ai_healthy:
            picked = AI_SEAT_NAME
        else:
            picked = resolve_for_seat(seat_id, config)
    else:
        picked = resolve_for_seat(seat_id, config)

    declaration.routed_to = picked
    return RoutedTurn(
        operator_name=picked, declaration=declaration, stakes=stakes
    )
