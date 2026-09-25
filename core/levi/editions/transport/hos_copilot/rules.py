"""FMCSA HOS rules as checked logic — not advice.

The four headline rules, enforced by :func:`check_plan` against a
:class:`DriverClock` and a :class:`PlanUsage`. This is the independent
checker: the projector (``projection.py``) simulates the route, and this
module renders the verdict. The two must agree — property-tested.

Break model, stated plainly: the first driving stretch may run at most
``clock.break_remaining_hrs``; every stretch after a 30-minute break
gets a fresh 8 hours. The projector records each stretch's limit in
``PlanUsage.segment_limits`` so the checker verifies the same contract
the simulator drove.

Simplified model (honestly labeled): sleeper-berth splits, adverse
driving conditions, short-haul exceptions, and state variations are
NOT modeled. Stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .clocks import DriverClock

#: Headline FMCSA limits (hours, unless noted).
DRIVE_LIMIT_HRS = 11.0
SHIFT_WINDOW_HRS = 14.0
BREAK_DRIVE_WINDOW_HRS = 8.0
BREAK_MIN_MINUTES = 30
CYCLE_LIMIT_HRS = 70.0
CYCLE_LOOKBACK_DAYS = 8

#: Floating-point slack for clock comparisons (hours).
EPS_HRS = 1e-6


@dataclass(frozen=True)
class PlanUsage:
    """What a projected plan consumes, in hours."""

    drive_hrs: float  # total driving time
    onduty_hrs: float  # driving + dwell + inserted breaks (breaks sit in the 14h window)
    drive_segments: Tuple[float, ...]  # driving hours between 30-min breaks
    segment_limits: Tuple[float, ...]  # max legal hours per segment, same order


@dataclass(frozen=True)
class Violation:
    code: str  # DRIVE_LIMIT | SHIFT_WINDOW | BREAK_REQUIRED | CYCLE_LIMIT
    message: str


def check_plan(clock: DriverClock, usage: PlanUsage) -> Tuple[Violation, ...]:
    """Render the verdict: every rule the plan would break, or none.

    Empty tuple means the plan is legally runnable against these clocks.
    This never approves — it only refuses to find violations. The caller
    decides what a clean check means (advisory display, shortlist filter).
    """
    violations = []

    if usage.drive_hrs - clock.drive_remaining_hrs > EPS_HRS:
        violations.append(
            Violation(
                "DRIVE_LIMIT",
                "plan drives %.2fh but only %.2fh of the 11-hour drive "
                "clock remain" % (usage.drive_hrs, clock.drive_remaining_hrs),
            )
        )

    if usage.onduty_hrs - clock.shift_remaining_hrs > EPS_HRS:
        violations.append(
            Violation(
                "SHIFT_WINDOW",
                "plan needs %.2fh on duty but only %.2fh of the 14-hour "
                "window remain" % (usage.onduty_hrs, clock.shift_remaining_hrs),
            )
        )

    if len(usage.drive_segments) != len(usage.segment_limits):
        violations.append(
            Violation(
                "BREAK_REQUIRED",
                "internal error: %d driving segments but %d segment limits"
                % (len(usage.drive_segments), len(usage.segment_limits)),
            )
        )
    else:
        for i, (segment, limit) in enumerate(
            zip(usage.drive_segments, usage.segment_limits)
        ):
            if segment - limit > EPS_HRS:
                violations.append(
                    Violation(
                        "BREAK_REQUIRED",
                        "driving stretch %d runs %.2fh; its limit is %.2fh "
                        "— a 30-minute break is due first"
                        % (i + 1, segment, limit),
                    )
                )
                break  # one break violation is enough to fail the plan

    if usage.onduty_hrs - clock.cycle_remaining_hrs > EPS_HRS:
        violations.append(
            Violation(
                "CYCLE_LIMIT",
                "plan needs %.2fh on duty but only %.2fh of the 70-hour "
                "8-day cycle remain"
                % (usage.onduty_hrs, clock.cycle_remaining_hrs),
            )
        )

    return tuple(violations)
