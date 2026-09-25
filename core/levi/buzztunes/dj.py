"""SI DJ — the Buzz Tunes picker with a voice.

Chauncey's order: "add an AI/SI DJ — pick a song or a playlist — have
levi nano it."

Pick-path design (honest, stated up front):
  * SELECTION is deterministic and lives here: mood/activity/energy/era
    -> concept -> scored pick over the real catalog. Nothing is guessed;
    the DJ never invents a track.
  * VOICE is attempted through the nano-bit operator seat
    (``levi.operator.registry`` "nano-bit" — the Xi nano-bit tier:
    smallest, fastest, cheapest). Nano-bit answers trivial turns and
    REFUSES non-trivial ones with an escalation hint — never faked.
    So the DJ sends the pick line as one fast turn; on refusal (or on
    any import/lookup failure) it falls back to its own voice renderer.
    The receipt records which path rendered the line. This is the
    "have levi nano it" order, implemented without pretending nano-bit
    does the choosing.

The DJ persona: plain speech, confident picks, says why this track now.
Never claims what it can't prove; the reason always traces to the
inputs and the real catalog.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .providers import Track
from .receipts import ReceiptLog

# ---------------------------------------------------------------------------
# Laws (declared up front; tests prove them)
# ---------------------------------------------------------------------------
# DJ-L1 honest catalog — every picked track comes from the passed catalog;
#          the DJ never invents an artist or title.
# DJ-L2 nano-first, fallback-clean — the voice line is attempted via the
#          nano-bit seat; refusal/error falls back to the local renderer.
#          The path is recorded on the receipt. Never raises.
# DJ-L3 deterministic — same inputs + same catalog => same pick. Proven
#          by the determinism test.

_VOICE_NAME = "buzz-dj"

# Reason fragments per axis — plain speech, why-this-track-now.
_MOOD_WHY = {
    "rainy-night": "low light music for low light weather",
    "sunrise": "built for the hour the day starts",
    "restless": "gives the restlessness somewhere to go",
    "triumphant": "victory-lap energy, earned",
    "lonely": "keeps you company without talking over you",
    "euphoric": "matches the high instead of fighting it",
    "focused": "stays out of the way of the work",
    "nostalgic": "sounds like a memory you actually had",
    "rebellious": "teeth out, volume up",
    "tender": "handles you gently",
    "wired": "meets the buzz where it lives",
    "weightless": "no gravity in it at all",
}
_ACTIVITY_WHY = {
    "coding": "no lyrics fighting your brain",
    "driving": "keeps your eyes on the road and your foot honest",
    "workout": "counts your reps for you",
    "cooking": "moves at kitchen speed",
    "studying": "background that doesn't become foreground",
    "running": "a metronome with a pulse",
    "winding-down": "lowers the lights one song at a time",
    "cleaning": "makes the boring part move faster",
    "writing": "words in the music would steal yours",
    "gaming": "boss-fight pacing without the boss",
    "commuting": "shortens the distance",
    "stargazing": "big sky needs big quiet",
}


def _tokens(text: str) -> List[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


@dataclass
class DJPick:
    """One DJ decision: track + concept + voice + reason + voice path."""
    track: Track
    concept: str
    voice_line: str
    reason: str
    voice_path: str  # "nano-bit" or "dj-fallback"
    axes: Dict[str, str] = field(default_factory=dict)


def build_concept(mood: str, activity: str, energy: Optional[str] = None,
                  era: Optional[str] = None) -> str:
    """A specific, non-generic concept string from the axes."""
    parts = [mood.strip().lower().replace(" ", "-"),
             activity.strip().lower().replace(" ", "-")]
    concept = f"{parts[0]} {parts[1]}"
    if era:
        concept += f", {era.strip().lower()} sound"
    if energy:
        concept += f", {energy.strip().lower()} energy"
    return concept


def _score_track(track: Track, concept_tokens: List[str],
                 demand_boost: float = 0.0) -> float:
    hay = _tokens(f"{track.artist} {track.title}")
    score = sum(2.0 for tok in concept_tokens if tok in hay)
    # Prefer real duration metadata (a finished track over a stub).
    if track.duration:
        score += 0.5
    return score + demand_boost


def _render_voice(track: Track, concept: str, reason: str) -> str:
    return (f"{track.artist} \u2014 {track.title}. {reason[0].upper()}"
            f"{reason[1:]}. This is the one.")


def _nano_voice(line: str) -> Optional[str]:
    """Attempt the voice line through the nano-bit seat.

    Returns the rendered line on a clean nano-bit turn, else None.
    Never raises; every failure mode is a quiet None.
    """
    try:
        from levi.operator import registry as _reg
        from levi.operator.contract import OperatorMessage
        reg = _reg.default_registry()
        nano = reg.get("nano-bit")
        result = nano.step(
            [OperatorMessage(role="user", content=line, name=None,
                             tool_call_id=None)],
            [], {},
        )
    except Exception:
        return None
    if getattr(result, "ok", False) and (result.text or "").strip():
        return result.text.strip()
    return None


def pick_song(mood: str, activity: str, catalog: List[Track],
              energy: Optional[str] = None, era: Optional[str] = None,
              demand_boosts: Optional[Dict[str, float]] = None,
              receipts: Optional[ReceiptLog] = None,
              actor: str = "dj") -> DJPick:
    """Pick one song. Deterministic; honest catalog; nano-first voice.

    Raises ValueError on empty mood/activity, KeyError on empty catalog.
    """
    if not (mood or "").strip():
        raise ValueError("dj: mood is required")
    if not (activity or "").strip():
        raise ValueError("dj: activity is required")
    if not catalog:
        raise KeyError("dj: catalog is empty — nothing honest to pick from")

    concept = build_concept(mood, activity, energy=energy, era=era)
    ctoks = _tokens(concept)
    boosts = demand_boosts or {}
    ranked = sorted(
        catalog,
        key=lambda t: (-_score_track(t, ctoks, boosts.get(t.id, 0.0)), t.id),
    )
    track = ranked[0]

    mood_key = mood.strip().lower().replace(" ", "-")
    act_key = activity.strip().lower().replace(" ", "-")
    why_bits = []
    if mood_key in _MOOD_WHY:
        why_bits.append(_MOOD_WHY[mood_key])
    if act_key in _ACTIVITY_WHY:
        why_bits.append(_ACTIVITY_WHY[act_key])
    if energy:
        why_bits.append(f"{energy.strip().lower()} energy, no more no less")
    if era:
        why_bits.append(f"{era.strip().lower()} the way you asked")
    reason = "; ".join(why_bits) if why_bits else f"built for {concept}"

    draft = _render_voice(track, concept, reason)
    nano_line = _nano_voice(f"Announce this pick in one confident line: "
                            f"{track.artist} - {track.title} for {concept}.")
    voice_path = "nano-bit" if nano_line else "dj-fallback"
    voice_line = nano_line or draft

    if receipts is not None:
        receipts.emit("dj.pick", actor=actor, details={
            "concept": concept,
            "track": track.to_record(),
            "voice_path": voice_path,
            "reason": reason,
        })
    return DJPick(track=track, concept=concept, voice_line=voice_line,
                  reason=reason, voice_path=voice_path,
                  axes={"mood": mood, "activity": activity,
                        "energy": energy or "", "era": era or ""})


def pick_fingerprint(pick: DJPick) -> str:
    """Stable fingerprint of a pick: concept + track id."""
    return hashlib.sha256(
        f"{pick.concept}|{pick.track.id}".encode("utf-8")).hexdigest()[:16]
