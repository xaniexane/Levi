"""
EI-routed persona selection (TRACK 2).

DNA law: 5D EI evaluates BEFORE persona/model routing. The EI state
(presence, empathy, regulation, relational, integrity + the read of the
user's tone/intensity) produces an ADVISORY lens suggestion — it
modulates tone, nothing more.

ADVISORY-ONLY LAW (hard):
    EI never overrides safety, permission, or factual integrity.
    This module returns a suggestion, not a directive. It performs no
    policy checks, grants no permissions, and cannot suppress, reorder,
    or bypass any safety gate, consent requirement, or truth constraint.
    A downstream router may ignore the suggestion entirely; policy gates
    run independently of (and after) any lens application.

Track-1 note: this module deliberately does NOT import any personas
package. It speaks only lens-id strings, taken as a plain list from the
caller, so it is decoupled from whatever lens set the personas layer
provides.

Stdlib only.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from levi.ei.five_d import FiveDEI, EIState

# User intensity at or above this is treated as "needs steadying",
# regardless of the named tone (crisis 0.95, distress 0.85, anger 0.8,
# fear 0.75, exhausted 0.7 in levi.ei.tone).
HIGH_INTENSITY = 0.7

# Tones that always call for a steadying lens, even if intensity reads low.
_STEADY_TONES = frozenset({"crisis", "distress", "fear", "anger", "grief", "exhausted"})

# user_tone -> lens mapping. Keys are lowercased tone labels; values are
# advisory lens ids. Tones not seen here (incl. "neutral") fall through
# to the warm default "friend".
_LENS_BY_TONE: Dict[str, str] = {
    "playful": "trickster",
    "learning": "mentor",
    "exploratory": "mentor",
    "curious": "mentor",
    "confusion": "mentor",
    "reflective": "archivist",
    "archival": "archivist",
    "adversarial": "challenger",
    "pushback": "challenger",
    "challenger": "challenger",
    "debate": "challenger",
}

# Doc-level mapping table (kept in sync with the rules in suggest_lens):
#   high user_intensity (>= 0.7)          -> "protector"  (steadies)
#   steadying tones (crisis/distress/...) -> "protector"  (steadies)
#   user_tone == "playful"               -> "trickster"
#   learning/exploratory/curious/confusion -> "mentor"
#   reflective/archival                 -> "archivist"
#   adversarial/pushback/debate (steelman) -> "challenger"
#   anything else (neutral, warm, unknown) -> "friend" (warm default)


def _suggest(ei_state: EIState) -> str:
    """Core advisory mapping: EIState -> lens id (before availability check)."""
    tone = (ei_state.user_tone or "neutral").strip().lower()
    try:
        intensity = float(ei_state.user_intensity or 0.0)
    except (TypeError, ValueError):
        intensity = 0.0

    # 1. High intensity -> steady the frame.
    if intensity >= HIGH_INTENSITY:
        return "protector"
    # 2. Steadying tones even at moderate intensity.
    if tone in _STEADY_TONES:
        return "protector"
    # 3. Named-tone mapping.
    if tone in _LENS_BY_TONE:
        return _LENS_BY_TONE[tone]
    # 4. Warm default.
    return "friend"


def suggest_lens(ei_state: EIState, available: List[str]) -> str:
    """
    Advise a persona lens for this turn from an EIState.

    Returns the suggested lens id, resolved against `available`:
      - suggestion present -> use it
      - suggestion absent -> "friend" if offered, else available[0]
      - available empty -> "friend" (fail closed to a safe default)

    Never raises for missing/empty availability; the fallback is the
    safe default, not an exception.
    """
    pick = _suggest(ei_state)
    avail = list(available or [])
    if pick in avail:
        return pick
    if "friend" in avail:
        return "friend"
    if avail:
        return avail[0]
    return "friend"


def route_for_text(
    text: str, available: List[str], context: Optional[dict] = None
) -> Tuple[str, EIState]:
    """
    Cheap, side-effect-free convenience: run FiveDEI().evaluate on the
    text, then suggest a lens. No I/O, no writes, no policy decisions.
    """
    state = FiveDEI().evaluate(text, context)
    return suggest_lens(state, available), state
