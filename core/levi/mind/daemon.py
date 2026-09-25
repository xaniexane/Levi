"""Mind daemon control — start / stop / status for the runner.

Start is a proposer/verifier pair: the request proposes, the offline guard
verifies, and only a ``local`` verdict spawns the worker. Status is also a
pair: the pidfile and the worker's heartbeat must BOTH agree before the
daemon is reported ``running`` — one record alone is never trusted.

States are ternary: ``running`` / ``stopped`` / ``stale``. A pidfile with
no living process behind it gets its own name instead of being rounded
into either binary state.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from levi.mind import config as mind_config
from levi.mind import guard
from levi.mind.worker import HEARTBEAT_S

#: Heartbeat older than this (seconds) means the worker is gone or wedged.
STALE_AFTER_S = HEARTBEAT_S * 3

#: Exit codes. 2 is the guard refusal — distinct from a plain error (1).
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_REFUSED = 2

#: ``core/`` derived from this file's location, so the spawned worker always
#: finds the ``levi`` package no matter how the parent was launched.
_CORE_DIR = str(Path(__file__).resolve().parents[2])


def _child_env() -> dict:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = _CORE_DIR + (os.pathsep + existing if existing else "")
    return env


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_pid(home: Path) -> int | None:
    pid_file = home / mind_config.PID_FILE
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def _read_state(home: Path) -> dict[str, Any] | None:
    state_file = home / mind_config.STATE_FILE
    if not state_file.exists():
        return None
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _heartbeat_fresh(state: dict[str, Any] | None) -> bool:
    if not state:
        return False
    beat = state.get("heartbeat_at")
    if not isinstance(beat, (int, float)):
        return False
    return (time.time() - beat) <= STALE_AFTER_S


def status(home: Path | None = None) -> dict[str, Any]:
    """Ternary status. Never trusts a single record alone."""
    home = home or mind_config.mind_home()
    pid = _read_pid(home)
    if pid is None:
        return {"state": "stopped", "pid": None, "detail": "the mind is not running"}

    state = _read_state(home)
    if _pid_alive(pid) and _heartbeat_fresh(state):
        return {
            "state": "running",
            "pid": pid,
            "detail": f"the mind is awake (pid {pid}); pidfile and heartbeat agree",
            "heartbeat_age_s": round(time.time() - state["heartbeat_at"], 1),
        }

    # Stale: pidfile claims a mind that no longer answers. Clean it up and
    # say so plainly — this is the third state the binary view hides.
    try:
        (home / mind_config.PID_FILE).unlink(missing_ok=True)
    except OSError:
        pass
    why = "process gone" if not _pid_alive(pid) else "heartbeat stale"
    return {
        "state": "stale",
        "pid": pid,
        "detail": f"stale pidfile (pid {pid}, {why}); cleaned up",
    }


def start(home: Path | None = None, wait_s: float = 8.0) -> tuple[int, dict[str, Any]]:
    """Propose a start; the guard verifies; only then spawn."""
    home = home or mind_config.mind_home()

    try:
        cfg = mind_config.ensure(home)
    except ValueError as exc:
        report = guard.GuardReport(guard.Verdict.UNCERTAIN, [str(exc)])
        return EXIT_REFUSED, {
            "verdict": report.as_dict(),
            "state": "stopped",
            "detail": "config unreadable — failing closed; refusing to start",
        }

    verdict = guard.check(cfg)
    if not verdict.allowed:
        return EXIT_REFUSED, {
            "verdict": verdict.as_dict(),
            "state": "stopped",
            "detail": "offline-mandatory guard refused the start",
        }

    current = status(home)
    if current["state"] == "running":
        return EXIT_OK, {
            "verdict": verdict.as_dict(),
            **current,
            "detail": f"already awake (pid {current['pid']})",
        }

    log_path = home / mind_config.LOG_FILE
    with open(log_path, "ab") as log:
        proc = subprocess.Popen(  # noqa: S603
            [sys.executable, "-m", "levi.mind.worker", "--home", str(home)],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
            env=_child_env(),
        )
    _atomic_write(home / mind_config.PID_FILE, str(proc.pid))

    # Paired confirmation: don't claim "running" until the worker's own
    # heartbeat lands. Deterministic upper bound, no infinite waits.
    deadline = time.time() + wait_s
    while time.time() < deadline:
        st = _read_state(home)
        if st and _pid_alive(proc.pid) and _heartbeat_fresh(st):
            return EXIT_OK, {
                "verdict": verdict.as_dict(),
                "state": "running",
                "pid": proc.pid,
                "detail": f"the mind is awake (pid {proc.pid}); guard verified local-only",
            }
        if not _pid_alive(proc.pid):
            (home / mind_config.PID_FILE).unlink(missing_ok=True)
            return EXIT_ERROR, {
                "verdict": verdict.as_dict(),
                "state": "stopped",
                "detail": f"worker (pid {proc.pid}) died before its first heartbeat; see {log_path}",
            }
        time.sleep(0.2)

    try:
        os.kill(proc.pid, signal.SIGKILL)
    except OSError:
        pass
    (home / mind_config.PID_FILE).unlink(missing_ok=True)
    return EXIT_ERROR, {
        "verdict": verdict.as_dict(),
        "state": "stopped",
        "detail": "worker did not heartbeat in time; start aborted, no mind running",
    }


def stop(home: Path | None = None, wait_s: float = 5.0) -> tuple[int, dict[str, Any]]:
    home = home or mind_config.mind_home()
    pid = _read_pid(home)
    if pid is None:
        return EXIT_OK, {"state": "stopped", "detail": "already stopped"}

    if not _pid_alive(pid):
        (home / mind_config.PID_FILE).unlink(missing_ok=True)
        return EXIT_OK, {
            "state": "stopped",
            "pid": pid,
            "detail": f"stale pidfile (pid {pid}); process already gone, cleaned up",
        }

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass

    deadline = time.time() + wait_s
    while time.time() < deadline:
        if not _pid_alive(pid):
            break
        time.sleep(0.2)
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

    (home / mind_config.PID_FILE).unlink(missing_ok=True)
    return EXIT_OK, {
        "state": "stopped",
        "pid": pid,
        "detail": f"the mind (pid {pid}) is down; pidfile removed",
    }
