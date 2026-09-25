"""HOS co-pilot: the driver's clock, projected against the plan.

Reads ELD clock snapshots (read-only, fleet's own credentials), projects
the driver's remaining hours against a planned route, and flags
violations *before* they happen — e.g. "this plan burns your 14 at
mile 612 — break at mile 540."

Advisory only: flags go to driver/dispatcher; humans own the clock.
Stdlib only.
"""

from __future__ import annotations

from .adapters import (
    FixtureProvider,
    HosProvider,
    MotiveProvider,
    NotConfiguredError,
    PayloadSchemaError,
    ProviderError,
    SamsaraProvider,
)
from .clocks import DriverClock
from .projection import (
    PreViolationFlag,
    Projection,
    RouteLeg,
    RoutePlan,
    project,
)
from .refusals import Refusal, check_request
from .rules import (
    BREAK_DRIVE_WINDOW_HRS,
    BREAK_MIN_MINUTES,
    CYCLE_LIMIT_HRS,
    CYCLE_LOOKBACK_DAYS,
    DRIVE_LIMIT_HRS,
    SHIFT_WINDOW_HRS,
    PlanUsage,
    Violation,
    check_plan,
)
from .shortlist import Candidate, LoadOffer, Shortlist, build_shortlist

__all__ = [
    "DriverClock",
    "RouteLeg",
    "RoutePlan",
    "PreViolationFlag",
    "Projection",
    "project",
    "PlanUsage",
    "Violation",
    "check_plan",
    "DRIVE_LIMIT_HRS",
    "SHIFT_WINDOW_HRS",
    "BREAK_DRIVE_WINDOW_HRS",
    "BREAK_MIN_MINUTES",
    "CYCLE_LIMIT_HRS",
    "CYCLE_LOOKBACK_DAYS",
    "LoadOffer",
    "Candidate",
    "Shortlist",
    "build_shortlist",
    "Refusal",
    "check_request",
    "HosProvider",
    "MotiveProvider",
    "SamsaraProvider",
    "FixtureProvider",
    "ProviderError",
    "NotConfiguredError",
    "PayloadSchemaError",
]
