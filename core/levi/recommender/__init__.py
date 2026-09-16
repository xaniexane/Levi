"""Goal-directed recommender — interest-graph math, no engagement mining.

REMIX DELTA: TikTok/YouTube/Spotify maximize time-on-device; opacity is
load-bearing — if you could see the weights you could see the
manipulation. LEVI inverts it: recommendations are pure, inspectable
math over a local item corpus. The inputs are *user-stated goals*
("learn X", "catch up on Y") plus explicit ratings — never inferred
engagement, watch time, or scroll behavior. The weight vector is visible
and tunable, every recommendation ships its signal contributions, and
diversity/serendipity is a knob (MMR), not a growth hack. No network,
no profile, no ads auction.

Layout:
    model.py    Item / Goal schema + validation
    weights.py  visible weight vector (show/set, validated, normalized)
    engine.py   signal math, scoring, explanations, MMR diversity
    store.py    call-time home paths, JSON persistence
"""

from __future__ import annotations

from levi.recommender.engine import (
    Rec,
    content_fit,
    goal_alignment,
    quality_score,
    recency_score,
    recommend,
)
from levi.recommender.model import Goal, Item, new_id, parse_topics
from levi.recommender.weights import (
    DEFAULT_WEIGHTS,
    SIGNALS,
    normalize_weights,
    parse_weights,
)

__all__ = [
    "Rec",
    "Goal",
    "Item",
    "content_fit",
    "goal_alignment",
    "quality_score",
    "recency_score",
    "recommend",
    "new_id",
    "parse_topics",
    "DEFAULT_WEIGHTS",
    "SIGNALS",
    "normalize_weights",
    "parse_weights",
    "SHELF",
]

# Warehouse atlas entry (wired later by the interop/warehouses crew).
SHELF = {
    "name": "recommender",
    "summary": (
        "Goal-directed recommender with visible math: user-stated goals "
        "and explicit ratings drive scoring (goal/content/quality/recency "
        "signals under a tunable weight vector); every recommendation is "
        "explained with per-signal contributions; MMR diversity control. "
        "No engagement mining, no network."
    ),
    "items": [
        "model: Item/Goal schema — topics as explicit weight maps",
        "weights: visible tunable signal weights (validated, normalized)",
        "engine: cosine goal alignment, liked-centroid content fit, "
        "explicit-rating quality, recency decay, MMR diversity, explanations",
        "cli: python -m levi.recommender add-item|add-goal|rate|recommend|"
        "weights|list|export",
    ],
}
