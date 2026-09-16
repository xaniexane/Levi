"""revival/otp.py — Erlang/OTP-style supervision trees for LEVI's local services.

Revival of: Erlang/OTP supervision (Joe Armstrong et al., 1990s).

Why it matters: OTP supervisors are one of computing's best reliability ideas.
Services are arranged in supervision trees: a supervisor watches child workers
and restarts them when they crash — "let it crash". Business logic stays simple
because it never has to handle its own failure modes; the supervisor owns
restarts, restart-rate limits, and graceful shutdown.

LEVI adaptation — supervision is for LOCAL services only: heartbeats, queue
consumers, watchers, local model runners. It never retries remote calls, places
orders, or sends messages. No autonomous outbound actions beyond existing LEVI
policy.

Design:
- ``ChildSpec``: declarative child description (name, target callable, args,
  restart mode, restart-intensity limits, shutdown timeout).
- ``Supervisor``: restart strategies ``one_for_one`` / ``one_for_all`` /
  ``rest_for_one``, exactly as in OTP.
- Restart intensity: ``max_restarts`` restarts inside ``restart_window``
  seconds; exceeding it means the supervisor GIVES UP — it shuts down
  gracefully and reports, mirroring OTP. A supervisor that restarts a broken
  child forever is a bug, not resilience.
- ``CrashReport``: every crash is logged structurally (child, exception,
  traceback, restart count).
- Steppable core: call ``start(start_monitor=False)`` and drive ``tick()``
  yourself (deterministic tests), or let the monitor thread drive it.

Honest limits:
- Threads, not processes or Erlang actors: a segfaulting native extension
  takes the supervisor with it. This is supervision for Python-level failures.
- No hot code upgrades, no distributed nodes — that would require OTP itself.
"""

from __future__ import annotations

import threading
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class Strategy(str, Enum):
    ONE_FOR_ONE = "one_for_one"
    ONE_FOR_ALL = "one_for_all"
    REST_FOR_ONE = "rest_for_one"


