"""Variation transforms — "variated many ways".

Pure functions: each takes a seed text and returns a transformed variant.
Rule-based and offline; no model calls. The engine scores each variant and
marks failures for compost.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List

_WORD = re.compile(r"[a-z0-9]+")


def _words(text: str) -> List[str]:
    return _WORD.findall(text.lower())


def invert(text: str) -> str:
    """Flip the polarity: what if the goal were the opposite?"""
    return (
        f"Inverted: instead of pursuing '{text}', pursue its opposite — "
        "refuse the obvious win and optimize for what the original avoids."
    )


def amplify(text: str) -> str:
    """Scale the seed up 10x: what breaks, what compounds?"""
    return (
        f"Amplified 10x: '{text}' at ten times the scale — "
        "name what breaks first and what compounds fastest."
    )


def transplant(text: str) -> str:
    """Move the seed into an unrelated domain."""
    domains = ["a kitchen", "a tide pool", "a night market", "a relay race", "a garden"]
    # deterministic pick from seed hash so dreams are reproducible
    pick = domains[sum(map(ord, text)) % len(domains)]
    return f"Transplanted into {pick}: '{text}' re-expressed there — keep the structure, change the soil."


def negate_constraint(text: str) -> str:
    """Remove the main constraint: what becomes possible?"""
    return (
        f"Constraint removed: '{text}' with the hardest limit lifted — "
        "describe what becomes possible that was unthinkable before."
    )


def compress(text: str) -> str:
    """Distill the seed to its load-bearing sentence."""
    words = _words(text)
    core = " ".join(words[:12]) if words else text[:60]
    return f"Compressed to its spine: '{core}' — everything else was scaffolding."


VARIATIONS: Dict[str, Callable[[str], str]] = {
    "invert": invert,
    "amplify": amplify,
    "transplant": transplant,
    "negate_constraint": negate_constraint,
    "compress": compress,
}


def variate(text: str, kinds: List[str] | None = None) -> List[Dict[str, str]]:
    """Apply each variation transform; returns [{kind, text}]."""
    kinds = kinds or list(VARIATIONS)
    out = []
    for kind in kinds:
        fn = VARIATIONS.get(kind)
        if fn is None:
            continue
        try:
            out.append({"kind": kind, "text": fn(text)})
        except Exception:
            continue
    return out
