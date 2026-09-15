"""Modulation — turn affect reads into agent-loop behavior.

Dimension 3 (MOTIVATION) wiring: :func:`record_signal` persists
per-session affect signals (frustration streaks, repair events, rapport)
to ``~/.levi/affect/signals.jsonl``; the growth loop harvests that file
as an experience source, so repeated user frustration becomes a *drive
to improve* — LEVI's motivation dimension, grounded in observed
conduct rather than asserted desire.

Dimension 4 (EMPATHY) + 5 (SOCIAL SKILLS) wiring: :func:`affect_hint`
builds the prompt addendum injected into the agent loop's system prompt.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from levi.affect.detector import EmotionReading
from levi.affect.policy import PolicyDecision, evaluate
from levi.affect.registers import (
    RegisterSuggestion,
    check_wit_safety,
    detect_rapport,
    detect_repair,
    suggest_register,
)
from levi.affect.state import SessionEI

_DISCLAIMER = (
    "Affect note (pattern-based, not felt): the labels below come from "
    "word-pattern matching on the user's text. They are operational guesses "
    "to guide your conduct — stay attuned, never claim to feel anything, "
    "and never present a label as a diagnosis of the person."
)


def affect_hint(
    reading: EmotionReading,
    policy: PolicyDecision,
    suggestion: RegisterSuggestion,
    session: Optional[SessionEI] = None,
) -> str:
    """Build the system-prompt addendum for this turn."""
    lines = [_DISCLAIMER]
    lines.append(
        f"User affect read: dominant={reading.dominant} "
        f"valence={reading.valence:+.2f} arousal={reading.arousal:.2f} "
        f"confidence={reading.confidence:.2f}"
    )
    if reading.stress_signals:
        lines.append(
            "Stress signals: " + ", ".join(reading.stress_signals)
        )
    lines.append(f"Suggested register: {suggestion.register_id} ({suggestion.rationale})")
    for hint in policy.hints:
        lines.append(f"- {hint}")
    if policy.avoid:
        lines.append("Avoid this turn: " + "; ".join(policy.avoid))
    repair = session is not None and session.needs_repair()
    if repair:
        lines.append(
            "- REPAIR MODE: the user has been frustrated for multiple turns. "
            "Slow down, acknowledge the friction explicitly, and ask what "
            "would actually help before doing more."
        )
    return "\n".join(lines)


def modulate(
    text: str,
    session: SessionEI,
    user_register: Optional[str] = None,
) -> Dict:
    """Full per-turn modulation: observe, decide, suggest, hint.

    Returns a dict with the reading, policy, register suggestion, and the
    prompt hint. Pure except for updating ``session`` scores.
    """
    reading = session.observe_user(text)
    policy = evaluate(text, reading)
    suggestion = suggest_register(
        text, reading, policy, user_choice=user_register
    )
    # Safety veto: wit registers can never override a de-escalation policy.
    allowed, veto_reason = check_wit_safety(suggestion.register_id, policy)
    if not allowed:
        suggestion = RegisterSuggestion(
            register_id="kai_9000_care" if policy.crisis else "kai_9000",
            rationale=f"veto: {veto_reason}",
        )
    repair_hint = detect_repair(text)
    rapport = detect_rapport(text)
    session.observe_self(
        stayed_regulated=not policy.provoked,
        repaired=bool(repair_hint),
    )
    hint = affect_hint(reading, policy, suggestion, session)
    if repair_hint:
        hint += "\n- " + repair_hint
    return {
        "reading": reading.to_dict(),
        "policy": policy.to_dict(),
        "register": suggestion.register_id,
        "register_rationale": suggestion.rationale,
        "repair": repair_hint,
        "rapport": rapport,
        "hint": hint,
    }


# ---------------------------------------------------------------------------
# Motivation -> growth loop
# ---------------------------------------------------------------------------

def _signals_path() -> Path:
    base = Path(os.environ.get("LEVI_HOME", Path.home() / ".levi"))
    return base / "affect" / "signals.jsonl"


def record_signal(
    session: SessionEI,
    kind: str,
    detail: str = "",
    path: Optional[Path] = None,
) -> Dict:
    """Persist one motivation signal for the growth loop to harvest.

    ``kind``: "frustration-streak" | "repair" | "rapport-positive" |
    "proactive-opportunity". Returns the record written.
    """
    target = Path(path) if path else _signals_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": kind,
        "detail": detail[:500],
        "session_turns": session.turns,
        "dimensions": {k: round(v, 3) for k, v in session.scores.items()},
    }
    with open(target, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record


def growth_signals(session: SessionEI, path: Optional[Path] = None) -> List[Dict]:
    """Decide which motivation signals this session owes the growth loop."""
    signals: List[Dict] = []
    if session.needs_repair():
        signals.append(
            record_signal(
                session,
                "frustration-streak",
                f"user frustrated {session.frustration_streak} consecutive turns; "
                "improvement drive: find what kept missing and fix the pattern",
                path,
            )
        )
    if session.scores["motivation"] < 0.5:
        signals.append(
            record_signal(
                session,
                "proactive-opportunity",
                "low proactive score this session; look for unprompted helpful moves",
                path,
            )
        )
    return signals
