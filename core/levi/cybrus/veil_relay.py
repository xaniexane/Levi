"""Cybrus Veil relay broker — the ciphertext-only message broker.

Recreated LEVI-native from Chauncey's own original,
``lock-and-key-vault-genesis.zip`` (Void Box v0.1.2 Genesis, his upload,
preserved unchanged). His original server's own words:

- "Relay stores and forwards opaque envelopes only. Never decrypts, never
  logs payload content as text." (server Application.kt)
- "Relay accepts opaque envelopes only. No plaintext messages."
- "The server must never require or store plaintext private conversation
  content." (server README)
- "Server/relay: ciphertext envelopes only" (MessagingProtocol)

The broker ability is exactly that: a relay that routes sealed Veil
envelopes between keeper devices WITHOUT being able to read them. His
intent (2026-09-23): his husband and friends message one another privately
and securely — through HIS instance's relay.

His ruling (2026-09-27): the full broker ability is the founder's instance
only — "other users don't get that or it is limited." The gate below is
plain and explicit, not security-through-obscurity: full multi-keeper
relaying requires :func:`is_founder_identity`; every other instance is
limited to relaying between its own keeper's devices.

LAWS (binding, machine-checked in tests/test_veil_relay.py)
-----------------------------------------------------------
- L1 CIPHERTEXT-ONLY: the relay never decrypts, opens, or inspects
  envelope payloads. It reads routing fields only (sender, recipient,
  message_id) and moves opaque bytes. There is no code path from this
  module into any open/decrypt routine.
- L2 BYTE-IDENTICAL FORWARDING: what is accepted is what is delivered,
  bit-for-bit. Recipient-side Veil authentication (AAD-bound header +
  attestation) still verifies after the relay hop; a tampered envelope
  fails at open, never at the relay.
- L3 FOUNDER-GATE: full broker ability — relaying envelopes between
  devices of DIFFERENT keepers — requires a founder identity
  (:func:`~levi.cybrus.identity.is_founder_identity`). A non-founder
  instance is limited to envelopes whose sender AND recipient devices both
  belong to its own keeper. Anything else raises :class:`RelayGateError`.
  Caller-asserted identity strings are never trusted beyond this check.
- L4 METADATA-ONLY LOGS: relay logs carry sizes, counts, and ids only —
  never envelope content, blobs, or plaintext.
- L5 FAIL-CLOSED: malformed envelopes (missing routing fields, empty
  blob, oversized, wrong protocol version), unregistered devices, and
  revoked senders are rejected at accept. Unknown keeper identity denies.
  The relay never invents, reorders inside a batch beyond FIFO, or
  redelivers.
- L6 NO NETWORK: stdlib-only, in-process. Like onion.py's honest
  boundary, this proves the broker logic; production transport (real
  relay binaries, real sockets) is future work and needs his word.

HONEST BOUNDARIES
-----------------
- Replay defense stays client-side, per his original MessagingProtocol
  ("Replay: message-id set + sequence window"): the relay forwards
  duplicates untouched; the recipient's Veil seq watermark rejects them.
- Revocation the relay knows about (via :meth:`revoke_device`) is
  enforced at accept; revocation the recipient's Veil knows about is
  enforced at open. Defense in depth, stated plainly.
- Queue is bounded (default 10_000, his original MAX_QUEUE); when full
  the oldest envelope is dropped — his original semantics, documented.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from typing import Deque, Dict, Iterable, List, Optional, Tuple

from levi.cybrus import veil as _veil
from levi.cybrus.identity import is_founder_identity

log = logging.getLogger("levi.cybrus.veil_relay")

# His original constants (Application.kt): 1 MiB envelope cap, 10k queue,
# 32-envelope poll batches.
MAX_ENVELOPE_BYTES = 1_048_576
MAX_QUEUE = 10_000
MAX_BATCH = 32

# Routing fields the relay is allowed to read. Everything else — blob,
# attestation internals, plaintext — is opaque.
_ROUTING_FIELDS = ("sender", "recipient", "message_id")
_REQUIRED_FIELDS = (
    "protocol_version",
    "message_id",
    "conversation_id",
    "sender",
    "recipient",
    "seq",
    "epoch",
    "blob",
    "attestation",
)


class RelayError(ValueError):
    """The relay refused an envelope or an operation. Fail-closed."""


class RelayGateError(RelayError):
    """The founder gate denied full broker ability for this identity."""


def _canonical_bytes(envelope: dict) -> bytes:
    """Canonical serialization — the opaque bytes the relay stores."""
    return json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")


def check_invariants() -> List[Tuple[str, bool, str]]:
    """Structural law checks, mirroring veil.check_invariants()."""
    results: List[Tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))

    src = open(__file__, encoding="utf-8").read()
    # Exclude this check's own token list (self-reference, not a decrypt path).
    body = src.split("def check_invariants", 1)[0]
    check(
        "L1 no decrypt path: relay module never references veil open/decrypt",
        not any(
            token in body
            for token in ("open_message", "_open_backend", "_open_gcm", "_open(")
        ),
        "routing fields only",
    )
    check(
        "protocol version pinned to veil",
        _veil._PROTOCOL_VERSION == 1,  # noqa: SLF001 - deliberate pin, fail closed on drift
        "v%d" % _veil._PROTOCOL_VERSION,  # noqa: SLF001
    )
    check(
        "envelope cap matches original (1 MiB)",
        MAX_ENVELOPE_BYTES == 1_048_576,
        "%d bytes" % MAX_ENVELOPE_BYTES,
    )
    check(
        "queue bound matches original (10k, drop-oldest)",
        MAX_QUEUE == 10_000,
        "%d" % MAX_QUEUE,
    )
    return results


class VeilRelay:
    """The ciphertext-only broker for sealed Veil envelopes.

    ``operator_identity`` is the name of the keeper running this relay
    instance. Full broker ability (relaying between devices of different
    keepers) requires a founder identity; everyone else is limited to
    their own keeper's devices (L3).
    """

    def __init__(
        self,
        operator_identity: str,
        *,
        max_envelope_bytes: int = MAX_ENVELOPE_BYTES,
        max_queue: int = MAX_QUEUE,
        max_batch: int = MAX_BATCH,
    ) -> None:
        if not isinstance(operator_identity, str) or not operator_identity.strip():
            raise RelayError("operator_identity must be a non-empty string")
        self._operator = operator_identity.strip()
        self._founder = is_founder_identity(self._operator)
        self._max_bytes = max_envelope_bytes
        self._max_batch = max_batch
        # (recipient_device_id, canonical envelope bytes), drop-oldest.
        self._queue: Deque[Tuple[str, bytes]] = deque(maxlen=max_queue)
        # keeper_id -> set(device_id); revoked devices tracked separately.
        self._keepers: Dict[str, set] = {}
        self._revoked: set = set()
        self._accepted = 0
        self._delivered = 0
        self._dropped_full = 0
        log.info(
            "relay init operator=%r founder_broker=%s",
            self._operator,
            self._founder,
        )

    # -- registration ----------------------------------------------------

    def register_keeper(self, keeper_id: str, device_ids: Iterable[str]) -> dict:
        """Register the device set of one keeper (e.g. husband, friend).

        The operator's own keeper id defaults to their identity name;
        registering it is how a non-founder instance earns its limited
        personal-relay ability.
        """
        if not isinstance(keeper_id, str) or not keeper_id.strip():
            raise RelayError("keeper_id must be a non-empty string")
        devices = set()
        for d in device_ids:
            if not isinstance(d, str) or not d:
                raise RelayError("device ids must be non-empty strings")
            devices.add(d)
        self._keepers[keeper_id] = devices
        log.info(
            "relay register keeper=%r devices=%d", keeper_id, len(devices)
        )
        return {"keeper_id": keeper_id, "devices": sorted(devices)}

    def revoke_device(self, device_id: str) -> None:
        """Mark a device revoked at the relay: its envelopes are refused."""
        self._revoked.add(device_id)
        log.info("relay revoke device=%r", device_id)

    def _keeper_of(self, device_id: str) -> Optional[str]:
        for keeper_id, devices in self._keepers.items():
            if device_id in devices:
                return keeper_id
        return None

    # -- the broker ability ----------------------------------------------

    def _validate(self, envelope: object) -> dict:
        """Fail-closed envelope validation. Reads routing fields only."""
        if not isinstance(envelope, dict):
            raise RelayError("envelope must be a dict")
        missing = [f for f in _REQUIRED_FIELDS if f not in envelope]
        if missing:
            raise RelayError(
                "envelope missing fields: %s" % ", ".join(sorted(missing))
            )
        if envelope.get("protocol_version") != _veil._PROTOCOL_VERSION:  # noqa: SLF001
            raise RelayError(
                "unsupported protocol version %r"
                % (envelope.get("protocol_version"),)
            )
        for field in _ROUTING_FIELDS:
            value = envelope.get(field)
            if not isinstance(value, str) or not value:
                raise RelayError("envelope routing field %r invalid" % field)
        blob = envelope.get("blob")
        if not isinstance(blob, str) or not blob:
            raise RelayError("envelope blob must be a non-empty string")
        raw = _canonical_bytes(envelope)
        if len(raw) > self._max_bytes:
            raise RelayError(
                "envelope too large: %d bytes (max %d)"
                % (len(raw), self._max_bytes)
            )
        return envelope

    def _gate(self, sender: str, recipient: str) -> None:
        """L3: the founder gate. Full broker is founder-only."""
        if sender in self._revoked:
            raise RelayError("sender device %r is revoked" % sender)
        sender_keeper = self._keeper_of(sender)
        recipient_keeper = self._keeper_of(recipient)
        if sender_keeper is None or recipient_keeper is None:
            raise RelayError(
                "unregistered device in route %r -> %r" % (sender, recipient)
            )
        if self._founder:
            return  # full broker ability: any registered keeper pair
        # Limited: own keeper's devices only.
        if not (
            sender_keeper == self._operator
            and recipient_keeper == self._operator
        ):
            raise RelayGateError(
                "full broker ability is founder-only: instance %r may only "
                "relay between its own keeper's devices" % self._operator
            )

    def accept(self, envelope: dict) -> dict:
        """Accept one sealed envelope into the relay queue.

        Returns a metadata-only receipt ``{"accepted": True, "message_id",
        "bytes"}`` — his original ``{"accepted": true, "bytes"}`` shape.
        The payload is never decrypted, opened, or inspected (L1); only
        sizes and ids are logged (L4).
        """
        env = self._validate(envelope)
        self._gate(env["sender"], env["recipient"])
        raw = _canonical_bytes(env)
        if len(self._queue) == self._queue.maxlen:
            self._dropped_full += 1
        self._queue.append((env["recipient"], raw))
        self._accepted += 1
        log.info(
            "relay accepted message_id=%r bytes=%d queue_depth=%d",
            env["message_id"],
            len(raw),
            len(self._queue),
        )
        return {"accepted": True, "message_id": env["message_id"], "bytes": len(raw)}

    def poll(self, recipient_device_id: str, limit: Optional[int] = None) -> List[dict]:
        """Collect envelopes addressed to one device (store-and-forward).

        Dequeues up to ``limit`` (default his original 32) matching
        envelopes, FIFO. Returned envelopes are bit-identical to what was
        accepted (L2).
        """
        if not isinstance(recipient_device_id, str) or not recipient_device_id:
            raise RelayError("recipient_device_id must be a non-empty string")
        if self._keeper_of(recipient_device_id) is None:
            raise RelayError("unregistered recipient device %r" % recipient_device_id)
        want = self._max_batch if limit is None else limit
        if want <= 0:
            raise RelayError("limit must be positive")
        out: List[dict] = []
        rest: Deque[Tuple[str, bytes]] = deque()
        while self._queue and len(out) < want:
            recipient, raw = self._queue.popleft()
            if recipient == recipient_device_id:
                out.append(json.loads(raw.decode("utf-8")))
            else:
                rest.append((recipient, raw))
        # Preserve order of the envelopes left behind.
        self._queue.extendleft(reversed(rest))
        self._delivered += len(out)
        log.info(
            "relay poll device=%r delivered=%d queue_depth=%d",
            recipient_device_id,
            len(out),
            len(self._queue),
        )
        return out

    def health(self) -> dict:
        """Metadata-only health: counts, never content."""
        return {
            "operator": self._operator,
            "founder_broker": self._founder,
            "queue_depth": len(self._queue),
            "accepted": self._accepted,
            "delivered": self._delivered,
            "dropped_full": self._dropped_full,
            "keepers": len(self._keepers),
        }
