"""
Premium story craft — old techniques × modern methods × L.W.P. physics.

Classical (retired-but-gold): scene/sequel, try/fail cycles, dramatic unities,
Freytag tension, in medias res, objective correlative, icebergs, chekhov,
free indirect style, stichomythia, tragic flaw, recognition/reversal.

Modern: in-late-out-early, kishōtenketsu-aware turns, focalization control,
A/B story braid, plant/payoff ledger, sensory triangle, prose rhythm,
refusal of explanation-dumps, micro-tension per paragraph.

LEVI-unique: cascade-locked beats, scar law, void-ghost residue, ROM rupture hooks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import hashlib


# Named cascade for premium expansions (order matters)
PREMIUM_CASCADE = [
    "In Medias Res Hook",
    "Plant (Chekhov)",
    "Try-Fail 1",
    "Sequel Reaction",
    "Midpoint Reversal",
    "B-Story Mirror",
    "Dark Night Cost",
    "Recognition (Anagnorisis)",
    "Convergence Payoff",
    "Aftermath Image",
]

SCENE_GOALS = [
    "obtain information under cost",
    "escape a tightening frame",
    "force a confession without power",
    "protect someone while lying to themselves",
    "cross a threshold they swore to avoid",
]

SEQUEL_MOVES = [
    "emotion → dilemma → decision",
    "rationalize the wound → see the lie → choose pain",
    "review the failure → name the real need → act smaller",
]

SENSORY_BUCKETS = ("sight", "sound", "body", "place-time")


@dataclass
class CraftLens:
    name: str
    era: str  # classical | modern | lwp
    instruction: str


LENSES: List[CraftLens] = [
    CraftLens("scene_sequel", "classical", "Alternate scene (goal/conflict/disaster) with sequel (emotion/dilemma/decision)."),
    CraftLens("try_fail", "classical", "Protagonist tries; fails at escalating cost before any win."),
    CraftLens("chekhov", "classical", "Every introduced object or line must fire later."),
    CraftLens("iceberg", "classical", "Show 1/8th; imply the rest through behavior and omission."),
    CraftLens("objective_correlative", "classical", "External image carries emotion; do not name the feeling first."),
    CraftLens("in_medias_res", "classical", "Open after the irreversible has begun."),
    CraftLens("recognition_reversal", "classical", "Anagnorisis + peripeteia: knowledge changes the power map."),
    CraftLens("free_indirect", "classical", "Narration leans into character diction without full 1st person."),
    CraftLens("in_late_out_early", "modern", "Enter scenes late; leave early; cut throat-clearing."),
    CraftLens("micro_tension", "modern", "Every paragraph ends with unanswered pressure."),
    CraftLens("focalization", "modern", "Lock whose eyes we borrow; do not head-hop mid-beat."),
    CraftLens("plant_payoff", "modern", "Ledger plants early; pay off under cascade pressure."),
    CraftLens("kishotenketsu_turn", "modern", "Twists can reframe without pure antagonist opposition."),
    CraftLens("sensory_triangle", "modern", "At least two senses + one body state per major beat."),
    CraftLens("cascade_lock", "lwp", "Next beat is typed by cascade order, not random flourish."),
    CraftLens("scar_law", "lwp", "Consequences accrue; wounds do not reset for convenience."),
    CraftLens("void_ghost", "lwp", "Denied paths leave residue that can haunt later prose."),
    CraftLens("rom_hook", "lwp", "Optional rupture only when anomaly budget allows."),
]


def craft_menu() -> str:
    lines = ["=== Premium Craft Lenses (old × new × L.W.P.) ===", ""]
    for era in ("classical", "modern", "lwp"):
        lines.append(f"— {era.upper()} —")
        for L in LENSES:
            if L.era == era:
                lines.append(f"  {L.name}: {L.instruction}")
        lines.append("")
    lines.append("Cascade order: " + " → ".join(PREMIUM_CASCADE))
    return "\n".join(lines)


def pick_cascade_beat(expand_index: int) -> str:
    return PREMIUM_CASCADE[expand_index % len(PREMIUM_CASCADE)]


def scene_goal(seed: str) -> str:
    h = int(hashlib.sha1(seed.encode()).hexdigest()[:8], 16)
    return SCENE_GOALS[h % len(SCENE_GOALS)]


def sequel_move(seed: str) -> str:
    h = int(hashlib.sha1(("s" + seed).encode()).hexdigest()[:8], 16)
    return SEQUEL_MOVES[h % len(SEQUEL_MOVES)]


def premium_opening(
    lead_name: str,
    genre: str,
    premise: str,
    want: str,
    need: str,
    wound: str,
    voice: str = "",
) -> str:
    """Offline premium opening: in medias res + objective correlative + micro-tension."""
    g = genre.replace("_", " ")
    goal = scene_goal(premise or lead_name)
    # Avoid explaining the genre; embody it
    p1 = (
        f"The bill arrived before the apology. {lead_name} was already mid-step — "
        f"{premise.rstrip('.')}. In a {g} world, that was not setup; it was the middle."
    )
    p2 = (
        f"Someone had left a glass ring on the table that would not wipe clean. "
        f"{lead_name} noticed it the way you notice a locked door: not decoration — inventory."
    )
    p3 = (
        f"Want, on paper: {want}. Need, unpaid: {need}. "
        f"The wound they refused to invoice still set the interest rate: {wound}."
    )
    p4 = (
        f"Scene goal now: {goal}. "
        f"No throat-clearing. Enter late. Leave before the air goes soft."
    )
    if voice:
        p4 += f" Voice leans {voice}."
    return "\n\n".join([p1, p2, p3, p4])


def premium_expand_paragraph(
    beat_name: str,
    lead: str,
    genre: str,
    premise: str,
    wound: str,
    expand_index: int,
) -> str:
    g = genre.replace("_", " ")
    goal = scene_goal(f"{beat_name}{expand_index}")
    sequel = sequel_move(f"{beat_name}{expand_index}")
    # Technique rotation by index
    techniques = [
        f"**{beat_name}** — try/fail: {lead} attempts to {goal}, and the {g} frame taxes the attempt.",
        f"Sequel beat ({sequel}): the body registers the cost before the plan does. Wound echo: {wound}.",
        f"Plant/payoff pressure: an earlier detail returns sharper. Cascade will not skip sequence.",
        f"Micro-tension: the paragraph ends before safety. {lead} still owes the next irreversible inch.",
        f"Focalization locked on {lead}; other minds are weather, not narration rights.",
        f"Iceberg: what is not said about {premise[:80]} carries more weight than a speech.",
    ]
    core = techniques[expand_index % len(techniques)]
    sensory = (
        f"Sensory triangle — sound of the room changing; cold at the wrists; "
        f"the place-time of {g} pressing in."
    )
    scar = "Scar law: yesterday's compromise is still collecting."
    return f"{core}\n{sensory}\n{scar}"


def premium_beats(lead: str, ant: str, genre: str, premise: str) -> List[Dict[str, Any]]:
    """Richer default spine than bare 6-beat list."""
    g = genre.replace("_", " ")
    return [
        {"order": 1, "name": "In Medias Res Hook", "summary": f"{lead} is already paying for: {premise[:100]}"},
        {"order": 2, "name": "Plant (Chekhov)", "summary": f"A detail appears that must matter later under {g} rules."},
        {"order": 3, "name": "Try-Fail 1", "summary": f"{lead} acts; the world answers with cost, not lecture."},
        {"order": 4, "name": "Sequel Reaction", "summary": f"Emotion → dilemma → decision; wound shapes the choice."},
        {"order": 5, "name": "Midpoint Reversal", "summary": f"{ant} or the system flips the power map."},
        {"order": 6, "name": "B-Story Mirror", "summary": f"Secondary thread reflects the true need, not the stated want."},
        {"order": 7, "name": "Dark Night Cost", "summary": f"{lead}'s best strategy fails against the wound."},
        {"order": 8, "name": "Recognition", "summary": f"What was true becomes visible; names change leverage."},
        {"order": 9, "name": "Convergence Payoff", "summary": f"Plants fire; cascade peaks; no free resets."},
        {"order": 10, "name": "Aftermath Image", "summary": f"One concrete image holds the new equilibrium."},
    ]
