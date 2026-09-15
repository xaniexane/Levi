"""DemandPulse five-factor opportunity scoring — clean-room LEVI module.

Scores an *analyst-assessed* opportunity on five factors and combines them
into a deterministic composite. The five factors and their default weights
follow the DemandPulse blueprint's scoring model (Demand .30 / Market Size
.25 / Competition Gap .20 / Trend Velocity .15 / Entry Feasibility .10,
alert threshold 75); the implementation here is original LEVI work.

Honesty contract (this is what separates this module from the prototype it
was inspired by):
  - Every factor score MUST carry a ``basis`` — a short note saying *why*
    the analyst assigns that value. A score without a stated basis is
    rejected. Scores are judgments, never measurements.
  - The composite is deterministic: identical inputs always produce the
    identical card. No randomness, no hidden state.
  - ``explain()`` renders the full breakdown including each basis, so a
    composite can always be audited back to its inputs.
  - Nothing here invents market data. If a factor cannot be honestly
    assessed, leave the opportunity unscored.

stdlib-only. Advisory: a score describes an assessment; it executes
nothing and touches no money.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union
import math

# Canonical factor order — also the tie-break-safe iteration order.
FACTORS: Tuple[str, ...] = (
    "demand",
    "market_size",
    "competition_gap",
    "trend_velocity",
    "entry_feasibility",
)

# Blueprint default weights: 30/25/20/15/10. Must sum to 1.0.
DEFAULT_WEIGHTS: Dict[str, float] = {
    "demand": 0.30,
    "market_size": 0.25,
    "competition_gap": 0.20,
    "trend_velocity": 0.15,
    "entry_feasibility": 0.10,
}

DEFAULT_THRESHOLD = 75.0
TIER_HIGH = 75.0  # composite >= 75 -> "high"
TIER_WATCH = 50.0  # composite >= 50 -> "watch", else "low"

_WEIGHT_EPS = 1e-9


@dataclass(frozen=True)
class FactorScore:
    """One assessed factor: a 0-100 score plus the required basis note."""

    name: str
    value: float
    basis: str

    def __post_init__(self) -> None:
        if self.name not in FACTORS:
            raise ValueError(f"unknown factor {self.name!r}; expected one of {FACTORS}")
        if not isinstance(self.value, (int, float)) or isinstance(self.value, bool):
            raise ValueError(
                f"factor {self.name!r}: value must be numeric, got {self.value!r}"
            )
        if not 0.0 <= float(self.value) <= 100.0:
            raise ValueError(
                f"factor {self.name!r}: value {self.value} out of range 0-100"
            )
        if not str(self.basis).strip():
            raise ValueError(
                f"factor {self.name!r}: basis is required — "
                "a score without a stated reason is rejected"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "value": float(self.value), "basis": self.basis}


# Flexible factor input accepted by score_card(): name -> FactorScore,
# (value, basis) tuple, or {"value":.., "basis":..} mapping.
FactorInput = Union[FactorScore, Tuple[float, str], Mapping[str, Any]]


def validate_weights(weights: Optional[Mapping[str, float]]) -> Dict[str, float]:
    """Return a validated copy of ``weights`` (defaults when None).

    Raises ValueError when the weight set is not exactly the five factors,
    when any weight is outside [0, 1], or when they do not sum to 1.0.
    """
    if weights is None:
        w = dict(DEFAULT_WEIGHTS)
    elif not isinstance(weights, Mapping):
        raise ValueError(
            f"weights must be a mapping over {FACTORS}, got {type(weights).__name__}"
        )
    else:
        w = dict(weights)
    if set(w) != set(FACTORS):
        raise ValueError(f"weights must cover exactly {FACTORS}; got {sorted(w)}")
    for name, val in w.items():
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            raise ValueError(f"weight {name!r} must be numeric, got {val!r}")
        if not 0.0 <= float(val) <= 1.0:
            raise ValueError(f"weight {name!r}={val} outside [0, 1]")
    total = sum(float(v) for v in w.values())
    if abs(total - 1.0) > _WEIGHT_EPS:
        raise ValueError(f"weights must sum to 1.0, got {total:.6f}")
    return {k: float(v) for k, v in w.items()}


def _coerce_factor(name: str, raw: FactorInput) -> FactorScore:
    if isinstance(raw, FactorScore):
        if raw.name != name:
            raise ValueError(
                f"factor key {name!r} mismatches FactorScore.name {raw.name!r}"
            )
        return raw
    if isinstance(raw, Mapping):
        try:
            value = raw["value"]
            basis = raw["basis"]
        except KeyError as exc:
            raise ValueError(
                f"factor {name!r} mapping needs 'value' and 'basis' keys "
                f"(missing {exc})"
            ) from None
        return FactorScore(name=name, value=value, basis=basis)
    if isinstance(raw, (str, bytes)) or not isinstance(raw, (tuple, list)):
        raise ValueError(
            f"factor {name!r} must be a FactorScore, a (value, basis) pair, "
            f"or a {{'value':.., 'basis':..}} mapping; got {raw!r}"
        )
    try:
        value, basis = raw
    except ValueError as exc:
        raise ValueError(
            f"factor {name!r} pair must be exactly (value, basis); got {raw!r}"
        ) from exc
    return FactorScore(name=name, value=value, basis=basis)


def validate_factors(factors: Mapping[str, FactorInput]) -> List[FactorScore]:
    """Return the five factors in canonical order, validated.

    Raises ValueError on missing/extra factors; FactorScore raises on
    out-of-range values or empty basis.
    """
    if not isinstance(factors, Mapping):
        raise ValueError(
            f"factors must be a mapping over {FACTORS}, got {type(factors).__name__}"
        )
    if set(factors) != set(FACTORS):
        missing = [f for f in FACTORS if f not in factors]
        extra = [k for k in factors if k not in FACTORS]
        raise ValueError(
            f"factors must be exactly {FACTORS}; missing={missing} extra={extra}"
        )
    return [_coerce_factor(name, factors[name]) for name in FACTORS]


def composite_score(factors: List[FactorScore], weights: Mapping[str, float]) -> float:
    """Deterministic weighted mean of factor values, rounded to 2 dp."""
    if not isinstance(factors, (list, tuple)) or not all(
        isinstance(f, FactorScore) for f in factors
    ):
        raise ValueError("factors must be a list of FactorScore")
    names = [f.name for f in factors]
    if len(names) != len(FACTORS) or set(names) != set(FACTORS):
        raise ValueError(f"factors must cover exactly {FACTORS}; got {sorted(names)}")
    weights = validate_weights(weights)
    total = sum(f.value * weights[f.name] for f in factors)
    return round(total, 2)


def tier_for(composite: float) -> str:
    """high >= 75, watch >= 50, else low."""
    if (
        isinstance(composite, bool)
        or not isinstance(composite, (int, float))
        or not math.isfinite(composite)
    ):
        raise ValueError(f"composite must be a finite number, got {composite!r}")
    if composite >= TIER_HIGH:
        return "high"
    if composite >= TIER_WATCH:
        return "watch"
    return "low"


@dataclass
class ScoreCard:
    """The auditable result of scoring one opportunity."""

    opportunity_id: str
    title: str
    factors: List[FactorScore]
    weights: Dict[str, float]
    threshold: float = DEFAULT_THRESHOLD
    notes: str = ""
    scored_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    composite: float = field(init=False)
    tier: str = field(init=False)
    alert: bool = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.opportunity_id, str) or not self.opportunity_id.strip():
            raise ValueError(
                f"opportunity_id must be a non-empty string, got {self.opportunity_id!r}"
            )
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title must be a non-empty string")
        if not isinstance(self.notes, str):
            raise ValueError(f"notes must be a string, got {type(self.notes).__name__}")
        weights = validate_weights(self.weights)
        object.__setattr__(self, "weights", weights)
        factors = validate_factors({f.name: f for f in self.factors})
        object.__setattr__(self, "factors", factors)
        if not isinstance(self.threshold, (int, float)) or isinstance(
            self.threshold, bool
        ):
            raise ValueError("threshold must be numeric")
        if not 0.0 <= float(self.threshold) <= 100.0:
            raise ValueError("threshold must be within 0-100")
        comp = composite_score(factors, weights)
        object.__setattr__(self, "composite", comp)
        object.__setattr__(self, "tier", tier_for(comp))
        object.__setattr__(self, "alert", comp >= float(self.threshold))

    def explain(self) -> str:
        """Human-readable audit trail: every input, weight, and basis."""
        lines = [
            f"[{self.opportunity_id}] {self.title}",
            f"composite={self.composite:.2f}  tier={self.tier}  "
            f"threshold={float(self.threshold):.0f}  alert={'YES' if self.alert else 'no'}",
            "",
        ]
        for f in self.factors:
            w = self.weights[f.name]
            contrib = f.value * w
            lines.append(
                f"  {f.name:16s} value={f.value:6.1f}  weight={w:.2f}  "
                f"contrib={contrib:6.2f}"
            )
            lines.append(f"    basis: {f.basis}")
        if self.notes:
            lines.append("")
            lines.append(f"notes: {self.notes}")
        lines.append("")
        lines.append(
            "Scores are analyst judgments with stated bases — not measured data."
        )
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["factors"] = [f.to_dict() for f in self.factors]
        return d

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ScoreCard":
        data = dict(raw)
        data["factors"] = [FactorScore(**f) for f in data["factors"]]
        data.pop("composite", None)
        data.pop("tier", None)
        data.pop("alert", None)
        return cls(**data)  # type: ignore[arg-type]


def score_card(
    opportunity_id: str,
    title: str,
    factors: Mapping[str, FactorInput],
    weights: Optional[Mapping[str, float]] = None,
    threshold: float = DEFAULT_THRESHOLD,
    notes: str = "",
) -> ScoreCard:
    """Score one opportunity; pure and deterministic."""
    return ScoreCard(
        opportunity_id=opportunity_id,
        title=title,
        factors=validate_factors(factors),
        weights=validate_weights(weights),
        threshold=threshold,
        notes=notes,
    )


def rank_cards(cards: List[ScoreCard]) -> List[ScoreCard]:
    """Rank highest composite first; ties break by opportunity_id (deterministic)."""
    if not isinstance(cards, (list, tuple)) or not all(
        isinstance(c, ScoreCard) for c in cards
    ):
        raise ValueError("cards must be a list of ScoreCard")
    return sorted(cards, key=lambda c: (-c.composite, c.opportunity_id))


def parse_weights(spec: str) -> Dict[str, float]:
    """Parse a CLI weight spec like ``"0.3,0.25,0.2,0.15,0.1"`` in factor order."""
    if not isinstance(spec, str):
        raise ValueError(
            f"weight spec must be a string like '0.3,0.25,0.2,0.15,0.1', "
            f"got {type(spec).__name__}"
        )
    parts = [p.strip() for p in spec.split(",")]
    if len(parts) != len(FACTORS):
        raise ValueError(
            f"weight spec needs {len(FACTORS)} comma-separated values in order "
            f"{FACTORS}; got {spec!r}"
        )
    try:
        values = [float(p) for p in parts]
    except ValueError:
        raise ValueError(f"weight spec has non-numeric values: {spec!r}")
    return validate_weights(dict(zip(FACTORS, values)))