class ChildState(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"  # clean exit (transient) or supervisor shutdown
    DEFUNCT = "defunct"  # gave up: exceeded restart intensity


class ChildExitedNormally(Exception):
    """Marker used when a 'permanent' child returns instead of crashing."""


@dataclass
class ChildSpec:
    """Declarative description of one supervised child.

    ``target`` is a callable invoked as ``target(stop_event, *args, **kwargs)``
    in its own thread. It should loop until ``stop_event.is_set()``.
    ``restart_mode``: ``"permanent"`` (always restart, even on clean exit) or
    ``"transient"`` (restart only on exception).
    """

    name: str
    target: Callable[..., None]
    args: tuple = ()
    kwargs: Dict[str, Any] = field(default_factory=dict)
    restart_mode: str = "permanent"
    max_restarts: int = 3
    restart_window: float = 5.0
    shutdown_timeout: float = 5.0

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise ValueError("ChildSpec.name must be a non-empty string")
        if not callable(self.target):
            raise ValueError("ChildSpec.target must be callable")
        if self.restart_mode not in ("permanent", "transient"):
            raise ValueError("restart_mode must be 'permanent' or 'transient'")
        if self.max_restarts < 0:
            raise ValueError("max_restarts must be >= 0")
        if self.restart_window <= 0:
            raise ValueError("restart_window must be > 0")


@dataclass
class CrashReport:
    child: str
    exc_type: str
    message: str
    traceback: str
    at: float
    restart_count: int

    def summary(self) -> str:
        return (
            f"[{self.child}] {self.exc_type}: {self.message} "
            f"(restart #{self.restart_count})"
        )


class _ChildRuntime:
    __slots__ = (
        "spec",
        "thread",
        "stop_event",
        "state",
        "restarts",
        "crashes",
        "pending_exc",
        "clean_exit",
        "alive_since",
    )

    def __init__(self, spec: ChildSpec) -> None:
        self.spec = spec
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.state = ChildState.STOPPED
        self.restarts: List[float] = []
        self.crashes: List[CrashReport] = []
        self.pending_exc: Optional[BaseException] = None
        self.clean_exit = False
        self.alive_since: Optional[float] = None


class Supervisor:
    """OTP-style supervisor for local worker callables."""

    def __init__(
        self,
        specs: List[ChildSpec],
        strategy: str = "one_for_one",
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        try:
            self._strategy = Strategy(strategy)
        except ValueError:
            raise ValueError(
                f"unknown strategy {strategy!r}; "
                "choose one_for_one, one_for_all, rest_for_one"
            ) from None
        names = [s.name for s in specs]
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate child names: {names}")
        self._specs = list(specs)
        self._runtimes: Dict[str, _ChildRuntime] = {
            s.name: _ChildRuntime(s) for s in specs
        }
        self._order = [s.name for s in specs]  # start order (matters for rest_for_one)
        self._clock = clock
        self._lock = threading.RLock()
        self._shutdown = False
        self._gave_up: Optional[str] = None
        self._monitor: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ API
    def start(self, start_monitor: bool = True) -> "Supervisor":
        """Start all children in spec order; optionally start monitor thread."""
        with self._lock:
            if self._shutdown:
                raise RuntimeError("supervisor already shut down")
            for name in self._order:
                self._start_child(self._runtimes[name])
            if start_monitor and self._monitor is None:
                self._monitor = threading.Thread(
                    target=self._monitor_loop,
                    name="otp-supervisor-monitor",
                    daemon=True,
                )
                self._monitor.start()
        return self

    def tick(self) -> None:
        """One supervision step: detect dead children, restart per strategy.

        The deterministic core — drive it manually in tests instead of using
        the monitor thread.
        """
        with self._lock:
            if self._shutdown:
                return
            for name in self._order:
                rt = self._runtimes[name]
                if rt.state is not ChildState.RUNNING:
                    continue
                if rt.alive_since is None:
                    continue  # thread not entered yet; not a crash
                if rt.stop_event.is_set():
                    continue  # we are stopping it ourselves
                if rt.thread is not None and rt.thread.is_alive():
                    continue
                self._handle_death(rt)

    def shutdown(self, timeout: Optional[float] = None) -> None:
        """Graceful shutdown: signal every child, join with timeout."""
        with self._lock:
            if self._shutdown:
                return
            self._shutdown = True
            runtimes = list(self._runtimes.values())
        for rt in runtimes:
            rt.stop_event.set()
        for rt in runtimes:
            t = rt.thread
            if t is not None and t.is_alive():
                t.join(timeout if timeout is not None else rt.spec.shutdown_timeout)
        with self._lock:
            for rt in runtimes:
                if rt.state is not ChildState.DEFUNCT:
                    rt.state = ChildState.STOPPED
            mon = self._monitor
        if mon is not None and mon.is_alive() and mon is not threading.current_thread():
            mon.join(timeout=2.0)

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "strategy": self._strategy.value,
                "shutdown": self._shutdown,
                "gave_up": self._gave_up,
                "children": {
                    name: {
                        "state": rt.state.value,
                        "restarts": len(rt.restarts),
                        "crashes": len(rt.crashes),
                        "alive": rt.thread.is_alive() if rt.thread else False,
                    }
                    for name, rt in self._runtimes.items()
                },
            }

    @property
    def gave_up(self) -> Optional[str]:
        """Name of the child whose restart intensity exhausted, if any."""
        return self._gave_up

    def crash_reports(self, child: Optional[str] = None) -> List[CrashReport]:
        with self._lock:
            rts = [self._runtimes[child]] if child else self._runtimes.values()
            out: List[CrashReport] = []
            for rt in rts:
                out.extend(rt.crashes)
            return sorted(out, key=lambda r: r.at)

    # -------------------------------------------------------------- internals
    def _start_child(self, rt: _ChildRuntime) -> None:
        rt.stop_event = threading.Event()
        rt.pending_exc = None
        rt.clean_exit = False
        rt.alive_since = None
        rt.state = ChildState.RUNNING
        rt.thread = threading.Thread(
            target=self._run_child,
            args=(rt,),
            name=f"otp-child-{rt.spec.name}",
            daemon=True,
        )
        rt.thread.start()

    def _run_child(self, rt: _ChildRuntime) -> None:
        rt.alive_since = self._clock()
        try:
            rt.spec.target(rt.stop_event, *rt.spec.args, **rt.spec.kwargs)
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:  # "let it crash": record, supervisor decides
            rt.pending_exc = exc
        else:
            if rt.spec.restart_mode == "permanent":
                rt.pending_exc = ChildExitedNormally(
                    f"child {rt.spec.name!r} exited normally but is permanent"
                )
            else:
                rt.clean_exit = True
        # thread ends; tick()/monitor notices

    def _handle_death(self, rt: _ChildRuntime) -> None:
        now = self._clock()
        exc = rt.pending_exc
        rt.pending_exc = None
        if exc is None and rt.clean_exit:
            rt.state = ChildState.STOPPED  # transient child done; nothing to do
            rt.clean_exit = False
            return
        if exc is None:  # pragma: no cover - defensive
            exc = ChildExitedNormally("child thread died without a recorded cause")
        rt.crashes.append(
            CrashReport(
                child=rt.spec.name,
                exc_type=type(exc).__name__,
                message=str(exc),
                traceback="".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__)
                ),
                at=now,
                restart_count=len(rt.restarts) + 1,
            )
        )
        # restart intensity: sliding window
        rt.restarts = [t for t in rt.restarts if now - t <= rt.spec.restart_window]
        rt.restarts.append(now)
        if len(rt.restarts) > rt.spec.max_restarts:
            rt.state = ChildState.DEFUNCT
            self._gave_up = rt.spec.name
            self._shutdown = True  # supervisor terminates itself, OTP-style
            for other in self._runtimes.values():
                if other is not rt and other.state is ChildState.RUNNING:
                    other.stop_event.set()
                    other.state = ChildState.STOPPED
            return
        # restart per strategy
        if self._strategy is Strategy.ONE_FOR_ONE:
            self._start_child(rt)
        elif self._strategy is Strategy.ONE_FOR_ALL:
            self._stop_all_running()
            for name in self._order:
                self._start_child(self._runtimes[name])
        else:  # REST_FOR_ONE: crashed child + everything started after it
            idx = self._order.index(rt.spec.name)
            for name in self._order[idx:]:
                other = self._runtimes[name]
                if other.state is ChildState.RUNNING:
                    other.stop_event.set()
                    other.state = ChildState.STOPPED
            for name in self._order[idx:]:
                self._start_child(self._runtimes[name])

    def _stop_all_running(self) -> None:
        for rt in self._runtimes.values():
            if rt.state is ChildState.RUNNING:
                rt.stop_event.set()
                rt.state = ChildState.STOPPED

    def _monitor_loop(self) -> None:
        while not self._shutdown:
            try:
                self.tick()
            except Exception:  # supervisor must not die on monitor bugs
                pass
            time.sleep(0.05)


