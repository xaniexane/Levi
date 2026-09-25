"""Muster engine — a readiness roll-call rebuilt as a LEVI-native decision machine.

The pattern is the ship's muster: before the vessel gets underway, every
station answers the roll. Ready stations are silent confidence; a single
down station holds the whole ship. This module is original stdlib-only
code re-implementing the *idea* — never any artifact's text, never a
paid anything.

An engine, so it is pure and stateless: the checks arrive with the input
and the verdict is deterministic — same inputs, same verdict, every time.
The engine computes readiness; it never takes the ship out.

Input schema::

    {
        "checks": [
            {"id": "db", "status": "ready", "weight": 2.0},
            {"id": "cache", "status": "warn"},
            {"id": "queue", "status": "down"},
        ],
        "strict": true,   # optional; default true
    }

``status`` is one of ``ready`` | ``warn`` | ``down``; ``weight`` is a
non-negative number defaulting to 1.0. The score is the weighted
readiness fraction (warn counts half). Verdict::

    {
        "roll": "ready" | "degraded" | "standdown",
        "score": 0.0-1.0,
        "blocking": ["queue"],
        "warns": ["cache"],
        "checked": 3,
    }

Any ``down`` station holds the muster: ``standdown`` when ``strict`` is
true (the default), ``degraded`` when false. Warns without downs give
``degraded``. All ready gives ``ready``.
"""

from __future__ import annotations

from typing import Any, Dict, List

from levi.engines.base import Engine, EngineInputError, EngineResult, registry

STATUS = ("ready", "warn", "down")
_SCORE_OF = {"ready": 1.0, "warn": 0.5, "down": 0.0}


def _validate_checks(checks: Any) -> List[Dict[str, Any]]:
    if not isinstance(checks, list) or not checks:
        raise EngineInputError("muster: 'checks' must be a non-empty list")
    cleaned: List[Dict[str, Any]] = []
    for i, check in enumerate(checks):
        if not isinstance(check, dict):
            raise EngineInputError(
                f"muster: checks[{i}] must be a dict with 'id' and 'status'"
            )
        cid = check.get("id")
        status = check.get("status")
        weight = check.get("weight", 1.0)
        if not isinstance(cid, str) or not cid.strip():
            raise EngineInputError(f"muster: checks[{i}].id must be a non-empty str")
        if status not in STATUS:
            raise EngineInputError(
                f"muster: checks[{i}].status must be one of "
                f"{'/'.join(STATUS)}, got {status!r}"
            )
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise EngineInputError(f"muster: checks[{i}].weight must be a number")
        if weight < 0:
            raise EngineInputError(f"muster: checks[{i}].weight must be >= 0")
        cleaned.append({"id": cid.strip(), "status": status, "weight": float(weight)})
    ids = [c["id"] for c in cleaned]
    if len(set(ids)) != len(ids):
        raise EngineInputError("muster: check ids must be unique")
    return cleaned


def _validate_strict(strict: Any) -> bool:
    if not isinstance(strict, bool):
        raise EngineInputError("muster: 'strict' must be a bool when given")
    return strict


def _muster(inputs: Dict[str, Any]) -> EngineResult:
    checks = _validate_checks(inputs.get("checks"))
    strict = _validate_strict(inputs.get("strict", True))

    total_weight = sum(c["weight"] for c in checks)
    earned = sum(c["weight"] * _SCORE_OF[c["status"]] for c in checks)
    score = round(earned / total_weight, 3) if total_weight else 0.0

    trace: List[str] = [f"mustering {len(checks)} station(s), strict={strict}"]
    blocking: List[str] = []
    warns: List[str] = []
    for c in checks:
        trace.append(f"  {c['id']}: {c['status']} (weight {c['weight']:g})")
        if c["status"] == "down":
            blocking.append(c["id"])
        elif c["status"] == "warn":
            warns.append(c["id"])

    if blocking:
        roll = "standdown" if strict else "degraded"
    elif warns:
        roll = "degraded"
    else:
        roll = "ready"
    trace.append(f"roll call: {roll} (score {score})")

    verdict = {
        "roll": roll,
        "score": score,
        "blocking": blocking,
        "warns": warns,
        "checked": len(checks),
    }
    return EngineResult(
        engine_id="muster",
        verdict=verdict,
        confidence=score,  # the weighted readiness IS the confidence
        trace=trace,
    )


MUSTER_ENGINE = Engine(
    id="muster",
    name="Muster",
    description=(
        "Readiness roll-call over named stations: every station answers "
        "ready/warn/down (optionally weighted); any down holds the muster "
        "as standdown (strict) or degraded. Deterministic, weighted "
        "readiness score."
    ),
    required=("checks",),
    schema={
        "checks": "list[{id:str, status:'ready'|'warn'|'down', weight:num?}] (≥1, unique ids)",
        "strict": "bool? — down ⇒ standdown when true (default), degraded when false",
    },
    risk="info",
    handler=_muster,
)

registry.register(MUSTER_ENGINE)
