"""Duplicate independent computation: break error correlation.

Studied from: pre-digital-computation-20260916, report.md [Beat C #11, LOAD-BEARING].

Inspired by the *shape* of the old duplicate-computation discipline:
correlated errors are the enemy, so the same calculation is performed
twice by independent methods — and ideally independent personnel. The
modern form is a unit test written by other hands than the ones that
wrote the code. This is an original, from-scratch implementation for
LEVI.

A :class:`DuplicateCheck` runs two registered methods (callables) on the
same inputs and compares outputs. Methods carry a ``team`` tag, and the
check *refuses* to run when both methods come from the same team —
independence of method and personnel is the whole point, and a same-team
pair is just one method wearing a costume.

Honest limits: independence is declared, not proven — the registry
trusts the team tags it is given. Outputs are compared by equality of
repr; numeric tolerance must be opted into explicitly via ``tolerance``.
Agreement raises confidence; it never proves correctness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

ORIGIN = "levi-revival/independent-dup"


class DuplicationError(Exception):
    """Base class for duplicate-computation failures."""


class SameTeamError(DuplicationError):
    """Both methods came from the same team: not independent."""


class MethodFailed(DuplicationError):
    """One of the independent methods raised during computation."""


@dataclass
class Method:
    """One independent way of computing an answer."""

    name: str
    team: str
    fn: Callable[..., Any]
    description: str = ""


@dataclass
class Attempt:
    """What one method produced: value, or the error it raised."""

    method_name: str
    team: str
    value: Any = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class Report:
    """The verdict of one duplicate run."""

    inputs: tuple
    attempts: List[Attempt] = field(default_factory=list)
    agreed: bool = False
    notes: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"inputs: {self.inputs!r}"]
        for a in self.attempts:
            outcome = repr(a.value) if a.ok else f"FAILED: {a.error}"
            lines.append(f"  [{a.team}] {a.method_name}: {outcome}")
        lines.append("VERDICT: AGREE" if self.agreed else "VERDICT: DISAGREE")
        lines.extend(self.notes)
        return "\n".join(lines)


class DuplicateCheck:
    """Runs registered independent methods pairwise and compares."""

    def __init__(self) -> None:
        self.methods: Dict[str, Method] = {}

    def register(self, method: Method) -> None:
        """Register a method; names must be unique."""
        if method.name in self.methods:
            raise DuplicationError(f"method {method.name!r} already registered")
        self.methods[method.name] = method

    def _attempt(self, method: Method, args: tuple, kwargs: dict) -> Attempt:
        try:
            return Attempt(method.name, method.team, value=method.fn(*args, **kwargs))
        except Exception as exc:  # noqa: BLE001 - captured as evidence
            return Attempt(
                method.name, method.team, error=f"{type(exc).__name__}: {exc}"
            )

    def verify(
        self,
        first: str,
        second: str,
        *args: Any,
        tolerance: Optional[float] = None,
        **kwargs: Any,
    ) -> Report:
        """Run two methods on the same inputs and compare their outputs.

        Raises :class:`SameTeamError` if both methods share a team tag.
        With ``tolerance`` set, numeric outputs agree when they differ by
        at most that much; otherwise outputs must be exactly equal.
        """
        try:
            m1, m2 = self.methods[first], self.methods[second]
        except KeyError as exc:
            raise DuplicationError(f"unknown method: {exc}") from exc
        if m1.team == m2.team:
            raise SameTeamError(
                f"{m1.name!r} and {m2.name!r} are both team {m1.team!r}: "
                "independent duplication requires different teams"
            )
        report = Report(inputs=(args, kwargs))
        a1 = self._attempt(m1, args, kwargs)
        a2 = self._attempt(m2, args, kwargs)
        report.attempts = [a1, a2]
        if not a1.ok or not a2.ok:
            report.notes.append("at least one method failed; no agreement possible")
            return report
        if tolerance is not None and _both_numbers(a1.value, a2.value):
            report.agreed = abs(a1.value - a2.value) <= tolerance
            if report.agreed:
                report.notes.append(f"values agree within tolerance {tolerance}")
        else:
            report.agreed = a1.value == a2.value
        if not report.agreed:
            report.notes.append(
                f"mismatch: {m1.name}={a1.value!r} vs {m2.name}={a2.value!r} "
                "— correlated-error assumption broken, investigate both"
            )
        return report

    def verify_all(self, *args: Any, **kwargs: Any) -> List[Report]:
        """Run every cross-team pair; useful for more than two methods."""
        names = sorted(self.methods)
        reports = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                try:
                    reports.append(self.verify(names[i], names[j], *args, **kwargs))
                except SameTeamError:
                    continue  # same-team pairs are not independent evidence
        return reports


def _both_numbers(a: Any, b: Any) -> bool:
    return (
        isinstance(a, (int, float))
        and isinstance(b, (int, float))
        and not isinstance(a, bool)
        and not isinstance(b, bool)
    )
