"""LEVI's per-application private namespace stacks: the skill-confinement
discipline (built on plan9).

Inspired by Inferno (Bell Labs, 1996 — Blaze et al.; commercial from
Lucent/Vita Nuova). The ahead-of-its-time mechanism: everything (devices,
networks, services, files) exposed through a uniform per-process
namespace via Styx/9P; the Dis VM ran type-safe Limbo bytecode; resources
mounted and unmounted locally or remotely identically. It died for lack of
commercial workstation traction; its ideas were absorbed into Plan 9/9P
use.

Remix delta: Inferno's per-process namespaces reimagined as LEVI's
*skill-confinement* discipline — not an OS clone. Each task assembles an
ad-hoc namespace of mounted services and unmounts it when the task ends,
so a skill literally cannot name a service it was not granted; inner
scopes shadow outer ones (a true stack). Built directly on
revival.plan9's Namespace/Channel primitives rather than reimplementing
isolation — the improvement is composition, not duplication. No Dis VM
(handlers are plain Python callables), no remote mounts; the mount
*protocol* is what transfers.

This is an original, from-scratch reimplementation for LEVI — no Inferno
code is used — and it is deliberately built ON TOP OF
:mod:`levi.revival.plan9` rather than duplicating it:

- plan9 provides the primitives: ``Namespace`` (per-task execution
  isolation) and ``Channel``/``serve`` (9P-style message passing over a
  loopback socketpair — NOT a real 9P server).
- inferno adds the *namespace discipline*: per-application **private
  mount stacks**. Each task assembles its own mount table of named
  services; names resolve only through that table; inner scopes shadow
  outer ones (a true stack); everything unmounts when the task ends, so
  skills never see services they were not explicitly granted.

The LEVI application: each "skill" is a mounted service; the assistant
assembles an ad-hoc namespace per task and unmounts it after — a skill
literally cannot name a service that is not mounted in its namespace.
Deny-closed: resolving an unmounted name raises; nothing is mounted by
default.

Honesty: LOAD-BEARING — per-task namespaces as a confinement discipline.
What is NOT revived: the Dis VM / Limbo bytecode (no bytecode execution
here — handlers are plain Python callables), and remote mounting (all
services here are in-process; the mount *protocol* is what transfers).
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from levi.revival import plan9


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class NamespaceError(Exception):
    """Base class for namespace-stack failures."""


class UnknownService(NamespaceError):
    """The name is not mounted in this namespace stack (deny-closed)."""


class MountConflict(NamespaceError):
    """The name is already mounted at this stack level."""


# ---------------------------------------------------------------------------
# Mount tables and application namespaces
# ---------------------------------------------------------------------------


class MountTable:
    """One level of the stack: names bound to 9P-style service servers."""

    def __init__(self):
        self._services: dict[str, plan9.ServedChannel] = {}

    def bind(self, name: str,
             handler: Callable[[str, Any], Any],
             request_types: Optional[set[str]] = None) -> None:
        """Mount a service: ``handler(msg_type, payload)`` served on a
        background plan9 channel. Raises :class:`MountConflict` if the name
        is already bound at this level."""
        if not name or not name.strip():
            raise ValueError("service name must be non-empty")
        if name in self._services:
            raise MountConflict(f"service {name!r} is already mounted here")
        served = plan9.serve_in_background(handler, request_types=request_types)
        self._services[name] = served

    def unbind(self, name: str) -> None:
        try:
            served = self._services.pop(name)
        except KeyError:
            raise UnknownService(f"service {name!r} is not mounted") from None
        served.stop()

    def resolve(self, name: str) -> plan9.Channel:
        try:
            return self._services[name].client
        except KeyError:
            raise UnknownService(f"service {name!r} is not mounted") from None

    def names(self) -> list[str]:
        return sorted(self._services)

    def unbind_all(self) -> None:
        for name in list(self._services):
            self.unbind(name)


class AppNamespace:
    """A per-application private namespace: a stack of mount tables.

    ``AppNamespace(parent=...)`` creates a nested scope: name resolution
    walks up the stack, and a bind at an inner level shadows the outer
    one. Used as a context manager, all mounts made at this level are
    unmounted on exit — the ad-hoc namespace is torn down after the task.
    """

    def __init__(self, name: str, parent: Optional["AppNamespace"] = None):
        if not name or not name.strip():
            raise ValueError("namespace name must be non-empty")
        self.name = name.strip()
        self.parent = parent
        self.table = MountTable()

    # -- mounting ---------------------------------------------------------------
    def mount(self, name: str, handler: Callable[[str, Any], Any],
              request_types: Optional[set[str]] = None) -> None:
        self.table.bind(name, handler, request_types=request_types)

    def unmount(self, name: str) -> None:
        self.table.unbind(name)

    def child(self, name: str) -> "AppNamespace":
        """A nested namespace stacked on this one."""
        return AppNamespace(name, parent=self)

    # -- resolution (walks up the stack) --------------------------------------------
    def resolve(self, name: str) -> plan9.Channel:
        """Resolve ``name`` to a service channel, inner scope first."""
        scope: Optional[AppNamespace] = self
        while scope is not None:
            try:
                return scope.table.resolve(name)
            except UnknownService:
                scope = scope.parent
        raise UnknownService(
            f"service {name!r} is not mounted in namespace {self.name!r} "
            "or any enclosing scope")

    def mounted(self) -> list[str]:
        """All names visible from here (inner shadowing outer)."""
        seen: dict[str, None] = {}
        scope: Optional[AppNamespace] = self
        while scope is not None:
            for name in scope.table.names():
                seen.setdefault(name)
            scope = scope.parent
        return sorted(seen)

    def call(self, service: str, msg_type: str, payload: Any = None,
             timeout: float = 5.0) -> Any:
        """Resolve ``service`` and issue a 9P-style request."""
        return self.resolve(service).request(msg_type, payload, timeout=timeout)

    # -- context manager: unmount everything mounted here on exit -----------------------
    def __enter__(self) -> "AppNamespace":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.table.unbind_all()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"AppNamespace({self.name!r}, mounted={self.mounted()})"


def namespace(name: str) -> AppNamespace:
    """Create a top-level application namespace (use as a context manager)."""
    return AppNamespace(name)


__all__ = [
    "NamespaceError",
    "UnknownService",
    "MountConflict",
    "MountTable",
    "AppNamespace",
    "namespace",
]
