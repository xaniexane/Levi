"""CLEAR mesh protocol v1 — packet format, addressing, hop budget, priority.

The CLEAR network is the open, transparent fabric — the opposite of a dark
web. Every packet kind is declared in the closed registry below, every
packet is authenticated, and anything undeclared is rejected and logged.
There are no hidden channels.

Wire format (big-endian, deterministic):
    magic(4) | version(1) | kind(1) | priority(1) | flags(1)
    | src(8) | dst(8) | channel(4) | seq(4) | ttl(1) | payload_len(2)
    | payload(payload_len) | mac(32)

mac = HMAC-SHA256(channel_key, header || payload). Receivers MUST verify
before acting on a packet. Unauthenticated packets are dropped, not queued.

Ternary states (the skipped third option, everywhere the giants build
binary):
* Priority: EMERGENCY / PRIORITY / NORMAL — not just high/low.
* LinkState: UP / DEGRADED / DOWN — not just up/down.
* CycleState: ACTIVE / LISTEN / SLEEP — not just on/off.
* NodeTrust: ATTESTED / UNVERIFIED / REVOKED — not just trusted/untrusted.
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import struct
from dataclasses import dataclass
from enum import IntEnum

PROTOCOL_MAGIC = b"CLRM"
PROTOCOL_VERSION = 1

MAX_PAYLOAD = 1024
MAX_TTL = 16
DEFAULT_TTL = 8
NODE_ID_LEN = 8
MAC_LEN = 32

BROADCAST_ID = b"\x00" * NODE_ID_LEN
CONTROL_CHANNEL = 0

FLAG_ACK_REQUESTED = 0x01

_HEADER = struct.Struct("!4sBBBB8s8sIIBH")
HEADER_LEN = _HEADER.size  # 35


class ProtocolError(Exception):
    """Base for all CLEAR protocol failures."""


class BadMagic(ProtocolError):
    pass


class BadVersion(ProtocolError):
    pass


class UnknownKind(ProtocolError):
    """Packet kind outside the closed registry — rejected, never queued."""


class TruncatedPacket(ProtocolError):
    pass


class MacMismatch(ProtocolError):
    """Authentication failed — packet is dropped, not queued."""


class AttestationFailed(ProtocolError):
    """Nodeinfo attestation did not verify — rejected at the protocol layer."""


class PolicyDenied(ProtocolError):
    """The verifier refused a transmission plan."""


class MessageKind(IntEnum):
    """Closed registry of packet kinds. Nothing else may travel the wire."""

    HELLO = 1
    CHALLENGE = 2
    RESPONSE = 3
    PAIRCONFIRM = 4
    DATA = 5
    ACK = 6
    HEARTBEAT = 7
    NODEINFO = 8
    GOODBYE = 9


class Priority(IntEnum):
    """EMERGENCY gets reserved airtime; the third class the binary world skips."""

    EMERGENCY = 0
    PRIORITY = 1
    NORMAL = 2


class LinkState(IntEnum):
    """Tri-state link health — DEGRADED is the state binary meshes skip."""

    UP = 0
    DEGRADED = 1
    DOWN = 2


class CycleState(IntEnum):
    """Power-aware duty cycle — not just on/off."""

    ACTIVE = 0
    LISTEN = 1
    SLEEP = 2


class NodeTrust(IntEnum):
    """Directory trust — UNVERIFIED is never persisted as truth."""

    ATTESTED = 0
    UNVERIFIED = 1
    REVOKED = 2


@dataclass(frozen=True)
class Packet:
    kind: MessageKind
    priority: Priority
    flags: int
    src: bytes
    dst: bytes
    channel: int
    seq: int
    ttl: int
    payload: bytes

    def __post_init__(self) -> None:
        if len(self.src) != NODE_ID_LEN or len(self.dst) != NODE_ID_LEN:
            raise ProtocolError("node ids must be 8 bytes")
        if len(self.payload) > MAX_PAYLOAD:
            raise ProtocolError(f"payload exceeds {MAX_PAYLOAD} bytes")
        if not 0 <= self.ttl <= MAX_TTL:
            raise ProtocolError("ttl out of range")

    @property
    def is_broadcast(self) -> bool:
        return self.dst == BROADCAST_ID

    @property
    def ack_requested(self) -> bool:
        return bool(self.flags & FLAG_ACK_REQUESTED)

    def encode(self, channel_key: bytes) -> bytes:
        """Encode and authenticate. The MAC key is the channel key."""
        header = _HEADER.pack(
            PROTOCOL_MAGIC,
            PROTOCOL_VERSION,
            int(self.kind),
            int(self.priority),
            self.flags & 0xFF,
            self.src,
            self.dst,
            self.channel,
            self.seq,
            self.ttl,
            len(self.payload),
        )
        body = header + self.payload
        tag = _hmac.new(channel_key, body, hashlib.sha256).digest()
        return body + tag

    @classmethod
    def decode_unverified(cls, raw: bytes) -> "Packet":
        """Parse structure only — NO authentication. For routing the key only."""
        if len(raw) < HEADER_LEN + MAC_LEN:
            raise TruncatedPacket(f"frame too short: {len(raw)} bytes")
        magic, version, kind, priority, flags, src, dst, channel, seq, ttl, plen = (
            _HEADER.unpack(raw[:HEADER_LEN])
        )
        if magic != PROTOCOL_MAGIC:
            raise BadMagic(f"bad magic: {magic!r}")
        if version != PROTOCOL_VERSION:
            raise BadVersion(f"unsupported version: {version}")
        try:
            kind_e = MessageKind(kind)
        except ValueError:
            raise UnknownKind(f"kind {kind} is not in the registry") from None
        try:
            prio_e = Priority(priority)
        except ValueError:
            raise UnknownKind(f"priority {priority} is not a known class") from None
        if len(raw) != HEADER_LEN + plen + MAC_LEN:
            raise TruncatedPacket(f"declared payload {plen}, frame length {len(raw)}")
        payload = raw[HEADER_LEN : HEADER_LEN + plen]
        return cls(
            kind=kind_e,
            priority=prio_e,
            flags=flags,
            src=src,
            dst=dst,
            channel=channel,
            seq=seq,
            ttl=ttl,
            payload=payload,
        )

    @classmethod
    def decode_and_verify(cls, raw: bytes, channel_key: bytes) -> "Packet":
        """Decode and authenticate. Raises MacMismatch on any tampering."""
        pkt = cls.decode_unverified(raw)
        body, tag = raw[:-MAC_LEN], raw[-MAC_LEN:]
        expect = _hmac.new(channel_key, body, hashlib.sha256).digest()
        if not _hmac.compare_digest(expect, tag):
            raise MacMismatch("packet authentication failed — dropped")
        return pkt


def pack_nodeinfo(node_id: bytes, long_name: str, short_name: str) -> bytes:
    """Unverified nodeinfo block: node_id(8) | llen(1) | long | slen(1) | short."""
    long_b = long_name.encode("utf-8")[:64]
    short_b = short_name.encode("utf-8")[:8]
    return (
        bytes(node_id) + bytes([len(long_b)]) + long_b + bytes([len(short_b)]) + short_b
    )


def unpack_nodeinfo(block: bytes) -> tuple[bytes, str, str]:
    if len(block) < NODE_ID_LEN + 2:
        raise AttestationFailed("nodeinfo block too short")
    node_id = block[:NODE_ID_LEN]
    llen = block[NODE_ID_LEN]
    long_b = block[NODE_ID_LEN + 1 : NODE_ID_LEN + 1 + llen]
    rest = block[NODE_ID_LEN + 1 + llen :]
    if len(long_b) != llen or len(rest) < 1:
        raise AttestationFailed("nodeinfo block malformed")
    slen = rest[0]
    short_b = rest[1 : 1 + slen]
    if len(short_b) != slen:
        raise AttestationFailed("nodeinfo block malformed")
    return (
        node_id,
        long_b.decode("utf-8", "replace"),
        short_b.decode("utf-8", "replace"),
    )


def attest_nodeinfo(
    identity_key: bytes, node_id: bytes, long_name: str, short_name: str
) -> bytes:
    """Attested nodeinfo: block || HMAC(identity_key, block).

    Only the holder of the identity key can produce a valid attestation for
    a node id, so spoofed nodeinfo (the DEF CON 2025 finding) is rejected at
    the protocol layer, not the app layer.
    """
    info = pack_nodeinfo(node_id, long_name, short_name)
    tag = _hmac.new(identity_key, info, hashlib.sha256).digest()
    return info + tag


def verify_nodeinfo(
    attested: bytes, identity_key: bytes, expected_node_id: bytes
) -> tuple[str, str]:
    """Verify an attested nodeinfo block. Returns (long_name, short_name)."""
    if len(attested) < MAC_LEN:
        raise AttestationFailed("attested nodeinfo too short")
    info, tag = attested[:-MAC_LEN], attested[-MAC_LEN:]
    expect = _hmac.new(identity_key, info, hashlib.sha256).digest()
    if not _hmac.compare_digest(expect, tag):
        raise AttestationFailed("nodeinfo attestation tag invalid")
    node_id, long_name, short_name = unpack_nodeinfo(info)
    if node_id != bytes(expected_node_id):
        raise AttestationFailed("nodeinfo attestation is for a different node")
    return long_name, short_name


def describe(pkt: Packet) -> str:
    """One human-readable line per packet — the clear network is auditable."""
    dst = "broadcast" if pkt.is_broadcast else pkt.dst.hex()
    return (
        f"{pkt.kind.name} pri={pkt.priority.name} "
        f"{pkt.src.hex()}->{dst} ch={pkt.channel} "
        f"seq={pkt.seq} ttl={pkt.ttl} len={len(pkt.payload)}"
    )
