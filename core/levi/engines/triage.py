"""Triage engine — a weighted multi-option verdict.

Inputs
------
``options``: list of ``{"id": str, "scores": {criterion: number}}``
``weights``: dict of ``{criterion: positive_number}`` (default: equal)

The engine normalizes each criterion 0–1 across the option set
(min-max; a constant criterion contributes 0, noted in the trace),
applies the weights, and emits a ranked verdict with the winner and
its margin over second place. Ties break on option id (deterministic,
disclosed in the trace). Confidence is calibrated from the margin:
a runaway winner scores near 1.0; a photo finish lands near 0.5.

Pure computation — no actions, no side effects.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from levi.engines.base import Engine, EngineInputError, EngineResult, registry


def _triage(inputs: Dict[str, Any]) -> EngineResult:
    options = inputs.get("options")
    weights = inputs.get("weights") or {}
    if not isinstance(options, list) or len(options) < 2:
        raise EngineInputError("triage: 'options' needs at least 2 entries")
    for o in options:
        if not isinstance(o, dict) or "id" not in o or "scores" not in o:
            raise EngineInputError(
                "triage: each option needs 'id' and 'scores'"
            )

    trace: List[str] = []
    criteria = sorted({c for o in options for c in o["scores"]})

    # Per-criterion range across the option set; constant criteria carry
    # zero signal and are named so the verdict stays honest.
    ranges: Dict[str, Tuple[float, float]] = {}
    for c in criteria:
        vals = [float(o["scores"].get(c, 0.0)) for o in options]
        lo, hi = min(vals), max(vals)
        ranges[c] = (lo, hi)
        if hi == lo:
            trace.append(
                f"criterion '{c}' is constant across options → 0 signal"
            )

    # Normalize weights (equal share when none given).
    raw_w = {c: float(weights.get(c, 1.0)) for c in criteria}
    if any(w < 0 for w in raw_w.values()):
        raise EngineInputError("triage: weights must be non-negative")
    total = sum(raw_w.values()) or 1.0
    norm_w = {c: w / total for c, w in raw_w.items()}
    trace.append(
        "weights normalized: "
        + ", ".join(f"{c}={norm_w[c]:.2f}" for c in criteria)
    )

    totals: Dict[str, float] = {}
    contribs: Dict[str, Dict[str, float]] = {}
    for o in options:
        oid = o["id"]
        contribs[oid] = {}
        score_sum = 0.0
        for c in criteria:
            lo, hi = ranges[c]
            raw = float(o["scores"].get(c, 0.0))
            normed = (raw - lo) / (hi - lo) if hi != lo else 0.0
            part = normed * norm_w[c]
            contribs[oid][c] = part
            score_sum += part
        totals[oid] = score_sum

    ranked: List[Tuple[str, float]] = sorted(
        totals.items(), key=lambda kv: (-kv[1], kv[0])
    )
    winner, win_score = ranked[0]
    runner_score = ranked[1][1]
    margin = win_score - runner_score
    tied = margin == 0.0
    if tied:
        trace.append(
            "exact tie on weighted score; broken deterministically by id "
            f"('{winner}' < '{ranked[1][0]}')"
        )
    # Confidence from margin: 0.5 at a dead heat → ~1.0 at a blowout.
    confidence = round(0.5 + 0.5 * min(margin * 4.0, 1.0), 3)
    trace.append(
        f"winner '{winner}' scored {win_score:.3f}; "
        f"runner-up {runner_score:.3f}; margin {margin:.3f}"
    )
    for oid, sc in ranked:
        parts = ", ".join(f"{c}:{contribs[oid][c]:.2f}" for c in criteria)
        trace.append(f"  {oid}: total {sc:.3f} [{parts}]")

    verdict = {
        "winner": winner,
        "margin": round(margin, 4),
        "tied": tied,
        "ranking": [{"id": oid, "score": round(sc, 4)} for oid, sc in ranked],
    }
    return EngineResult(
        engine_id="triage", verdict=verdict, confidence=confidence, trace=trace
    )


TRIAGE_ENGINE = Engine(
    id="triage",
    name="Triage",
    description=(
        "Deterministic weighted verdict over competing options: rank, "
        "winner, and margin with a full scoring trace."
    ),
    required=("options",),
    schema={
        "options": "list[{id, scores:{criterion:number}}] (≥2)",
        "weights": "dict criterion→non-negative weight (optional)",
    },
    risk="info",
    handler=_triage,
)

registry.register(TRIAGE_ENGINE)
