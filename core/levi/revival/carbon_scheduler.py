"""Greenhour — carbon-aware elastic workload shifting.

Studied from: hybrid-cost-cutting-combos-20260916-0006/report.md
[§8 — cited analog] (the carbon-intelligent scheduler: elastic workloads
shifted to low-carbon hours, cutting roughly a third of CO₂ on the shifted
work — cited in the report as the analog for off-peak energy scheduling).

This is an original, from-scratch implementation for LEVI of the *shape*
studied, not a port. The caller supplies a carbon-intensity forecast: a
sequence of (hour, grams-CO₂-per-kWh) readings. ``ElasticJob``s declare
energy need, earliest start, deadline, and whether they may pause and
resume. ``Greenhour`` then:

- ``shift()``: places each job's energy into the lowest-carbon feasible
  hours (pauseable jobs are sliced hour by hour; rigid jobs take the
  lowest-carbon contiguous block).
- ``baseline()``: the run-it-now reference — same jobs started at their
  earliest start, unsliced — so the avoided-CO₂ claim is computed, not
  asserted.
- ``report()``: grams avoided, percentage cut, and the delay cost in hours
  (shifting later is not free: the report says how late each job finished).

Honest limits: the forecast is user-supplied (no grid API, no fetching);
intensities are trusted as given. This is a planning model — it does not
execute or throttle any real process.

Public surface:
- ``CarbonForecast``: ``intensity_at(hour)``, ``cleanest_hours``.
- ``ElasticJob``: kwh, earliest_start, deadline_hour, pausable.
- ``Greenhour``: ``shift``, ``baseline``, ``report``.
- ``CarbonError`` for embedding.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/carbon_scheduler"


class CarbonError(ValueError):
    """Raised when a carbon-aware placement cannot be honored."""


@dataclass
class CarbonForecast:
    """Grams of CO₂ per kWh for each hour of the planning horizon."""

    intensities: List[float]  # index = hour offset from "now"
    label: str = "grid forecast"

    def __post_init__(self) -> None:
        if not self.intensities:
            raise CarbonError("forecast must contain at least one hour")
        if any(v < 0 for v in self.intensities):
            raise CarbonError("carbon intensity cannot be negative")

    def intensity_at(self, hour: int) -> float:
        if not (0 <= hour < len(self.intensities)):
            raise CarbonError(f"hour {hour} outside forecast horizon")
        return self.intensities[hour]

    def cleanest_hours(self, start: int, end: int) -> List[int]:
        """Feasible hours in [start, end) sorted by ascending intensity."""
        if not (0 <= start <= end <= len(self.intensities)):
            raise CarbonError("window outside forecast horizon")
        return sorted(range(start, end), key=lambda h: (self.intensities[h], h))


@dataclass(frozen=True)
class ElasticJob:
    """One shiftable workload."""

    name: str
    kwh: float
    earliest_start: int = 0  # hour offset from "now"
    deadline_hour: Optional[int] = None  # must finish by this offset
    pausable: bool = True  # may be sliced across non-adjacent hours
    max_power_kw: float = 1.0  # per-hour energy cap when sliced

    def __post_init__(self) -> None:
        if self.kwh <= 0:
            raise CarbonError("job kwh must be positive")
        if self.max_power_kw <= 0:
            raise CarbonError("max_power_kw must be positive")
        if self.earliest_start < 0:
            raise CarbonError("earliest_start cannot be negative")
        if self.deadline_hour is not None and self.deadline_hour <= self.earliest_start:
            raise CarbonError("deadline must be after earliest_start")


@dataclass
class Shift:
    """Where a job's energy landed: (hour, kwh) slices plus CO₂ cost."""

    job_name: str
    slices: List[Tuple[int, float]]
    grams_co2: float
    finish_hour: int


