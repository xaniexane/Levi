"""LEVI's minikern — a whole local system in an API you can hold in your head.

Studied from: revival-50-more-20260916-0009/report-part1.md [entry #6]
(AtheOS/Syllable).

The studied lesson: a local system defined by a *small, object-oriented
API surface* that one team can fully own for a decade. This module is an
original, from-scratch expression of that lesson: ``MiniKernel``, a tiny
cooperative kernel whose entire public surface is the fixed tuple
``API_SURFACE`` — fourteen methods, no more. Cooperative tasks
(generators), named message ports with queues, and an in-memory file
system: the whole machine, ownable in an afternoon.

API surface (the whole of it — this list is the law):

    version()                 kernel name and version string
    spawn(name, gen, *args)    start a cooperative task; returns pid
    tasks()                   every task: pid, name, state
    kill(pid)                 terminate a task
    step()                    advance every ready task once; returns ran count
    run(max_steps=None)       step until no ready tasks (or the cap)
    open_port(name)           create a named message port
    close_port(name)          remove a port
    send(port, msg)           enqueue a message
    recv(port)                dequeue oldest message, or None
    write(path, text)         store a file
    read(path)                read a file
    listdir(dir="/")          list a directory
    delete(path)              remove a file

Honest limits, stated plainly: tasks are single-threaded generator
coroutines, not preemptive threads — a task that never yields never lets
go. The file system is in-memory; nothing persists unless you say so.
Ports are unbounded FIFO queues. Fourteen methods is a *choice*: small
enough to own, big enough to run small programs. A test pins
``API_SURFACE`` so the surface cannot silently grow.

Original, from-scratch implementation for LEVI. Local-first, stdlib
only, no network. Not artificial. Synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, Generator, List, Optional
from collections import deque

ORIGIN = "levi-revival/minimal-os"

#: The entire public API surface. The law: public methods of MiniKernel
#: are exactly these names, in this count, forever.
API_SURFACE = (
    "version",
    "spawn",
    "tasks",
    "kill",
    "step",
    "run",
    "open_port",
    "close_port",
    "send",
    "recv",
    "write",
    "read",
    "listdir",
    "delete",
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class KernelError(Exception):
    """Base class for minikern failures."""


class UnknownTask(KernelError):
    """A pid that isn't (or is no longer) a task."""

    def __init__(self, pid: int):
        super().__init__(f"no task with pid {pid}")
        self.pid = pid


class UnknownPort(KernelError):
    """A port name that isn't open."""

    def __init__(self, name: str):
        super().__init__(f"no open port {name!r}")
        self.name = name


class DuplicatePort(KernelError):
    """A port name opened twice."""

    def __init__(self, name: str):
        super().__init__(f"port {name!r} already open")
        self.name = name


class NotAFile(KernelError):
    """A read/write/delete named something that isn't a file."""

    def __init__(self, path: str):
        super().__init__(f"no file at {path!r}")
        self.path = path


class NotAGenerator(KernelError):
    """spawn was given something that isn't a generator function."""

    def __init__(self, name: str):
        super().__init__(f"task {name!r} must be a generator function")
        self.name = name


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@dataclass
class _Task:
    pid: int
    name: str
    gen: Generator
    state: str = "ready"  # ready | done | killed
    result: Any = None


# ---------------------------------------------------------------------------
# The kernel
# ---------------------------------------------------------------------------


