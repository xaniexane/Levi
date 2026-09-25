"""livewire — direct object wiring and a responder chain.

Studied from: revival-50-more-20260916-0009/report-part1.md (Section 4).

The load-bearing idea: objects talk to objects with no switchboard in
the middle — you wire a source's event straight to a target's method —
and anything unhandled walks up a *responder chain* of parents until
something claims it.

LEVI's take: ``Wireboard`` is a tiny registry mapping
``(source_id, event)`` to ``(target, method_name)``; ``emit`` calls the
method directly. ``Responder`` gives any object a ``parent``; when a
wire has no entry for an event, ``emit`` hands the event to the
source's responder chain — each link either handles it (returns True)
or passes it up. Direct calls where possible, chain where not; no
event bus, no broker, no middleware.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

ORIGIN = "levi-revival/livewire"


@dataclass
class Wire:
    """One live connection: source event -> target method."""

    source_id: str
    event: str
    target: Any
    method: str

    def fire(self, *args: Any, **kwargs: Any) -> Any:
        return getattr(self.target, self.method)(*args, **kwargs)


class Responder:
    """Anything that can sit in a responder chain.

    Subclass and override ``respond(event, *args)``: return True when
    the event is handled, False (or None) to pass it to the parent.
    """

    def __init__(self, parent: Optional["Responder"] = None) -> None:
        self.parent = parent

    def respond(self, event: str, *args: Any, **kwargs: Any) -> bool:
        return False

    def handle_chain(self, event: str, *args: Any, **kwargs: Any) -> bool:
        """Walk up the parent chain until someone handles the event."""
        node: Optional[Responder] = self
        while node is not None:
            if node.respond(event, *args, **kwargs):
                return True
            node = node.parent
        return False


class Wireboard:
    """Direct live wiring between objects, plus responder-chain fallback."""

    def __init__(self) -> None:
        self._wires: Dict[Tuple[str, str], List[Wire]] = {}

    # -- wiring --------------------------------------------------------
    def wire(self, source_id: str, event: str, target: Any, method: str) -> Wire:
        """Connect ``source_id``'s ``event`` directly to ``target.method``."""
        if not hasattr(target, method):
            raise AttributeError(f"{target!r} has no method {method!r}")
        wire = Wire(source_id, event, target, method)
        self._wires.setdefault((source_id, event), []).append(wire)
        return wire

    def unwire(self, source_id: str, event: str, target: Any, method: str) -> bool:
        wires = self._wires.get((source_id, event), [])
        for wire in wires:
            if wire.target is target and wire.method == method:
                wires.remove(wire)
                return True
        return False

    def wired(self, source_id: str, event: str) -> List[Wire]:
        return list(self._wires.get((source_id, event), []))

    # -- emission ------------------------------------------------------
    def emit(
        self,
        source: Any,
        source_id: str,
        event: str,
        *args: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Fire an event: wired targets first, responder chain as fallback.

        Returns a small report of what happened — LEVI reports honestly
        instead of dropping events silently.
        """
        fired = [wire.fire(*args, **kwargs) for wire in self.wired(source_id, event)]
        chained = False
        if not fired and isinstance(source, Responder):
            chained = source.handle_chain(event, *args, **kwargs)
        return {"fired": len(fired), "results": fired, "chain_handled": chained}
