"""Redundant independent computation with an adversarial comparer.

Studied from: forgotten-methods-wave3-20260916-0015/report.md (method #30).

The mechanism under study: every computation is performed
**independently by two workers** — same inputs, no communication —
then checked by a third, the **comparer**, who reconciles. Agreement
means accepted; disagreement means flagged with both values on the
table. Errors are *assumed*, not hoped away: the workflow's unit is
the checked result, and the comparer role is a distinct skill (reading
two solution paths for divergence).

This is an original, from-scratch implementation for LEVI. ``verify``
runs two callables over identical inputs, compares their outputs with
a caller-set numeric tolerance (exact equality otherwise), and returns
a ``VerificationResult``: AGREE with the accepted value, DISAGREE with
both values and their delta, or WORKER_ERROR if a worker raised. The
``Comparer`` keeps a log of every check so the reconciliation record
is inspectable. ``require_agreement`` raises on anything but agreement.

Public surface:
- ``Status``: AGREE, DISAGREE, WORKER_ERROR.
- ``verify(fn_a, fn_b, *args, tol=0.0, **kwargs) -> VerificationResult``.
- ``Comparer``: stateful verifier with ``log()`` and ``summary()``.
- ``require_agreement(...)``: return the value or raise ``Mismatch``.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Callable, Dict, List

ORIGIN = "levi-revival/duplex"


class Mismatch(Exception):
    """The comparer refused: workers disagreed, or a worker failed."""


class Status(Enum):
    AGREE = auto()
    DISAGREE = auto()
    WORKER_ERROR = auto()


@dataclass
class VerificationResult:
    """The checker's unit: a checked result, never a single uncompared number."""

    status: Status
    value: Any = None  # accepted value, when AGREE
    value_a: Any = None  # worker A's value, always recorded
    value_b: Any = None  # worker B's value, always recorded
    delta: Any = None  # |a - b| when both numeric and disagreeing
    error: str = ""  # worker failure detail, when WORKER_ERROR
    agreed: bool = False


def _compare(a: Any, b: Any, tol: float) -> bool:
    """Agreement test: numeric tolerance for numbers, equality otherwise."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= tol
    return a == b


def _delta(a: Any, b: Any) -> Any:
    if isinstance(a, bool) or isinstance(b, bool):
        return None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b)
    return None


def verify(
    fn_a: Callable[..., Any],
    fn_b: Callable[..., Any],
    *args: Any,
    tol: float = 0.0,
    **kwargs: Any,
) -> VerificationResult:
    """Run two independent workers on identical inputs; the comparer reconciles.

    Same args/kwargs to both, no shared state between them. Agreement ->
    accepted value. Disagreement -> flagged with both values and delta.
    A raised worker -> WORKER_ERROR with the failure recorded.
    """
    if tol < 0:
        raise Mismatch("tolerance cannot be negative")
    try:
        value_a = fn_a(*args, **kwargs)
    except Exception as exc:  # errors are assumed, not hoped away
        return VerificationResult(
            status=Status.WORKER_ERROR,
            value_a=None,
            value_b=None,
            error=f"worker A failed: {exc}",
        )
    try:
        value_b = fn_b(*args, **kwargs)
    except Exception as exc:
        return VerificationResult(
            status=Status.WORKER_ERROR,
            value_a=value_a,
            value_b=None,
            error=f"worker B failed: {exc}",
        )
    if _compare(value_a, value_b, tol):
        return VerificationResult(
            status=Status.AGREE,
            value=value_a,
            value_a=value_a,
            value_b=value_b,
            agreed=True,
        )
    return VerificationResult(
        status=Status.DISAGREE,
        value_a=value_a,
        value_b=value_b,
        delta=_delta(value_a, value_b),
    )


class Comparer:
    """The standing comparer: verifies checks and keeps the reconciliation record."""

    def __init__(self, tol: float = 0.0) -> None:
        self.tol = tol
        self._log: List[Dict[str, Any]] = []

    def check(
        self,
        label: str,
        fn_a: Callable[..., Any],
        fn_b: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> VerificationResult:
        """Verify one computation; log the outcome."""
        result = verify(fn_a, fn_b, *args, tol=self.tol, **kwargs)
        self._log.append(
            {
                "label": label,
                "status": result.status.name,
                "agreed": result.agreed,
                "value_a": result.value_a,
                "value_b": result.value_b,
                "delta": result.delta,
                "error": result.error,
            }
        )
        return result

    def log(self) -> List[Dict[str, Any]]:
        return [dict(entry) for entry in self._log]

    def summary(self) -> Dict[str, int]:
        """How many checks agreed, disagreed, or hit worker errors."""
        counts = {"AGREE": 0, "DISAGREE": 0, "WORKER_ERROR": 0}
        for entry in self._log:
            counts[entry["status"]] += 1
        return {"total": len(self._log), **counts}


def require_agreement(
    fn_a: Callable[..., Any],
    fn_b: Callable[..., Any],
    *args: Any,
    tol: float = 0.0,
    **kwargs: Any,
) -> Any:
    """Return the accepted value, or raise on disagreement / worker error.

    Use this at trust boundaries: anything consequential goes through
    the comparer, and a single uncompared number never escapes.
    """
    result = verify(fn_a, fn_b, *args, tol=tol, **kwargs)
    if result.status is Status.AGREE:
        return result.value
    if result.status is Status.DISAGREE:
        raise Mismatch(
            f"workers disagreed: A={result.value_a!r}, B={result.value_b!r}"
            + (f" (delta {result.delta})" if result.delta is not None else "")
        )
    raise Mismatch(f"worker error: {result.error}")
