"""Watchdog for the v2 native-brain trainer — relaunch on silent death.

The trainer is a long CPU run; the session that spawned it can die without
it (the 2026-09-16 morning run died exactly this way). This supervisor is a
one-shot checker, meant to be invoked periodically (cron, systemd timer,
or a human), NOT a daemon: each invocation decides, acts at most once, and
exits.

Semantics (same as ``runs/<name>/LAUNCH.md``):

- Relaunch is the SAME command the launch doc prescribes: the trainer
  auto-resumes from the latest checkpoint in ``checkpoints/`` and refuses
  to resume if the config hash changed (config-hash gating lives in the
  trainer; this watchdog preserves it by never passing a different config).
- Relaunch is detached (new session) with stdout/stderr appended to the
  run's ``train.log``, exactly as ``nohup ... &`` would.

State lives in ``<run-dir>/watchdog.json`` (pid, restart count, event log).
A max-restart cap prevents infinite crash loops; every decision is logged,
plainly. Torch is never imported — stdlib only.

Exit codes: 0 = trainer alive (or just launched); 1 = cap reached /
cannot decide safely; 2 = bad arguments.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE_NAME = "watchdog.json"
DEFAULT_MAX_RESTARTS = 5

# Decision labels
OK = "ok"  # trainer alive; nothing to do
RESTART = "restart"  # dead (or never launched); relaunch under cap
CAP_REACHED = "cap_reached"  # dead but restart budget exhausted


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_state() -> dict:
    return {"pid": None, "restarts": 0, "events": []}


def load_state(path: str | Path) -> dict:
    """Load watchdog state; missing/corrupt files mean a fresh state, logged."""
    p = Path(path)
    if not p.is_file():
        return new_state()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return new_state()
        state = new_state()
        state.update({k: v for k, v in data.items() if k in state})
        if not isinstance(state["events"], list):
            state["events"] = []
        return state
    except (json.JSONDecodeError, OSError):
        return new_state()


def save_state(path: str | Path, state: dict) -> None:
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def record_event(state: dict, kind: str, detail: str) -> None:
    state.setdefault("events", []).append(
        {"at": utcnow(), "kind": kind, "detail": detail}
    )


def process_alive(pid: int | None) -> bool:
    """True if the pid exists right now (no signal sent). Never raises."""
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Exists but not ours — treat as alive (we cannot supervise it).
        return True
    except OSError:
        return False
    return True


def decide(state: dict, max_restarts: int, *, alive: bool) -> str:
    """Pure decision logic. ``alive`` is injected for hermetic testing."""
    if alive:
        return OK
    if state.get("restarts", 0) >= max_restarts:
        return CAP_REACHED
    return RESTART


def build_launch_cmd(
    python: str, repo_root: str | Path, config: str | Path, run_dir: str | Path
) -> list[str]:
    """The LAUNCH.md command as an argv list (no shell)."""
    return [
        python,
        "-m",
        "levi.brain.train.v2.trainer",
        "--config",
        str(config),
        "--run-dir",
        str(run_dir),
    ]


def launch(state_path: Path, python: str, repo_root: Path, config: Path,
           run_dir: Path, log_path: Path, state: dict) -> int:
    """Detach a trainer process; record pid + event. Returns the pid."""
    argv = build_launch_cmd(python, repo_root, config, run_dir)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root / "core") + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = log_path.open("ab")
    try:
        proc = subprocess.Popen(  # noqa: S603 — argv is operator-supplied
            argv,
            cwd=str(repo_root),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    finally:
        log_fh.close()
    pid = proc.pid
    state["pid"] = pid
    state["restarts"] = state.get("restarts", 0) + 1
    record_event(
        state,
        "restart",
        f"launched pid={pid} (restart #{state['restarts']}); "
        f"cmd={' '.join(argv)}; auto-resume + config-hash gate in trainer",
    )
    save_state(state_path, state)
    return pid


def check(
    run_dir: Path,
    repo_root: Path,
    config: Path,
    python: str,
    log_path: Path,
    state_path: Path,
    max_restarts: int,
) -> tuple[str, str]:
    """Run one supervision cycle. Returns (decision, message)."""
    state = load_state(state_path)
    alive = process_alive(state.get("pid"))
    decision = decide(state, max_restarts, alive=alive)
    if decision == OK:
        record_event(state, "check", f"trainer pid={state['pid']} alive")
        save_state(state_path, state)
        return OK, f"trainer alive (pid {state['pid']})"
    if decision == CAP_REACHED:
        detail = (
            f"trainer dead (last pid={state.get('pid')}); "
            f"restart budget exhausted ({state.get('restarts', 0)}/{max_restarts})"
        )
        record_event(state, "cap_reached", detail)
        save_state(state_path, state)
        return CAP_REACHED, detail + " — manual intervention required"
    # RESTART
    if not config.is_file():
        detail = f"refusing restart: config {config} missing"
        record_event(state, "refused", detail)
        save_state(state_path, state)
        return CAP_REACHED, detail
    pid = launch(state_path, python, repo_root, config, run_dir, log_path, state)
    return RESTART, f"relaunched trainer (pid {pid})"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", default=".", help="repo root (launch cwd)")
    ap.add_argument("--run-dir", required=True, help="training run directory")
    ap.add_argument("--config", required=True, help="trainer config yaml")
    ap.add_argument("--python", default=sys.executable,
                    help="python with torch (default: this interpreter)")
    ap.add_argument("--log", default="", help="trainer log (default: <run-dir>/train.log)")
    ap.add_argument("--state", default="", help="state file (default: <run-dir>/watchdog.json)")
    ap.add_argument("--max-restarts", type=int, default=DEFAULT_MAX_RESTARTS)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.max_restarts < 0:
        print("watchdog: --max-restarts must be >= 0")
        return 2
    run_dir = Path(args.run_dir)
    repo_root = Path(args.repo_root)
    config = Path(args.config)
    log_path = Path(args.log) if args.log else run_dir / "train.log"
    state_path = Path(args.state) if args.state else run_dir / STATE_NAME
    decision, message = check(run_dir, repo_root, config, args.python,
                              log_path, state_path, args.max_restarts)
    print(f"watchdog: {decision}: {message}")
    return 0 if decision in (OK, RESTART) else 1


if __name__ == "__main__":
    raise SystemExit(main())
