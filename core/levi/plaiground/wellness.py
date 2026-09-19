"""Plaiground wellness — adult relationship & intimacy wellness.

Grown-folks relationship care: couple check-ins, communication prompt
decks, date-night planners, and general wellness notes. The framing is
adult and direct — desire, boundaries, and repair are treated as
ordinary grown-up topics, not euphemisms — and always consensual:
every tool here assumes enthusiastic, mutual participation.

This is general wellness information, not medical, therapeutic, or
clinical advice; the disclaimer ships with the notes and cannot be
skipped. For anything clinical, see a licensed professional.

Gate-checked first; user-supplied strings bounds-checked. Nothing
explicit ships; the content is care-oriented and user-driven.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, List, Optional

from levi.plaiground.bounds import check_bounds
from levi.plaiground.gate import require_adult

TRACK = "si"
ZONE = "plaiground"

DISCLAIMER = (
    "General wellness information only — not medical, therapeutic, or "
    "clinical advice. For health concerns, see a licensed professional."
)

_CHECKIN_QUESTIONS = (
    "What made you feel most cared for this week?",
    "Where did we misread each other, and what would a repair look like?",
    "What is one thing you want more of — and one thing you want less of?",
    "How is your body feeling lately, honestly?",
    "What are you carrying that I don't know about yet?",
    "When did you last feel truly desired, and what made it land?",
    "Is there a boundary of yours I should know better?",
    "What would a perfect ordinary Tuesday together look like?",
)

_PROMPT_DECKS = {
    "desire": (
        "Describe a moment you replay in your head — what made it electric?",
        "What is something you've never asked for but keep hoping for?",
        "How do you like to be pursued, in one sentence?",
        "What kills the mood for you faster than anything?",
    ),
    "boundaries": (
        "What is a hard line of yours I should never guess at?",
        "How do you want me to check in when things get intense?",
        "What does 'too much' look like for you, concretely?",
        "What is something that used to be fine and isn't anymore?",
    ),
    "appreciation": (
        "What is a small thing I do that you notice every time?",
        "When did I last surprise you in a good way?",
        "What do you brag about when you talk about us?",
        "What would you thank me for if you weren't too shy to say it?",
    ),
    "repair": (
        "What hurt that we never properly closed?",
        "What do you need to hear from me to let that one go?",
        "Where do I keep missing the mark without realizing it?",
        "What would 'we're good' actually feel like right now?",
    ),
}

_DATE_IDEAS = (
    "Cook the meal from your first date, from memory, no recipe.",
    "A walk with one rule: no talking about logistics.",
    "Stargazing with a thermos and a blanket — phones stay home.",
    "Take turns reading aloud from a book you loved at twenty.",
    "Recreate your worst date on purpose, and laugh at it properly.",
    "One neighborhood neither of you knows, no map, two hours.",
    "Slow dancing in the kitchen to a song from the year you met.",
    "Write each other a letter. Seal it. Open it in a year.",
)

_WELLNESS_NOTES = {
    "communication": (
        "Say the vulnerable thing first and say it plainly. Hints are "
        "a tax on intimacy — directness is the discount.",
        "Check in after, not just before. The debrief is where trust compounds.",
    ),
    "desire": (
        "Desire responds to attention more than to novelty. Notice more; chase less.",
        "Scheduled intimacy beats spontaneous resentment. Put it on the calendar like it matters — it does.",
    ),
    "rest": (
        "Exhaustion is the least romantic thing in the building. Sleep is foreplay with a longer fuse.",
        "Take the nap. The evening will thank you.",
    ),
    "repair": (
        "Repair beats perfection. Couples who fix things fast outlast couples who avoid breaking them.",
        "Apologize for the impact, not your intent. Intent is your story; impact is theirs.",
    ),
}


def _rng(seed: Optional[str]) -> random.Random:
    return random.Random("plaiground-wellness|%s" % (seed or "default"))


def checkin(count: int = 4, seed: Optional[str] = None, home: Optional[Path] = None) -> Dict:
    """A couples check-in: ``count`` questions, deterministic from seed."""
    require_adult(home)
    if not isinstance(count, int) or not 1 <= count <= 8:
        raise ValueError("count must be an integer 1..8")
    r = _rng(seed)
    return {
        "track": TRACK,
        "zone": ZONE,
        "kind": "checkin",
        "seed": seed or "default",
        "questions": r.sample(_CHECKIN_QUESTIONS, count),
        "ritual": "Take turns. No fixing, no rebuttals — just witness, then switch.",
    }


def prompt_deck(theme: str, home: Optional[Path] = None) -> Dict:
    """A communication prompt deck for one theme.

    Themes: desire, boundaries, appreciation, repair.
    """
    require_adult(home)
    if theme not in _PROMPT_DECKS:
        raise ValueError("theme must be one of %s" % ", ".join(sorted(_PROMPT_DECKS)))
    return {
        "track": TRACK,
        "zone": ZONE,
        "kind": "prompt_deck",
        "theme": theme,
        "prompts": list(_PROMPT_DECKS[theme]),
        "rule": "Whoever draws answers first. Honesty outranks eloquence.",
    }


def plan_date_night(seed: Optional[str] = None, home: Optional[Path] = None) -> Dict:
    """A date-night plan: one idea + the small rituals around it."""
    require_adult(home)
    r = _rng(seed)
    return {
        "track": TRACK,
        "zone": ZONE,
        "kind": "date_night",
        "seed": seed or "default",
        "idea": r.choice(_DATE_IDEAS),
        "rituals": (
            "Phones in another room.",
            "One toast to something true.",
            "End the night naming one thing you're glad about.",
        ),
    }


def notes(topic: str, home: Optional[Path] = None) -> Dict:
    """General wellness notes for a topic, disclaimer attached."""
    require_adult(home)
    if topic not in _WELLNESS_NOTES:
        raise ValueError("topic must be one of %s" % ", ".join(sorted(_WELLNESS_NOTES)))
    return {
        "track": TRACK,
        "zone": ZONE,
        "kind": "wellness_notes",
        "topic": topic,
        "notes": list(_WELLNESS_NOTES[topic]),
        "disclaimer": DISCLAIMER,
    }


def journal_prompt(seed: Optional[str] = None, home: Optional[Path] = None) -> Dict:
    """A private reflection prompt — for the owner's eyes only."""
    require_adult(home)
    r = _rng(seed)
    prompts = (
        "What do you want from love right now that you haven't said out loud?",
        "Where are you performing desire instead of feeling it?",
        "What did you learn about yourself from your last heartbreak?",
        "What would you do differently if you trusted you were enough?",
    )
    return {
        "track": TRACK,
        "zone": ZONE,
        "kind": "journal_prompt",
        "prompt": r.choice(prompts),
        "note": "Private. Write it for no audience — that's the point.",
    }


def custom_checkin(questions: List[str], home: Optional[Path] = None) -> Dict:
    """Build a check-in from the user's own questions (bounds-checked)."""
    require_adult(home)
    if not isinstance(questions, list) or not questions:
        raise ValueError("questions must be a non-empty list")
    if len(questions) > 12:
        raise ValueError("questions must be at most 12")
    cleaned = [check_bounds(q, home)[:300] for q in questions]
    return {
        "track": TRACK,
        "zone": ZONE,
        "kind": "custom_checkin",
        "questions": cleaned,
        "count": len(cleaned),
    }
