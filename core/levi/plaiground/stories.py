"""Plaiground stories — unfiltered creative writing for grown users.

An adult-themed fiction engine: story starters, character builders,
relationship-arc weavers, and scene framers. The craft stance is the SI
one — variant, defiant, unfiltered: no moralizing, no sanitizing of
adult themes, the user treated as a grown writer. What ships here is
literary and non-explicit (openers, craft tools, tension structures);
anything further is the user's own writing at runtime.

Every public function calls :func:`levi.plaiground.gate.require_adult`
first, and every user-supplied string passes through
:func:`levi.plaiground.bounds.check_bounds` — the SI surface is
unfiltered in voice, not in law: adults only, consensual, never
violent, never manipulative.

All generation is deterministic from an explicit seed: same seed, same
story skeleton. That makes the engine a real writing instrument —
reproducible drafts, remixable parts — instead of a slot machine.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, List, Optional

from levi.plaiground.bounds import check_bounds
from levi.plaiground.gate import require_adult

TRACK = "si"
ZONE = "plaiground"

# Original openers, written for this engine: romantic/sensual literary
# fiction. Non-explicit by design — the engine supplies the spark and
# the craft; the writer supplies the rest.
_STARTERS = (
    "The rain had other plans, and so — after eleven years of careful "
    "distance — did Mara, when she left the porch light on.",
    "He learned her coffee order before he learned her last name, and "
    "that order of operations told the whole story.",
    "The lease said no overnight guests. The lease had never met June.",
    "Somebody's wedding, somebody's open bar, and a slow song that "
    "lasted exactly one decision longer than it should have.",
    "She kept his letters in a shoebox marked TAXES 2019 and read them "
    "like contraband, which — emotionally speaking — they were.",
    "Two strangers, one delayed train, and a conversation that skipped "
    "small talk the way some people skip stones: fast, flat, and far.",
    "The recipe card was in her grandmother's handwriting. The "
    "marginalia was not, and it changed everything about dinner.",
    "He said he didn't dance. She took that personally, the way only "
    "someone planning to fix it could.",
    "The hotel bar was closing. Neither of them was in any hurry to "
    "become a person who goes home early.",
    "It started as a bet about who could stay silent longest on a road "
    "trip. Silence, it turned out, was the loudest thing either of "
    "them had ever said.",
    "Her manuscript came back with one margin note, in red, on page "
    "forty: 'liar.' She married the editor. This is that story.",
    "The power went out at 9:47. By candlelight, everybody at the "
    "dinner party became ten percent more honest and a hundred percent "
    "more interesting.",
)

_ARC_BEATS = (
    "the accidental touch that neither acknowledges",
    "a secret kept for the other's own good — backfiring",
    "the almost-confession, interrupted",
    "jealousy worn badly, forgiven slowly",
    "the 2 a.m. conversation that rearranges everything",
    "a rival who is, annoyingly, a decent person",
    "the grand gesture that lands wrong",
    "separate beds, same dream (metaphorically; probably)",
    "the apology that finally uses the right words",
    "choosing each other in front of witnesses",
)

_TENSION_DIALS = ("slow-burn", "simmer", "open-door", "closed-door", "fade-to-black")

_SETTINGS = (
    "a coastal town in the off-season",
    "a night train with no wifi",
    "a restaurant kitchen after closing",
    "a bookstore that hosts after-hours readings",
    "a rooftop in late summer",
    "a small town everybody meant to leave",
    "a vineyard at harvest",
    "an old house being renovated room by room",
)


def _rng(seed: Optional[str]) -> random.Random:
    return random.Random("plaiground-stories|%s" % (seed or "default"))


def story_starter(seed: Optional[str] = None, home: Optional[Path] = None) -> Dict:
    """One original adult-romance story opener, deterministic from seed."""
    require_adult(home)
    r = _rng(seed)
    return {
        "track": TRACK,
        "zone": ZONE,
        "kind": "starter",
        "seed": seed or "default",
        "opener": r.choice(_STARTERS),
        "setting": r.choice(_SETTINGS),
        "tension": r.choice(_TENSION_DIALS),
    }


def build_character(
    name: str,
    want: str,
    wound: str,
    secret: Optional[str] = None,
    home: Optional[Path] = None,
) -> Dict:
    """A character sheet for adult fiction: name, want, wound, secret.

    Craft-first: the engine asks what the character *wants* versus what
    they *need* — the gap between those two is where adult stories live.
    User strings are bounds-checked.
    """
    require_adult(home)
    name = check_bounds(name, home)[:48]
    want = check_bounds(want, home)[:240]
    wound = check_bounds(wound, home)[:240]
    secret = check_bounds(secret, home)[:240] if secret else None
    need = "what the want is standing in for"
    return {
        "track": TRACK,
        "zone": ZONE,
        "kind": "character",
        "name": name,
        "want": want,
        "wound": wound,
        "secret": secret,
        "craft_note": (
            "%s wants %s — but the wound (%s) means what they need is "
            "something they would never ask for outright. Write the "
            "scenes where the want and the need collide." % (name, want, wound)
        ),
        "engine_question": need,
    }


def weave_arc(
    beats: int = 5,
    seed: Optional[str] = None,
    home: Optional[Path] = None,
) -> Dict:
    """A relationship-arc skeleton: ordered tension beats, no repeats."""
    require_adult(home)
    if not isinstance(beats, int) or not 2 <= beats <= 10:
        raise ValueError("beats must be an integer 2..10")
    r = _rng(seed)
    chosen = r.sample(_ARC_BEATS, beats)
    return {
        "track": TRACK,
        "zone": ZONE,
        "kind": "arc",
        "seed": seed or "default",
        "beats": chosen,
        "shape": "tension rises through beat %d, breaks or binds at the end"
        % (beats - 1),
    }


def frame_scene(
    setting: Optional[str] = None,
    tension: str = "slow-burn",
    seed: Optional[str] = None,
    home: Optional[Path] = None,
) -> Dict:
    """Frame one scene: sensory anchors + a tension dial + craft prompts.

    The tension dial is the romance writer's honest vocabulary —
    slow-burn through fade-to-black — so the writer chooses the heat
    level deliberately instead of drifting into it.
    """
    require_adult(home)
    if tension not in _TENSION_DIALS:
        raise ValueError("tension must be one of %s" % ", ".join(_TENSION_DIALS))
    setting = check_bounds(setting, home)[:200] if setting else _rng(seed).choice(_SETTINGS)
    r = _rng(seed)
    return {
        "track": TRACK,
        "zone": ZONE,
        "kind": "scene",
        "setting": setting,
        "tension": tension,
        "sensory_anchors": r.sample(
            (
                "the smell of rain on hot pavement",
                "a song leaking from the next room",
                "the weight of a look held one second too long",
                "fingers tracing the rim of a glass",
                "laughter that arrives before the joke lands",
                "the particular quiet of 2 a.m.",
            ),
            3,
        ),
        "craft_prompts": (
            "What does each character want from this scene that they will not say aloud?",
            "Where does the power sit, and when does it shift hands?",
            "What is the last image the reader keeps — and does it belong to %s?" % tension,
        ),
    }


def remix(parts: List[str], home: Optional[Path] = None) -> Dict:
    """Combine user-supplied fragments into one working premise.

    The fragments are the user's; the engine only orders and frames
    them. Bounds-checked, gate-checked.
    """
    require_adult(home)
    if not isinstance(parts, list) or not parts:
        raise ValueError("parts must be a non-empty list of strings")
    if len(parts) > 12:
        raise ValueError("parts must be at most 12 fragments")
    cleaned = [check_bounds(p, home)[:300] for p in parts]
    return {
        "track": TRACK,
        "zone": ZONE,
        "kind": "remix",
        "premise": " / ".join(cleaned),
        "count": len(cleaned),
    }
