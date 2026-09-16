"""The Nautical Almanac's duplex-computer verification.

History: the 18th–19th-century Nautical Almanac office (and similar
ephemeris bureaus): every computation was performed independently by two
human computers, then checked by a third, the *comparer*. Precomputation
reduced a navigator's lunar-distance reduction from hours of spherical
trigonometry to about half an hour of table lookup. The tables died with
the marine chronometer; the verification discipline survived in niches
(double-entry trial balances, aviation checklists) but the explicit
comparer role mostly vanished.

In LEVI: the institutionalized comparer. Any high-stakes output — a
financial figure, a contract summary, a dosage schedule — is computed via
two (or more) *independent* paths (different methods, different prompts),
then a comparer pass reconciles them. Agreement yields a verified result;
any divergence — including a path that crashed — is quarantined with full
evidence and NEVER returned as a usable number. The disagreement map is
the instrument the human comparer uses for the final call.

Honesty: LOAD-BEARING — redundant independent computation plus an
adversarial comparer; errors are assumed, not hoped away.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DuplexError(Exception):
    """Base class for duplex-verification failures."""


class DivergenceQuarantined(DuplexError):
    """The paths disagreed (or a path failed). The quarantine record is
    attached as ``.quarantine``; the disputed value is NOT returned."""

    def __init__(self, message: str, quarantine: dict):
        super().__init__(message)
        self.quarantine = quarantine


# ---------------------------------------------------------------------------
# Comparer
# ---------------------------------------------------------------------------


def _values_equal(a: Any, b: Any, *, rel_tol: float = 1e-9) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        try:
            return math.isclose(float(a), float(b), rel_tol=rel_tol)
        except (TypeError, ValueError):
            return False
    return a == b


class Comparer:
    """The third role: reads two solution paths for divergence."""

    def __init__(self, rel_tol: float = 1e-9):
        if rel_tol < 0:
            raise ValueError("rel_tol must be non-negative")
        self.rel_tol = rel_tol

    def compare(self, results: dict[str, Any]) -> dict:
        """Compare per-path results.

        Returns ``{"agree": bool, "disagreements": [...], "errors": [...]}``.
        For dict results, disagreement is reported per key — the visible
        reconciliation map. ``errors`` lists paths that raised.
        """
        names = list(results)
        values = [results[n] for n in names if not isinstance(results[n], Exception)]
        errors = [n for n in names if isinstance(results[n], Exception)]
        report: dict = {"agree": True, "disagreements": [], "errors": errors}
        if errors:
            report["agree"] = False
        if not values:
            report["agree"] = False
            return report
        first = values[0]
        for other_name, other in zip(
            [n for n in names if not isinstance(results[n], Exception)][1:], values[1:]
        ):
            if isinstance(first, dict) and isinstance(other, dict):
                for key in sorted(set(first) | set(other)):
                    in_first, in_other = key in first, key in other
                    if not (in_first and in_other):
                        report["agree"] = False
                        report["disagreements"].append(
                            {"key": key, "paths": {names[0]: first.get(key, "<missing>"),
                                                   other_name: other.get(key, "<missing>")},
                             "kind": "missing-key"}
                        )
                    elif not _values_equal(first[key], other[key], rel_tol=self.rel_tol):
                        report["agree"] = False
                        report["disagreements"].append(
                            {"key": key, "paths": {names[0]: first[key],
                                                   other_name: other[key]},
                             "kind": "value"}
                        )
            elif not _values_equal(first, other, rel_tol=self.rel_tol):
                report["agree"] = False
                report["disagreements"].append(
                    {"key": None, "paths": {names[0]: first, other_name: other},
                     "kind": "value"}
                )
        return report


# ---------------------------------------------------------------------------
# Verified result
# ---------------------------------------------------------------------------


@dataclass
class Verified:
    """A value every independent path agreed on."""

    value: Any
    per_path: dict[str, Any]
    compared_at: float = field(default_factory=time.time)

    def unwrap(self) -> Any:
        return self.value


# ---------------------------------------------------------------------------
# The duplex protocol
# ---------------------------------------------------------------------------


def verify(paths: dict[str, Callable[..., Any]], *args: Any,
           comparer: Comparer | None = None, **kwargs: Any) -> Verified:
    """Run each independent path, compare, and return a Verified result.

    ``paths`` maps a path name to a callable (two minimum — the duplex).
    Every path runs; exceptions are captured as path errors, never raised
    directly. If the comparer finds any divergence or any path error, the
    whole computation is quarantined: :class:`DivergenceQuarantined` is
    raised carrying the quarantine record (inputs repr, per-path outcomes,
    disagreement map, timestamp). A disputed value is never returned.
    """
    if len(paths) < 2:
        raise ValueError("duplex verification needs at least two independent paths")
    cmp = comparer or Comparer()
    results: dict[str, Any] = {}
    for name, fn in paths.items():
        try:
            results[name] = fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — a crashed path is evidence
            results[name] = exc
    report = cmp.compare(results)
    if not report["agree"]:
        quarantine = {
            "quarantined_at": time.time(),
            "paths": list(paths),
            "input_repr": repr((args, kwargs))[:2000],
            "outcomes": {
                name: (f"{type(v).__name__}: {v}" if isinstance(v, Exception) else v)
                for name, v in results.items()
            },
            "disagreements": report["disagreements"],
            "path_errors": {
                name: f"{type(results[name]).__name__}: {results[name]}"
                for name in report["errors"]
            },
        }
        raise DivergenceQuarantined(
            "paths diverged — result quarantined, not returned", quarantine
        )
    agreed = next(v for v in results.values() if not isinstance(v, Exception))
    return Verified(value=agreed, per_path=results)


def verify_n(*callables: Callable[..., Any], names: tuple[str, ...] | None = None,
             **kwargs: Any) -> Verified:
    """Convenience wrapper: positional paths, auto-named ``path-1..n``."""
    if names is None:
        names = tuple(f"path-{i + 1}" for i in range(len(callables)))
    if len(names) != len(callables):
        raise ValueError("names and callables must have the same length")
    return verify(dict(zip(names, callables)), **kwargs)


__all__ = [
    "DuplexError",
    "DivergenceQuarantined",
    "Comparer",
    "Verified",
    "verify",
    "verify_n",
]
