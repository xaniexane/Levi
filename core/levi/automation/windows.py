"""Windows — maintenance-window gating for automations.

Heavy automation flows (backups, bulk syncs, repo sweeps) should not fire
during focus hours. A window spec like::

    "Mon-Fri 22:00-06:00; Sat,Sun"

parses into :class:`Window` objects — day sets plus one or more daily
time ranges, overnight wrap supported. :class:`WindowSet` answers
:func:`allows` ("is now inside any window?") and :func:`next_allowed`
("when does the next window open?"), both pure functions over naive
local datetimes. :func:`gate` wraps the decision for a named flow with a
plain-language reason, suitable for logging or a HITL prompt.

Parsing is strict and deny-closed: a malformed spec raises
:class:`WindowError` instead of guessing. Times are local wall-clock;
``24:00`` is not a time and neither is ``Mon-Friday``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

__all__ = [
    "WindowError",
    "Window",
    "WindowSet",
    "parse_window",
    "parse_windows",
    "gate",
    "DAY_NAMES",
    "main",
]

DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


class WindowError(ValueError):
    """A window spec that refuses to parse — deny-closed, never guessed."""


# ---------------------------------------------------------------- parsing

_DAY_RE = r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)"
_TIME_RE = r"([01]\d|2[0-3]):([0-5]\d)"


def _parse_days(text: str) -> Set[int]:
    """`Mon`, `Mon-Fri`, `Sat,Sun`, `Mon,Wed,Fri` -> weekday numbers."""
    days: Set[int] = set()
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            lo, hi = (p.strip() for p in chunk.split("-", 1))
            if lo not in DAY_NAMES or hi not in DAY_NAMES:
                raise WindowError(f"bad day range: {chunk!r}")
            i, j = DAY_NAMES.index(lo), DAY_NAMES.index(hi)
            if j < i:  # wrap: Fri-Mon
                rng = list(range(i, 7)) + list(range(0, j + 1))
            else:
                rng = list(range(i, j + 1))
            days.update(rng)
        else:
            if chunk not in DAY_NAMES:
                raise WindowError(f"bad day name: {chunk!r}")
            days.add(DAY_NAMES.index(chunk))
    if not days:
        raise WindowError(f"no days in: {text!r}")
    return days


def _parse_time(text: str) -> int:
    """`22:00` -> minutes since midnight."""
    m = re.fullmatch(_TIME_RE, text.strip())
    if not m:
        raise WindowError(f"bad time: {text!r} (want HH:MM 24h)")
    return int(m.group(1)) * 60 + int(m.group(2))


def _parse_ranges(text: str) -> List[Tuple[int, int]]:
    """`22:00-06:00, 12:00-13:00` -> [(1320, 360), (720, 780)]."""
    ranges: List[Tuple[int, int]] = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split("-", 1)
        if len(parts) != 2:
            raise WindowError(f"bad time range: {chunk!r} (want HH:MM-HH:MM)")
        start, end = _parse_time(parts[0]), _parse_time(parts[1])
        if start == end:
            raise WindowError(f"zero-length range: {chunk!r}")
        ranges.append((start, end))
    if not ranges:
        raise WindowError(f"no time ranges in: {text!r}")
    return ranges


def parse_window(spec: str) -> "Window":
    """Parse one window: `<days> <ranges>`, e.g. `Mon-Fri 22:00-06:00`.

    The time part is optional — `Sat,Sun` means the whole weekend.
    """
    spec = spec.strip()
    if not spec:
        raise WindowError("empty window spec")
    parts = spec.split(None, 1)
    days = _parse_days(parts[0])
    ranges = _parse_ranges(parts[1]) if len(parts) > 1 else [(0, 24 * 60)]
    return Window(days=days, ranges=ranges)


def parse_windows(spec: str) -> "WindowSet":
    """Parse `;`-separated windows into a :class:`WindowSet`."""
    windows = [parse_window(p) for p in spec.split(";") if p.strip()]
    if not windows:
        raise WindowError("no windows in spec")
    return WindowSet(windows=windows)


# ---------------------------------------------------------------- windows


@dataclass
class Window:
    """One maintenance window: a day set plus daily time ranges."""

    days: Set[int] = field(default_factory=set)
    ranges: List[Tuple[int, int]] = field(default_factory=lambda: [(0, 24 * 60)])

    def contains(self, dt: datetime) -> bool:
        minutes = dt.hour * 60 + dt.minute
        weekday = dt.weekday()
        for start, end in self.ranges:
            if start < end:
                if weekday in self.days and start <= minutes < end:
                    return True
            else:  # overnight wrap: 22:00-06:00 covers two calendar days
                if weekday in self.days and minutes >= start:
                    return True
                prev = (weekday - 1) % 7
                if prev in self.days and minutes < end:
                    return True
        return False

    def describe(self) -> str:
        day_list = ",".join(DAY_NAMES[d] for d in sorted(self.days))
        parts = []
        for start, end in self.ranges:
            fmt = lambda m: f"{m // 60:02d}:{m % 60:02d}"  # noqa: E731
            parts.append(f"{fmt(start)}-{fmt(end)}")
        return f"{day_list} {','.join(parts)}"


@dataclass
class WindowSet:
    """The union of one or more windows."""

    windows: List[Window] = field(default_factory=list)

    def allows(self, dt: Optional[datetime] = None) -> bool:
        dt = datetime.now() if dt is None else dt
        return any(w.contains(dt) for w in self.windows)

    def next_allowed(
        self,
        dt: Optional[datetime] = None,
        step_minutes: int = 5,
        horizon_hours: int = 168,
    ) -> Optional[datetime]:
        """First time >= dt inside a window, or None past the horizon."""
        dt = datetime.now() if dt is None else dt
        if self.allows(dt):
            return dt
        probe = dt + timedelta(minutes=step_minutes)
        deadline = dt + timedelta(hours=horizon_hours)
        while probe <= deadline:
            if self.allows(probe):
                return probe.replace(second=0, microsecond=0)
            probe += timedelta(minutes=step_minutes)
        return None

    def describe(self) -> str:
        return "; ".join(w.describe() for w in self.windows)


# ----------------------------------------------------------------- gate


def gate(
    name: str,
    spec: str,
    dt: Optional[datetime] = None,
) -> Dict[str, object]:
    """Decide whether flow ``name`` may run under window spec ``spec``."""
    dt = datetime.now() if dt is None else dt
    try:
        windows = parse_windows(spec)
    except WindowError as exc:
        return {
            "flow": name,
            "decision": "denied",
            "reason": f"unparseable window spec: {exc}",
            "at": dt.isoformat(),
            "next_allowed": None,
        }
    if windows.allows(dt):
        return {
            "flow": name,
            "decision": "allowed",
            "reason": f"inside window: {windows.describe()}",
            "at": dt.isoformat(),
            "next_allowed": dt.isoformat(),
        }
    nxt = windows.next_allowed(dt)
    return {
        "flow": name,
        "decision": "deferred",
        "reason": f"outside window: {windows.describe()}",
        "at": dt.isoformat(),
        "next_allowed": None if nxt is None else nxt.isoformat(),
    }


# ------------------------------------------------------------------ cli


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="levi.automation.windows", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    check_p = sub.add_parser("check", help="is now (or --at) inside the window?")
    check_p.add_argument("spec", help='e.g. "Mon-Fri 22:00-06:00; Sat,Sun"')
    check_p.add_argument("--at", default=None, help="ISO datetime, default now")

    gate_p = sub.add_parser("gate", help="gate a named flow on a window spec")
    gate_p.add_argument("flow")
    gate_p.add_argument("spec")
    gate_p.add_argument("--at", default=None)

    args = ap.parse_args(argv)
    dt = datetime.fromisoformat(args.at) if getattr(args, "at", None) else None

    if args.cmd == "check":
        import json

        windows = parse_windows(args.spec)
        probe = dt or datetime.now()
        print(
            json.dumps(
                {
                    "allows": windows.allows(probe),
                    "windows": windows.describe(),
                    "at": probe.isoformat(),
                },
                indent=2,
            )
        )
    elif args.cmd == "gate":
        import json

        print(json.dumps(gate(args.flow, args.spec, dt), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
