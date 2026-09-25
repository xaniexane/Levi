"""Goal-directed recommender: visible weights, stated goals, no engagement trap.

Studied from: giant-patterns-hunt-20260916-0016/report.md [Additions 13]
(interest-graph math with visible weights and user-stated goals instead of
engagement maximization).

This is an original, from-scratch implementation for LEVI. The recommender
optimizes for what the user *said they want*, never for predicted
engagement. The user declares ``Goal`` objects — a name plus explicit
weights over item attributes (e.g. ``{"calm": 0.8, "short": 0.5}``) —
and scores each catalog item as the weight-normalized dot product of goal
weights and item attributes, blended across goals by per-goal priority.
Every recommendation ships with ``explain``: the per-goal contribution and
the per-attribute contribution, so the user can see exactly why an item
surfaced. There is no click model, no dwell-time tracking, no engagement
score anywhere in the math — those signals simply do not exist here.

Feedback is explicit too: ``feedback(item_id, liked)`` nudges attribute
weights toward (or away from) the item's attributes with a bounded learning
rate, and the full weight history is inspectable via ``weight_history``.
The user can always pin, freeze, or reset weights back to their stated
values with ``reset_weights``.

Public surface:
- ``GoalRecommender``: ``add_item``, ``set_goal`` / ``goals``,
  ``recommend``, ``explain``, ``feedback``, ``weight_history``,
  ``reset_weights``.
- ``Goal``, ``Item``, ``Recommendation``, ``RecommenderError``.

Honest limits: dot-product scoring assumes attributes are independent and
linearly combinable — real preferences are messier. Feedback nudging is a
simple exponential move, not a model of the user.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Tuple

ORIGIN = "levi-revival/goal-recommender"


class RecommenderError(ValueError):
    """Raised for invalid recommender operations."""


@dataclass
class Goal:
    """A user-stated goal: name, attribute weights, priority."""

    name: str
    weights: Dict[str, float]
    priority: float = 1.0

    def __post_init__(self) -> None:
        if not self.name:
            raise RecommenderError("goal needs a name")
        if self.priority <= 0:
            raise RecommenderError("goal priority must be positive")
        for attr, weight in self.weights.items():
            if weight < 0:
                raise RecommenderError(f"weight for {attr!r} must be >= 0")


@dataclass
class Item:
    """One recommendable item: id, label, attribute scores 0..1."""

    item_id: str
    label: str
    attributes: Dict[str, float]

    def __post_init__(self) -> None:
        for attr, value in self.attributes.items():
            if not 0.0 <= value <= 1.0:
                raise RecommenderError(f"attribute {attr!r} must be in 0..1")


@dataclass
class Recommendation:
    item_id: str
    label: str
    score: float
    breakdown: Dict[str, float]  # goal name -> contribution


class GoalRecommender:
    """Recommendations from stated goals, with every weight visible."""

    def __init__(self, learning_rate: float = 0.1) -> None:
        if not 0.0 < learning_rate <= 1.0:
            raise RecommenderError("learning rate must be in (0, 1]")
        self.learning_rate = learning_rate
        self._items: Dict[str, Item] = {}
        self._goals: Dict[str, Goal] = {}
        self._history: List[Tuple[str, str, Dict[str, float]]] = []
        # (goal name, event, weight snapshot)

    # -- catalog + goals --------------------------------------------------
    def add_item(self, item: Item) -> None:
        if item.item_id in self._items:
            raise RecommenderError(f"duplicate item {item.item_id!r}")
        self._items[item.item_id] = item

    def set_goal(self, goal: Goal) -> None:
        self._goals[goal.name] = goal
        self._history.append((goal.name, "set", dict(goal.weights)))

    def goals(self) -> List[Goal]:
        return list(self._goals.values())

    def weight_history(self) -> List[Tuple[str, str, Dict[str, float]]]:
        return list(self._history)

    # -- scoring ----------------------------------------------------------
    @staticmethod
    def _goal_score(goal: Goal, item: Item) -> Tuple[float, Dict[str, float]]:
        """(normalized weighted score, per-attribute contributions)."""
        total_weight = sum(goal.weights.values())
        if total_weight == 0:
            return 0.0, {}
        contributions: Dict[str, float] = {}
        score = 0.0
        for attr, weight in goal.weights.items():
            value = item.attributes.get(attr, 0.0)
            contrib = (weight / total_weight) * value
            contributions[attr] = round(contrib, 4)
            score += contrib
        return round(score, 4), contributions

    def item_score(self, goal_name: str, item_id: str) -> float:
        goal = self._goal(goal_name)
        item = self._item(item_id)
        return self._goal_score(goal, item)[0]

    def explain(self, item_id: str) -> Dict[str, object]:
        """Why this item: per-goal contribution + per-attribute detail."""
        item = self._item(item_id)
        per_goal: Dict[str, float] = {}
        detail: Dict[str, Dict[str, float]] = {}
        total = 0.0
        for goal in self._goals.values():
            score, contributions = self._goal_score(goal, item)
            weighted = round(score * goal.priority, 4)
            per_goal[goal.name] = weighted
            detail[goal.name] = contributions
            total += weighted
        return {
            "item_id": item_id,
            "label": item.label,
            "total": round(total, 4),
            "per_goal": per_goal,
            "per_attribute": detail,
        }

    def recommend(self, limit: int = 5) -> List[Recommendation]:
        """Top items by goal alignment. No engagement signal exists."""
        if not self._goals:
            raise RecommenderError("no goals set — state what you want first")
        scored: List[Recommendation] = []
        for item in self._items.values():
            explanation = self.explain(item.item_id)
            scored.append(
                Recommendation(
                    item_id=item.item_id,
                    label=item.label,
                    score=explanation["total"],  # type: ignore[arg-type]
                    breakdown=explanation["per_goal"],  # type: ignore[arg-type]
                )
            )
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:limit]

    # -- explicit feedback -------------------------------------------------
    def feedback(self, goal_name: str, item_id: str, liked: bool) -> Goal:
        """Nudge a goal's weights toward (or away from) an item's attributes.

        Explicit only: the user decides what counts as a signal. The move is
        bounded by the learning rate and every step is logged to the weight
        history.
        """
        goal = self._goal(goal_name)
        item = self._item(item_id)
        new_weights: Dict[str, float] = {}
        for attr in set(goal.weights) | set(item.attributes):
            current = goal.weights.get(attr, 0.0)
            target = item.attributes.get(attr, 0.0)
            if liked:
                moved = current + self.learning_rate * (target - current)
            else:
                moved = current - self.learning_rate * target
            new_weights[attr] = round(max(moved, 0.0), 4)
        goal.weights.clear()
        goal.weights.update(new_weights)
        self._history.append(
            (goal_name, "liked" if liked else "disliked", dict(new_weights))
        )
        return goal

    def reset_weights(self, goal_name: str, weights: Mapping[str, float]) -> Goal:
        """Restore user-stated weights verbatim."""
        goal = self._goal(goal_name)
        for attr, weight in weights.items():
            if weight < 0:
                raise RecommenderError(f"weight for {attr!r} must be >= 0")
        goal.weights.clear()
        goal.weights.update(dict(weights))
        self._history.append((goal_name, "reset", dict(goal.weights)))
        return goal

    # -- helpers ----------------------------------------------------------
    def _goal(self, goal_name: str) -> Goal:
        try:
            return self._goals[goal_name]
        except KeyError as exc:
            raise RecommenderError(f"no goal {goal_name!r}") from exc

    def _item(self, item_id: str) -> Item:
        try:
            return self._items[item_id]
        except KeyError as exc:
            raise RecommenderError(f"no item {item_id!r}") from exc
