"""supervise — OTP supervision trees around LEVI's long-running services.

Wraps the Erlang/OTP-style ``Supervisor`` from ``levi.revival.otp`` around
three local services:

- ``levi-heartbeat`` — the periodic self-check (``levi.daemon.heartbeat``)
- ``levi-growth``    — the growth loop cycle (``levi.growth.cycle``)
- ``levi-automation``— due scheduled bot automations (``levi.daemon.automation``)

Everything here is an adapter: this module never edits the daemon, bot, or
growth code. Service callables are resolved lazily at child start time, so
importing this module never imports LEVI service modules (a broken service
module surfaces as an ordinary child crash — restarted per strategy, reported
in crash reports, never a silent fallback).

Supervision is LOCAL-ONLY: it restarts Python-level service loops. It never
retries remote calls, places orders, or sends messages. Crash reports are
persisted under ``~/.levi/perpetual/crashes/``; a live supervisor refreshes
an alive-marker so the ``pulse`` view can prove the engine is running.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from levi.revival.otp import ChildSpec, Supervisor

ALIVE_MARKER = "supervisor.alive"
STARTED_AT = "started_at"
CRASH_DIR = "crashes"
ALIVE_STALE_S = 120.0


def perpetual_home(home: "str | os.PathLike[str] | None" = None) -> Path:
    """Directory holding perpetual-engine state. ``home`` is the HOME dir."""
    base = Path(home) if home is not None else Path(os.path.expanduser("~"))
    return base / ".levi" / "perpetual"


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def _write_private(path: Path, data: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


# ------------------------------------------------------- service adapters
# Each adapter runs as an OTP child target: ``fn(stop_event)``. Exceptions
# propagate and become crashes (restarted per strategy). Adapters resolve
# the real service lazily so this module imports cleanly even when a service
# module is broken.


def _heartbeat_loop(stop_event: threading.Event, interval_s: float = 3600.0) -> None:
    from levi.daemon.heartbeat import run_heartbeat

    while not stop_event.is_set():
        run_heartbeat(force=True)
        stop_event.wait(interval_s)


def _growth_loop(stop_event: threading.Event, interval_s: float = 21600.0) -> None:
    from levi.growth.cycle import run_cycle

    while not stop_event.is_set():
        # Offline-safe: the supervised growth tick never requires a model.
        # A model-assisted reflection happens in interactive sessions.
        run_cycle(use_model=False)
        stop_event.wait(interval_s)


def _due_schedule_automations() -> List[str]:
    """Run ACTIVE+SCHEDULE automations whose interval has elapsed.

    Only automations with a parseable ``interval_min`` in trigger_config are
    ever run. Anything else is skipped — never run blindly.
    Returns the ids that were run.
    """
    from levi.daemon.automation import AutomationRegistry, AutomationStatus, TriggerKind

    reg = AutomationRegistry()
    now = datetime.now(timezone.utc)
    ran: List[str] = []
    for auto in reg.list():
        if auto.status is not AutomationStatus.ACTIVE:
            continue
        if auto.trigger is not TriggerKind.SCHEDULE:
            continue
        interval_min = auto.trigger_config.get("interval_min")
        if not isinstance(interval_min, (int, float)) or interval_min <= 0:
            continue  # no parseable schedule: skip, never run blindly
        last = auto.last_run
        due = True
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                due = (now - last_dt).total_seconds() >= interval_min * 60
            except ValueError:
                due = True  # unparseable last_run: treat as due, run_manual logs
        if due:
            reg.run_manual(auto.id)
            ran.append(auto.id)
    return ran


def _automation_loop(stop_event: threading.Event, interval_s: float = 300.0) -> None:
    while not stop_event.is_set():
        _due_schedule_automations()
        stop_event.wait(interval_s)


SERVICE_ADAPTERS: Dict[str, Callable[[threading.Event], None]] = {
    "levi-heartbeat": _heartbeat_loop,
    "levi-growth": _growth_loop,
    "levi-automation": _automation_loop,
}


def build_supervisor(
    clock: Callable[[], float] = time.monotonic,
    intervals: Optional[Dict[str, float]] = None,
) -> Supervisor:
    """Build (not start) the OTP supervisor for LEVI's local services."""
    intervals = intervals or {}
    specs = [
        ChildSpec(
            name=name,
            target=adapter,
            kwargs=({"interval_s": intervals[name]} if name in intervals else {}),
            restart_mode="permanent",
            max_restarts=5,
            restart_window=300.0,
            shutdown_timeout=10.0,
        )
        for name, adapter in SERVICE_ADAPTERS.items()
    ]
    return Supervisor(specs, strategy="one_for_one", clock=clock)


# ------------------------------------------------------- crash persistence


def persist_crash_reports(
    sup: Supervisor,
    home: "str | os.PathLike[str] | None" = None,
    since: float = 0.0,
) -> int:
    """Append new crash reports to ``crashes/``. Returns reports written."""
    crash_dir = _ensure_dir(perpetual_home(home) / CRASH_DIR)
    written = 0
    for rep in sup.crash_reports():
        if rep.at <= since:
            continue
        fname = "crash-%s-%s-%d.json" % (
            rep.child,
            datetime.fromtimestamp(rep.at, timezone.utc).strftime("%Y%m%dT%H%M%S"),
            rep.restart_count,
        )
        payload = {
            "child": rep.child,
            "exc_type": rep.exc_type,
            "message": rep.message,
            "traceback": rep.traceback,
            "at": rep.at,
            "at_iso": datetime.fromtimestamp(rep.at, timezone.utc).isoformat(),
            "restart_count": rep.restart_count,
        }
        _write_private(crash_dir / fname, json.dumps(payload, indent=2))
        written += 1
    return written


