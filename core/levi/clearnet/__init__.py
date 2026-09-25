"""CLEAR network — the open, transparent fabric (KFX² MESH milestone 0.1).

The opposite of a dark web: every packet kind is declared in a closed
registry, every packet is authenticated, every routing decision is
deterministic and audit-logged. Opt-in peering, no hidden channels,
no deceptive routing, no cloud relay in the data path.

Milestone 0.1 (mesh protocol spec) as a loopback-proven reference:
packet format, addressing, hop budget, priority classes (EMERGENCY gets
reserved airtime), authenticated channel handshake, nodeinfo
attestation. Transports are 127.0.0.1-only; wide-area peering is gated.

Ternary third-states: Priority EMERGENCY/PRIORITY/NORMAL,
LinkState UP/DEGRADED/DOWN, CycleState ACTIVE/LISTEN/SLEEP,
NodeTrust ATTESTED/UNVERIFIED/REVOKED.
Paired mind: Proposer drafts forwarding plans, Verifier approves them.

Honest limits: payload sealing is reference-grade (HKDF keystream), not
a vetted AEAD — milestone 0.3 must replace it before any field use.
"""

from __future__ import annotations

from .crypto import (
    ChainRatchet,
    DeviceIdentity,
    GoldenImageError,
    EntropyGateError,
    load_device,
    provision_device,
)
from .protocol import (
    BROADCAST_ID,
    CONTROL_CHANNEL,
    DEFAULT_TTL,
    MAX_PAYLOAD,
    MAX_TTL,
    PROTOCOL_MAGIC,
    PROTOCOL_VERSION,
    CycleState,
    LinkState,
    MessageKind,
    NodeTrust,
    Packet,
    PolicyDenied,
    Priority,
    ProtocolError,
    attest_nodeinfo,
    describe,
    verify_nodeinfo,
)
from .routing import Forwarder, Proposer, RoutePlan, Verifier
from .tower import ClearTower
from .wire import (
    LoopbackPair,
    NetworkExposureError,
    VirtualWire,
    assert_loopback,
    loopback_connect,
)

__all__ = [
    "ClearTower",
    "VirtualWire",
    "LoopbackPair",
    "NetworkExposureError",
    "assert_loopback",
    "loopback_connect",
    "Proposer",
    "Verifier",
    "RoutePlan",
    "Forwarder",
    "Packet",
    "ProtocolError",
    "PolicyDenied",
    "GoldenImageError",
    "EntropyGateError",
    "DeviceIdentity",
    "provision_device",
    "load_device",
    "ChainRatchet",
    "MessageKind",
    "Priority",
    "LinkState",
    "CycleState",
    "NodeTrust",
    "attest_nodeinfo",
    "verify_nodeinfo",
    "describe",
    "BROADCAST_ID",
    "CONTROL_CHANNEL",
    "DEFAULT_TTL",
    "MAX_PAYLOAD",
    "MAX_TTL",
    "PROTOCOL_MAGIC",
    "PROTOCOL_VERSION",
]
