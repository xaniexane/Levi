"""REIM — compost failure (kernel organ).

REIM (failure composting) takes a structured failure record and extracts
reusable fertilizer: a one-line lesson, the mirror-image success
(inverse map), a compost class, and a reusable flag. Everything is
deterministic and hash-seeded, like the sibling organs echo.py and
mandella.py.

REIM never writes anything and never auto-applies anything — it returns a
compost record (data). Promotion into genome proposals is the job of the
RIEM organ (levi/organs/riem.py).

A malformed record renders as an explicit ValueError (fail-closed), not a
KeyError or a silent default.
"""

from __future__ import annotations

from typing import Dict
import hashlib

ORGAN = "reim"

SEVERITIES = ("low", "medium", "high")

COMPOST_CLASSES = (
    "flaky-input",
    "wrong-assumption",
    "missing-guard",
    "resource-exhaustion",
    "unknown",
)

# Deterministic keyword rules: (class, keywords). First class whose keyword
# set intersects the record text wins; no match -> "unknown".
_CLASS_RULES = (
    (
        "resource-exhaustion",
        (
            "timeout",
            "timed out",
            "out of memory",
            "oom",
            "exhausted",
            "quota",
            "disk full",
            "rate limit",
            "overloaded",
            "no space",
            "memoryerror",
            "recursionerror",
            "thread pool",
            "socket",
        ),
    ),
    (
        "missing-guard",
        (
            "missing guard",
            "no guard",
            "unvalidated",
            "no validation",
            "precondition",
            "none check",
            "null check",
            "boundary",
            "off-by-one",
            "race condition",
            "unchecked",
            "no lock",
        ),
    ),
    (
        "flaky-input",
        (
            "invalid input",
            "malformed",
            "unexpected input",
            "bad input",
            "schema",
            "parse",
            "decode",
            "encoding",
            "empty input",
            "truncated",
            "corrupt",
            "serialization",
        ),
    ),
    (
        "wrong-assumption",
        (
            "assumed",
            "assumption",
            "expected",
            "invariant",
            "contract",
            "believed",
            "thought",
            "meant to",
            "supposed to",
            "version",
            "api changed",
            "drift",
            "stale",
            "out of date",
        ),
    ),
)

_INVERSE_MAPS = {
    "flaky-input": "Same path with input validated at the boundary: the operation succeeds on the first attempt.",
    "wrong-assumption": "Same decision with the assumption checked first: the plan holds because the ground is solid.",
    "missing-guard": "Same flow with the guard in place: the edge case is caught early and handled cheaply.",
    "resource-exhaustion": "Same workload with the resource bounded: the operation completes inside the budget.",
    "unknown": "Same attempt with the failure characterized: the unknown becomes a named, testable risk.",
}


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _validate_record(record: Dict) -> Dict:
    """Fail-closed validation; returns the record unchanged when valid."""
    if not isinstance(record, dict):
        raise ValueError(
            "compost_failure: record must be a dict, got %s" % type(record).__name__
        )
    missing = [
        k for k in ("source", "what", "context", "ts", "severity") if k not in record
    ]
    if missing:
        raise ValueError(
            "compost_failure: record is missing keys: %s" % ", ".join(missing)
        )
    for key in ("source", "what", "context", "ts"):
        value = record[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                "compost_failure: record[%r] must be a non-empty string, got %r"
                % (key, value)
            )
    severity = record["severity"]
    if severity not in SEVERITIES:
        raise ValueError(
            "compost_failure: record['severity'] must be one of %s, got %r"
            % (SEVERITIES, severity)
        )
    return record


def _classify(text: str) -> str:
    lowered = text.lower()
    for cls, keywords in _CLASS_RULES:
        if any(kw in lowered for kw in keywords):
            return cls
    return "unknown"


