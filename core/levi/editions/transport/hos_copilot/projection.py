"""Route projection: the clock against the plan, mile by mile.

:func:`project` walks a :class:`RoutePlan` leg by leg against a
:class:`DriverClock`, inserts 30-minute breaks where the break rule
demands them (a taken break earns a fresh 8-hour stretch), and emits
:class:`PreViolationFlag`s with mile markers — the "this plan burns
your 14 at mile 612 — break at mile 540" move.

The simulation is one code path; ``rules.check_plan`` is the other.
A projection is ``legal`` iff the checker finds zero violations on the
simulated usage — and an internal assertion machine-checks that the
two paths agree on every single projection, not just in tests.
Stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from .clocks import DriverClock
from .rules import (
    BREAK_DRIVE_WINDOW_HRS,
    BREAK_MIN_MINUTES,
    EPS_HRS,
    PlanUsage,
    check_plan,
)

BREAK_HRS = BREAK_MIN_MINUTES / 60.0


@dataclass(frozen=True)
class RouteLeg:
    """One stretch of a route: miles to drive, dwell at its end."""

    miles: float
    dwell_hrs: float = 0.0  # loading, unloading, fueling — on-duty, not driving
    label: str = ""

    def __post_init__(self) -> None:
        if self.miles < 0 or self.dwell_hrs < 0:
            raise ValueError("leg miles and dwell must be >= 0")


@dataclass(frozen=True)
class RoutePlan:
    """The planned route: legs plus the assumed average speed."""

    legs: Tuple[RouteLeg, ...]
    avg_mph: float

    def __post_init__(self) -> None:
        if self.avg_mph <= 0:
            raise ValueError("avg_mph must be positive")
        if not self.legs:
            raise ValueError("a route needs at least one leg")

    @property
    def total_miles(self) -> float:
        return sum(leg.miles for leg in self.legs)


@dataclass(frozen=True)
class PreViolationFlag:
    """One advisory flag: what breaks, where, in plain words."""

    code: str  # BREAK_DUE | DRIVE_CLOCK | SHIFT_CLOCK | CYCLE_CLOCK
    message: str
    mile_marker: float  # miles into the route where it happens
    clock_name: str  # "break" | "drive" | "shift" | "cycle"


@dataclass(frozen=True)
class Projection:
    """The verdict on one driver running one route."""

    legal: bool  # True iff rules.check_plan found zero violations
    flags: Tuple[PreViolationFlag, ...]
    drive_hrs: float
    onduty_hrs: float
    breaks_inserted: int
    usage: PlanUsage = field(repr=False)


def _death_mile(
    remaining_hrs: float,
    consumed_before: float,
    rate_per_mile: float,
    miles_done: float,
) -> float:
    """Mile marker where a clock hits zero inside the current leg."""
    if rate_per_mile <= 0:
        return miles_done
    return miles_done + max(0.0, remaining_hrs - consumed_before) / rate_per_mile


def project(clock: DriverClock, route: RoutePlan) -> Projection:
    """Project a driver's clocks against a route. Advisory, never binding."""
    flags: List[PreViolationFlag] = []
    segments: List[float] = []
    segment_limits: List[float] = []

    miles_done = 0.0
    drive_cum = 0.0  # driving hours so far
    onduty = 0.0  # on-duty hours so far (drive + dwell + breaks)
    seg_drive = 0.0  # driving hours since the last 30-min break
    break_budget = clock.break_remaining_hrs  # fresh 8h after each break
    breaks = 0

    for leg in route.legs:
        leg_drive = leg.miles / route.avg_mph

        # --- 30-minute break insertion: drive in chunks that fit the budget.
        remaining = leg_drive
        offset = 0.0  # miles into this leg already accounted
        breaks_this_leg = 0
        while remaining > EPS_HRS:
            room = break_budget - seg_drive
            chunk = min(remaining, room if room > EPS_HRS else 0.0)
            if chunk <= EPS_HRS:
                # The stretch runs out right here: break now.
                marker = miles_done + offset
                flags.append(
                    PreViolationFlag(
                        code="BREAK_DUE",
                        message=(
                            "take the 30-minute break at mile %d — the "
                            "driving stretch runs out there"
                            % round(marker)
                        ),
                        mile_marker=marker,
                        clock_name="break",
                    )
                )
                segments.append(seg_drive)
                segment_limits.append(break_budget)
                seg_drive = 0.0
                break_budget = BREAK_DRIVE_WINDOW_HRS  # a taken break earns 8 fresh hours
                # NOTE: the break's 0.5h is NOT added to onduty here — it is
                # counted once via breaks_this_leg in leg_onduty below.
                breaks += 1
                breaks_this_leg += 1
                continue
            remaining -= chunk
            offset += chunk * route.avg_mph
            seg_drive += chunk

        # --- Clock deaths inside this leg, earliest first.
        # Breaks inserted above sit inside the 14h window / 70h cycle.
        leg_onduty = leg_drive + leg.dwell_hrs + breaks_this_leg * BREAK_HRS
        drive_rate = 1.0 / route.avg_mph  # drive-hours per mile
        onduty_rate = leg_onduty / leg.miles if leg.miles else 0.0

        deaths = []  # (mile_marker, code, message, clock_name)
        if drive_cum + leg_drive - clock.drive_remaining_hrs > EPS_HRS:
            deaths.append(
                (
                    _death_mile(
                        clock.drive_remaining_hrs, drive_cum, drive_rate, miles_done
                    ),
                    "DRIVE_CLOCK",
                    "this plan burns your 11-hour drive clock at mile %d",
                    "drive",
                )
            )
        if onduty + leg_onduty - clock.shift_remaining_hrs > EPS_HRS:
            deaths.append(
                (
                    _death_mile(
                        clock.shift_remaining_hrs, onduty, onduty_rate, miles_done
                    ),
                    "SHIFT_CLOCK",
                    "this plan burns your 14-hour window at mile %d",
                    "shift",
                )
            )
        if onduty + leg_onduty - clock.cycle_remaining_hrs > EPS_HRS:
            deaths.append(
                (
                    _death_mile(
                        clock.cycle_remaining_hrs, onduty, onduty_rate, miles_done
                    ),
                    "CYCLE_CLOCK",
                    "your 70-hour 8-day cycle runs out at mile %d of this plan",
                    "cycle",
                )
            )
        for marker, code, template, clock_name in sorted(deaths):
            flags.append(
                PreViolationFlag(
                    code=code,
                    message=template % round(marker),
                    mile_marker=marker,
                    clock_name=clock_name,
                )
            )

        # Advance through the whole leg either way: flags stay complete so
        # the driver sees every death, not just the first.
        drive_cum += leg_drive
        onduty += leg_onduty
        miles_done += leg.miles

    segments.append(seg_drive)
    segment_limits.append(break_budget)
    usage = PlanUsage(
        drive_hrs=drive_cum,
        onduty_hrs=onduty,
        drive_segments=tuple(segments),
        segment_limits=tuple(segment_limits),
    )
    violations = check_plan(clock, usage)
    hard = any(
        f.code in ("DRIVE_CLOCK", "SHIFT_CLOCK", "CYCLE_CLOCK") for f in flags
    )
    legal = not violations and not hard
    # The two paths must agree on every projection: the checker is the
    # verdict of record; the simulator's flags must tell the same story.
    assert legal == (not violations), (
        "simulator/checker disagreement: flags=%r violations=%r"
        % ([f.code for f in flags], [v.code for v in violations])
    )
    return Projection(
        legal=legal,
        flags=tuple(sorted(flags, key=lambda f: f.mile_marker)),
        drive_hrs=drive_cum,
        onduty_hrs=onduty,
        breaks_inserted=breaks,
        usage=usage,
    )
