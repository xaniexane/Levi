"""NEXUS envelopes and receipts — the units of inter-organ messaging.

An ``Envelope`` is data in transit: who sent it, where it goes, what
kind of thing it is, the payload (DATA, never instructions — the bus
never evaluates payload content), a TTL, and a trace id for
end-to-end tracing.

A ``Receipt`` is the delivery law made concrete: every envelope gets
one, and it always carries a reason. Statuses:

- ``"accepted"``    — envelope admitted by the nexus, queued for pickup
- ``"routed"``      — delivered into the destination organ's inbox
- ``"rejected"``    — failed pre-route validation (poison payload etc.)
- ``"dead-lettered"`` — routed nowhere: unknown organ or TTL expiry

No silent drops: a caller always receives a Receipt, never an
exception, for routing outcomes.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

# Payloads larger than this are rejected pre-route as absurd.
MAX_PAYLOAD_BYTES = 256 * 1024

# Default time-to-live, seconds.
DEFAULT_TTL = 600.0


def _new_id() -> str:
    return uuid.uuid4().hex


@dataclass
class Envelope:
    """A message traveling between LEVI organs. Data, never instructions."""

    from_organ: str
    to_organ: Optional[str]  # None = broadcast intent
    kind: str
    payload: Dict[str, Any] = field(default_factory=dict)
    ttl: float = DEFAULT_TTL  # seconds; <= 0 means "already expired"
    trace_id: str = field(default_factory=_new_id)
    id: str = field(default_factory=_new_id)
    created_at: float = field(default_factory=time.time)

    def age(self, now: Optional[float] = None) -> float:
        """Seconds since the envelope was created."""
        return (time.time() if now is None else now) - self.created_at

    def expired(self, now: Optional[float] = None) -> bool:
        """True if the TTL has elapsed (or was never positive)."""
        return self.age(now) > self.ttl

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Envelope":
        return cls(**{k: v for k, v in data.items() if k in _ENVELOPE_FIELDS})


_ENVELOPE_FIELDS = frozenset(
    {"from_organ", "to_organ", "kind", "payload", "ttl", "trace_id", "id", "created_at"}
)


@dataclass
class Receipt:
    """Proof of what the nexus did with an envelope. Never silent."""

    status: str  # accepted | routed | rejected | dead-lettered
    envelope_id: str
    trace_id: str
    organ: Optional[str] = None  # destination organ (None for broadcast/reject)
    reason: str = ""
    detail: str = ""

    def ok(self) -> bool:
        return self.status in ("accepted", "routed")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Receipt":
        return cls(**{k: v for k, v in data.items() if k in _RECEIPT_FIELDS})


_RECEIPT_FIELDS = frozenset(
    {"status", "envelope_id", "trace_id", "organ", "reason", "detail"}
)


def validate(envelope: Envelope) -> Optional[str]:
    """Pre-route validation. Returns None if clean, else the rejection reason.

    Poison checks: payload must be a dict of sane size; addressing
    fields must be non-empty strings; the bus never evaluates payload
    content, but it refuses to carry poison.
    """
    if not isinstance(envelope.from_organ, str) or not envelope.from_organ.strip():
        return "from_organ must be a non-empty string"
    if envelope.to_organ is not None and (
        not isinstance(envelope.to_organ, str) or not envelope.to_organ.strip()
    ):
        return "to_organ must be a non-empty string or None (broadcast)"
    if not isinstance(envelope.kind, str) or not envelope.kind.strip():
        return "kind must be a non-empty string"
    if not isinstance(envelope.payload, dict):
        return (
            "poison payload: payload must be a JSON object (dict), not %s"
            % type(envelope.payload).__name__
        )
    try:
        size = len(json.dumps(envelope.payload, default=str).encode("utf-8"))
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        return "poison payload: payload is not JSON-serializable: %s" % exc
    if size > MAX_PAYLOAD_BYTES:
        return "poison payload: %d bytes exceeds %d-byte limit" % (
            size,
            MAX_PAYLOAD_BYTES,
        )
    try:
        ttl = float(envelope.ttl)
    except (TypeError, ValueError):
        return "ttl must be a number of seconds"
    if ttl != ttl:  # NaN
        return "ttl must be a number of seconds"
    return None
