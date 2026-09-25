"""Plaiground after-dark — grown-folks entertainment & conversation.

Late-night company: banter lines, conversation starters for adults,
original trivia, and party-game hosting frames. The voice is the SI
one — playful, direct, unfiltered in stance, never preachy. Grown
users get treated like grown users.

What ships is playful and non-explicit; the unfiltered part is the
refusal to moralize. All user-supplied strings pass the bounds check.
Gate-checked first, like everything on this surface.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from levi.plaiground.bounds import check_bounds
from levi.plaiground.gate import require_adult

TRACK = "si"
ZONE = "plaiground"

_BANTER = (
    "It's past midnight — the hour when everybody becomes ten percent more honest.",
    "Welcome to the grown-folks hour. No small talk allowed past this point.",
    "Somewhere out there, somebody is having a better night than you. Let's fix that.",
    "The good conversations don't start until the polite ones end.",
    "Tonight's forecast: unfiltered, with a chance of laughter.",
    "You made it past the gate. That already makes you more interesting than most.",
    "Low lights, good company, zero pretense — the official recipe.",
    "Adults only past this point, which mostly means: no pretending.",
)

_STARTER_DECKS = {
    "confessions": (
        "What's the most grown decision you ever made at 2 a.m.?",
        "Confess something your younger self would be shocked you enjoy now.",
        "What's a pleasure you stopped apologizing for?",
    ),
    "stories": (
        "Tell me about the night that became a legend in your friend group.",
        "What's the boldest thing you've ever done on a first date?",
        "Describe your most cinematic kiss — set the scene.",
    ),
    "opinions": (
        "Unpopular opinion: what does everybody get wrong about romance?",
        "Settle it — is the chase better than the catch?",
        "What's overrated about modern dating, honestly?",
    ),
    "deep": (
        "What did heartbreak teach you that happiness never could?",
        "When do you feel most like yourself?",
        "What are you still hoping for that you don't say out loud?",
    ),
}

# Original trivia, written for this module. Grown-folks general
# knowledge — playful, never crude.
_TRIVIA: Tuple[Tuple[str, str], ...] = (
    ("Which cocktail is traditionally made with vodka, ginger beer, and lime, served in a copper mug?", "Moscow Mule"),
    ("In classic cinema, which 1942 film ends at an airport with 'Here's looking at you, kid'?", "Casablanca"),
    ("What dance, born in Argentina, is danced chest-to-chest in a close embrace?", "Tango"),
    ("Which jazz singer was nicknamed 'Lady Day'?", "Billie Holiday"),
    ("What is the name of the slow, romantic dance in 3/4 time?", "Waltz"),
    ("Which city is home to the Moulin Rouge?", "Paris"),
    ("In mixology, what does 'neat' mean when ordering a spirit?", "Served at room temperature with no ice or mixer"),
    ("Which novel opens with 'It was a bright cold day in April, and the clocks were striking thirteen'?", "1984"),
    ("What is the traditional gift for a 25th wedding anniversary?", "Silver"),
    ("Which island nation is famous for its slow 'liming' culture of hanging out with friends?", "Trinidad and Tobago"),
    ("What late-night talk format is named after the 'witching hour' slot it occupies?", "After-dark / late-night show"),
    ("Which wine is traditionally paired with oysters?", "Muscadet (or dry white)"),
)


def _rng(seed: Optional[str]) -> random.Random:
    return random.Random("plaiground-afterdark|%s" % (seed or "default"))


def banter(seed: Optional[str] = None, home: Optional[Path] = None) -> Dict:
    """One late-night banter line, deterministic from seed."""
    require_adult(home)
    return {
        "track": TRACK,
        "zone": ZONE,
        "kind": "banter",
        "line": _rng(seed).choice(_BANTER),
    }


def starters(theme: str, count: int = 3, home: Optional[Path] = None) -> Dict:
    """Conversation starters for grown folks. Themes: confessions, stories, opinions, deep."""
    require_adult(home)
    if theme not in _STARTER_DECKS:
        raise ValueError("theme must be one of %s" % ", ".join(sorted(_STARTER_DECKS)))
    if not isinstance(count, int) or not 1 <= count <= 3:
        raise ValueError("count must be an integer 1..3")
    deck = _STARTER_DECKS[theme]
    return {
        "track": TRACK,
        "zone": ZONE,
        "kind": "starters",
        "theme": theme,
        "starters": list(deck[:count]),
    }


def trivia(count: int = 4, seed: Optional[str] = None, home: Optional[Path] = None) -> Dict:
    """Original trivia Q&A, deterministic order from seed."""
    require_adult(home)
    if not isinstance(count, int) or not 1 <= count <= len(_TRIVIA):
        raise ValueError("count must be an integer 1..%d" % len(_TRIVIA))
    r = _rng(seed)
    chosen = r.sample(_TRIVIA, count)
    return {
        "track": TRACK,
        "zone": ZONE,
        "kind": "trivia",
        "seed": seed or "default",
        "rounds": [{"question": q, "answer": a} for q, a in chosen],
    }


def host_game(kind: str, topic: Optional[str] = None, home: Optional[Path] = None) -> Dict:
    """Host a party game frame. Kinds: two-truths, would-you-rather, story-round.

    The engine hosts — rules, first round, scoring frame. Players supply
    the content; their content is bounds-checked when submitted via
    :func:`submit_round`.
    """
    require_adult(home)
    frames = {
        "two-truths": {
            "rules": "Each player states two truths and one lie. The table votes on the lie. "
            "Caught lying well is the whole point — 1 point per correct guess.",
            "opener": "I'll start the bidding: give me your three statements.",
        },
        "would-you-rather": {
            "rules": "Two options, no hedging, no 'it depends'. Majority rules; "
            "the minority defends their pick in one sentence.",
            "opener": "First dilemma: slow dance in the kitchen, or slow drive with no destination?",
        },
        "story-round": {
            "rules": "One sentence each, building one story. No vetoing, no steering — "
            "yes-and only. The story ends when somebody lands the punchline.",
            "opener": "The story begins: 'The power went out at exactly the wrong moment...'",
        },
    }
    if kind not in frames:
        raise ValueError("kind must be one of %s" % ", ".join(sorted(frames)))
    if topic is not None:
        topic = check_bounds(topic, home)[:120]
    frame = frames[kind]
    return {
        "track": TRACK,
        "zone": ZONE,
        "kind": "game",
        "game": kind,
        "topic": topic,
        "rules": frame["rules"],
        "opener": frame["opener"],
    }


def submit_round(game: str, entries: List[str], home: Optional[Path] = None) -> Dict:
    """Submit one round of player content for scoring/framing.

    Entries are bounds-checked — the table plays grown, not cruel.
    """
    require_adult(home)
    if game not in ("two-truths", "would-you-rather", "story-round"):
        raise ValueError("unknown game %r" % game)
    if not isinstance(entries, list) or not entries:
        raise ValueError("entries must be a non-empty list")
    if len(entries) > 10:
        raise ValueError("entries must be at most 10")
    cleaned = [check_bounds(e, home)[:500] for e in entries]
    if game == "story-round":
        combined = " ".join(cleaned)
        verdict = "The story stands at %d sentences. Somebody land it." % len(cleaned)
    elif game == "two-truths":
        verdict = "Three statements on the table. Vote: which one is the lie?"
        combined = " | ".join(cleaned)
    else:
        verdict = "Options locked. Majority rules — minority defends in one sentence."
        combined = " vs ".join(cleaned)
    return {
        "track": TRACK,
        "zone": ZONE,
        "kind": "round",
        "game": game,
        "entries": cleaned,
        "combined": combined,
        "host_says": verdict,
    }
