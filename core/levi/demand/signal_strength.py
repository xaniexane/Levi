"""DemandPulse signal strength — the enriched opportunity-signal layer.

Chauncey's verdict: the opportunity signals felt "weak and less detailed
than originally." This module is the fix, on three axes:

  (a) MORE DIMENSIONS — six assessed strength dimensions alongside the
      five blueprint factors in ``levi.demand.scoring`` (timing window,
      monetization path, defensibility, resource fit, evidence strength,
      action clarity). The blueprint five stay exactly as they are;
      these six are the depth the cards were missing.
  (b) DETAILED EXPLANATIONS — every dimension carries a required basis,
      observed evidence pointers, a required confidence (honest
      uncertainty, never hidden), and a sensitivity note ("what would
      change this value"). ``explain()`` renders the full depth.
  (c) ACTIONABLE DETAIL — recommended actions (ranked, with rationale
      and effort), watch conditions (what to monitor, what each would
      change), a plain-language summary for users, and an upgrade
      directive: the scored, ranked advisory DemandPulse now issues as
      the UPGRADE ADVISOR for the builder sequence.

INVARIANTS (law-guard-prove — enforced by
tests/test_demand_signal_strength.py):
  L1. No naked scores: every dimension value requires a basis, a
      confidence in [0, 1], and a sensitivity note. Missing any of the
      three is rejected.
  L2. Deterministic: identical inputs produce the identical card and
      identical advisory. No randomness, no hidden state, no clock reads
      inside scoring paths (``as_of`` is caller-supplied record data,
      never an input to the math).
  L3. Real signals only: evidence lists carry caller-supplied observed
      strings. The module never invents evidence, and low confidence is
      surfaced and flagged — never smoothed over.
  L4. Risks are surfaced, never silently subtracted: risks ride
      alongside the composite as explicit flags; the math never hides a
      penalty inside a score.
  L5. Advisory honesty: the combined score shows its exact weighting
      (including the reweight when direction fit is absent), and every
      verdict carries its math string.
  L6. No network, stdlib only, pure functions. Advisory: a signal
      describes an assessment; it executes nothing and moves no money.

Schema version is pinned in SCHEMA_VERSION and rides on every
serialized card — the stability the user/business signal packs will
build on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from levi.demand import scoring
from levi.demand.direction import verdict as direction_verdict

SCHEMA_VERSION = "1"

# Canonical dimension order — also the tie-break-safe iteration order.
DIMENSIONS: Tuple[str, ...] = (
    "timing_window",
    "monetization_path",
    "defensibility",
    "resource_fit",
    "evidence_strength",
    "action_clarity",
)

# Dimension weights. Must sum to 1.0.
DEFAULT_DIMENSION_WEIGHTS: Dict[str, float] = {
    "timing_window": 0.20,
    "monetization_path": 0.20,
    "defensibility": 0.15,
    "resource_fit": 0.15,
    "evidence_strength": 0.15,
    "action_clarity": 0.15,
}

# Advisory combination weights (applied to 0-1 normalized inputs).
W_BLUEPRINT = 0.50  # five-factor composite
W_STRENGTH = 0.30   # six-dimension strength composite
W_FIT = 0.20        # direction fit (when present)

LOW_CONFIDENCE = 0.5  # confidence < 0.5 is flagged, never hidden

EFFORTS = ("low", "medium", "high")

_WEIGHT_EPS = 1e-9


def _require_text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string, got {value!r}")
    return value


def _require_01(name: str, value: Any) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise ValueError(f"{name} must be a number in [0, 1], got {value!r}")
    return float(value)


def _require_0_100(name: str, value: Any) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0.0 <= float(value) <= 100.0
    ):
        raise ValueError(f"{name} must be a number in [0, 100], got {value!r}")
    return float(value)


@dataclass(frozen=True)
class DimensionScore:
    """One assessed strength dimension.

    value: 0-100, higher = stronger for the opportunity.
    basis: required — why the analyst assigns this value.
    evidence: observed evidence pointers (caller-supplied strings only).
    confidence: required 0-1 — the analyst's confidence in their own
        assessment. Low confidence is flagged, never hidden.
    sensitivity: required — what would change this value.
    """

    name: str
    value: float
    basis: str
    confidence: float
    sensitivity: str
    evidence: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.name not in DIMENSIONS:
            raise ValueError(
                f"unknown dimension {self.name!r}; expected one of {DIMENSIONS}"
            )
        object.__setattr__(self, "value", _require_0_100(
            f"dimension {self.name!r} value", self.value))
        _require_text(f"dimension {self.name!r} basis", self.basis)
        object.__setattr__(self, "confidence", _require_01(
            f"dimension {self.name!r} confidence", self.confidence))
        _require_text(
            f"dimension {self.name!r} sensitivity", self.sensitivity)
        if not isinstance(self.evidence, (tuple, list)):
            raise ValueError(
                f"dimension {self.name!r}: evidence must be a list of "
                f"strings, got {self.evidence!r}"
            )
        for e in self.evidence:
            _require_text(f"dimension {self.name!r} evidence entry", e)
        object.__setattr__(self, "evidence", tuple(self.evidence))

    @property
    def low_confidence(self) -> bool:
        return self.confidence < LOW_CONFIDENCE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "basis": self.basis,
            "confidence": self.confidence,
            "sensitivity": self.sensitivity,
            "evidence": list(self.evidence),
        }


# Flexible dimension input: DimensionScore, (value, basis, confidence,
# sensitivity) tuple, or mapping with those keys (+ optional evidence).
DimensionInput = Any


def _coerce_dimension(name: str, raw: DimensionInput) -> DimensionScore:
    if isinstance(raw, DimensionScore):
        if raw.name != name:
            raise ValueError(
                f"dimension key {name!r} mismatches "
                f"DimensionScore.name {raw.name!r}"
            )
        return raw
    if isinstance(raw, Mapping):
        try:
            value = raw["value"]
            basis = raw["basis"]
            confidence = raw["confidence"]
            sensitivity = raw["sensitivity"]
        except KeyError as exc:
            raise ValueError(
                f"dimension {name!r} mapping needs 'value', 'basis', "
                f"'confidence' and 'sensitivity' keys (missing {exc})"
            ) from None
        return DimensionScore(
            name=name,
            value=value,
            basis=basis,
            confidence=confidence,
            sensitivity=sensitivity,
            evidence=tuple(raw.get("evidence", ())),
        )
    if isinstance(raw, (str, bytes)) or not isinstance(raw, (tuple, list)):
        raise ValueError(
            f"dimension {name!r} must be a DimensionScore, a "
            "(value, basis, confidence, sensitivity[, evidence]) tuple, or "
            f"a mapping; got {raw!r}"
        )
    if len(raw) not in (4, 5):
        raise ValueError(
            f"dimension {name!r} tuple must be (value, basis, confidence, "
            f"sensitivity[, evidence]); got {raw!r}"
        )
    value, basis, confidence, sensitivity = raw[:4]
    evidence = tuple(raw[4]) if len(raw) == 5 else ()
    return DimensionScore(
        name=name,
        value=value,
        basis=basis,
        confidence=confidence,
        sensitivity=sensitivity,
        evidence=evidence,
    )


def validate_dimension_weights(
    weights: Optional[Mapping[str, float]],
) -> Dict[str, float]:
    """Validated copy of dimension weights (defaults when None)."""
    if weights is None:
        w = dict(DEFAULT_DIMENSION_WEIGHTS)
    elif not isinstance(weights, Mapping):
        raise ValueError(
            f"weights must be a mapping over {DIMENSIONS}, "
            f"got {type(weights).__name__}"
        )
    else:
        w = dict(weights)
    if set(w) != set(DIMENSIONS):
        raise ValueError(
            f"weights must cover exactly {DIMENSIONS}; got {sorted(w)}"
        )
    for name, val in w.items():
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise ValueError(f"weight {name!r} must be numeric, got {val!r}")
        if not 0.0 <= float(val) <= 1.0:
            raise ValueError(f"weight {name!r}={val} outside [0, 1]")
    total = sum(float(v) for v in w.values())
    if abs(total - 1.0) > _WEIGHT_EPS:
        raise ValueError(f"weights must sum to 1.0, got {total:.6f}")
    return {k: float(v) for k, v in w.items()}


def validate_dimensions(
    dimensions: Mapping[str, DimensionInput],
) -> List[DimensionScore]:
    """The six dimensions in canonical order, validated."""
    if not isinstance(dimensions, Mapping):
        raise ValueError(
            f"dimensions must be a mapping over {DIMENSIONS}, "
            f"got {type(dimensions).__name__}"
        )
    if set(dimensions) != set(DIMENSIONS):
        missing = [d for d in DIMENSIONS if d not in dimensions]
        extra = [k for k in dimensions if k not in DIMENSIONS]
        raise ValueError(
            f"dimensions must be exactly {DIMENSIONS}; "
            f"missing={missing} extra={extra}"
        )
    return [_coerce_dimension(name, dimensions[name]) for name in DIMENSIONS]


def strength_composite(
    dimensions: Sequence[DimensionScore],
    weights: Mapping[str, float],
) -> float:
    """Deterministic weighted mean of dimension values, rounded to 2 dp."""
    if not isinstance(dimensions, (list, tuple)) or not all(
        isinstance(d, DimensionScore) for d in dimensions
    ):
        raise ValueError("dimensions must be a list of DimensionScore")
    names = [d.name for d in dimensions]
    if len(names) != len(DIMENSIONS) or set(names) != set(DIMENSIONS):
        raise ValueError(
            f"dimensions must cover exactly {DIMENSIONS}; got {sorted(names)}"
        )
    weights = validate_dimension_weights(weights)
    total = sum(d.value * weights[d.name] for d in dimensions)
    return round(total, 2)


@dataclass(frozen=True)
class Risk:
    """A flagged risk — surfaced, never silently subtracted from a score."""

    description: str
    severity: float  # 0-100, higher = more severe
    basis: str

    def __post_init__(self) -> None:
        _require_text("risk description", self.description)
        object.__setattr__(
            self, "severity", _require_0_100("risk severity", self.severity)
        )
        _require_text("risk basis", self.basis)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "severity": self.severity,
            "basis": self.basis,
        }


@dataclass(frozen=True)
class RecommendedAction:
    """One ranked recommended action: what, why, and what it costs."""

    action: str
    rationale: str
    effort: str = "medium"

    def __post_init__(self) -> None:
        _require_text("action", self.action)
        _require_text("action rationale", self.rationale)
        if self.effort not in EFFORTS:
            raise ValueError(
                f"action effort must be one of {EFFORTS}, got {self.effort!r}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "rationale": self.rationale,
            "effort": self.effort,
        }


@dataclass(frozen=True)
class WatchCondition:
    """Something to monitor, and what it would change if it fires."""

    condition: str
    would_change: str

    def __post_init__(self) -> None:
        _require_text("watch condition", self.condition)
        _require_text("watch condition would_change", self.would_change)

    def to_dict(self) -> Dict[str, Any]:
        return {"condition": self.condition, "would_change": self.would_change}


def _coerce_risks(raw: Sequence[Any]) -> Tuple[Risk, ...]:
    out = []
    for r in raw or ():
        if isinstance(r, Risk):
            out.append(r)
        elif isinstance(r, Mapping):
            out.append(Risk(
                description=r["description"],
                severity=r["severity"],
                basis=r["basis"],
            ))
        elif isinstance(r, (tuple, list)) and len(r) == 3:
            out.append(Risk(description=r[0], severity=r[1], basis=r[2]))
        else:
            raise ValueError(
                "risks must be Risk, mappings, or "
                f"(description, severity, basis) triples; got {r!r}"
            )
    return tuple(out)


def _coerce_actions(raw: Sequence[Any]) -> Tuple[RecommendedAction, ...]:
    out = []
    for a in raw or ():
        if isinstance(a, RecommendedAction):
            out.append(a)
        elif isinstance(a, Mapping):
            out.append(RecommendedAction(
                action=a["action"],
                rationale=a["rationale"],
                effort=a.get("effort", "medium"),
            ))
        elif isinstance(a, (tuple, list)) and len(a) in (2, 3):
            out.append(RecommendedAction(
                action=a[0],
                rationale=a[1],
                effort=a[2] if len(a) == 3 else "medium",
            ))
        else:
            raise ValueError(
                "actions must be RecommendedAction, mappings, or "
                f"(action, rationale[, effort]) tuples; got {a!r}"
            )
    return tuple(out)


def _coerce_watch(raw: Sequence[Any]) -> Tuple[WatchCondition, ...]:
    out = []
    for w_ in raw or ():
        if isinstance(w_, WatchCondition):
            out.append(w_)
        elif isinstance(w_, Mapping):
            out.append(WatchCondition(
                condition=w_["condition"], would_change=w_["would_change"]))
        elif isinstance(w_, (tuple, list)) and len(w_) == 2:
            out.append(WatchCondition(condition=w_[0], would_change=w_[1]))
        else:
            raise ValueError(
                "watch_conditions must be WatchCondition, mappings, or "
                f"(condition, would_change) pairs; got {w_!r}"
            )
    return tuple(out)


@dataclass
class StrengthCard:
    """The enriched signal: six dimensions + risks + actions + watches."""

    opportunity_id: str
    title: str
    dimensions: List[DimensionScore]
    weights: Optional[Mapping[str, float]] = None
    risks: Sequence[Any] = ()
    actions: Sequence[Any] = ()
    watch_conditions: Sequence[Any] = ()
    notes: str = ""
    segment: str = "general"
    as_of: str = ""
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    strength: float = field(init=False)
    mean_confidence: float = field(init=False)

    def __post_init__(self) -> None:
        _require_text("opportunity_id", self.opportunity_id)
        _require_text("title", self.title)
        if not isinstance(self.notes, str):
            raise ValueError("notes must be a string")
        _require_text("segment", self.segment)
        if not isinstance(self.as_of, str):
            raise ValueError("as_of must be a string")
        weights = validate_dimension_weights(self.weights)
        object.__setattr__(self, "weights", weights)
        dims = validate_dimensions({d.name: d for d in self.dimensions})
        object.__setattr__(self, "dimensions", dims)
        object.__setattr__(self, "risks", _coerce_risks(self.risks))
        object.__setattr__(self, "actions", _coerce_actions(self.actions))
        object.__setattr__(
            self, "watch_conditions", _coerce_watch(self.watch_conditions))
        object.__setattr__(
            self, "strength", strength_composite(dims, weights))
        mean_conf = round(
            sum(d.confidence for d in dims) / len(dims), 4)
        object.__setattr__(self, "mean_confidence", mean_conf)

    @property
    def low_confidence_dimensions(self) -> List[DimensionScore]:
        return [d for d in self.dimensions if d.low_confidence]

    @property
    def weakest_dimensions(self) -> List[DimensionScore]:
        """Dimensions sorted weakest-first — the strengthen targets."""
        return sorted(self.dimensions, key=lambda d: (d.value, d.name))

    def explain(self) -> str:
        """Full-depth audit render: every dimension, risk, action, watch."""
        lines = [
            f"[{self.opportunity_id}] {self.title}  (signal-strength v{self.schema_version})",
            f"strength={self.strength:.2f}  mean_confidence={self.mean_confidence:.2f}  "
            f"segment={self.segment}",
            "",
            "DIMENSIONS (higher = stronger for the opportunity):",
        ]
        for d in self.dimensions:
            w = self.weights[d.name]
            contrib = d.value * w
            flag = "  <-- LOW CONFIDENCE" if d.low_confidence else ""
            lines.append(
                f"  {d.name:17s} value={d.value:6.1f}  weight={w:.2f}  "
                f"contrib={contrib:6.2f}  confidence={d.confidence:.2f}{flag}"
            )
            lines.append(f"    basis: {d.basis}")
            if d.evidence:
                for e in d.evidence:
                    lines.append(f"    evidence (OBSERVED): {e}")
            lines.append(f"    sensitivity: {d.sensitivity}")
        if self.risks:
            lines.append("")
            lines.append("RISKS (flagged — not subtracted from the score):")
            for r in self.risks:
                lines.append(
                    f"  - severity={r.severity:.0f}: {r.description}"
                )
                lines.append(f"    basis: {r.basis}")
        if self.actions:
            lines.append("")
            lines.append("RECOMMENDED ACTIONS (ranked):")
            for i, a in enumerate(self.actions, 1):
                lines.append(
                    f"  {i}. [{a.effort} effort] {a.action}"
                )
                lines.append(f"     why: {a.rationale}")
        if self.watch_conditions:
            lines.append("")
            lines.append("WATCH CONDITIONS:")
            for w_ in self.watch_conditions:
                lines.append(f"  - if: {w_.condition}")
                lines.append(f"    then: {w_.would_change}")
        if self.notes:
            lines.append("")
            lines.append(f"notes: {self.notes}")
        lines.append("")
        lines.append(
            "Dimension values are analyst judgments with stated bases, "
            "evidence, and confidence — not measured data."
        )
        return "\n".join(lines)

    def plain_summary(self) -> str:
        """Plain-language summary for users — no jargon, no hidden math."""
        tier = scoring.tier_for(self.strength)
        top = self.weakest_dimensions[-1]
        lines = [
            f"{self.title}: signal strength {self.strength:.0f}/100 ({tier}).",
            f"Strongest read: {top.name.replace('_', ' ')} "
            f"({top.value:.0f}/100) — {top.basis}",
        ]
        if self.low_confidence_dimensions:
            names = ", ".join(
                d.name.replace("_", " ")
                for d in self.low_confidence_dimensions
            )
            lines.append(
                f"Honest caveat: low confidence on {names} — treat those "
                "reads as provisional."
            )
        if self.risks:
            worst = max(self.risks, key=lambda r: (r.severity, r.description))
            lines.append(
                f"Biggest risk to watch: {worst.description} "
                f"(severity {worst.severity:.0f}/100)."
            )
        if self.actions:
            lines.append(f"First move: {self.actions[0].action}")
        return " ".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "opportunity_id": self.opportunity_id,
            "title": self.title,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "weights": dict(self.weights),
            "risks": [r.to_dict() for r in self.risks],
            "actions": [a.to_dict() for a in self.actions],
            "watch_conditions": [w.to_dict() for w in self.watch_conditions],
            "notes": self.notes,
            "segment": self.segment,
            "as_of": self.as_of,
            "strength": self.strength,
            "mean_confidence": self.mean_confidence,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "StrengthCard":
        data = dict(raw)
        data["dimensions"] = [
            DimensionScore(
                name=d["name"],
                value=d["value"],
                basis=d["basis"],
                confidence=d["confidence"],
                sensitivity=d["sensitivity"],
                evidence=tuple(d.get("evidence", ())),
            )
            for d in data["dimensions"]
        ]
        data.pop("strength", None)
        data.pop("mean_confidence", None)
        data.pop("schema_version", None)
        return cls(**data)  # type: ignore[arg-type]


def strength_card(
    opportunity_id: str,
    title: str,
    dimensions: Mapping[str, DimensionInput],
    weights: Optional[Mapping[str, float]] = None,
    risks: Sequence[Any] = (),
    actions: Sequence[Any] = (),
    watch_conditions: Sequence[Any] = (),
    notes: str = "",
    segment: str = "general",
    as_of: str = "",
) -> StrengthCard:
    """Build one enriched strength card. Pure and deterministic."""
    return StrengthCard(
        opportunity_id=opportunity_id,
        title=title,
        dimensions=validate_dimensions(dimensions),
        weights=weights,
        risks=risks,
        actions=actions,
        watch_conditions=watch_conditions,
        notes=notes,
        segment=segment,
        as_of=as_of,
    )


# ---------------------------------------------------------------------------
# Advisory — DemandPulse as UPGRADE ADVISOR.
#
# advise() fuses the blueprint five-factor card, the six-dimension
# strength card, and (optionally) direction fit into one scored, ranked
# advisory with an explicit upgrade directive for the builder sequence.
# The fusion math is always disclosed; nothing is a black box.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UpgradeDirective:
    """What the builder sequence should do about this opportunity.

    focus_order: weakest-first dimension/action targets — the strengthen
    list, derived from the card, never invented.
    """

    opportunity_id: str
    title: str
    rank: int
    combined: float
    verdict: str
    focus_order: Tuple[str, ...]
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "title": self.title,
            "rank": self.rank,
            "combined": self.combined,
            "verdict": self.verdict,
            "focus_order": list(self.focus_order),
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "UpgradeDirective":
        data = dict(raw)
        data["focus_order"] = tuple(data.get("focus_order", ()))
        return cls(**data)  # type: ignore[arg-type]


@dataclass(frozen=True)
class AdvisorReport:
    """The full advisory for one opportunity."""

    opportunity_id: str
    title: str
    blueprint_composite: float
    strength_composite: float
    direction_fit: Optional[float]
    combined: float
    math: str
    tier: str
    verdict: str
    verdict_math: str
    directive: UpgradeDirective
    plain_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "opportunity_id": self.opportunity_id,
            "title": self.title,
            "blueprint_composite": self.blueprint_composite,
            "strength_composite": self.strength_composite,
            "direction_fit": self.direction_fit,
            "combined": self.combined,
            "math": self.math,
            "tier": self.tier,
            "verdict": self.verdict,
            "verdict_math": self.verdict_math,
            "directive": self.directive.to_dict(),
            "plain_summary": self.plain_summary,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "AdvisorReport":
        data = dict(raw)
        data.pop("schema_version", None)
        data["directive"] = UpgradeDirective.from_dict(data["directive"])
        return cls(**data)  # type: ignore[arg-type]


def advise(
    score_card: "scoring.ScoreCard",
    strength: StrengthCard,
    direction_fit: Optional[float] = None,
    rank: int = 0,
) -> AdvisorReport:
    """Fuse blueprint card + strength card + direction fit into an advisory.

    combined = 0.50*blueprint + 0.30*strength + 0.20*fit (0-1 scale).
    Without direction fit the weights reweight to 0.625/0.375 and the
    math string says so. Deterministic; the directive's focus order is
    weakest-dimension-first, then ranked actions.
    """
    if not isinstance(score_card, scoring.ScoreCard):
        raise ValueError(
            f"score_card must be a scoring.ScoreCard, "
            f"got {type(score_card).__name__}"
        )
    if not isinstance(strength, StrengthCard):
        raise ValueError(
            f"strength must be a StrengthCard, got {type(strength).__name__}"
        )
    if score_card.opportunity_id != strength.opportunity_id:
        raise ValueError(
            "score_card and strength card must describe the same "
            f"opportunity: {score_card.opportunity_id!r} vs "
            f"{strength.opportunity_id!r}"
        )
    fit: Optional[float] = None
    if direction_fit is not None:
        fit = _require_01("direction_fit", direction_fit)

    b = score_card.composite / 100.0
    s = strength.strength / 100.0
    if fit is None:
        wb, ws = 0.625, 0.375
        combined = round(wb * b + ws * s, 4)
        math_s = (
            f"0.625*{b:.4f} + 0.375*{s:.4f} = {combined:.4f} "
            "(no direction fit: reweighted 5/8 + 3/8)"
        )
        v = direction_verdict(combined, combined)
    else:
        combined = round(W_BLUEPRINT * b + W_STRENGTH * s + W_FIT * fit, 4)
        math_s = (
            f"0.50*{b:.4f} + 0.30*{s:.4f} + 0.20*{fit:.4f} = {combined:.4f}"
        )
        v = direction_verdict(combined, fit)

    tier = scoring.tier_for(combined * 100.0)

    # Directive: weakest dimensions first (the strengthen targets),
    # then the analyst's ranked actions.
    focus = [d.name for d in strength.weakest_dimensions[:3]]
    focus += [f"action:{a.action[:60]}" for a in strength.actions[:2]]
    low = strength.low_confidence_dimensions
    rationale_bits = [
        f"weakest dimension: {strength.weakest_dimensions[0].name} "
        f"({strength.weakest_dimensions[0].value:.0f}/100)",
    ]
    if low:
        rationale_bits.append(
            "low-confidence dimensions to verify first: "
            + ", ".join(d.name for d in low)
        )
    if strength.risks:
        worst = max(strength.risks, key=lambda r: (r.severity, r.description))
        rationale_bits.append(
            f"top risk to contain: {worst.description} "
            f"(severity {worst.severity:.0f})"
        )
    directive = UpgradeDirective(
        opportunity_id=strength.opportunity_id,
        title=strength.title,
        rank=rank,
        combined=combined,
        verdict=v["verdict"],
        focus_order=tuple(focus),
        rationale="; ".join(rationale_bits),
    )
    return AdvisorReport(
        opportunity_id=strength.opportunity_id,
        title=strength.title,
        blueprint_composite=score_card.composite,
        strength_composite=strength.strength,
        direction_fit=fit,
        combined=combined,
        math=math_s,
        tier=tier,
        verdict=v["verdict"],
        verdict_math=v["math"],
        directive=directive,
        plain_summary=strength.plain_summary(),
    )


def rank_advisories(reports: Sequence[AdvisorReport]) -> List[AdvisorReport]:
    """Rank advisories highest combined first; ties break by
    opportunity_id (deterministic). Re-stamps directive ranks."""
    if not isinstance(reports, (list, tuple)) or not all(
        isinstance(r, AdvisorReport) for r in reports
    ):
        raise ValueError("reports must be a list of AdvisorReport")
    ordered = sorted(
        reports, key=lambda r: (-r.combined, r.opportunity_id))
    out = []
    for i, r in enumerate(ordered, 1):
        d = r.directive
        new_directive = UpgradeDirective(
            opportunity_id=d.opportunity_id,
            title=d.title,
            rank=i,
            combined=d.combined,
            verdict=d.verdict,
            focus_order=d.focus_order,
            rationale=d.rationale,
        )
        out.append(AdvisorReport(
            opportunity_id=r.opportunity_id,
            title=r.title,
            blueprint_composite=r.blueprint_composite,
            strength_composite=r.strength_composite,
            direction_fit=r.direction_fit,
            combined=r.combined,
            math=r.math,
            tier=r.tier,
            verdict=r.verdict,
            verdict_math=r.verdict_math,
            directive=new_directive,
            plain_summary=r.plain_summary,
        ))
    return out
