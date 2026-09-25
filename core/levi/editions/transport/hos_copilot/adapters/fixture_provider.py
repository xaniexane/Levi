"""Fixture provider: deterministic sample clocks.

Four realistic driver snapshots for development, demos, and tests —
no credentials, no network, no fleet. Every clock here is labeled
``source="fixture"`` so fixture data can never be mistaken for a live
ELD read.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Sequence

from ..clocks import DriverClock
from .base import HosProvider


def _at(minutes_ago: float, now: datetime) -> datetime:
    from datetime import timedelta

    return now - timedelta(minutes=minutes_ago)


class FixtureProvider(HosProvider):
    """Deterministic sample clocks. The only provider tests may touch."""

    provider_name = "fixture"
    required_scopes = ()

    def __init__(self, now: Optional[datetime] = None) -> None:
        self._now = now or datetime.now(timezone.utc)

    def get_clocks(
        self, driver_ids: Optional[Sequence[str]] = None
    ) -> List[DriverClock]:
        now = self._now
        clocks = [
            # Fresh off a 10-hour reset: the whole board is open.
            DriverClock(
                driver_id="d-001",
                captured_at=_at(4, now),
                drive_remaining_hrs=11.0,
                shift_remaining_hrs=14.0,
                break_remaining_hrs=8.0,
                cycle_remaining_hrs=70.0,
                source="fixture",
            ),
            # Mid-shift: break coming due in 3.5 driving hours.
            DriverClock(
                driver_id="d-002",
                captured_at=_at(11, now),
                drive_remaining_hrs=6.2,
                shift_remaining_hrs=7.1,
                break_remaining_hrs=3.5,
                cycle_remaining_hrs=41.0,
                source="fixture",
            ),
            # Near the limits: only short hops stay legal.
            DriverClock(
                driver_id="d-003",
                captured_at=_at(2, now),
                drive_remaining_hrs=1.2,
                shift_remaining_hrs=2.0,
                break_remaining_hrs=1.2,
                cycle_remaining_hrs=8.5,
                source="fixture",
            ),
            # Break overdue soon: 0.4 driving hours to the 30-min break.
            DriverClock(
                driver_id="d-004",
                captured_at=_at(7, now),
                drive_remaining_hrs=9.5,
                shift_remaining_hrs=11.0,
                break_remaining_hrs=0.4,
                cycle_remaining_hrs=55.0,
                source="fixture",
            ),
        ]
        if driver_ids is None:
            return clocks
        wanted = set(driver_ids)
        return [c for c in clocks if c.driver_id in wanted]
