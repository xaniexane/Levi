"""oracle: strategy; long-term goal weighting (LEVI-native).

Canon role (ORGANISM_FORMS): "strategy; long-term goal weighting".

Canon evidence (founder corpus: copilot-sweep/ser13-18-21-master-conversation.md):
  - "Oracle (Strategy) — long-term goal weighting (oracle_strategy.py)."
  - SER-21 (World Model): "Oracle weights objectives."
  - Hierarchy: Oracle sits in the Intelligence Layer with Echo, Alpha, ELI,
    HyperCube, OmniPulse, DemandPulse.

This is a LEVI-native recreation with LEVI's own twist — never a copy of
the original code. Oracle scores goals against a stated strategy (named
criteria with weights) using plain weighted arithmetic:

  - :class:`Strategy`: named criteria, each with a non-negative weight.
    Fail-closed: negative weights, empty criteria, or duplicate criterion
    names are rejected (ValueError).
  - :func:`weight_goals`: every goal rates itself 0..1 per criterion
    (``ratings``); Oracle computes the weighted sum. Goals with unknown
    criteria or out-of-range ratings are rejected as data with a reason —
    never silently dropped, never silently renormalized without a note.
  - Dry-run purity: ``weight_goals(..., dry_run=True)`` validates
    everything and returns the would-be ranking without committing any
    ranking into the returned strategy state.
  - Hostile input as data: rating blobs that are not mappings, or goals
    that are not mappings, are reported in the receipt, not executed.

HONESTY LAW (this is the whole point of the module): Oracle weights
declared strategy — stated founder preferences — against self-reported
ratings. Its scores are arithmetic, not predictions. A high score means
"this goal aligns with the stated strategy," never "this goal will
succeed." Forecasts belong to forecasting methods (see levi.methods);
Oracle does strategy arithmetic only.

Ready-for-review by the keeper. Never claims his review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence

FORM_NAME = "oracle"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _receipt(
    status: str, reason: str, *, dry_run: bool = False, **extra: Any
) -> Dict[str, Any]:
    receipt = {
        "form": FORM_NAME,
        "status": status,
        "reason": reason,
        "dry_run": dry_run,
        "at": _utcnow(),
    }
    receipt.update(extra)
    return receipt


@dataclass(frozen=True)
class Criterion:
    name: str
    weight: float
    description: str = ""


@dataclass
class Strategy:
    """A named weighting strategy: criteria + weights, committed ranking."""

    name: str
    criteria: List[Criterion] = field(default_factory=list)
    last_ranking: Optional[List[Dict[str, Any]]] = None

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise ValueError("strategy name must be a non-empty string")
        if not self.criteria:
            raise ValueError("strategy needs at least one criterion")
        names = [c.name for c in self.criteria]
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate criterion names: {names}")
        for c in self.criteria:
            if not isinstance(c.name, str) or not c.name.strip():
                raise ValueError("criterion names must be non-empty strings")
            if (
                not isinstance(c.weight, (int, float))
                or isinstance(c.weight, bool)
                or c.weight < 0
            ):
                raise ValueError(
                    f"criterion {c.name!r}: weight must be a non-negative "
                    f"number, got {c.weight!r}"
                )
        if all(c.weight == 0 for c in self.criteria):
            raise ValueError("strategy weights are all zero: nothing to weight by")

    @property
    def total_weight(self) -> float:
        return float(sum(c.weight for c in self.criteria))

    def score(self, ratings: Mapping[str, Any]) -> float:
        """Weighted score of one goal's criterion ratings (0..1 each)."""
        total = 0.0
        for c in self.criteria:
            if c.name not in ratings:
                raise ValueError(f"goal missing rating for criterion {c.name!r}")
            r = ratings[c.name]
            if (
                not isinstance(r, (int, float))
                or isinstance(r, bool)
                or not 0.0 <= r <= 1.0
            ):
                raise ValueError(
                    f"criterion {c.name!r}: rating must be a number in "
                    f"[0, 1], got {r!r}"
                )
            total += c.weight * float(r)
        return round(total / self.total_weight, 4)


def weight_goals(
    strategy: Strategy,
    goals: Sequence[Any],
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Rank goals against the strategy. Validates fail-closed; dry-run pure.

    ``goals``: sequence of mappings with ``id``, ``name``, ``ratings``
    (criterion -> 0..1). Non-mapping goals and goals with unknown criteria
    are rejected as DATA in the receipt — never executed, never silently
    dropped.
    """
    if not isinstance(goals, Sequence) or isinstance(goals, (str, bytes)):
        return _receipt(
            "rejected",
            f"goals must be a sequence of mappings, got {type(goals).__name__}",
            dry_run=dry_run,
        )
    known = {c.name for c in strategy.criteria}
    ranked: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    for i, g in enumerate(goals):
        if not isinstance(g, Mapping):
            rejected.append(
                {
                    "index": i,
                    "reason": f"not a mapping ({type(g).__name__}): data, not a goal",
                }
            )
            continue
        ratings = g.get("ratings")
        if not isinstance(ratings, Mapping):
            rejected.append(
                {"index": i, "goal": g.get("id"), "reason": "ratings must be a mapping"}
            )
            continue
        unknown = [k for k in ratings if k not in known]
        if unknown:
            rejected.append(
                {
                    "index": i,
                    "goal": g.get("id"),
                    "reason": f"unknown criteria {unknown}: data, not scored",
                }
            )
            continue
        try:
            score = strategy.score(ratings)
        except ValueError as exc:
            rejected.append({"index": i, "goal": g.get("id"), "reason": str(exc)})
            continue
        ranked.append(
            {
                "id": g.get("id"),
                "name": g.get("name"),
                "score": score,
                "ratings": dict(ratings),
            }
        )
    ranked.sort(key=lambda r: (-r["score"], str(r["id"])))
    if dry_run:
        return _receipt(
            "dry-run",
            f"validated {len(ranked)} goals, rejected {len(rejected)}; "
            "no ranking committed to the strategy",
            dry_run=True,
            strategy=strategy.name,
            ranking=ranked,
            rejected=rejected,
        )
    strategy.last_ranking = [dict(r) for r in ranked]
    return _receipt(
        "ranked",
        f"{len(ranked)} goals ranked against strategy '{strategy.name}'; "
        f"{len(rejected)} rejected as data",
        strategy=strategy.name,
        ranking=ranked,
        rejected=rejected,
        honest_note=(
            "scores are strategy-alignment arithmetic on stated ratings, "
            "not predictions of success"
        ),
    )
