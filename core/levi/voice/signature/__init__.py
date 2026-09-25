"""Chauncey's signature voice — deterministic voice layer for LEVI's generators.

The training generator (academy) and the content generators (income,
king) teach and write in his voice: endpoint-first, plain speech,
intensity with craft. This module is the single source of that voice.

LAWS (proof-checked, see tests/test_voice.py):
1. Deterministic — same inputs always produce the same output. Selection
   is seeded by sha256 of the inputs, never random.
2. Non-fabricating — the voice wraps content the caller supplies. It never
   invents traction, revenue, users, prices, or outcomes.
3. Non-empty — every voice function returns a non-empty string.
4. Profile-loadable — chauncey_voice.md parses into its sections; the
   module refuses to voice anything if the profile is missing or broken.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Dict, List

_PROFILE_PATH = Path(__file__).with_name("chauncey_voice.md")


def profile_path() -> Path:
    return _PROFILE_PATH


def load_profile() -> Dict[str, str]:
    """Parse chauncey_voice.md into {section_title: body}. Raises if broken."""
    text = _PROFILE_PATH.read_text(encoding="utf-8")
    sections: Dict[str, List[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            current = m.group(1).strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    parsed = {k: "\n".join(v).strip() for k, v in sections.items()}
    required = (
        "Diction",
        "Rhythm",
        "Signature moves",
        "Openers (teaching / content)",
        "Closers",
        "Spiral prompts (interrogation lines)",
        "Voice laws (binding on every generator)",
    )
    missing = [r for r in required if r not in parsed or not parsed[r]]
    if missing:
        raise ValueError(f"voice profile broken; missing sections: {missing}")
    return parsed


def _pick(items: List[str], seed: str) -> str:
    """Deterministic pick: sha256(seed) indexes the list. Never random."""
    if not items:
        raise ValueError("voice pick from empty list")
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return items[int.from_bytes(digest[:8], "big") % len(items)]


# -- voice banks -----------------------------------------------------------
# Every line is craft, not noise: short, plain, endpoint-first. None of
# these invent facts — they frame content the caller already holds.


OPENERS: Dict[str, List[str]] = {
    "lesson": [
        "Here's the endpoint, then the road:",
        "Name the pattern, not the textbook:",
        "The whole road, not the headlights:",
        "Make the movie in your head first — then we move:",
    ],
    "drill": [
        "Think it every angle before you answer:",
        "Run the movie in your head — then act:",
        "Pressure is the teacher today. It'll show, but we never let it get to us:",
    ],
    "debrief": [
        "Honest journal, no varnish — what actually happened?",
        "Better than yesterday: what did this pass leave behind?",
    ],
    "newsletter": [
        "Here's what got built, plain and true:",
        "The road this week, not the headlights:",
    ],
    "social": [
        "Endpoint first:",
        "Name the pattern:",
        "Two faces, one coin:",
    ],
    "document": [
        "Here's the thing, straight:",
        "The endpoint up front — the road after:",
    ],
}

CLOSERS: Dict[str, List[str]] = {
    "lesson": [
        "Better than yesterday. That's the bar.",
        "The standard doesn't move. You do.",
        "Receipts or it didn't happen.",
    ],
    "drill": [
        "The standard doesn't move. You do.",
        "Run it again tomorrow — better than today.",
    ],
    "debrief": [
        "Better than yesterday. That's the bar.",
        "We never let it get to us. We get to it first.",
    ],
    "newsletter": [
        "Now go build it — completely, and more.",
        "Better than yesterday. See you next issue.",
    ],
    "social": [
        "Receipts or it didn't happen.",
        "Better than yesterday. That's the bar.",
    ],
    "document": [
        "Now go build it — completely, and more.",
        "For we are many — and every one of us is better than yesterday.",
    ],
}

SPIRAL_PROMPTS = [
    "Run it back backwards — what breaks first?",
    "Four steps past the checkpoint: then what?",
    "Where does this fail? Name the boundary, then stay inside it.",
    "What's the inverse face of this — and what does it tell you?",
    "If you can't say it in your own words, you don't own it yet.",
    "Observe, then infer — and keep the two visibly separate.",
]

ENDPOINT_FRAMES = [
    "{x} + {y} = {z}. That's the endpoint — now the road.",
    "The verdict up front: {x} + {y} = {z}.",
    "Cut the noise: {x} + {y} = {z}. Everything after is proof.",
]

COIN_FRAMES = [
    "Two faces, one coin: {a} on one side, {b} on the other — each exists only against the other.",
    "Hold both faces or hold nothing: {a}, and its inverse, {b}.",
]

INTENSITY_LINES = [
    "No sugarcoating — half-truths disarm people.",
    "Done is a direction, not a state.",
    "Intensity with craft. Noise is for other people.",
    "We do what's needed completely — and more.",
]


# -- public API ------------------------------------------------------------


def voice_open(kind: str, seed: str) -> str:
    """A voiced opener line for the given kind. Deterministic."""
    bank = OPENERS.get(kind, OPENERS["document"])
    return _pick(bank, f"open:{kind}:{seed}")


def voice_close(kind: str, seed: str) -> str:
    """A voiced closer line for the given kind. Deterministic."""
    bank = CLOSERS.get(kind, CLOSERS["document"])
    return _pick(bank, f"close:{kind}:{seed}")


def spiral_prompt(seed: str) -> str:
    """One interrogation line — 'think every angle' in a sentence."""
    return _pick(SPIRAL_PROMPTS, f"spiral:{seed}")


def endpoint_line(x: str, y: str, z: str, seed: str = "") -> str:
    """Endpoint-first equation framing: x + y = z, then the road."""
    return _pick(ENDPOINT_FRAMES, f"endpoint:{seed}:{x}:{y}:{z}").format(
        x=x, y=y, z=z
    )


def coin_frame(a: str, b: str, seed: str = "") -> str:
    """Two-sided-coin framing for a concept and its inverse."""
    return _pick(COIN_FRAMES, f"coin:{seed}:{a}:{b}").format(a=a, b=b)


def intensity(seed: str) -> str:
    """A short intensity line — craft, never noise."""
    return _pick(INTENSITY_LINES, f"intensity:{seed}")


def apply_voice(text: str, kind: str, seed: str) -> str:
    """Wrap caller-supplied text with a voiced opener and closer.

    The body is never altered — the voice frames, never fabricates.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("apply_voice needs non-empty text")
    return f"{voice_open(kind, seed)}\n\n{text.strip()}\n\n_{voice_close(kind, seed)}_"
