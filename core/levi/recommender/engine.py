"""Signal math, scoring, explanations, and MMR diversity.

THE MATH (the whole model, nothing hidden):

    cosine(a, b) = dot(a,b) / (|a| * |b|)      over topic-weight maps

Signals for item i (each in [0, 1]):

    goal(i)    = max over active goals of cosine(i.topics, goal.topics)
                 (kind_filter on a goal excludes non-matching kinds first)
    content(i) = cosine(i.topics, liked_centroid) where liked_centroid is
                 the mean topic vector of items the user rated >= 4.
                 Zero — honestly reported — until the user rates something.
    quality(i) = mean(explicit ratings for i) / 5. Zero until rated.
    recency(i) = 0.5 ** (age_days / half_life_days), half-life 90d default.

    total(i)   = SUM_s  w_s * signal_s(i)

Diversity (MMR — maximal marginal relevance). After scoring, items are
picked greedily:

    pick = argmax  λ * total(i) − (1−λ) * max_{picked p} cosine(i, p)

λ = 1 → pure relevance order. Lower λ trades relevance for topical
spread (serendipity). λ is a CLI flag, not a secret.

HONESTY RULES baked into the math:
- No engagement signals exist. Watch time, clicks, scrolls, dwell —
  none of them are inputs, so none of them can steer you.
- content_fit and quality are zero until YOU rate things, and the
  explanation says so instead of silently substituting a prior.
- Goals are user-stated. There is no inferred-interest vector.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Set, Tuple

from levi.recommender.model import Goal, Item
from levi.recommender.weights import DEFAULT_WEIGHTS, SIGNALS, normalize_weights

LIKE_THRESHOLD = 4.0
DEFAULT_HALF_LIFE_DAYS = 90.0


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Cosine similarity over topic-weight maps. Empty -> 0.0."""
    if not a or not b:
        return 0.0
    dot = sum(a.get(t, 0.0) * w for t, w in b.items())
    na = math.sqrt(sum(w * w for w in a.values()))
    nb = math.sqrt(sum(w * w for w in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _age_days(item: Item, now: datetime) -> float:
    try:
        added = datetime.fromisoformat(item.added_at)
    except ValueError:
        return 0.0
    if added.tzinfo is None:
        added = added.replace(tzinfo=timezone.utc)
    return max(0.0, (now - added).total_seconds() / 86400.0)


def goal_alignment(item: Item, goals: Sequence[Goal]) -> Tuple[float, str]:
    """Max cosine to any active goal (kind_filter applied)."""
    best, which = 0.0, ""
    for goal in goals:
        if goal.kind_filter and item.kind.lower() not in goal.kind_filter:
            continue
        score = cosine(item.topics, goal.topics)
        if score > best:
            best, which = score, goal.id
    return best, which


def content_fit(item: Item, liked_centroid: Dict[str, float]) -> float:
    return cosine(item.topics, liked_centroid)


def quality_score(item: Item, ratings: Dict[str, List[float]]) -> float:
    vals = ratings.get(item.id, [])
    if not vals:
        return 0.0
    return (sum(vals) / len(vals)) / 5.0


def recency_score(
    item: Item, now: datetime, half_life_days: float = DEFAULT_HALF_LIFE_DAYS
) -> float:
    if half_life_days <= 0:
        raise ValueError("half-life must be positive")
    return 0.5 ** (_age_days(item, now) / half_life_days)


def liked_centroid(
    items: Sequence[Item], ratings: Dict[str, List[float]]
) -> Dict[str, float]:
    """Mean topic vector of items rated >= LIKE_THRESHOLD (explicit only)."""
    liked = [
        it
        for it in items
        if ratings.get(it.id)
        and sum(ratings[it.id]) / len(ratings[it.id]) >= LIKE_THRESHOLD
    ]
    if not liked:
        return {}
    centroid: Dict[str, float] = {}
    for it in liked:
        for topic, w in it.topics.items():
            centroid[topic] = centroid.get(topic, 0.0) + w
    n = len(liked)
    return {t: w / n for t, w in centroid.items()}


@dataclass
class Rec:
    item: Item
    total: float
    contributions: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    best_goal: str = ""


def score_item(
    item: Item,
    goals: Sequence[Goal],
    centroid: Dict[str, float],
    ratings: Dict[str, List[float]],
    weights: Dict[str, float],
    now: datetime,
    half_life_days: float,
) -> Rec:
    w = normalize_weights(dict(weights))
    notes: List[str] = []
    g, best_goal = goal_alignment(item, goals)
    if not goals:
        notes.append(
            "no active goals — goal signal is 0; add a goal to steer recommendations"
        )
    c = content_fit(item, centroid)
    if not centroid:
        notes.append(
            "no liked items yet — content signal is 0; rate items 4+ to enable it"
        )
    q = quality_score(item, ratings)
    if not ratings.get(item.id):
        notes.append("unrated — quality signal is 0; your rating sets it")
    r = recency_score(item, now, half_life_days)
    signals = {"goal": g, "content": c, "quality": q, "recency": r}
    contributions = {s: w[s] * signals[s] for s in SIGNALS}
    return Rec(
        item=item,
        total=sum(contributions.values()),
        contributions=contributions,
        notes=notes,
        best_goal=best_goal,
    )


def mmr_order(scored: List[Rec], lambda_: float) -> List[Rec]:
    """Maximal-marginal-relevance greedy ordering by topic cosine."""
    if not 0.0 <= lambda_ <= 1.0:
        raise ValueError("diversity lambda must be in [0, 1]")
    remaining = list(scored)
    picked: List[Rec] = []
    while remaining:

        def mmr_score(rec: Rec) -> float:
            if not picked or lambda_ == 1.0:
                return lambda_ * rec.total
            redundancy = max(cosine(rec.item.topics, p.item.topics) for p in picked)
            return lambda_ * rec.total - (1 - lambda_) * redundancy

        # Deterministic tie-break on item id.
        remaining.sort(key=lambda r: (-mmr_score(r), r.item.id))
        picked.append(remaining.pop(0))
    return picked


def recommend(
    items: Sequence[Item],
    goals: Sequence[Goal],
    ratings: Dict[str, List[float]],
    weights: Dict[str, float] | None = None,
    active_goal_ids: Optional[Set[str]] = None,
    exclude_ids: Sequence[str] = (),
    top_k: int = 10,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    mmr_lambda: float = 1.0,
    now: Optional[datetime] = None,
) -> List[Rec]:
    """Score, diversify, and return the top_k recommendations."""
    w = normalize_weights(dict(weights) if weights else DEFAULT_WEIGHTS)
    now = now or datetime.now(timezone.utc)
    if active_goal_ids is not None:
        goals = [g for g in goals if g.id in active_goal_ids]
    excluded = set(exclude_ids)
    centroid = liked_centroid(items, ratings)
    scored = [
        score_item(it, goals, centroid, ratings, w, now, half_life_days)
        for it in items
        if it.id not in excluded
    ]
    ordered = mmr_order(scored, mmr_lambda)
    return ordered[: max(1, top_k)]


def explain(rec: Rec, weights: Dict[str, float]) -> str:
    """Human-readable account of which signals produced this recommendation."""
    w = normalize_weights(dict(weights))
    lines = [
        "%s  [%s]  (total %.4f)" % (rec.item.title, rec.item.kind, rec.total),
        "  id: %s   topics: %s"
        % (rec.item.id, ", ".join("%s:%.2f" % kv for kv in rec.item.topics.items())),
    ]
    if rec.best_goal:
        lines.append("  best goal match: %s" % rec.best_goal)
    for signal in SIGNALS:
        raw = rec.contributions[signal] / w[signal] if w[signal] else 0.0
        lines.append(
            "  %-7s weight %.2f  signal %.4f  contribution %.4f"
            % (signal, w[signal], raw, rec.contributions[signal])
        )
    for note in rec.notes:
        lines.append("  note: %s" % note)
    return "\n".join(lines)