class MiniKernel:
    """Fourteen methods. One ownable machine."""

    def __init__(self) -> None:
        self._tasks: Dict[int, _Task] = {}
        self._next_pid = 1
        self._ports: Dict[str, Deque[Any]] = {}
        self._files: Dict[str, str] = {}

    # -- identity ----------------------------------------------------------

    def version(self) -> str:
        """Kernel name and version."""
        return "levi-minikern 1.0"

    # -- tasks ---------------------------------------------------------------

    def spawn(self, name: str, gen_fn: Callable, *args: Any) -> int:
        """Start a cooperative task; returns its pid.

        ``gen_fn`` must be a generator function: the kernel advances it
        one ``next()`` per ``step()``. A task that never yields holds
        the machine — cooperation is the contract.
        """
        gen = gen_fn(*args)
        if not hasattr(gen, "__next__") or not hasattr(gen, "send"):
            raise NotAGenerator(name)
        # Reject plain values that merely quack: require a real generator.
        import types

        if not isinstance(gen, types.GeneratorType):
            raise NotAGenerator(name)
        pid = self._next_pid
        self._next_pid += 1
        self._tasks[pid] = _Task(pid, name, gen)
        return pid

    def tasks(self) -> List[Dict[str, Any]]:
        """Every task: pid, name, state."""
        return [
            {"pid": t.pid, "name": t.name, "state": t.state}
            for t in self._tasks.values()
        ]

    def kill(self, pid: int) -> None:
        """Terminate a task; a finished task cannot be killed twice."""
        task = self._tasks.get(pid)
        if task is None:
            raise UnknownTask(pid)
        if task.state != "ready":
            raise KernelError(f"task {pid} already {task.state}")
        task.state = "killed"
        task.gen.close()

    def step(self) -> int:
        """Advance every ready task by one yield; returns tasks run."""
        ran = 0
        for task in list(self._tasks.values()):
            if task.state != "ready":
                continue
            ran += 1
            try:
                next(task.gen)
            except StopIteration as done:
                task.state = "done"
                task.result = done.value
        return ran

    def run(self, max_steps: Optional[int] = None) -> int:
        """Step until no task is ready, or the step cap; returns steps."""
        steps = 0
        while any(t.state == "ready" for t in self._tasks.values()):
            if max_steps is not None and steps >= max_steps:
                break
            self.step()
            steps += 1
        return steps

    # -- message ports ---------------------------------------------------------

    def open_port(self, name: str) -> None:
        """Create a named message port."""
        if name in self._ports:
            raise DuplicatePort(name)
        self._ports[name] = deque()

    def close_port(self, name: str) -> None:
        """Remove a port and drop its queued messages."""
        if name not in self._ports:
            raise UnknownPort(name)
        del self._ports[name]

    def send(self, port: str, msg: Any) -> None:
        """Enqueue a message on a port."""
        queue = self._ports.get(port)
        if queue is None:
            raise UnknownPort(port)
        queue.append(msg)

    def recv(self, port: str) -> Optional[Any]:
        """Dequeue the oldest message, or None if the port is empty."""
        queue = self._ports.get(port)
        if queue is None:
            raise UnknownPort(port)
        return queue.popleft() if queue else None

    # -- file system (in-memory) -------------------------------------------------

    @staticmethod
    def _norm(path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        while "//" in path:
            path = path.replace("//", "/")
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        return path

    def write(self, path: str, text: str) -> None:
        """Store a file's full text."""
        self._files[self._norm(path)] = text

    def read(self, path: str) -> str:
        """Read a file's full text."""
        try:
            return self._files[self._norm(path)]
        except KeyError:
            raise NotAFile(path) from None

    def listdir(self, dir: str = "/") -> List[str]:
        """Names directly inside a directory."""
        prefix = self._norm(dir)
        if prefix != "/":
            prefix += "/"
        names = []
        for path in self._files:
            if path.startswith(prefix):
                rest = path[len(prefix) :]
                if rest and "/" not in rest:
                    names.append(rest)
        return sorted(names)

    def delete(self, path: str) -> None:
        """Remove a file."""
        normed = self._norm(path)
        if normed not in self._files:
            raise NotAFile(path)
        del self._files[normed]


def api_surface() -> List[str]:
    """The kernel's whole public surface, as a list."""
    return list(API_SURFACE)


__all__ = [
    "ORIGIN",
    "API_SURFACE",
    "KernelError",
    "UnknownTask",
    "UnknownPort",
    "DuplicatePort",
    "NotAFile",
    "NotAGenerator",
    "MiniKernel",
    "api_surface",
]
