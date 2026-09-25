"""Insurance actuarial departments: the cohort experience table.

Origin: 1890s-1920s — Prudential, Metropolitan Life, and their actuarial
departments became the largest private users of punched-card tabulation.
Mortality-experience tables, reserve calculations, and policy administration
required sorting, accumulating (summing, not just counting), and printing —
capabilities Hollerith's census machines lacked. Prudential actuary John K.
Gore patented an automatic card sorter (1894, 15,000 cards/hour) after
Hollerith's because Prudential needed throughput Hollerith couldn't give;
Metropolitan Life commissioned J. Royden Peirce to build a custom printing
tabulator — effectively the first enterprise software customization deal.
Insurance was computing's first *demanding customer*, and the pressure
drove the tabulator industry to invent accumulation, high-speed sorting,
and automatic printing of lists and totals.

What it is in LEVI: an experience table. Add exposure/outcome records per
cohort; ``build()`` sorts the records into cohorts, ACCUMULATES (sums, not
counts) exposure and claims, computes a rate per cohort with running
cumulative columns, and accumulates reserves — the exact operation the
actuaries forced into the tabulator.

Honesty label: LOAD-BEARING — cohort accumulation with rates, running
sums, and reserves is a concrete computation.

Deny-closed inputs: non-positive reserve factors, empty cohort names,
non-positive exposure, negative claims, non-numeric exposure or claims, and
building an empty table are all rejected with ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["ExperienceTable", "CohortRow", "TableBuild"]


def _clean(value: str, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} must be a non-empty string")
    return value.strip()


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass
class CohortRow:
    cohort: str
    exposure: float
    claims: float
    rate: float  # claims / exposure
    cumulative_exposure: float
    cumulative_claims: float
    reserve: float  # claims * reserve_factor


@dataclass
class TableBuild:
    rows: list = field(default_factory=list)  # [CohortRow], sorted by cohort
    total_exposure: float = 0.0
    total_claims: float = 0.0
    overall_rate: float = 0.0
    total_reserve: float = 0.0


class ExperienceTable:
    """Sort policy records into cohorts, accumulate, print the table."""

    def __init__(self, reserve_factor: float = 1.0) -> None:
        if not _is_number(reserve_factor) or reserve_factor <= 0:
            raise ValueError("reserve_factor must be a positive number")
        self._reserve_factor = float(reserve_factor)
        self._records: list[tuple[str, float, float]] = []

    def add_record(self, cohort: str, exposure: float, claims: float) -> None:
        """Add one policy record: its cohort, its exposure, its outcome.

        Exposure is accumulated by SUMMING — the actuaries' demanding
        feature — never by counting records.
        """
        cohort = _clean(cohort, "cohort")
        if not _is_number(exposure) or exposure <= 0:
            raise ValueError(f"exposure must be a positive number, got {exposure!r}")
        if not _is_number(claims) or claims < 0:
            raise ValueError(f"claims must be a non-negative number, got {claims!r}")
        self._records.append((cohort, float(exposure), float(claims)))

    def build(self) -> TableBuild:
        """Sort into cohorts, accumulate, and print the table."""
        if not self._records:
            raise ValueError("cannot build a table from zero records")
        by_cohort: dict[str, list[float]] = {}
        for cohort, exposure, claims in self._records:
            bucket = by_cohort.setdefault(cohort, [0.0, 0.0])
            bucket[0] += exposure
            bucket[1] += claims
        rows: list[CohortRow] = []
        cum_exposure = 0.0
        cum_claims = 0.0
        for cohort in sorted(by_cohort):
            exposure, claims = by_cohort[cohort]
            cum_exposure += exposure
            cum_claims += claims
            rows.append(
                CohortRow(
                    cohort=cohort,
                    exposure=exposure,
                    claims=claims,
                    rate=claims / exposure,
                    cumulative_exposure=cum_exposure,
                    cumulative_claims=cum_claims,
                    reserve=claims * self._reserve_factor,
                )
            )
        return TableBuild(
            rows=rows,
            total_exposure=cum_exposure,
            total_claims=cum_claims,
            overall_rate=cum_claims / cum_exposure,
            total_reserve=sum(r.reserve for r in rows),
        )
