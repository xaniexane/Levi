"""The mind daemon worker — the thing ``start`` wakes.

Milestone 1.1: the worker idles, owns the state file, and heartbeats. It is
the placeholder the brain will wake into — milestone 1.2 loads weights here.

Shape:
- claims ``mind.pid`` (written by the parent before exec)
- heartbeats ``mind.state.json`` every ``HEARTBEAT_S`` (atomic writes)
- on SIGTERM/SIGINT: writes a final "waking_down" state, then exits 0
- never opens a socket, never touches the network — there is no code path
  in this file that can
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

HEARTBEAT_S = 5

_stop = False


def _on_term(signum, frame):  # noqa: ARG001
    global _stop
    _stop = True


def _write_state(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)


def run(home: Path) -> int:
    state_path = home / "mind.state.json"
    pid = os.getpid()
    started = time.time()
    payload = {
        "phase": "waking",
        "pid": pid,
        "started_at": started,
        "heartbeat_at": time.time(),
        "weights_loaded": False,
        "note": "runner skeleton awake; brain weights load in milestone 1.2",
    }
    _write_state(state_path, payload)

    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGINT, _on_term)

    while not _stop:
        time.sleep(min(HEARTBEAT_S, 1.0))
        if _stop:
            break
        # Heartbeat at most every HEARTBEAT_S; cheap loop keeps signals responsive.
        if time.time() - payload["heartbeat_at"] >= HEARTBEAT_S:
            payload["heartbeat_at"] = time.time()
            _write_state(state_path, payload)

    payload["phase"] = "waking_down"
    payload["heartbeat_at"] = time.time()
    payload["stopped_at"] = time.time()
    _write_state(state_path, payload)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m levi.mind.worker")
    parser.add_argument("--home", required=True, help="mind home directory")
    args = parser.parse_args(argv)
    home = Path(args.home)
    home.mkdir(parents=True, exist_ok=True)
    return run(home)


if __name__ == "__main__":
    sys.exit(main())