def load_crash_reports(
    home: "str | os.PathLike[str] | None" = None,
) -> List[Dict[str, Any]]:
    """Load persisted crash reports, newest last. Empty list if none."""
    crash_dir = perpetual_home(home) / CRASH_DIR
    if not crash_dir.is_dir():
        return []
    out: List[Dict[str, Any]] = []
    for path in sorted(crash_dir.glob("crash-*.json")):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue  # corrupt report file: skip, never crash the pulse
    return out


# ------------------------------------------------------- alive marker


def write_alive_marker(
    home: "str | os.PathLike[str] | None" = None,
    now: Optional[float] = None,
) -> None:
    marker = _ensure_dir(perpetual_home(home)) / ALIVE_MARKER
    _write_private(
        marker,
        json.dumps(
            {
                "pid": os.getpid(),
                "at": now if now is not None else time.time(),
                "at_iso": datetime.now(timezone.utc).isoformat(),
            }
        ),
    )


def read_alive_marker(
    home: "str | os.PathLike[str] | None" = None,
    now: Optional[float] = None,
    stale_s: float = ALIVE_STALE_S,
) -> Dict[str, Any]:
    """Read the supervisor alive marker.

    Returns ``{"running": bool, ...}``. ``running`` is False when no marker
    exists or it is older than ``stale_s`` — a dead supervisor must never
    look alive.
    """
    marker = perpetual_home(home) / ALIVE_MARKER
    at_now = now if now is not None else time.time()
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        age = at_now - float(data.get("at", 0))
    except (OSError, ValueError, TypeError, KeyError):
        return {"running": False, "reason": "no-marker"}
    if age > stale_s:
        return {
            "running": False,
            "reason": "stale",
            "age_s": age,
            "pid": data.get("pid"),
        }
    return {"running": True, "age_s": age, "pid": data.get("pid")}


def write_started_at(
    home: "str | os.PathLike[str] | None" = None,
    now: Optional[float] = None,
) -> None:
    at = now if now is not None else time.time()
    _write_private(
        _ensure_dir(perpetual_home(home)) / STARTED_AT,
        datetime.fromtimestamp(at, timezone.utc).isoformat(),
    )


def read_started_at(
    home: "str | os.PathLike[str] | None" = None,
) -> Optional[str]:
    try:
        return (perpetual_home(home) / STARTED_AT).read_text(encoding="utf-8").strip()
    except OSError:
        return None


# ------------------------------------------------------- run forever


def run_forever(
    home: "str | os.PathLike[str] | None" = None,
    tick_s: float = 5.0,
    alive_every_s: float = 30.0,
    stop_after_s: Optional[float] = None,
) -> None:
    """Start the supervisor and keep it alive until interrupted.

    ``stop_after_s`` is a test/maintenance hatch — the real daemon runs
    until SIGTERM/SIGINT. Crash reports are persisted continuously so a
    killed supervisor loses nothing.
    """
    base = _ensure_dir(perpetual_home(home))
    write_started_at(home)
    sup = build_supervisor().start(start_monitor=True)
    last_persisted = 0.0
    last_alive = 0.0
    started = time.monotonic()
    try:
        while True:
            now_mono = time.monotonic()
            if stop_after_s is not None and now_mono - started >= stop_after_s:
                break
            if now_mono - last_alive >= alive_every_s:
                write_alive_marker(home)
                last_alive = now_mono
            last_persisted = _drain_crashes(sup, home, last_persisted)
            if sup.gave_up is not None:
                # Restart intensity exhausted: stop honestly, don't spin.
                break
            time.sleep(tick_s)
    except KeyboardInterrupt:
        pass
    finally:
        _drain_crashes(sup, home, last_persisted)
        sup.shutdown()
        # Remove the marker so a stopped engine never looks alive.
        try:
            (base / ALIVE_MARKER).unlink()
        except OSError:
            pass


def _drain_crashes(sup: Supervisor, home, last_persisted: float) -> float:
    reports = sup.crash_reports()
    if reports:
        persist_crash_reports(sup, home, since=last_persisted)
        return max(r.at for r in reports)
    return last_persisted


def service_overview(
    home: "str | os.PathLike[str] | None" = None,
) -> Dict[str, Any]:
    """Static view for the CLI: configured services + persisted crashes."""
    crashes = load_crash_reports(home)
    by_child: Dict[str, int] = {}
    for rep in crashes:
        by_child[rep.get("child", "?")] = by_child.get(rep.get("child", "?"), 0) + 1
    return {
        "services": sorted(SERVICE_ADAPTERS),
        "strategy": "one_for_one",
        "alive": read_alive_marker(home),
        "crash_counts": by_child,
        "crashes_total": len(crashes),
    }