def _lesson_for(cls: str, seed_hash: int) -> str:
    # Deterministic: the lesson template is fixed per class; the hash picks
    # a stable phrasing variant so distinct failures read distinctly.
    variants = {
        "flaky-input": (
            "Normalize and validate input at the boundary before it reaches logic.",
            "Treat every input boundary as hostile until validated.",
            "Fail at the boundary with a clear message, not deep in the logic.",
        ),
        "wrong-assumption": (
            "Turn the broken assumption into an explicit, verified precondition.",
            "Write the assumption down before trusting it; check it at runtime.",
            "Replace silent expectations with loud, cheap verification.",
        ),
        "missing-guard": (
            "Add the guard that would have caught this before the failure.",
            "Every branch that can surprise you deserves a precondition.",
            "Catch the edge case early where it is cheap, not late where it is not.",
        ),
        "resource-exhaustion": (
            "Bound the resource before committing work against it.",
            "Size the job to the budget; degrade gracefully when the budget is tight.",
            "Monitor the resource with a circuit-breaker, not a hope.",
        ),
        "unknown": (
            "Reproduce and characterize the failure before changing anything.",
            "An unknown failure is a test you have not written yet.",
            "Log the full context now; classify later with evidence.",
        ),
    }
    picks = variants[cls]
    return picks[seed_hash % len(picks)]


def compost_failure(record: Dict) -> Dict:
    """Compost a failure record into a reusable compost record.

    ``record`` must be a dict with keys ``source``, ``what``, ``context``,
    ``ts`` (all non-empty strings) and ``severity`` (one of "low",
    "medium", "high"). Raises ValueError on malformed records.

    Returns a compost record dict::

        {
            "organ": "reim",
            "source": ...,
            "what": ...,
            "context": ...,
            "ts": ...,
            "severity": ...,
            "compost_class": one of flaky-input / wrong-assumption /
                             missing-guard / resource-exhaustion / unknown,
            "lesson": one-line lesson,
            "inverse_map": what the mirror-image success looks like,
            "reusable": bool,
            "corroboration": 1,
            "fingerprint": sha256-derived id of the failure,
            "provenance": {"source": ..., "ts": ..., "organ": "reim"},
        }

    ``reusable`` is True only when the failure was classifiable and the
    severity was at least medium — unknowns and trivial failures stay
    compost, not genome material.
    """
    record = _validate_record(record)
    seed_text = "|".join(
        (record["source"], record["what"], record["context"], record["severity"])
    )
    fp = _fingerprint(seed_text)
    seed_hash = int(fp, 16)
    cls = _classify(record["what"] + " " + record["context"])
    reusable = cls != "unknown" and record["severity"] in ("medium", "high")
    return {
        "organ": ORGAN,
        "source": record["source"],
        "what": record["what"],
        "context": record["context"],
        "ts": record["ts"],
        "severity": record["severity"],
        "compost_class": cls,
        "lesson": _lesson_for(cls, seed_hash),
        "inverse_map": _INVERSE_MAPS[cls],
        "reusable": reusable,
        "corroboration": 1,
        "fingerprint": fp,
        "provenance": {
            "source": record["source"],
            "ts": record["ts"],
            "organ": ORGAN,
        },
    }


def format_compost(compost: Dict) -> str:
    """Render a :func:`compost_failure` result.

    Raises ValueError when ``compost`` lacks the expected keys (fail-closed,
    like echo.format_echo).
    """
    if not isinstance(compost, dict):
        raise ValueError("format_compost: compost must be a dict")
    for key in ("source", "what", "compost_class", "lesson", "reusable"):
        if key not in compost:
            raise ValueError("format_compost: compost is missing key %r" % key)
    lines = [
        "=== REIM compost (source: %s) ===" % str(compost["source"])[:60],
        "",
        "Failure: %s" % str(compost["what"])[:120],
        "Class:   %s" % compost["compost_class"],
        "Lesson:  %s" % compost["lesson"],
        "Inverse: %s" % str(compost.get("inverse_map", ""))[:120],
        "",
        "Reusable: %s" % ("yes" if compost["reusable"] else "no"),
    ]
    return "\n".join(lines)
