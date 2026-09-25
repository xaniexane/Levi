"""pulse — the one-glance proof that LEVI never stopped.

Aggregates, read-only, from every perpetual subsystem:

- supervisor alive-marker + uptime (``supervise``)
- service crash counts (persisted crash reports)
- archive record count and growth (``~/.levi/archive/``)
- hunt state: waves completed, last hunt, next due, overdue?
- token budgets remaining (``levi.governor``)
- build queue depth (findings waiting to be built)

Every source degrades honestly: a missing subsystem is reported as
``"unavailable"`` with a reason, never as zero and never as an exception.
(Distinct from ``levi.pulse``, which is the periodic self-check that runs
*as* a supervised service — this module is the *view* of the whole engine.)
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from levi.perpetual import hunt, supervise


def _archive_stats(home) -> Dict[str, Any]:
    """Count archive records without depending on the archive store API.

    The archive builder is still landing its store module; count whatever
    durable record files exist and say exactly what was counted.
    """
    arch = (
        Path(home if home is not None else os.path.expanduser("~"))
        / ".levi"
        / "archive"
    )
    if not arch.is_dir():
        return {"status": "not-initialized", "records": 0}
    total = 0
    sources: Dict[str, int] = {}
    for path in sorted(arch.rglob("*.jsonl")):
        try:
            n = sum(
                1
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        except OSError:
            continue
        # Only count files that look like record stores, not logs.
        name = path.name.lower()
        if "record" in name or "pending" in name or path.parent.name == "pending":
            total += n
            sources[str(path.relative_to(arch))] = n
    pending = hunt.pending_waves(home)
    return {
        "status": "ok" if total else "empty",
        "records": total,
        "sources": sources,
        "pending_waves": pending,
    }


def _budgets(home) -> Dict[str, Any]:
    try:
        from levi.governor import BudgetEnforcer
    except Exception as exc:  # governor missing/broken: honest, not fatal
        return {"status": "unavailable", "reason": str(exc)[:120]}
    try:
        enforcer = BudgetEnforcer(home=home)
        return {"status": "ok", "remaining": enforcer.remaining()}
    except Exception as exc:
        return {"status": "unavailable", "reason": str(exc)[:120]}


def _hunt_summary(home, now: float) -> Dict[str, Any]:
    try:
        state = hunt.load_state(home)
    except ValueError as exc:
        return {"status": "corrupt", "reason": str(exc)[:120]}
    completed = [w for w in state.waves if w.status == "completed"]
    last = max(completed, key=lambda w: w.completed_at or "") if completed else None
    overdue: Optional[bool] = None
    if state.next_due:
        try:
            due_dt = datetime.fromisoformat(state.next_due)
            if due_dt.tzinfo is None:
                due_dt = due_dt.replace(tzinfo=timezone.utc)
            overdue = datetime.fromtimestamp(now, timezone.utc) > due_dt
        except ValueError:
            overdue = None
    return {
        "status": "ok",
        "waves_completed": len(completed),
        "last_wave": last.id if last else None,
        "last_completed_at": last.completed_at if last else None,
        "last_findings": last.findings_count if last else 0,
        "next_due": state.next_due or None,
        "overdue": overdue,
    }


def read_pulse(
    home: "str | os.PathLike[str] | None" = None, now: Optional[float] = None
) -> Dict[str, Any]:
    """Read the full proof-of-life snapshot. Never raises for missing data."""
    now = now if now is not None else time.time()
    alive = supervise.read_alive_marker(home, now=now)
    started_at = supervise.read_started_at(home)
    uptime_s: Optional[float] = None
    if started_at:
        try:
            dt = datetime.fromisoformat(started_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            uptime_s = max(0.0, now - dt.timestamp())
        except ValueError:
            uptime_s = None
    crashes = supervise.load_crash_reports(home)
    crash_counts: Dict[str, int] = {}
    for rep in crashes:
        child = str(rep.get("child", "?"))
        crash_counts[child] = crash_counts.get(child, 0) + 1
    build_queue = hunt.read_build_queue(home)
    return {
        "at": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        "engine_running": alive.get("running", False),
        "engine_detail": alive,
        "started_at": started_at,
        "uptime_s": uptime_s,
        "services": sorted(supervise.SERVICE_ADAPTERS),
        "crashes_total": len(crashes),
        "crash_counts": crash_counts,
        "archive": _archive_stats(home),
        "hunts": _hunt_summary(home, now),
        "budgets": _budgets(home),
        "build_queue_depth": len(build_queue),
    }


def _fmt_uptime(uptime_s: Optional[float]) -> str:
    if uptime_s is None:
        return "unknown"
    days, rem = divmod(int(uptime_s), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return "%dd %dh" % (days, hours)
    if hours:
        return "%dh %dm" % (hours, minutes)
    return "%dm" % minutes


def format_pulse(p: Dict[str, Any]) -> str:
    """Render the snapshot as a one-glance text block."""
    lines = []
    eng = "ALIVE" if p["engine_running"] else "NOT RUNNING"
    lines.append(
        "LEVI perpetual engine: %s  (uptime %s)" % (eng, _fmt_uptime(p["uptime_s"]))
    )
    lines.append("services: %s" % ", ".join(p["services"]))
    if p["crash_counts"]:
        lines.append(
            "crashes: %d total %s"
            % (
                p["crashes_total"],
                "{"
                + ", ".join("%s:%d" % kv for kv in sorted(p["crash_counts"].items()))
                + "}",
            )
        )
    else:
        lines.append("crashes: none recorded")
    arch = p["archive"]
    if arch["status"] == "not-initialized":
        lines.append("archive: not initialized yet")
    else:
        lines.append(
            "archive: %d records%s"
            % (
                arch["records"],
                " | pending waves: %s" % ", ".join(arch["pending_waves"])
                if arch.get("pending_waves")
                else "",
            )
        )
    h = p["hunts"]
    if h["status"] == "ok":
        due = h["next_due"] or "unscheduled"
        flag = "  OVERDUE" if h["overdue"] else ""
        lines.append(
            "hunts: %d waves completed | last %s (%d findings) | next due %s%s"
            % (h["waves_completed"], h["last_wave"], h["last_findings"], due, flag)
        )
    else:
        lines.append("hunts: %s" % h["status"])
    b = p["budgets"]
    if b["status"] == "ok":
        rem = b["remaining"]
        lines.append(
            "token budgets: %s" % ", ".join("%s:%s" % kv for kv in sorted(rem.items()))
        )
    else:
        lines.append("token budgets: unavailable (%s)" % b.get("reason", "?"))
    lines.append("build queue: %d findings waiting" % p["build_queue_depth"])
    return "\n".join(lines)
