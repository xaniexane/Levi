"""Void Box Messenger — relay transport client.

A thin packet layer over ``levi.voidbox.relay.RelayClient``: the
messenger speaks in JSON packets (handshake offers/answers, DM frames,
sealed room envelopes); this client base64-wraps them into the relay's
opaque blobs and decodes them back on poll. Group messages are fanned
out to each member's mailbox, so dispatch is by packet kind and the
room id carried inside the packet. It holds no keys and performs no
crypto — the ciphertext-only carrier, nothing more.

Packet kinds (all JSON, base64'd into the blob):
- ``{"kind": "hs-offer", "from": <keeper>, "offer": {...}}``
- ``{"kind": "hs-answer", "from": <keeper>, "answer": {...}}``
- ``{"kind": "dm", "from": <keeper>, "envelope": {...}}`` — the envelope
  is a sealed ``veil_chat`` envelope; its plaintext is a JSON frame.
- ``{"kind": "room-sealed", "room_id": <room>, "from": <keeper>,
  "envelope": {...}}`` — a sealed ``rooms`` envelope, one copy per
  active member's mailbox.
"""

from __future__ import annotations

import base64
import binascii
import json
from pathlib import Path
from typing import Optional

from levi.plaiground.gate import require_adult
from levi.voidbox.relay import DEFAULT_HOST, DEFAULT_PORT, RelayClient

__all__ = ["MessengerTransport", "PacketError"]


class PacketError(ValueError):
    """A relay envelope could not be decoded as a messenger packet."""


class MessengerTransport:
    """The messenger's relay client. Stdlib only; no keys, no crypto.

    Gated like everything else on the messenger surface (M7): the
    transport alone grants no crypto capability, but it is a public
    entry point, so it checks the gate first too.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        timeout: float = 10.0,
        home: Optional[Path] = None,
    ) -> None:
        require_adult(home)  # M7: FIRST
        self._gate_home = home
        self._client = RelayClient(host=host, port=port, timeout=timeout)
        self.host = host
        self.port = port

    def _require_adult(self) -> None:
        require_adult(self._gate_home)

    # -- send ------------------------------------------------------------

    def send_packet(
        self, to: str, packet: dict, sender: Optional[str] = None
    ) -> dict:
        """POST one packet to a keeper's mailbox. Returns the relay's
        delivery report (id, stored/duplicate)."""
        self._require_adult()
        if not isinstance(packet, dict) or "kind" not in packet:
            raise PacketError("packet must be a dict with a 'kind'")
        blob = base64.b64encode(
            json.dumps(packet, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        return self._client.post(to, blob, sender=sender)

    # -- receive ---------------------------------------------------------

    def fetch_packets(self, recipient: str, limit: int = 50) -> list[dict]:
        """POLL the recipient's mailbox and decode packets. Returns a
        list of ``{"id", "from", "ts", "packet"}``. Envelopes whose blob
        is not a messenger packet are reported as malformed (counted,
        never crashed on) so one bad envelope can't wedge the inbox."""
        self._require_adult()
        out: list[dict] = []
        malformed = 0
        for env in self._client.poll(recipient, limit=limit):
            try:
                raw = base64.b64decode(env["blob"], validate=True)
                packet = json.loads(raw.decode("utf-8"))
                if not isinstance(packet, dict) or "kind" not in packet:
                    raise PacketError("not a messenger packet")
            except (binascii.Error, ValueError, KeyError, UnicodeDecodeError):
                malformed += 1
                continue
            out.append(
                {
                    "id": env.get("id"),
                    "from": env.get("from", ""),
                    "ts": env.get("ts"),
                    "packet": packet,
                }
            )
        return out

    def malformed_count(self, recipient: str, limit: int = 50) -> int:
        """How many pending envelopes are not decodable packets (the
        inbox equivalent of a spam count — the carrier stays dumb)."""
        self._require_adult()
        bad = 0
        for env in self._client.poll(recipient, limit=limit):
            try:
                raw = base64.b64decode(env["blob"], validate=True)
                packet = json.loads(raw.decode("utf-8"))
                if not isinstance(packet, dict) or "kind" not in packet:
                    raise PacketError("not a messenger packet")
            except (binascii.Error, ValueError, KeyError, UnicodeDecodeError):
                bad += 1
        return bad

    def ack(self, recipient: str, ids: list[str]) -> int:
        """Tombstone delivered envelopes (idempotent acks)."""
        self._require_adult()
        return self._client.ack(recipient, [i for i in ids if i])

    def ping(self) -> bool:
        """Is the relay reachable?"""
        self._require_adult()
        return self._client.ping()
