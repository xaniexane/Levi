"""Pseudonymous PIN identity with true push over one always-on connection.

Studied from: dead-networks-20260916 / report.md [BlackBerry Messenger +
BIS push] (pseudonymous, carrier-independent PIN identity; true push over a
single always-on connection with aggressive compression; D/R delivered/read
receipts).

This is an original, from-scratch implementation for LEVI. Three mechanisms:

- ``pin_from(secret)`` — a stable 8-hex-character PIN derived from a secret
  with SHA-256. The PIN identifies the *device*, not the person: no phone
  number, no carrier, no account name crosses the wire.
- ``PushChannel`` — one multiplexed connection object serving every
  registered PIN. Outgoing payloads are compressed with zlib level 9 (the
  aggressive-compression half of the trick) and queued per PIN until
  collected; a single ``drain`` call can also sweep every PIN at once, the
  way one radio connection served the whole device.
- D/R receipts — each message moves ``queued -> delivered -> read``.
  ``drain`` marks delivered (D), ``mark_read`` marks read (R), and
  ``receipts(pin)`` reports the current state of each message.

Public surface:
- ``pin_from(secret: str) -> str``: 8-hex-char PIN.
- ``PushChannel``: ``register(pin)``, ``unregister(pin)``,
  ``enqueue(pin, payload)`` -> msg_id, ``drain(pin=None)``,
  ``mark_read(pin, msg_id)``, ``receipts(pin)``, ``pending_count(pin)``,
  ``compression_ratio(msg_id)``.
- ``PushMessage``: frozen record with msg_id, pin, sizes, and state.
- ``PushError`` for violations (unknown PIN, empty payload, ...).

Honest limits: the "always-on connection" is an in-process queue — there
are no sockets, no radios, and no real push wakeups. Compression is real
(zlib) but the ratio depends on payload redundancy. PINs are only as secret
as the secret they are derived from; this module does no key management.

stdlib-only. No network.
"""

from __future__ import annotations

import hashlib
import uuid
import zlib
from dataclasses import dataclass
from typing import Dict, List, Optional


ORIGIN = "levi-revival/pin_push"


class PushError(ValueError):
    """Raised when push-channel rules are violated."""


#: zlib level used for every payload — maximum compression.
COMPRESSION_LEVEL = 9

#: Maximum payload size accepted per message (1 MiB).
MAX_PAYLOAD_BYTES = 1024 * 1024


def pin_from(secret: str) -> str:
    """Derive a stable 8-hex-character device PIN from a secret.

    Deterministic: the same secret always yields the same PIN. The PIN
    reveals nothing about the secret (one-way hash, truncated).
    """
    if not secret:
        raise PushError("secret must be non-empty")
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    return digest[:8]


@dataclass(frozen=True)
class PushMessage:
    """One pushed message: identity, sizes, and delivery state."""

    msg_id: str
    pin: str
    raw_bytes: int
    wire_bytes: int
    state: str  # "queued" | "delivered" | "read"


class PushChannel:
    """One always-on connection multiplexed across device PINs."""

    def __init__(self) -> None:
        self._pins: List[str] = []
        # pin -> list of (msg_id, compressed payload, raw size, state)
        self._queues: Dict[str, List[List[object]]] = {}
        self._seq = 0

    # -- identity ----------------------------------------------------------
    def register(self, pin: str) -> None:
        """Attach a device PIN to this connection."""
        self._guard_pin(pin)
        if pin in self._pins:
            raise PushError(f"PIN already registered: {pin!r}")
        self._pins.append(pin)
        self._queues[pin] = []

    def unregister(self, pin: str) -> None:
        """Detach a PIN; its queued messages are discarded with it."""
        if pin not in self._pins:
            raise PushError(f"unknown PIN: {pin!r}")
        self._pins.remove(pin)
        del self._queues[pin]

    def pins(self) -> List[str]:
        return list(self._pins)

    # -- push ---------------------------------------------------------------
    def enqueue(self, pin: str, payload: bytes) -> str:
        """Compress and queue a payload for a PIN. Returns the message id."""
        queue = self._queue(pin)
        if not isinstance(payload, (bytes, bytearray)):
            raise PushError("payload must be bytes")
        if len(payload) == 0:
            raise PushError("payload must be non-empty")
        if len(payload) > MAX_PAYLOAD_BYTES:
            raise PushError(f"payload over {MAX_PAYLOAD_BYTES} bytes")
        self._seq += 1
        msg_id = f"{self._seq:06d}-{uuid.uuid4().hex[:8]}"
        compressed = zlib.compress(bytes(payload), COMPRESSION_LEVEL)
        queue.append([msg_id, compressed, len(payload), "queued"])
        return msg_id

    def drain(self, pin: Optional[str] = None) -> Dict[str, List[bytes]]:
        """Collect queued payloads, decompressed, and mark them delivered.

        With ``pin=None`` sweeps every registered PIN in one call — the
        single-connection half of the trick. Returns pin -> [payloads].
        """
        targets = [pin] if pin is not None else list(self._pins)
        out: Dict[str, List[bytes]] = {}
        for target in targets:
            queue = self._queue(target)
            payloads: List[bytes] = []
            for entry in queue:
                entry[3] = "delivered"  # D receipt
                payloads.append(zlib.decompress(entry[1]))  # type: ignore[arg-type]
            out[target] = payloads
        return out

    def pending_count(self, pin: str) -> int:
        """Queued (not yet delivered) messages for a PIN."""
        return sum(1 for entry in self._queue(pin) if entry[3] == "queued")

    # -- receipts ------------------------------------------------------------
    def mark_read(self, pin: str, msg_id: str) -> None:
        """Mark a delivered message as read (the R receipt)."""
        for entry in self._queue(pin):
            if entry[0] == msg_id:
                if entry[3] == "queued":
                    raise PushError("cannot mark a queued message as read")
                entry[3] = "read"
                return
        raise PushError(f"unknown message: {msg_id!r}")

    def receipts(self, pin: str) -> List[PushMessage]:
        """Current D/R state of every message for a PIN, in enqueue order."""
        return [
            PushMessage(
                msg_id=entry[0],  # type: ignore[arg-type]
                pin=pin,
                raw_bytes=entry[2],  # type: ignore[arg-type]
                wire_bytes=len(entry[1]),  # type: ignore[arg-type]
                state=entry[3],  # type: ignore[arg-type]
            )
            for entry in self._queue(pin)
        ]

    def compression_ratio(self, pin: str, msg_id: str) -> float:
        """wire_bytes / raw_bytes for one message; < 1.0 means it shrank."""
        for entry in self._queue(pin):
            if entry[0] == msg_id:
                return len(entry[1]) / entry[2]  # type: ignore[operator]
        raise PushError(f"unknown message: {msg_id!r}")

    # -- internals ------------------------------------------------------------
    def _queue(self, pin: str) -> List[List[object]]:
        self._guard_pin(pin)
        try:
            return self._queues[pin]
        except KeyError:
            raise PushError(f"unknown PIN: {pin!r}") from None

    @staticmethod
    def _guard_pin(pin: str) -> None:
        if not pin or not pin.strip():
            raise PushError("PIN must be non-empty")
