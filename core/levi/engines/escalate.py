"""Escalate engine — a confidence-based escalation router.

Inputs
------
``confidence``: float in [0, 1] — the proposing system's confidence in
its own plan.
``stakes``: one of ``low`` | ``moderate`` | ``high`` | ``critical``.
``reversible``: bool — can the action be cleanly undone.
``retry_cost``: ``low`` | ``high`` (default ``low``) — price of being wrong.
``operator_available``: bool (default True) — whether the keeper can be asked.
``task_kind``: optional free-text label for the trace.

The engine emits one of four verdicts:

- ``handle_local`` — the rules engine runs it. Low stakes, reversible,
  confidence high.
- ``consult_brain`` — needs judgment, but stays inside LEVI: the native
  brain / reflection loop, never a paid call.
- ``ask_operator`` — high or critical stakes, irreversible, or confidence
  below the floor: the keeper decides. This is a *decision*, not a
  message — the engine never messages anyone.
- ``defer_queue`` — the keeper should decide but isn't reachable: park it
  in the queue with the full audit trail rather than guessing.

Deny-closed: malformed inputs are refused with a named error, never
coerced. Pure computation — no actions, no side effects.

This is LEVI's own escalation law, rebuilt natively: confidence, stakes,
and reversibility decide who touches the work — the rules, the brain,
the keeper, or the queue.
"""

from __future__ import annotations

from typing import Any, Dict, List

from levi.engines.base import Engine, EngineInputError, EngineResult, registry

ENGINE_ID = "escalate"

_STAKES = ("low", "moderate", "high", "critical")
_RETRY_COSTS = ("low", "high")


def _handler(inputs: Dict[str, Any]) -> EngineResult:
    confidence = inputs.get("confidence")
    stakes = inputs.get("stakes")
    reversible = inputs.get("reversible")
    retry_cost = inputs.get("retry_cost", "low")
    operator_available = inputs.get("operator_available", True)
    task_kind = inputs.get("task_kind")

    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise EngineInputError("escalate: 'confidence' must be a number")
    confidence = float(confidence)
    if not 0.0 <= confidence <= 1.0:
        raise EngineInputError(
            f"escalate: 'confidence' must be in [0, 1], got {confidence}"
        )
    if stakes not in _STAKES:
        raise EngineInputError(
            f"escalate: 'stakes' must be one of {list(_STAKES)}, got {stakes!r}"
        )
    if not isinstance(reversible, bool):
        raise EngineInputError("escalate: 'reversible' must be a bool")
    if retry_cost not in _RETRY_COSTS:
        raise EngineInputError(
            f"escalate: 'retry_cost' must be one of {list(_RETRY_COSTS)}, "
            f"got {retry_cost!r}"
        )
    if not isinstance(operator_available, bool):
        raise EngineInputError("escalate: 'operator_available' must be a bool")

    trace: List[str] = []
    label = task_kind or "the task"
    trace.append(
        f"{label}: confidence={confidence:.2f} stakes={stakes} "
        f"reversible={reversible} retry_cost={retry_cost} "
        f"operator_available={operator_available}"
    )

    # Rule 1: critical stakes always go to the keeper — no exceptions,
    # no confidence threshold can override this.
    if stakes == "critical":
        trace.append("rule 1: critical stakes → keeper decides, always")
        verdict = "ask_operator"
    # Rule 2: irreversible high-stakes work is never a guess.
    elif stakes == "high" and not reversible:
        trace.append("rule 2: high stakes + irreversible → keeper decides")
        verdict = "ask_operator"
    # Rule 3: below the confidence floor the plan is not trusted —
    # judgment or the keeper, never the rules engine.
    elif confidence < 0.5:
        if stakes in ("high", "critical") or retry_cost == "high":
            trace.append(
                "rule 3: confidence < 0.50 with high exposure → keeper decides"
            )
            verdict = "ask_operator"
        else:
            trace.append("rule 3: confidence < 0.50 with contained exposure → brain")
            verdict = "consult_brain"
    # Rule 4: high confidence, low stakes, reversible — just run it.
    elif confidence >= 0.8 and stakes in ("low", "moderate") and reversible:
        trace.append(
            "rule 4: confidence ≥ 0.80, low/moderate stakes, reversible "
            "→ handle locally"
        )
        verdict = "handle_local"
    # Rule 5: everything else needs judgment but stays inside LEVI.
    else:
        trace.append("rule 5: no rule above matched → brain judgment, stays local")
        verdict = "consult_brain"

    # Rule 6 (the honesty rule): when the verdict is the keeper but the
    # keeper is unreachable, the engine queues instead of guessing.
    if verdict == "ask_operator" and not operator_available:
        trace.append(
            "rule 6: keeper verdict but operator unavailable → "
            "defer to queue with the full audit trail"
        )
        verdict = "defer_queue"

    # Engine confidence: distance from the nearest decision boundary.
    # A call far from any edge is near-certain; a boundary call admits it.
    boundaries = [0.5, 0.8]
    distance = min(abs(confidence - b) for b in boundaries)
    engine_confidence = min(1.0, 0.55 + distance)
    if verdict in ("ask_operator", "defer_queue"):
        # Rule 1 and rule 6 are absolute by design, not by margin.
        engine_confidence = max(engine_confidence, 0.95)
    trace.append(
        f"engine confidence {engine_confidence:.2f} "
        f"(nearest rule boundary {distance:.2f} away)"
    )

    return EngineResult(
        engine_id=ENGINE_ID,
        verdict={
            "decision": verdict,
            "stakes": stakes,
            "confidence_in_plan": confidence,
        },
        confidence=engine_confidence,
        trace=trace,
    )


registry.register(
    Engine(
        id=ENGINE_ID,
        name="Escalate",
        description=(
            "Confidence-based escalation router: confidence, stakes, and "
            "reversibility decide who touches the work — the rules, the "
            "native brain, the keeper, or the queue. Never guesses."
        ),
        version="1.0.0",
        required=("confidence", "stakes", "reversible"),
        schema={
            "confidence": "float in [0, 1]",
            "stakes": "low | moderate | high | critical",
            "reversible": "bool",
            "retry_cost": "low | high (default low)",
            "operator_available": "bool (default True)",
            "task_kind": "optional free-text label for the trace",
        },
        risk="info",
        handler=_handler,
    )
)
