"""Driver clock snapshots: what the ELD says right now.

A DriverClock is a point-in-time read of the four FMCSA clocks:
drive (11h), shift (14h), break (8h to 30-min break), cycle (70h/8-day).
Built from provider snapshots (Motive / Samsara) or fixtures — never
written back to the ELD. Stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class DriverClock:
    """Remaining hours on each HOS clock, as read from the ELD."""

    driver_id: str
    captured_at: datetime
    drive_remaining_hrs: float  # 11-hour driving limit, remaining
    shift_remaining_hrs: float  # 14-hour window, remaining
    break_remaining_hrs: float  # driving hrs before a 30-min break is due
    cycle_remaining_hrs: float  # 70-hour / 8-day cycle, remaining
    source: str = "fixture"  # "motive" | "samsara" | "fixture"

    def __post_init__(self) -> None:
        if not self.driver_id:
            raise ValueError("driver_id is required")
        if self.captured_at.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware")
        bounds = (
            ("drive_remaining_hrs", self.drive_remaining_hrs, 11.0),
            ("shift_remaining_hrs", self.shift_remaining_hrs, 14.0),
            ("break_remaining_hrs", self.break_remaining_hrs, 8.0),
            ("cycle_remaining_hrs", self.cycle_remaining_hrs, 70.0),
        )
        for name, value, ceiling in bounds:
            if not 0.0 <= value <= ceiling:
                raise ValueError(
                    "%s=%r out of range [0, %s]" % (name, value, ceiling)
                )
        if self.source not in ("motive", "samsara", "fixture"):
            raise ValueError("unknown clock source: %r" % (self.source,))

    def binding_limit(self):
        """The tightest clock: (name, remaining hours). The dispatch filter."""
        clocks = (
            ("drive", self.drive_remaining_hrs),
            ("shift", self.shift_remaining_hrs),
            ("break", self.break_remaining_hrs),
            ("cycle", self.cycle_remaining_hrs),
        )
        return min(clocks, key=lambda c: c[1])

    @classmethod
    def fresh(
        cls,
        driver_id: str,
        *,
        source: str = "fixture",
        captured_at: datetime | None = None,
    ) -> "DriverClock":
        """A driver starting a fresh 10-hour reset: all clocks full."""
        return cls(
            driver_id=driver_id,
            captured_at=captured_at or datetime.now(timezone.utc),
            drive_remaining_hrs=11.0,
            shift_remaining_hrs=14.0,
            break_remaining_hrs=8.0,
            cycle_remaining_hrs=70.0,
            source=source,
        )
