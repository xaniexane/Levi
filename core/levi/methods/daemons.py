"""Named daemon archetypes with an owns-wake-visible contract.

Origin: the 2026 "KAI-9000" method entry — every background responsibility is
a NAMED daemon with a three-part contract: OWNS (the one domain it owns),
WAKE (its schedule), VISIBLE (when it may surface). The commitment daemon
owns locks, the focus daemon owns deep-work integrity, the digest daemon owns
session summaries, the hygiene daemon owns memory cleanup — and no daemon may
leak into another's domain.

What it is in LEVI: ``DaemonRegistry``. Daemons register with an ``owns``
domain, a ``wake`` schedule, and a ``visible`` predicate. ``dispatch`` routes
a task to the daemon that owns its domain, or raises when no daemon owns it.
``surface`` lets a daemon raise its head only when its visible rule allows —
surfacing against the rule raises. The contract is enforced, not suggested.

Honesty label: LOAD-BEARING — named routing plus a checked visibility rule is
a concrete contract.

Deny-closed inputs: empty names, duplicate names, empty owns domains, owns
domains already owned by another daemon, empty wake schedules, non-callable
visible predicates, dispatching a domain no daemon owns, surfacing an unknown
daemon, and surfacing while the visible rule denies it are all rejected with
ValueError.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional

__all__ = ["Daemon", "DaemonRegistry"]


@dataclass
class Daemon:
    """One background responsibility: owns one domain, wakes on a schedule,
    may surface only when its visible rule allows."""

    name: str
    owns: str
    wake: str
    visible: Callable[[dict], bool] = field(repr=False)


class DaemonRegistry:
    """The owns-wake-visible contract, enforced at registration, dispatch,
    and surfacing time."""

    def __init__(self) -> None:
        self._daemons: dict[str, Daemon] = {}

    # -- registration -------------------------------------------------------
    def register(
        self,
        name: str,
        owns: str,
        wake: str,
        visible: Callable[[dict], bool],
    ) -> Daemon:
        """Register a daemon. ``owns`` must not collide with another daemon's
        domain — no daemon may leak into another's domain."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("daemon name must be a non-empty string")
        name = name.strip()
        if name in self._daemons:
            raise ValueError(f"duplicate daemon name: {name!r}")
        if not isinstance(owns, str) or not owns.strip():
            raise ValueError("owns: daemon must own a non-empty domain")
        owns = owns.strip()
        for other in self._daemons.values():
            if other.owns == owns:
                raise ValueError(
                    f"domain {owns!r} is already owned by daemon "
                    f"{other.name!r} — no daemon may leak into another's domain"
                )
        if not isinstance(wake, str) or not wake.strip():
            raise ValueError("wake: daemon needs a non-empty wake schedule")
        if not callable(visible):
            raise ValueError("visible: must be a callable taking a context dict")
        daemon = Daemon(name=name, owns=owns, wake=wake.strip(), visible=visible)
        self._daemons[name] = daemon
        return daemon

    def get(self, name: str) -> Daemon:
        daemon = self._daemons.get(name)
        if daemon is None:
            raise ValueError(f"unknown daemon: {name!r}")
        return daemon

    def daemons(self) -> list[Daemon]:
        return list(self._daemons.values())

    # -- routing --------------------------------------------------------------
    def dispatch(self, domain: str) -> Daemon:
        """Route a task to the daemon that owns its domain. Unowned domains
        raise — there is no default handler."""
        if not isinstance(domain, str) or not domain.strip():
            raise ValueError("dispatch: domain must be a non-empty string")
        domain = domain.strip()
        for daemon in self._daemons.values():
            if daemon.owns == domain:
                return daemon
        owned = sorted(d.owns for d in self._daemons.values())
        raise ValueError(f"no daemon owns domain {domain!r}; owned domains: {owned}")

    # -- surfacing --------------------------------------------------------------
    def surface(self, name: str, payload: Any, context: Optional[dict] = None) -> Any:
        """Let a daemon surface a payload — only if its visible rule allows
        it under the given context. Surfacing against the rule raises."""
        daemon = self.get(name)
        ctx = dict(context) if context else {}
        try:
            allowed = daemon.visible(ctx)
        except Exception as exc:
            raise ValueError(
                f"daemon {name!r}: visible rule failed with {exc!r}"
            ) from None
        if not allowed:
            raise ValueError(
                f"daemon {name!r} may not surface now: its visible rule denied it"
            )
        return payload
