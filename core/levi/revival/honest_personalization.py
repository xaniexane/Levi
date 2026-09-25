"""honest_personalization — taste models you can inspect, tune, and delete.

Studied from: giant-patterns-hunt-20260916-0016/report.md [S6].

Load-bearing idea: personalization runs on-device as an explicit feature
model — a plain map of feature -> weight. The user can inspect every weight,
tune any of them, remove any of them, or wipe the whole model. Every
recommendation can explain itself by naming the features that drove the
score. Nothing is a black box and nothing leaves the device.

LEVI's take: ``TasteProfile`` learns from explicit like/dislike observations
with a small, documented update rule (a clipped perceptron-style step —
a heuristic, labeled as such). ``score()`` is a dot product, ``explain()``
lists the top contributing features, ``tune()``/``remove()``/``wipe()``
give the user full control.

Honest limits: this is a linear heuristic over hand-supplied features, not
a learned deep model; it only knows the features the surrounding app feeds
it, and cold-start means an empty model scores everything at zero.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/honest-personalization"

#: Update rule, stated plainly: a clipped perceptron-style step (heuristic).
LEARNING_RATE = 0.1
WEIGHT_MIN = -1.0
WEIGHT_MAX = 1.0


@dataclass
class TasteProfile:
    """An on-device taste model: feature -> weight, fully inspectable."""

    weights: Dict[str, float] = field(default_factory=dict)
    observations: int = 0

    def observe(self, features: Dict[str, float], liked: bool) -> None:
        """Learn from one explicit like/dislike.

        Heuristic update: nudge each observed feature's weight toward +1 for
        likes and -1 for dislikes, clipped to [-1, 1]. Labeled a heuristic
        because that is what it is — a simple, legible rule, not intelligence.
        """
        direction = 1.0 if liked else -1.0
        for feature, strength in features.items():
            current = self.weights.get(feature, 0.0)
            stepped = current + LEARNING_RATE * direction * strength
            self.weights[feature] = max(WEIGHT_MIN, min(WEIGHT_MAX, stepped))
        self.observations += 1

    def score(self, features: Dict[str, float]) -> float:
        """Score an item: dot product of weights and features. Nothing hidden."""
        return sum(self.weights.get(f, 0.0) * s for f, s in features.items())

    def explain(
        self, features: Dict[str, float], top: int = 3
    ) -> List[Tuple[str, float]]:
        """Name the features that drove the score, biggest contribution first."""
        contributions = [
            (feature, self.weights.get(feature, 0.0) * strength)
            for feature, strength in features.items()
        ]
        contributions.sort(key=lambda pair: abs(pair[1]), reverse=True)
        return contributions[:top]

    def inspect(self) -> List[Tuple[str, float]]:
        """Every weight the model holds, strongest first. The whole model."""
        return sorted(self.weights.items(), key=lambda pair: abs(pair[1]), reverse=True)

    def tune(self, feature: str, weight: float) -> None:
        """Set a weight directly. The user's hand overrides the heuristic."""
        if not (WEIGHT_MIN <= weight <= WEIGHT_MAX):
            raise ValueError(f"weight must be within [{WEIGHT_MIN}, {WEIGHT_MAX}]")
        self.weights[feature] = weight

    def remove(self, feature: str) -> None:
        """Forget a feature entirely."""
        self.weights.pop(feature, None)

    def wipe(self) -> None:
        """Delete the whole model. Observations counter resets too."""
        self.weights.clear()
        self.observations = 0

    def recommend(
        self, candidates: Dict[str, Dict[str, float]], top: int = 5
    ) -> List[Tuple[str, float]]:
        """Rank candidates by score. Ties and ordering are fully reproducible."""
        ranked = [(name, self.score(feats)) for name, feats in candidates.items()]
        ranked.sort(key=lambda pair: (-pair[1], pair[0]))
        return ranked[:top]
