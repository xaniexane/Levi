"""Nightshift — off-peak time-of-use scheduling for heavy compute.

Studied from: hybrid-cost-cutting-combos-20260916-0006/report.md
[§8 Energy] (mainframe-era batch-window thinking: heavy work — checkpointed
training, batch inference, transcoding — scheduled into off-peak electricity
windows for 25–45% energy-cost reductions).

This is an original, from-scratch implementation for LEVI. A ``Tariff``
describes the day's price windows (off-peak / shoulder / peak, in
dollars-per-kWh, possibly with weekend rules). A ``Job`` describes heavy
work: its power draw, duration, whether it can be checkpointed and resumed
(``preemptible``), and an optional deadline. ``Nightshift`` places each job
into the cheapest feasible hours — checkpointable jobs are split across
off-peak fragments; rigid jobs take the cheapest contiguous block that fits
before their deadline — and reports the honest before/after cost so the
savings claim is auditable, not asserted.

Public surface:
- ``Tariff`` / ``Window``: ``price_at(hour)``, ``offpeak_hours``.
- ``Job``: name, watts, duration_hours, preemptible, deadline_hour.
- ``Nightshift``: ``schedule``, ``cost_of``, ``savings_report``.
- ``ScheduleError`` for embedding.

Prices are user-supplied; no tariff database is bundled and nothing is
fetched. stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/offpeak_scheduling"


class ScheduleError(ValueError):
    """Raised when a job cannot be placed under the tariff."""


@dataclass(frozen=True)
class Window:
    """One named price band: hours are [start, end) in 0–24 local time."""

    name: str
    start_hour: int  # inclusive
    end_hour: int  # exclusive; may wrap past midnight
    dollars_per_kwh: float

    def __post_init__(self) -> None:
        if not (0 <= self.start_hour < 24 and 0 < self.end_hour <= 24):
            raise ScheduleError("window hours must lie in 0..24")
        if self.dollars_per_kwh < 0:
            raise ScheduleError("price cannot be negative")

    def covers(self, hour: int) -> bool:
        h = hour % 24
        if self.start_hour < self.end_hour:
            return self.start_hour <= h < self.end_hour
        return h >= self.start_hour or h < self.end_hour


@dataclass
class Tariff:
    """A day's price windows, first match wins (put off-peak first)."""

    name: str
    windows: List[Window] = field(default_factory=list)
    weekend_windows: Optional[List[Window]] = None  # optional cheaper weekend

    def price_at(self, hour: int, weekend: bool = False) -> float:
        table = self.windows
        if weekend and self.weekend_windows:
            table = self.weekend_windows
        for w in table:
            if w.covers(hour):
                return w.dollars_per_kwh
        raise ScheduleError(f"hour {hour} is not covered by any window")

    def offpeak_hours(self, weekend: bool = False) -> List[int]:
        """Hours sorted by ascending price — the placement preference order."""
        prices = {h: self.price_at(h, weekend) for h in range(24)}
        return sorted(range(24), key=lambda h: (prices[h], h))

    def cheapest_price(self, weekend: bool = False) -> float:
        return min(self.price_at(h, weekend) for h in range(24))


@dataclass(frozen=True)
class Job:
    """One unit of heavy work to place."""

    name: str
    watts: float
    duration_hours: float  # may be fractional; placed on hour granularity
    preemptible: bool = True  # checkpointable: may be split across windows
    deadline_hour: Optional[int] = None  # must finish by this hour (0-24)

    def __post_init__(self) -> None:
        if self.watts <= 0:
            raise ScheduleError("job watts must be positive")
        if self.duration_hours <= 0:
            raise ScheduleError("job duration must be positive")
        if self.deadline_hour is not None and not (0 <= self.deadline_hour <= 24):
            raise ScheduleError("deadline_hour must be in 0..24")

    @property
    def kwh(self) -> float:
        return self.watts * self.duration_hours / 1000.0


@dataclass
class Placement:
    """Where a job landed: list of (hour, fraction_of_hour) slices."""

    job_name: str
    slices: List[Tuple[int, float]]
    cost_dollars: float
    weekend: bool = False


class Nightshift:
    """Places jobs into the cheapest feasible tariff hours."""

    def __init__(self, tariff: Tariff) -> None:
        self.tariff = tariff
        # hour -> remaining fractional capacity (1.0 = fully free)
        self._free: Dict[Tuple[bool, int], float] = {}

    def _capacity(self, weekend: bool, hour: int) -> float:
        return self._free.get((weekend, hour), 1.0)

    def schedule(self, job: Job, weekend: bool = False) -> Placement:
        """Place one job; raises ScheduleError when it cannot fit."""
        need = job.duration_hours
        order = self.tariff.offpeak_hours(weekend)
        if job.deadline_hour is not None:
            order = [h for h in order if h < job.deadline_hour]
            if not order:
                raise ScheduleError(f"job {job.name!r}: no hours before deadline")

        slices: List[Tuple[int, float]] = []
        if job.preemptible:
            # Greedy: take cheapest available fragments first.
            for hour in order:
                if need <= 1e-9:
                    break
                avail = self._capacity(weekend, hour)
                if avail <= 0:
                    continue
                take = min(avail, need)
                slices.append((hour, take))
                self._free[(weekend, hour)] = avail - take
                need -= take
        else:
            # Rigid: cheapest contiguous whole-hour block (rounds up).
            block = int(job.duration_hours) + (1 if job.duration_hours % 1 else 0)
            best: Optional[List[int]] = None
            best_cost = float("inf")
            for start in order:
                hours = [(start + i) % 24 for i in range(block)]
                if job.deadline_hour is not None and any(
                    h >= job.deadline_hour for h in hours
                ):
                    continue
                if any(self._capacity(weekend, h) < 1.0 - 1e-9 for h in hours):
                    continue
                cost = sum(self.tariff.price_at(h, weekend) for h in hours)
                if cost < best_cost:
                    best_cost = cost
                    best = hours
            if best is None:
                raise ScheduleError(
                    f"job {job.name!r}: no contiguous {block}h block available"
                )
            for hour in best:
                slices.append((hour, 1.0))
                self._free[(weekend, hour)] = 0.0
            need = 0.0

        if need > 1e-9:
            raise ScheduleError(
                f"job {job.name!r}: only placed "
                f"{job.duration_hours - need:.2f}h of {job.duration_hours:.2f}h"
            )
        cost = sum(
            self.tariff.price_at(h, weekend) * (job.watts / 1000.0) * frac
            for h, frac in slices
        )
        return Placement(
            job_name=job.name, slices=slices, cost_dollars=cost, weekend=weekend
        )

    def cost_of(self, job: Job, at_peak: bool = True, weekend: bool = False) -> float:
        """What the job would cost run flat-out at peak (or cheapest) price."""
        price = (
            max(self.tariff.price_at(h, weekend) for h in range(24))
            if at_peak
            else self.tariff.cheapest_price(weekend)
        )
        return job.kwh * price

    def savings_report(
        self, jobs: List[Job], placements: List[Placement]
    ) -> Dict[str, float]:
        """Baseline (all at peak price) vs scheduled cost, honestly computed."""
        baseline = sum(self.cost_of(j) for j in jobs)
        scheduled = sum(p.cost_dollars for p in placements)
        saved = baseline - scheduled
        return {
            "baseline_dollars": round(baseline, 4),
            "scheduled_dollars": round(scheduled, 4),
            "saved_dollars": round(saved, 4),
            "savings_pct": round(100.0 * saved / baseline, 2) if baseline else 0.0,
        }

    def reset(self) -> None:
        self._free.clear()
