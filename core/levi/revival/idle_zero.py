"""idle_zero — the CGI-style idle-zero process model, as a real supervisor.

Studied from: hybrid-cost-cutting-combos-20260916-0006 report.md (section 4,
the cited analog: processes not currently being served consume no resources
— the old analog for scale-to-zero).

Functional pattern studied: instead of an always-on worker pool, a
supervisor starts a worker only when a request arrives and reaps it after
it has been idle past a timeout. Idle cost is exactly zero — no resident
processes, no warm memory — at the price of cold-start latency per request.

What this module is: a working local supervisor. ``IdleZeroSupervisor``
registers named workers (either a Python callable or a subprocess argv),
``serve(name, payload)`` spawns the worker on demand if none is alive,
delivers the payload, records the completion time, and ``reap()`` kills
workers idle longer than ``idle_timeout_s``. ``stats()`` reports spawns,
serves, reaps, and current residency so the operator can see the
idle-zero trade directly.

Honest limits: cold start is real — ``serve()`` pays spawn latency when no
worker is resident, and this module reports it (see ``last_cold_start_s``)
rather than hiding it. Callable workers run in-process (no isolation);
subprocess workers get real OS isolation. Resource accounting is
counts-and-timings, not cgroup metering.

This is an original, from-scratch implementation for LEVI. Not artificial.
Synthetic.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Union

ORIGIN = "levi-revival/idle-zero"

WorkerSpec = Union[Callable[[Any], Any], List[str]]


@dataclass
class WorkerState:
    name: str
    spec: WorkerSpec
    process: Optional[subprocess.Popen] = None
    last_served_at: float = 0.0
    serves: int = 0
    spawns: int = 0
    cold_starts: int = 0
    last_cold_start_s: float = 0.0

    @property
    def resident(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None

    @property
    def is_subprocess(self) -> bool:
        return isinstance(self.spec, list)


class IdleZeroSupervisor:
    """Spawn-on-demand, reap-when-idle worker supervision."""

    def __init__(self, idle_timeout_s: float = 60.0) -> None:
        if idle_timeout_s <= 0:
            raise ValueError("idle_timeout_s must be positive")
        self.idle_timeout_s = idle_timeout_s
        self._workers: Dict[str, WorkerState] = {}
        self.total_reaps = 0

    def register(self, name: str, spec: WorkerSpec) -> None:
        """Register a worker: a callable ``f(payload) -> result`` or a
        subprocess argv list (the payload is passed on stdin as text)."""
        if name in self._workers:
            raise ValueError(f"worker already registered: {name}")
        if not callable(spec) and not (
            isinstance(spec, list) and spec and all(isinstance(a, str) for a in spec)
        ):
            raise ValueError("spec must be a callable or a non-empty argv list")
        self._workers[name] = WorkerState(name=name, spec=spec)

    def _spawn(self, state: WorkerState) -> None:
        started = time.monotonic()
        if state.is_subprocess:
            assert isinstance(state.spec, list)
            state.process = subprocess.Popen(
                state.spec,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        # Callable workers need no spawn; "cold start" is still counted when
        # the worker was previously reaped (i.e. never served or long idle).
        state.spawns += 1
        state.cold_starts += 1
        state.last_cold_start_s = time.monotonic() - started

    def _ensure_live(self, state: WorkerState) -> None:
        if state.is_subprocess and not state.resident:
            self._kill(state)
            self._spawn(state)
        elif not state.is_subprocess and state.last_served_at == 0.0:
            # First use counts as the cold start for in-process callables.
            self._spawn(state)

    def serve(self, name: str, payload: Any, timeout_s: float = 30.0) -> Any:
        """Deliver one request, spawning the worker if needed. Returns the
        worker's result."""
        state = self._workers[name]  # KeyError for unknown workers: honest
        self._ensure_live(state)
        if state.is_subprocess:
            assert isinstance(state.spec, list) and state.process is not None
            assert state.process.stdin is not None and state.process.stdout is not None
            try:
                state.process.stdin.write(str(payload) + "\n")
                state.process.stdin.flush()
                line = state.process.stdout.readline()
            except (BrokenPipeError, OSError):
                # Worker died mid-request: respawn once and retry.
                self._kill(state)
                self._spawn(state)
                assert state.process is not None
                state.process.stdin.write(str(payload) + "\n")  # type: ignore[union-attr]
                state.process.stdin.flush()  # type: ignore[union-attr]
                line = state.process.stdout.readline()  # type: ignore[union-attr]
            result: Any = line.rstrip("\n")
        else:
            assert callable(state.spec)
            result = state.spec(payload)
        state.last_served_at = time.monotonic()
        state.serves += 1
        return result

    def reap(self, now: Optional[float] = None) -> List[str]:
        """Kill workers idle past the timeout. Returns reaped names."""
        now = time.monotonic() if now is None else now
        reaped = []
        for state in self._workers.values():
            idle_for = (
                now - state.last_served_at if state.last_served_at else float("inf")
            )
            if state.last_served_at and idle_for >= self.idle_timeout_s:
                self._kill(state)
                state.last_served_at = 0.0  # next serve is a cold start again
                reaped.append(state.name)
                self.total_reaps += 1
        return reaped

    def _kill(self, state: WorkerState) -> None:
        proc, state.process = state.process, None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)

    def resident_workers(self) -> List[str]:
        return [
            s.name
            for s in self._workers.values()
            if s.resident or (not s.is_subprocess and s.last_served_at)
        ]

    def stats(self) -> Dict[str, Any]:
        return {
            name: {
                "serves": s.serves,
                "spawns": s.spawns,
                "cold_starts": s.cold_starts,
                "resident": name in self.resident_workers(),
            }
            for name, s in self._workers.items()
        } | {"total_reaps": self.total_reaps}

    def shutdown(self) -> None:
        for state in self._workers.values():
            self._kill(state)
