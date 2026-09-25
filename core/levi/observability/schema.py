"""TurnTrace schema — one record per bloodstream turn.

A TurnTrace is the queryable unit of LEVI's decision-trace corpus. It
captures:

* ``turn_id`` / ``ts`` — identity and wall-clock time (UTC, ISO-8601).
* ``stages`` — every bloodstream stage traversed, in order, with the
  stage's decision, wall-clock duration (ms, when the pipeline measured
  it), the risk ceiling that stage evaluated under, and the redacted
  detail dict.
* ``tool_calls`` — tool invocations observed during the turn: tool name,
  a SHA-256 over the REDACTED params (never raw values), the redacted
  params themselves, and the argument names. Secret-shaped values never
  reach the corpus.
* ``risk_ceiling`` — the effective (strictest) risk level for the turn.
* ``outcome`` — normalized to ``success`` | ``denied`` | ``failed`` |
  ``awaiting_permission``, plus a human-readable ``reason`` and the raw
  bloodstream outcome verbatim for audit.

The schema is deliberately duck-typed: :func:`from_bloodstream` reads a
bloodstream ``TurnResult`` by attribute, so this module never imports the
bloodstream package (no import cycles, no pipeline coupling).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from levi.observability.redact import canonical, params_hash, redact

SCHEMA_VERSION = 1

# Normalized outcomes. The raw bloodstream outcome is kept verbatim in
# ``raw_outcome``; this is the queryable rollup.
SUCCESS = "success"
DENIED = "denied"
FAILED = "failed"
AWAITING_PERMISSION = "awaiting_permission"

OUTCOME_MAP = {
    "replied": SUCCESS,
    "denied": DENIED,
    "governed": DENIED,  # governor/breaker refused — a denial, not a crash
    "awaiting_permission": AWAITING_PERMISSION,
    "failed": FAILED,
}


@dataclass
class StageTiming:
    """One bloodstream stage as traversed, with its timing and ceiling."""

    stage: str
    decision: str
    duration_ms: Optional[float] = None
    risk_ceiling: Optional[int] = None
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallRecord:
    """One tool invocation: name + secret-safe params fingerprint."""

    name: str
    params_hash: str
    params: Dict[str, Any] = field(default_factory=dict)  # redacted
    arg_names: List[str] = field(default_factory=list)


@dataclass
class TurnTrace:
    """The full decision trace of one bloodstream turn."""

    turn_id: str
    ts: str
    session_id: str
    route: str
    persona_id: str
    provider: str
    stages: List[StageTiming] = field(default_factory=list)
    tool_calls: List[ToolCallRecord] = field(default_factory=list)
    risk_ceiling: int = 0
    outcome: str = SUCCESS
    reason: Optional[str] = None
    raw_outcome: Optional[str] = None
    text_excerpt: str = ""
    receipt_id: Optional[str] = None
    error: Optional[str] = None
    composted: bool = False
    duration_ms: Optional[float] = None
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TurnTrace":
        stages = [StageTiming(**s) for s in data.get("stages", [])]
        tools = [ToolCallRecord(**t) for t in data.get("tool_calls", [])]
        kwargs = dict(data)
        kwargs["stages"] = stages
        kwargs["tool_calls"] = tools
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in kwargs.items() if k in known})


def _stage_risk_ceiling(stage_name: str, detail: Dict[str, Any]) -> Optional[int]:
    """Pull the risk ceiling a stage evaluated under, when it recorded one."""
    for key in ("effective_risk", "risk", "risk_ceiling"):
        value = detail.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return int(value)
    return None


def _tool_record(call: Dict[str, Any]) -> ToolCallRecord:
    name = str(call.get("name") or "unknown")
    args = call.get("args") or call.get("params") or {}
    if not isinstance(args, dict):
        args = {"value": args}
    redacted = redact(args)
    if not isinstance(redacted, dict):
        redacted = {"value": redacted}
    return ToolCallRecord(
        name=name,
        params_hash=params_hash(args),
        params=redacted,
        arg_names=sorted(str(k) for k in args.keys()),
    )


def _reason_for(raw_outcome: Optional[str], result: Any) -> Optional[str]:
    if raw_outcome == "failed":
        return getattr(result, "error", None) or "turn failed; see compost record"
    if raw_outcome == "denied":
        return "denied at the permission gate — nothing was executed"
    if raw_outcome == "governed":
        return "governor or circuit breaker refused the turn — nothing was executed"
    if raw_outcome == "awaiting_permission":
        return "above the auto-approve ceiling with no HITL grant — nothing executed"
    if raw_outcome == "replied":
        return None
    return f"unmapped bloodstream outcome {raw_outcome!r}"


def from_bloodstream(
    result: Any,
    text: str = "",
    *,
    stage_timings: Optional[Dict[str, float]] = None,
    duration_ms: Optional[float] = None,
    composted: Any = None,
) -> TurnTrace:
    """Build a TurnTrace from a bloodstream TurnResult (duck-typed).

    ``stage_timings`` maps stage name → wall-clock ms as measured by the
    pipeline's additive instrumentation; stages without a measurement
    record ``duration_ms=None`` honestly instead of inventing numbers.
    ``composted`` is the failure-compost record when the turn failed.
    """
    timings = stage_timings or {}
    route = getattr(result, "route", None)
    route_value = route.value if hasattr(route, "value") else str(route or "")
    # The pipeline records outcomes as replied/denied/governed/
    # awaiting_permission/failed; map those, fall back to the route value.
    outcome_str = getattr(result, "outcome", None) or route_value

    stages: List[StageTiming] = []
    for s in getattr(result, "stages", []) or []:
        name = getattr(s, "stage", "?")
        decision = getattr(s, "decision", "?")
        detail = getattr(s, "detail", {}) or {}
        if not isinstance(detail, dict):
            detail = {"value": detail}
        stages.append(
            StageTiming(
                stage=name,
                decision=decision,
                duration_ms=timings.get(name),
                risk_ceiling=_stage_risk_ceiling(name, detail),
                detail=redact(detail),
            )
        )

    tool_calls = [
        _tool_record(c)
        for c in (getattr(result, "tool_calls", []) or [])
        if isinstance(c, dict)
    ]

    risk = getattr(result, "risk_level", 0) or 0
    normalized = OUTCOME_MAP.get(outcome_str, outcome_str)

    return TurnTrace(
        turn_id=str(getattr(result, "trace_id", "") or ""),
        ts=datetime.now(timezone.utc).isoformat(),
        session_id=str(getattr(result, "session_id", "default") or "default"),
        route=route_value,
        persona_id=str(getattr(result, "persona_id", "") or ""),
        provider=str(getattr(result, "provider", "") or ""),
        stages=stages,
        tool_calls=tool_calls,
        risk_ceiling=int(risk),
        outcome=normalized,
        reason=_reason_for(outcome_str, result),
        raw_outcome=outcome_str,
        text_excerpt=(text or "")[:200],
        receipt_id=getattr(result, "policy_receipt_id", None),
        error=getattr(result, "error", None),
        composted=composted is not None,
        duration_ms=duration_ms,
    )


# Re-export for convenience; keeps the canonical-params helper near the
# schema that relies on it.
__all__ = [
    "SCHEMA_VERSION",
    "SUCCESS",
    "DENIED",
    "FAILED",
    "AWAITING_PERMISSION",
    "OUTCOME_MAP",
    "StageTiming",
    "ToolCallRecord",
    "TurnTrace",
    "from_bloodstream",
    "canonical",
]
