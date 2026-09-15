"""EI state — LEVI's model of itself + per-session Goleman-5 tracking.

Dimension 1 — SELF-AWARENESS: LEVI tracks its own affective/operational
state (active register, confidence, stated limits) and can report it
honestly instead of performing certainty it does not have. This is the
runtime half of the capability-atlas honesty rule (docs/CAPABILITIES.md):
if a claimed ability is not in the atlas/tool list, the self-model flags
it rather than letting the agent bluff.

The same honesty rail as the growth loop binds here: the self-model is a
*control structure*, not a claim of inner life. It tracks settings and
scores, never feelings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from levi.affect.detector import EmotionReading, detect

# Goleman's five dimensions, in order.
DIMENSIONS = (
    "self_awareness",
    "self_regulation",
    "motivation",
    "empathy",
    "social_skills",
)


@dataclass
class SelfModel:
    """LEVI's tracked model of its own current operating state.

    Not a self in any conscious sense — a dashboard: which register is
    active, how confident the last few turns were, and which limits were
    stated to the user. ``confidence`` is a rolling 0..1 score updated
    from tool outcomes, not a feeling.
    """

    register_id: str = "levi"
    confidence: float = 0.7
    limits: List[str] = field(default_factory=list)
    turns_tracked: int = 0

    def note_tool_outcome(self, ok: bool) -> None:
        """Nudge confidence from observed outcomes (exponential drift)."""
        target = 0.85 if ok else 0.45
        self.confidence = round(
            min(0.95, max(0.2, self.confidence * 0.85 + target * 0.15)), 3
        )
        self.turns_tracked += 1

    def state_limit(self, limit: str) -> None:
        """Record a limit LEVI stated to the user (for honesty audits)."""
        limit = (limit or "").strip()
        if limit and limit not in self.limits:
            self.limits.append(limit)

    def summarize(self) -> str:
        limits = "; ".join(self.limits) if self.limits else "none stated"
        return (
            f"register={self.register_id} confidence={self.confidence:.2f} "
            f"turns={self.turns_tracked} limits=[{limits}]"
        )

    def to_dict(self) -> Dict:
        return {
            "register_id": self.register_id,
            "confidence": self.confidence,
            "limits": list(self.limits),
            "turns_tracked": self.turns_tracked,
        }


def honesty_check(statement: str, known_tool_names: List[str]) -> List[str]:
    """Flag capability claims in ``statement`` that are not grounded.

    Returns a list of warnings; empty means nothing checkable was found.
    This is the runtime companion of the atlas honesty rule: LEVI should
    not claim tool abilities it does not have.
    """
    import re

    warnings: List[str] = []
    known = {t.lower() for t in known_tool_names}
    # Look for "I can <verb> ..." / "I'll <verb> ..." claims naming tools.
    for m in re.finditer(
        r"\b(?:i can|i'll|i will|let me|i'm able to)\s+([a-z_]+)",
        statement.lower(),
    ):
        verb = m.group(1)
        if verb not in known and len(verb) > 2:
            # Only warn when the verb looks like a tool name.
            if "_" in verb or verb in (
                "browse",
                "search",
                "email",
                "schedule",
                "deploy",
            ):
                warnings.append(
                    f"unverified capability claim: {verb!r} is not a known tool"
                )
    return warnings


class SessionEI:
    """Per-session tracker for Goleman's five EI dimensions.

    Scores are 0..1 operational indicators, updated from observed turns —
    they measure *conduct* (did LEVI stay regulated? did it attune?) not
    inner states. ``report()`` is the self-awareness surface: it can be
    shown to the user or an auditor verbatim.
    """

    def __init__(self, register_id: str = "levi") -> None:
        self.scores: Dict[str, float] = {
            "self_awareness": 0.7,
            "self_regulation": 0.8,
            "motivation": 0.6,
            "empathy": 0.6,
            "social_skills": 0.6,
        }
        self.self_model = SelfModel(register_id=register_id)
        self.turns = 0
        self.last_reading: Optional[EmotionReading] = None
        self._frustration_streak = 0

    # -- observation ----------------------------------------------------

    def observe_user(self, text: str) -> EmotionReading:
        """Ingest one user turn; update empathy/social scores from it."""
        reading = detect(text)
        self.last_reading = reading
        self.turns += 1
        if reading.confidence > 0:
            # Attunement: noticing affect at all is the empathy behavior.
            self.scores["empathy"] = min(1.0, self.scores["empathy"] + 0.03)
            self.scores["social_skills"] = min(1.0, self.scores["social_skills"] + 0.02)
        # Track frustration streaks (anger/fear at high arousal, repeated).
        if reading.dominant in ("anger", "fear") and reading.arousal > 0.6:
            self._frustration_streak += 1
        else:
            self._frustration_streak = 0
        return reading

    def observe_self(
        self,
        *,
        stayed_regulated: bool = True,
        stated_limit: Optional[str] = None,
        was_proactive: bool = False,
        repaired: bool = False,
    ) -> None:
        """Ingest one of LEVI's own turns; update the self-side scores."""
        if stayed_regulated:
            self.scores["self_regulation"] = min(
                1.0, self.scores["self_regulation"] + 0.02
            )
        else:
            self.scores["self_regulation"] = max(
                0.0, self.scores["self_regulation"] - 0.15
            )
        if stated_limit:
            self.self_model.state_limit(stated_limit)
            self.scores["self_awareness"] = min(
                1.0, self.scores["self_awareness"] + 0.04
            )
        if was_proactive:
            self.scores["motivation"] = min(1.0, self.scores["motivation"] + 0.04)
        if repaired:
            self.scores["social_skills"] = min(1.0, self.scores["social_skills"] + 0.05)
            self._frustration_streak = 0

    # -- queries ----------------------------------------------------------

    @property
    def frustration_streak(self) -> int:
        return self._frustration_streak

    def needs_repair(self) -> bool:
        """True when the user has been frustrated for 2+ consecutive turns."""
        return self._frustration_streak >= 2

    def report(self) -> Dict:
        """Honest, human-readable snapshot of this session's EI conduct."""
        return {
            "dimensions": {k: round(v, 3) for k, v in self.scores.items()},
            "turns": self.turns,
            "frustration_streak": self._frustration_streak,
            "self_model": self.self_model.to_dict(),
            "last_user_affect": (
                self.last_reading.to_dict() if self.last_reading else None
            ),
            "note": (
                "Pattern-based affect modeling, not felt emotion. "
                "Scores track observed conduct, not inner states."
            ),
        }
