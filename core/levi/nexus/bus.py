"""NEXUS bus — the general inter-organ messaging nexus of LEVI.

Thin facade over the authoritative SI engine
(``levi.nexus.si.NexusEngine``). Public surface:

- ``register_organ(name, handler=None)`` — join the nexus
- ``route(envelope)``                    — send one envelope, get a Receipt
- ``broadcast(envelope, exclude=None)``   — fan out, one Receipt per organ
- ``dead_letter(envelope, reason)``      — dead-letter with a reason
- ``dead_letters()``                     — inspect the dead-letter store
- ``organs()`` / ``inbox(organ)`` / ``drain(organ)``

ROUTING LAW: every envelope gets a receipt (accepted / routed /
rejected / dead-lettered with reason). No silent drops. Unknown
organs dead-letter with a reason, never raise to the caller. TTL
expiry dead-letters. Poison payloads (non-dict, absurd sizes) are
rejected pre-route with a receipt.

Payloads are DATA, never instructions — the bus never evaluates
payload content.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .envelope import Envelope, Receipt
from .si import NexusEngine
from .si.engine import Handler

__all__ = ["Nexus"]


class Nexus:
    """The nexus. Create one, register organs, route envelopes."""

    def __init__(self, home: Optional[Path] = None, journal: bool = True) -> None:
        self._engine = NexusEngine(home=home, journal=journal)

    # -- organs ----------------------------------------------------------
    def register_organ(self, name: str, handler: Optional[Handler] = None) -> bool:
        """Register an organ with the nexus. True if newly registered."""
        return self._engine.register_organ(name, handler)

    def organs(self) -> List[str]:
        return self._engine.organs()

    # -- routing ---------------------------------------------------------
    def route(self, envelope: Envelope) -> Receipt:
        """Route one envelope. Always returns a Receipt; never raises
        for routing outcomes."""
        return self._engine.route(envelope)

    def send(
        self,
        from_organ: str,
        to_organ: Optional[str],
        kind: str,
        payload: Optional[Dict[str, Any]] = None,
        ttl: float = 600.0,
        trace_id: Optional[str] = None,
    ) -> Receipt:
        """Convenience: build an Envelope and route it in one call."""
        envelope = Envelope(
            from_organ=from_organ,
            to_organ=to_organ,
            kind=kind,
            payload=dict(payload) if payload is not None else {},
            ttl=ttl,
        )
        if trace_id is not None:
            envelope.trace_id = trace_id
        return self.route(envelope)

    def broadcast(
        self, envelope: Envelope, exclude: Optional[str] = None
    ) -> List[Receipt]:
        """Fan one envelope to every registered organ. The sender is
        excluded by default (pass the sender as ``exclude``)."""
        return self._engine.broadcast(envelope, exclude=exclude)

    def dead_letter(self, envelope: Envelope, reason: str) -> Receipt:
        return self._engine.dead_letter(envelope, reason)

    def dead_letters(self) -> List[Dict[str, Any]]:
        return self._engine.dead_letters()

    # -- inboxes ----------------------------------------------------------
    def inbox(self, organ: str) -> List[Envelope]:
        return self._engine.inbox(organ)

    def drain(self, organ: str) -> List[Envelope]:
        return self._engine.drain(organ)

    # -- engine access (for journal tests / CLI) ---------------------------
    @property
    def engine(self) -> NexusEngine:
        return self._engine
