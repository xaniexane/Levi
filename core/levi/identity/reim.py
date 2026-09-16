"""REIM — compost outcomes (identity variant engine).

Breaks a run's outcome down into lessons: failure signature, classified
cause, one-line lesson, severity. Information is never destroyed: every
lesson keeps the failure signature and the raw notes excerpt. Deterministic.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List

# Ordered (cause, keywords): first cause whose keyword set intersects the
# failure text wins. Deterministic.
_CAUSE_RULES = (
    ("trait-conflict", ("conflict", "contradict", "fracture", "incoherent")),
    ("param-drift", ("drift", "overflow", "threshold", "out of range", "unstable")),
    ("missing-signal", ("missing", "absent", "no signal", "unknown input")),
    ("resource-exhaustion", ("timeout", "exhausted", "oom", "quota", "overload")),
    ("external", ("external", "network", "upstream", "third-party")),
)


def _signature(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()[:16]


def _classify(text: str) -> str:
    lowered = text.lower()
    for cause, keywords in _CAUSE_RULES:
        if any(k in lowered for k in keywords):
            return cause
    return "unknown"


def _severity(score: float) -> str:
    if score < 0.4:
        return "high"
    if score < 0.7:
        return "medium"
    return "low"


class REIM:
    """Compost an outcome into lessons."""

    def compost(self, outcome: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not isinstance(outcome, dict):
            raise ValueError(
                "compost: outcome must be a dict, got %s" % type(outcome).__name__
            )
        identity = str(outcome.get("identity", ""))
        success = bool(outcome.get("success", False))
        score = outcome.get("score", 1.0 if success else 0.0)
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = 1.0 if success else 0.0
        notes = str(outcome.get("notes", ""))
        failures = outcome.get("failures", [])
        if not isinstance(failures, list):
            failures = [str(failures)]

        lessons: List[Dict[str, Any]] = []
        if success and not failures:
            lessons.append(
                {
                    "kind": "reinforcement",
                    "failure_signature": _signature("success:" + identity),
                    "cause": "none",
                    "lesson": "identity %r scored %.3f: keep current trait mix"
                    % (identity, score),
                    "severity": "low",
                    "source_identity": identity,
                    "score": round(score, 4),
                    "notes_excerpt": notes[:200],
                    "reusable": score >= 0.8,
                }
            )
            return lessons

        for failure in failures:
            text = str(failure)
            cause = _classify(text)
            lessons.append(
                {
                    "kind": "failure",
                    "failure_signature": _signature(text),
                    "cause": cause,
                    "lesson": "identity %r failed via %s: %s"
                    % (identity, cause, text[:120]),
                    "severity": _severity(score),
                    "source_identity": identity,
                    "score": round(score, 4),
                    "notes_excerpt": notes[:200],
                    "reusable": True,
                }
            )
        return lessons
