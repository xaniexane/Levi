"""LEVI's process tree — every process has a parent that answers for it.

Studied from: systems-internals survey (CAP computer, process-tree
section).

The mechanism, functionally: there are no separate kernel/user modes
here — supervision is direct parent-to-child. Every process is spawned
by a parent, and each parent declares a restart policy for its
children: ``none`` (let it die), ``one-for-one`` (restart just the
crashed child), or ``one-for-all`` (a crash restarts the child and all
its siblings). At spawn the parent hands down *capability registers* —
a small set of named rights the child may use; the child receives a
frozen copy and can never reach beyond what it was granted. Crashes
bubble to the parent, which applies its policy; a parent that dies
takes its whole subtree's supervision with it.

Honesty: in-process model. "Processes" are callables run by the tree;
a crash is an exception; restart re-invokes the callable. The
discipline — parent-owned supervision, granted-only capabilities — is
what transfers.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

ORIGIN = "levi-revival/proctree"

# Restart policies a parent may declare for its children.
NONE = "none"
ONE_FOR_ONE = "one-for-one"
ONE_FOR_ALL = "one-for-all"


class ProcError(Exception):
    """Base failure for process-tree operations."""


class Process:
    """A supervised process: a body, a parent, granted capabilities."""

    def __init__(
        self,
        pid: int,
        name: str,
        body: Callable[[Dict[str, Any]], Any],
        parent: Optional["Process"],
        caps: Dict[str, Any],
        policy: str = ONE_FOR_ONE,
        max_restarts: int = 3,
    ):
        self.pid = pid
        self.name = name
        self.body = body
        self.parent = parent
        self.caps = dict(caps)  # frozen at spawn; child cannot widen
        self.policy = policy
        self.max_restarts = max_restarts
        self.children: List["Process"] = []
        self.restarts = 0
        self.alive = False
        self.result: Any = None
        self.last_error: Optional[str] = None

    def grant(self, key: str) -> Any:
        """The child reaches only what the parent granted."""
        try:
            return self.caps[key]
        except KeyError:
            raise ProcError(
                f"process {self.name!r} was not granted capability {key!r}"
            ) from None

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Process(pid={self.pid}, name={self.name!r})"


class Tree:
    """The process tree: spawn, run, supervise."""

    def __init__(self) -> None:
        self._next_pid = 1
        self.roots: List[Process] = []
        self.events: List[str] = []

    def spawn(
        self,
        name: str,
        body: Callable[[Dict[str, Any]], Any],
        parent: Optional[Process] = None,
        caps: Optional[Dict[str, Any]] = None,
        policy: str = ONE_FOR_ONE,
        max_restarts: int = 3,
    ) -> Process:
        if policy not in (NONE, ONE_FOR_ONE, ONE_FOR_ALL):
            raise ProcError(f"unknown restart policy {policy!r}")
        proc = Process(
            pid=self._next_pid,
            name=name,
            body=body,
            parent=parent,
            caps=caps or {},
            policy=policy,
            max_restarts=max_restarts,
        )
        self._next_pid += 1
        if parent is None:
            self.roots.append(proc)
        else:
            parent.children.append(proc)
        self.events.append(f"spawned {name} (pid {proc.pid})")
        return proc

    # -- supervision ---------------------------------------------------
    def _run_one(self, proc: Process) -> bool:
        """Run a process once. Returns True if it completed cleanly."""
        proc.alive = True
        try:
            proc.result = proc.body(dict(proc.caps))
            proc.alive = False
            return True
        except Exception as exc:  # the crash the parent must answer for
            proc.alive = False
            proc.last_error = f"{type(exc).__name__}: {exc}"
            return False

    def _restart(self, proc: Process) -> None:
        proc.restarts += 1
        self.events.append(
            f"restarting {proc.name} (pid {proc.pid}, attempt {proc.restarts})"
        )

    def supervise(self, proc: Process) -> None:
        """Run a process under its policy; apply restarts on crash."""
        while True:
            ok = self._run_one(proc)
            if ok:
                self.events.append(f"{proc.name} exited cleanly")
                return
            self.events.append(f"{proc.name} crashed: {proc.last_error}")
            if proc.policy == NONE or proc.restarts >= proc.max_restarts:
                self.events.append(f"{proc.name} left dead by policy")
                return
            if proc.policy == ONE_FOR_ALL and proc.parent is not None:
                for sibling in proc.parent.children:
                    if sibling is not proc:
                        self._restart(sibling)
                        self.supervise(sibling)
            self._restart(proc)
            # loop: re-run the crashed child (one-for-one)

    def supervise_tree(self) -> None:
        """Supervise every root and its descendants depth-first."""
        for root in self.roots:
            self._supervise_subtree(root)

    def _supervise_subtree(self, proc: Process) -> None:
        self.supervise(proc)
        for child in proc.children:
            self._supervise_subtree(child)
