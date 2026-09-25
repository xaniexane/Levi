"""Greenwich computers & HMNAO: independent verification of your own product.

Origin: the HM Nautical Almanac Office (est. 1832 at Greenwich). Philip
Herbert Cowell and Andrew Crommelin computed the 1910 return of Halley's
Comet by numerical integration — and then checked the Almanac's *own*
tables against the comet's observed return. Beyond duplex-plus-comparer
discipline, HMNAO ran something harder: independent mathematical
verification of its own published product. The team integrated the orbit
backward through planetary perturbations — a months-long hand computation
— split the integration into independently computed segments, re-integrated
with different assumed masses, and compared the results against observed
positions, not against the original computation.

What it is in LEVI: post-publication audit. Publish a result together with
its derivation function, its assumptions, and the observed reality it
claims; then re-derive it with varied assumptions over independently
computed segments. The audit report flags any variant — including the
published baseline — whose re-derivation diverges from observation.
A discrepancy planted in the published assumptions is caught exactly this
way: the corrected variant matches reality while the published one does not.

Honesty label: LOAD-BEARING — re-derivation with varied assumptions and
segment splits, scored against observations, is a concrete discrepancy
detector.

Deny-closed inputs: duplicate or unknown result ids, non-callable
derivations, empty or non-numeric observations, negative tolerances, empty
variant sets, non-dict variants, and variants overriding unknown assumption
keys are all rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

__all__ = ["PostPublicationAudit", "AuditReport", "VariantFinding"]


def _clean(value: str, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} must be a non-empty string")
    return value.strip()


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass
class VariantFinding:
    name: str
    assumptions: dict = field(default_factory=dict)
    derived: float = 0.0
    divergence: float = 0.0  # |derived - observed_mean|
    flagged: bool = False


@dataclass
class AuditReport:
    result_id: str
    published_value: float
    observed_mean: float
    published_divergence: float
    published_flagged: bool
    variants: list = field(default_factory=list)  # [VariantFinding]


class PostPublicationAudit:
    """Verify your own published results by re-deriving them differently.

    ``derive`` is called as ``derive(assumptions, segment)`` for each
    segment index — independently computed segments, Cowell-and-Crommelin
    style — and the result is the mean across segments.
    """

    def __init__(self) -> None:
        self._derivations: dict[str, dict] = {}

    def publish(
        self,
        result_id: str,
        derive: Callable,
        assumptions: dict,
        observations: list[float],
        tolerance: float = 0.0,
    ) -> float:
        """Publish a result with its derivation, assumptions, and the
        observed reality it claims. Returns the derived published value."""
        result_id = _clean(result_id, "result id")
        if result_id in self._derivations:
            raise ValueError(f"duplicate result id: {result_id!r}")
        if not callable(derive):
            raise ValueError("derive must be callable(assumptions, segment)")
        if not isinstance(assumptions, dict):
            raise ValueError("assumptions must be a dict")
        observations = self._check_observations(observations)
        if not _is_number(tolerance) or tolerance < 0:
            raise ValueError("tolerance must be a non-negative number")
        value = self._derive_all(derive, dict(assumptions), len(observations))
        self._derivations[result_id] = {
            "derive": derive,
            "assumptions": dict(assumptions),
            "observations": observations,
            "tolerance": float(tolerance),
        }
        return value

    def re_derive(self, result_id: str, variants: dict[str, dict]) -> AuditReport:
        """Re-derive with varied assumptions; score every variant —
        including the published baseline — against observations."""
        entry = self._derivations.get(result_id)
        if entry is None:
            raise ValueError(f"unknown result id: {result_id!r}")
        if not isinstance(variants, dict) or not variants:
            raise ValueError("variants must be a non-empty dict of name->overrides")
        derive = entry["derive"]
        base = entry["assumptions"]
        obs = entry["observations"]
        tol = entry["tolerance"]
        observed_mean = sum(obs) / len(obs)
        findings: list[VariantFinding] = [
            self._run_variant(
                "published (baseline)", derive, base, obs, tol, observed_mean
            )
        ]
        for name, overrides in variants.items():
            name = _clean(name, "variant name")
            if not isinstance(overrides, dict):
                raise ValueError(f"variant {name!r}: overrides must be a dict")
            unknown = [k for k in overrides if k not in base]
            if unknown:
                raise ValueError(
                    f"variant {name!r} overrides unknown assumptions: {unknown}"
                )
            merged = {**base, **overrides}
            findings.append(
                self._run_variant(name, derive, merged, obs, tol, observed_mean)
            )
        published = findings[0]
        return AuditReport(
            result_id=result_id,
            published_value=published.derived,
            observed_mean=observed_mean,
            published_divergence=published.divergence,
            published_flagged=published.flagged,
            variants=findings[1:],
        )

    # -- internals -------------------------------------------------------------
    def _check_observations(self, observations: list[float]) -> list[float]:
        if not isinstance(observations, list) or not observations:
            raise ValueError("observations must be a non-empty list of numbers")
        if not all(_is_number(v) for v in observations):
            raise ValueError("observations must be a non-empty list of numbers")
        return [float(v) for v in observations]

    def _derive_all(self, derive: Callable, assumptions: dict, segments: int) -> float:
        try:
            values = [float(derive(assumptions, s)) for s in range(segments)]
        except Exception as exc:  # noqa: BLE001 - surface derivation bugs plainly
            raise ValueError(f"derivation failed: {exc}") from exc
        return sum(values) / len(values)

    def _run_variant(
        self,
        name: str,
        derive: Callable,
        assumptions: dict,
        observations: list[float],
        tolerance: float,
        observed_mean: float,
    ) -> VariantFinding:
        derived = self._derive_all(derive, assumptions, len(observations))
        divergence = abs(derived - observed_mean)
        return VariantFinding(
            name=name,
            assumptions=dict(assumptions),
            derived=derived,
            divergence=divergence,
            flagged=divergence > tolerance,
        )