class Greenhour:
    """Shifts elastic load into the forecast's cleanest feasible hours."""

    def __init__(self, forecast: CarbonForecast) -> None:
        self.forecast = forecast
        self._used: Dict[int, float] = {}  # hour -> kwh already placed

    def _free(self, hour: int) -> float:
        return 1.0 - self._used.get(hour, 0.0)

    def shift(self, job: ElasticJob) -> Shift:
        horizon = len(self.forecast.intensities)
        end = job.deadline_hour if job.deadline_hour is not None else horizon
        if end > horizon:
            raise CarbonError(f"job {job.name!r}: deadline beyond forecast horizon")
        order = self.forecast.cleanest_hours(job.earliest_start, end)
        need = job.kwh
        slices: List[Tuple[int, float]] = []

        if job.pausable:
            for hour in order:
                if need <= 1e-9:
                    break
                # Per-hour cap: the smaller of job power limit and a 1 kWh
                # planning quantum (keeps the model honest about rates).
                cap = min(job.max_power_kw, 1.0) - self._used.get(hour, 0.0)
                if cap <= 1e-9:
                    continue
                take = min(cap, need)
                slices.append((hour, take))
                self._used[hour] = self._used.get(hour, 0.0) + take
                need -= take
        else:
            # Rigid: contiguous block at constant max_power_kw.
            hours_needed = int(job.kwh / job.max_power_kw)
            if job.kwh % job.max_power_kw:
                hours_needed += 1
            best: Optional[List[int]] = None
            best_co2 = float("inf")
            for start in range(job.earliest_start, end - hours_needed + 1):
                hours = list(range(start, start + hours_needed))
                if any(self._used.get(h, 0.0) > 1e-9 for h in hours):
                    continue
                co2 = sum(
                    self.forecast.intensity_at(h) * job.max_power_kw for h in hours
                )
                if co2 < best_co2:
                    best_co2 = co2
                    best = hours
            if best is None:
                raise CarbonError(
                    f"job {job.name!r}: no clean contiguous block available"
                )
            placed = 0.0
            for hour in best:
                take = min(job.max_power_kw, job.kwh - placed)
                slices.append((hour, take))
                self._used[hour] = self._used.get(hour, 0.0) + take
                placed += take
            need = 0.0

        if need > 1e-9:
            raise CarbonError(
                f"job {job.name!r}: only placed {job.kwh - need:.3f} of {job.kwh:.3f} kWh"
            )
        grams = sum(self.forecast.intensity_at(h) * k for h, k in slices)
        return Shift(
            job_name=job.name,
            slices=slices,
            grams_co2=grams,
            finish_hour=max(h for h, _ in slices),
        )

    def baseline(self, jobs: List[ElasticJob]) -> Dict[str, float]:
        """Run-it-now reference: each job at earliest_start, unsliced."""
        total = 0.0
        for job in jobs:
            full_hours = int(job.kwh // job.max_power_kw)
            remainder = job.kwh - full_hours * job.max_power_kw
            co2 = sum(
                self.forecast.intensity_at(job.earliest_start + i) * job.max_power_kw
                for i in range(full_hours)
            ) + (
                self.forecast.intensity_at(job.earliest_start + full_hours) * remainder
                if remainder > 1e-9
                else 0.0
            )
            total += co2
        return {"grams_co2": total, "jobs": float(len(jobs))}

    def report(self, jobs: List[ElasticJob], shifts: List[Shift]) -> Dict[str, float]:
        """Shifted vs baseline CO₂, plus the delay cost of waiting."""
        base = self.baseline(jobs)["grams_co2"]
        shifted = sum(s.grams_co2 for s in shifts)
        avoided = base - shifted
        by_name = {s.job_name: s for s in shifts}
        delay = sum(
            max(0, by_name[j.name].finish_hour - j.earliest_start) for j in jobs
        )
        return {
            "baseline_grams": round(base, 3),
            "shifted_grams": round(shifted, 3),
            "avoided_grams": round(avoided, 3),
            "cut_pct": round(100.0 * avoided / base, 2) if base else 0.0,
            "total_delay_hours": float(delay),
        }

    def reset(self) -> None:
        self._used.clear()