def lazy_levi_target(dotted: str, *args: Any, **kwargs: Any) -> Callable[..., None]:
    """Build a child target that lazily imports a LEVI callable at start time.

    ``dotted`` like ``"levi.daemon.heartbeat:run"`` resolves to a callable
    taking ``(stop_event, *args, **kwargs)`` inside the child thread. Import
    happens lazily so importing this module never imports LEVI modules, and no
    edits to existing modules are needed. If the import fails, the failure
    surfaces as an ordinary child crash (restarted per strategy) — honest
    degradation, reported in crash reports, not a silent fallback.
    """

    def _target(stop_event: threading.Event) -> None:
        mod_name, _, attr = dotted.partition(":")
        if not attr:
            raise ValueError(f"dotted target must be 'module:attr', got {dotted!r}")
        try:
            import importlib

            mod = importlib.import_module(mod_name)
        except Exception as exc:
            raise RuntimeError(f"lazy import failed for {mod_name!r}: {exc}") from exc
        fn = getattr(mod, attr, None)
        if not callable(fn):
            raise RuntimeError(f"{dotted!r} is not a callable")
        fn(stop_event, *args, **kwargs)

    _target.__name__ = f"lazy_levi_target({dotted})"
    return _target


# ------------------------------------------------------------------- demo
def _heartbeat_worker(stop_event: threading.Event, beats: List[float]) -> None:
    while not stop_event.is_set():
        beats.append(time.monotonic())
        stop_event.wait(0.05)


def _queue_consumer(stop_event: threading.Event, queue, consumed: List[Any]) -> None:
    import queue as _q

    while not stop_event.is_set():
        try:
            consumed.append(queue.get(timeout=0.05))
        except _q.Empty:
            continue


def demo() -> Dict[str, Any]:
    """Supervise a heartbeat checker + queue consumer; return final status."""
    import queue as _q

    beats: List[float] = []
    consumed: List[Any] = []
    q: _q.Queue = _q.Queue()
    sup = Supervisor(
        [
            ChildSpec("heartbeat", _heartbeat_worker, args=(beats,)),
            ChildSpec("consumer", _queue_consumer, args=(q, consumed)),
        ],
        strategy="one_for_one",
    ).start()
    try:
        for i in range(3):
            q.put(f"msg-{i}")
        time.sleep(0.4)
        # crash the consumer on purpose: kill its thread's work by poison
        sup.tick()
    finally:
        sup.shutdown()
    return {
        "status": sup.status(),
        "beats": len(beats),
        "consumed": consumed,
    }


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(demo(), indent=2, default=str))
