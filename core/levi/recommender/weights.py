"""Visible weight vector for the recommender's signals."""

from __future__ import annotations

import math
from typing import Dict

SIGNALS = ("goal", "content", "quality", "recency")

# Defaults are a starting position, not a secret: the user can see and
# change every one of them. Goals lead; explicit taste follows; declared
# quality and freshness trail.
DEFAULT_WEIGHTS = {
    "goal": 0.45,
    "content": 0.25,
    "quality": 0.20,
    "recency": 0.10,
}


def normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
    """Validate (all signals present, finite, non-negative) and sum to 1."""
    cleaned = {}
    for name in SIGNALS:
        if name not in weights:
            raise ValueError("weight vector missing signal %r" % name)
        value = float(weights[name])
        if not math.isfinite(value) or value < 0:
            raise ValueError("weight %r must be a finite non-negative number" % name)
        cleaned[name] = value
    total = sum(cleaned.values())
    if total <= 0:
        raise ValueError("at least one weight must be positive")
    return {k: v / total for k, v in cleaned.items()}


def parse_weights(spec: str) -> Dict[str, float]:
    """Parse ``"goal=0.5,content=0.3,quality=0.2,recency=0"``."""
    parts = {}
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            raise ValueError("bad weight spec %r" % chunk)
        key, _, value = chunk.partition("=")
        key = key.strip()
        if key not in SIGNALS:
            raise ValueError("unknown signal %r (want: %s)" % (key, ", ".join(SIGNALS)))
        try:
            parts[key] = float(value)
        except ValueError:
            raise ValueError("bad weight value %r" % value) from None
    return normalize_weights(parts)
