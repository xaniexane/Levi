"""LEVI's door-extension bench: user-written in-game modules (IGMs).

Studied from: dead-networks-20260916/report.md [BBS door games].

The shape being studied: door games stayed alive because *players* could
extend them — user-written in-game modules that hook into the game's event
stream (on visit, on turn, on combat...) without forking the game itself.

``igms`` rebuilds that shape from scratch, LEVI-native:

- ``IGM`` — a user-written module: name, version, author, a map of event
  names to handler callables, and a priority for ordering.
- ``IGMRegistry`` — registers modules, validates them, and dispatches
  events to every hooked module in priority order.
- Dispatch is *fault-isolated*: a module that raises is recorded as failed
  and the rest still run — one bad IGM can't take the door down. Failures
  are returned to the caller, never swallowed silently.

Honest limits: hooks run in-process and synchronously with full access to
the context object you hand them — there is no sandboxing, no capability
system, no code signing. Treat IGMs like local scripts you chose to trust,
because that is what they are.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


ORIGIN = "levi-revival/igms"


# Well-known event names. The registry accepts any string, but doors should
# prefer these so IGMs written for one door work in another.
ON_VISIT = "on_visit"
ON_TURN = "on_turn"
ON_MOVE = "on_move"
ON_CHALLENGE = "on_challenge"
ON_RESOLVE = "on_resolve"
ON_PAYOUT = "on_payout"


class IGMError(Exception):
    """Base class for IGM failures."""


class DuplicateIGM(IGMError):
    """An IGM with that name is already registered."""


class BadIGM(IGMError):
    """An IGM failed validation (bad name, non-callable hook, ...)."""


class UnknownIGM(IGMError):
    """No registered IGM has that name."""


Hook = Callable[[Dict[str, Any]], Any]


@dataclass
class IGM:
    """A user-written in-game module.

    ``hooks`` maps event names to callables. Each callable receives one
    argument — a plain dict "context" the door builds per event — and may
    return anything (results are collected) or mutate the context in place.
    ``priority`` orders dispatch: lower numbers run first.
    """

    name: str
    hooks: Dict[str, Hook]
    version: str = "1.0"
    author: str = "anonymous"
    description: str = ""
    priority: int = 100


@dataclass
class DispatchResult:
    igm_name: str
    event: str
    ok: bool
    result: Any = None
    error: str = ""


class IGMRegistry:
    """Holds a door's user-written modules and fans events out to them."""

    def __init__(self):
        self._igms: Dict[str, IGM] = {}

    # -- registration ----------------------------------------------------

    def register(self, igm: IGM) -> IGM:
        self._validate(igm)
        if igm.name in self._igms:
            raise DuplicateIGM(f"IGM {igm.name!r} already registered")
        self._igms[igm.name] = igm
        return igm

    def unregister(self, name: str) -> IGM:
        try:
            return self._igms.pop(name)
        except KeyError:
            raise UnknownIGM(f"no IGM named {name!r}") from None

    def get(self, name: str) -> IGM:
        try:
            return self._igms[name]
        except KeyError:
            raise UnknownIGM(f"no IGM named {name!r}") from None

    def names(self) -> List[str]:
        return sorted(self._igms)

    def _validate(self, igm: IGM) -> None:
        if not igm.name or not igm.name.strip():
            raise BadIGM("IGM needs a non-empty name")
        if not igm.hooks:
            raise BadIGM(f"IGM {igm.name!r} hooks nothing")
        for event, hook in igm.hooks.items():
            if not event or not isinstance(event, str):
                raise BadIGM(f"IGM {igm.name!r} has a bad event name: {event!r}")
            if not callable(hook):
                raise BadIGM(f"IGM {igm.name!r} hook for {event!r} is not callable")

    # -- dispatch --------------------------------------------------------

    def hooks_for(self, event: str) -> List[IGM]:
        hooked = [m for m in self._igms.values() if event in m.hooks]
        return sorted(hooked, key=lambda m: (m.priority, m.name))

    def dispatch(
        self, event: str, ctx: Optional[Dict[str, Any]] = None
    ) -> List[DispatchResult]:
        """Run every hooked module for ``event``, in priority order.

        Each module's failure is isolated and reported; a raising module
        never stops the modules after it.
        """
        ctx = {} if ctx is None else ctx
        results: List[DispatchResult] = []
        for igm in self.hooks_for(event):
            try:
                out = igm.hooks[event](ctx)
                results.append(DispatchResult(igm.name, event, True, result=out))
            except Exception as exc:  # noqa: BLE001 — isolation is the point
                results.append(
                    DispatchResult(
                        igm.name, event, False, error=f"{type(exc).__name__}: {exc}"
                    )
                )
        return results

    def describe(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": m.name,
                "version": m.version,
                "author": m.author,
                "description": m.description,
                "priority": m.priority,
                "events": sorted(m.hooks),
            }
            for m in sorted(self._igms.values(), key=lambda m: m.name)
        ]
