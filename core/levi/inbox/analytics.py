"""Local-first usage analytics — the joint instrument of three founders.

Canon: analytics IS the DemandPulse + Omnipulse + CyberPulse composite.
DemandPulse senses demand patterns (which capabilities the user actually
reaches for — where the need is). CyberPulse feels the organism's
telemetry (the pulse of what runs, the health of the body). Omnipulse
tracks lifecycles (usage across the 18-phase cycle clock — what persists,
what decays, what is reborn). This module is their joint instrument: the
recording surface and aggregate views through which the three founders'
signals become readable to the user.

The user owns their data. Events are recorded locally in
``~/.levi/inbox/usage-YYYY-MM-DD.jsonl`` (override with
``LEVI_INBOX_DIR``); nothing leaves the machine, no external
telemetry, ever. Only aggregate views exist: daily/weekly totals and
per-capability counts — the user reading their own patterns, not
surveillance.

An event records *what* ran (capability name) and *when*; it never
records message content, arguments, or secrets. Set
``LEVI_ANALYTICS_OFF=1`` to disable recording.

Recording never raises into callers: :func:`record` returns ``True``
on success, ``False`` on failure.

Stdlib only.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

_ENV_DIR = "LEVI_INBOX_DIR"
_ENV_OFF = "LEVI_ANALYTICS_OFF"

_DAY_RE = re.compile(r"^usage-(\d{4}-\d{2}-\d{2})\.jsonl$")
_CAP_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-/]{0,63}$")


def default_inbox_dir() -> Path:
    override = os.environ.get(_ENV_DIR, "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".levi" / "inbox"


def analytics_enabled() -> bool:
    """False when LEVI_ANALYTICS_OFF=1."""
    return os.environ.get(_ENV_OFF, "").strip() != "1"


def _ensure_dir(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(path, 0o700)
    except OSError:
        pass  # record() reports failure; never raise


def _append_line(path: Path, line: str) -> bool:
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            with os.fdopen(fd, "a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError:
            return False
        return True
    except OSError:
        return False


def record(capability: str, detail: str = "") -> bool:
    """Record one usage event. Never records content, args, or secrets."""
    if not analytics_enabled():
        return True
    capability = (capability or "").strip()
    if not _CAP_RE.match(capability):
        return False
    # detail is a short label (e.g. session name), never content.
    detail = re.sub(r"\s+", " ", (detail or "").strip())[:80]
    base = default_inbox_dir()
    _ensure_dir(base)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = base / f"usage-{day}.jsonl"
    event = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "capability": capability,
        "detail": detail,
    }
    return _append_line(path, json.dumps(event) + "\n")


def _iter_events(base: Path, days: Optional[List[str]] = None):
    try:
        files = sorted(base.glob("usage-*.jsonl"))
    except OSError:
        return
    for path in files:
        m = _DAY_RE.match(path.name)
        if not m:
            continue
        if days is not None and m.group(1) not in days:
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield m.group(1), json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue  # one bad line never aborts the query
        except OSError:
            continue


class Analytics:
    """Query surface over the local usage event log."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else default_inbox_dir()

    def daily(self, day: Optional[str] = None) -> Dict:
        """Aggregate for one day (UTC date, default today)."""
        day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        by_cap: Counter = Counter()
        total = 0
        for _, ev in _iter_events(self.base_dir, days=[day]):
            cap = ev.get("capability") if isinstance(ev, dict) else None
            if isinstance(cap, str) and cap:
                by_cap[cap] += 1
                total += 1
        return {
            "day": day,
            "total": total,
            "by_capability": dict(by_cap.most_common()),
        }

    def weekly(self) -> Dict:
        """Aggregate for the last 7 days (UTC)."""
        from datetime import timedelta

        today = datetime.now(timezone.utc).date()
        days = [(today - timedelta(days=i)).isoformat() for i in range(7)]
        by_cap: Counter = Counter()
        by_day: Counter = Counter()
        total = 0
        for day, ev in _iter_events(self.base_dir, days=days):
            cap = ev.get("capability") if isinstance(ev, dict) else None
            if isinstance(cap, str) and cap:
                by_cap[cap] += 1
                by_day[day] += 1
                total += 1
        return {
            "days": sorted(days),
            "total": total,
            "by_capability": dict(by_cap.most_common()),
            "by_day": {d: by_day.get(d, 0) for d in sorted(days)},
        }

    def top(self, n: int = 10, day: Optional[str] = None) -> List[Dict]:
        """Most-used capabilities, optionally for one day."""
        if day:
            agg = self.daily(day)
        else:
            agg = self.weekly()
        items = sorted(
            agg["by_capability"].items(), key=lambda kv: kv[1], reverse=True
        )
        return [
            {"capability": cap, "count": count} for cap, count in items[: max(1, n)]
        ]


def render_daily(summary: Dict) -> str:
    lines = [f"analytics — {summary['day']}: {summary['total']} events"]
    for cap, count in summary["by_capability"].items():
        lines.append(f"  {cap}: {count}")
    return "\n".join(lines) if summary["total"] else f"analytics — {summary['day']}: no events yet"


def render_weekly(summary: Dict) -> str:
    lines = [f"analytics — last 7 days: {summary['total']} events"]
    for cap, count in summary["by_capability"].items():
        lines.append(f"  {cap}: {count}")
    lines.append("per day:")
    for day, count in summary["by_day"].items():
        lines.append(f"  {day}: {count}")
    return "\n".join(lines) if summary["total"] else "analytics — no events in the last 7 days"
