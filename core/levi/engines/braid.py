"""Braid engine — arbitration over verdicts from other engines.

Inputs
------
``verdicts``: list of ``{"engine": str, "verdict": <json-able>, "confidence": 0.0-1.0}``
``question``: the question being decided (non-empty string)
``max_verdicts``: refuse more than this (default 64)

The engine canonicalizes every verdict to JSON (sorted keys) and groups
the agreeing ones. All agreeing → ``"consensus"``. A strict majority (>
half) agreeing → ``"majority"``. Anything else → ``"deadlocked"``: the
verdict is None and the question is held for the keeper.

Braid arbitrates verdicts; it never runs the engines itself (the caller
ran them and hands over the receipts). Verdicts are data, not votes —
quorum counts votes, braid reconciles judgments.

The engine form of the two-sided coin: both faces show, or the coin is
held. Never flipped, never silently averaged.

Laws (declared up front, proved by the test suite)
--------------------------------------------------
1. **Unanimity law** — identical verdicts always yield ``"consensus"``,
   never ``"majority"``.
2. **Conflict-honesty law** — every disagreement is named in the trace;
   no merge happens off the books.
3. **Dissent-surfaces law** — a non-unanimous outcome lists every
   dissenting engine in the verdict itself.
4. **Determinism law** — same inputs → byte-identical verdict
   (first-seen group order, sorted engine lists inside groups).
5. **Hold-on-deadlock law** — no strict majority → ``outcome`` is
   ``"deadlocked"``, ``verdict`` is None, confidence is 0.0. The engine
   never invents a compromise.

Pure computation — no actions, no side effects.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from levi.engines.base import Engine, EngineInputError, EngineResult, registry

_DEFAULT_MAX_VERDICTS = 64


def _canonical(verdict: Any) -> str:
    """Deterministic JSON fingerprint; refuse what JSON can't hold."""
    try:
        return json.dumps(verdict, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise EngineInputError(
            f"braid: verdict is not JSON-serializable: {exc}"
        ) from exc


def _confidence(value: object, engine: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EngineInputError(
            f"braid: engine {engine!r} confidence must be a number, got {value!r}"
        )
    c = float(value)
    if not 0.0 <= c <= 1.0:
        raise EngineInputError(
            f"braid: engine {engine!r} confidence must be 0.0-1.0, got {c}"
        )
    return c


def _braid(inputs: Dict[str, Any]) -> EngineResult:
    verdicts = inputs.get("verdicts")
    question = inputs.get("question")
    max_verdicts = inputs.get("max_verdicts", _DEFAULT_MAX_VERDICTS)

    if not isinstance(verdicts, list) or not verdicts:
        raise EngineInputError("braid: 'verdicts' needs a non-empty list")
    if isinstance(max_verdicts, bool) or not isinstance(max_verdicts, int):
        raise EngineInputError(
            f"braid: 'max_verdicts' must be an int, got {max_verdicts!r}"
        )
    if max_verdicts < 2:
        raise EngineInputError(
            f"braid: 'max_verdicts' must be >= 2, got {max_verdicts}"
        )
    if len(verdicts) > max_verdicts:
        raise EngineInputError(
            f"braid: {len(verdicts)} verdicts exceeds max_verdicts={max_verdicts}"
        )
    if not isinstance(question, str) or not question.strip():
        raise EngineInputError(
            f"braid: 'question' must be a non-empty string, got {question!r}"
        )

    # Deny-closed per-entry checks: unique engine names, honest confidences.
    entries: List[Dict[str, Any]] = []
    seen: set = set()
    for i, item in enumerate(verdicts):
        if not isinstance(item, dict):
            raise EngineInputError(
                f"braid: verdicts[{i}] must be a dict, got {type(item).__name__}"
            )
        engine = item.get("engine")
        if not isinstance(engine, str) or not engine.strip():
            raise EngineInputError(
                f"braid: verdicts[{i}] needs a non-empty 'engine' name"
            )
        if engine in seen:
            raise EngineInputError(
                f"braid: duplicate engine {engine!r} — one verdict per engine"
            )
        seen.add(engine)
        if "verdict" not in item:
            raise EngineInputError(
                f"braid: verdicts[{i}] ({engine!r}) is missing 'verdict'"
            )
        if "confidence" not in item:
            raise EngineInputError(
                f"braid: verdicts[{i}] ({engine!r}) is missing 'confidence'"
            )
        entries.append(
            {
                "engine": engine,
                "verdict": item["verdict"],
                "canonical": _canonical(item["verdict"]),
                "confidence": _confidence(item["confidence"], engine),
            }
        )

    # Group by canonical verdict, first-seen order (determinism law).
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for entry in entries:
        groups.setdefault(entry["canonical"], []).append(entry)
    total = len(entries)
    ordered = sorted(groups.values(), key=lambda g: -len(g))
    top = ordered[0]

    trace = [
        f"braid over {total} verdicts on {question.strip()!r}: "
        f"{len(groups)} distinct verdicts",
    ]
    for group in ordered:
        names = sorted(e["engine"] for e in group)
        trace.append(
            f"verdict {group[0]['canonical'][:64]!r} held by "
            f"{', '.join(names)} ({len(group)}/{total})"
        )

    def _confidence_of(group: List[Dict[str, Any]]) -> float:
        return round(sum(e["confidence"] for e in group) / len(group), 3)

    if len(top) == total:
        outcome = "consensus"
        agreed_verdict: Any = top[0]["verdict"]
        agreeing = sorted(e["engine"] for e in top)
        dissenting: List[str] = []
        confidence = _confidence_of(top)
        trace.append("unanimous — consensus")
    elif len(top) > total / 2:
        outcome = "majority"
        agreed_verdict = top[0]["verdict"]
        agreeing = sorted(e["engine"] for e in top)
        dissenting = sorted(e["engine"] for group in ordered[1:] for e in group)
        confidence = _confidence_of(top)
        trace.append(
            f"strict majority holds — dissent kept on the record: "
            f"{', '.join(dissenting)}"
        )
    else:
        outcome = "deadlocked"
        agreed_verdict = None
        agreeing = []
        dissenting = sorted(e["engine"] for group in ordered for e in group)
        confidence = 0.0
        trace.append("no strict majority — held for the keeper, no compromise invented")

    verdict = {
        "question": question.strip(),
        "outcome": outcome,
        "verdict": agreed_verdict,
        "agreeing": agreeing,
        "dissenting": dissenting,
        "confidence": confidence,
        "distinct_verdicts": len(groups),
    }
    return EngineResult(
        engine_id="braid", verdict=verdict, confidence=confidence, trace=trace
    )


BRAID_ENGINE = Engine(
    id="braid",
    name="Braid",
    description=(
        "Arbitration over verdicts from other engines: consensus when all "
        "agree, majority with named dissent on a strict majority, deadlock "
        "held for the keeper otherwise. Conflicts are named, never averaged."
    ),
    version="1.0.0",
    required=("verdicts", "question"),
    schema={
        "verdicts": "list[{engine: str, verdict: json-able, confidence: 0.0-1.0}] (non-empty, engines unique)",
        "question": "non-empty string",
        "max_verdicts": "int >= 2, default 64",
    },
    risk="info",
    handler=_braid,
)

registry.register(BRAID_ENGINE)
