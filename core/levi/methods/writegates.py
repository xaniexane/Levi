"""Memory write gates against auto-vacuum sludge.

Origin: 2026 LEVI doctrine — memory is NEVER written by background
auto-extraction. Writes pass through named gates only: explicit user
capture, a review lesson, or an archivist promotion. All writes are
event-triggered and auditable: the user said remember, locked a
commitment, or promoted a fact; the evening review distilled a lesson; or
the archivist daemon promoted a repeated observation. Small talk produces
zero memory growth by construction.

What it is in LEVI: gated writes with an append-only audit log. Every write
names its gate and the trigger event that opened it; the audit log records
which gate, which trigger, and which entry — in order. Background or
automatic writes are refused outright: there is no auto-write path, and
``auto_write()`` exists only to raise. Closing a gate retires it; writes
through closed or unregistered gates are rejected.

Honesty label: LOAD-BEARING — the gate check plus the append-only audit
log is the enforcement mechanism; sludge has nowhere to enter.

Deny-closed inputs: empty gate names or descriptions, duplicate gate
registration, closing unknown gates, writing through unregistered or closed
gates, empty triggers or content, and any background/auto write attempt are
all rejected with ValueError.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

__all__ = ["WriteGates", "MemoryEntry", "AuditEntry"]


def _clean(value: str, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class MemoryEntry:
    id: str
    gate: str
    trigger: str
    content: str


@dataclass(frozen=True)
class AuditEntry:
    seq: int
    gate: str
    trigger: str
    entry_id: str


class WriteGates:
    """Memory is written through named gates only. No gates, no growth."""

    def __init__(self) -> None:
        self._gates: dict[str, str] = {}  # open gate name -> description
        self._closed: set[str] = set()
        self._entries: dict[str, MemoryEntry] = {}
        self._audit: list[AuditEntry] = []
        self._seq = 0

    # -- gates ---------------------------------------------------------------------
    def register_gate(self, name: str, description: str) -> str:
        """Open a named gate: explicit user capture, review lesson,
        archivist promotion — each named, each auditable."""
        name = _clean(name, "gate name")
        description = _clean(description, "gate description")
        if name in self._gates or name in self._closed:
            raise ValueError(f"duplicate gate: {name!r}")
        self._gates[name] = description
        return name

    def close_gate(self, name: str) -> None:
        """Retire a gate; nothing more passes through it."""
        name = _clean(name, "gate name")
        if name not in self._gates:
            if name in self._closed:
                raise ValueError(f"gate {name!r} is already closed")
            raise ValueError(f"unknown gate: {name!r}")
        del self._gates[name]
        self._closed.add(name)

    def gates(self) -> list[str]:
        return sorted(self._gates)

    # -- writes ----------------------------------------------------------------------
    def write(self, gate: str, trigger: str, content: str) -> MemoryEntry:
        """Write through a named gate, naming the trigger event that opened
        it. The audit log records the passage."""
        gate = _clean(gate, "gate name")
        trigger = _clean(trigger, "trigger event")
        content = _clean(content, "content")
        if gate in self._closed:
            raise ValueError(f"gate {gate!r} is closed — retired gates write nothing")
        if gate not in self._gates:
            raise ValueError(
                f"unknown gate: {gate!r} — memory is written through named gates only"
            )
        entry = MemoryEntry(
            id=uuid.uuid4().hex[:12],
            gate=gate,
            trigger=trigger,
            content=content,
        )
        self._entries[entry.id] = entry
        self._seq += 1
        self._audit.append(
            AuditEntry(seq=self._seq, gate=gate, trigger=trigger, entry_id=entry.id)
        )
        return entry

    def auto_write(self, content: str = "") -> None:
        """Background auto-extraction attempting a write. Always refused.

        This method exists so the refusal is explicit and loud — there is
        no silent path by which the vacuum can write.
        """
        raise ValueError(
            "background/auto writes are REFUSED: memory is written through "
            "named gates only — name a gate and a trigger event"
        )

    # -- audit -------------------------------------------------------------------------
    def audit(self) -> list[AuditEntry]:
        """Every gated write, in order. Small talk leaves no trace here."""
        return list(self._audit)

    def entries(self) -> list[MemoryEntry]:
        return list(self._entries.values())
