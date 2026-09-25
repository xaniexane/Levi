"""ClearTower — the tower is the node.

LEVI runs ON the tower: store-and-forward with on-node intelligence —
priority triage, delay-tolerant routing, a local directory, power-aware
duty cycling. A phone is a client, never a dependency.

Hard rules baked in:
* Loopback-only transport. The tower never dials beyond 127.0.0.1
  (see wire.assert_loopback); wide-area peering is gated on Chauncey.
* Opt-in everything. A tower starts with zero peers, zero channels, and
  relays nothing until the owner explicitly provisions them. Unsolicited
  HELLOs are ignored, not answered.
* No cloud relay in the data path — ever.
* Authenticated channels by default. Pairwise sessions are sealed with
  per-message ratchet keys (forward secrecy); channel traffic carries an
  HMAC the whole channel can check.

Pairing ceremony (explicit opt-in on BOTH sides):
    owner A: tower_a.initiate_pairing(id_b, psk)
    owner B: tower_b.expect_pairing(id_a, psk)
    HELLO -> CHALLENGE -> RESPONSE -> PAIRCONFIRM, then attested NODEINFO.
Both sides prove knowledge of the PSK; identity keys travel only inside
the session, sealed by the session key; nodeinfo is attested with the
identity key, so spoofed nodeinfo is rejected at the protocol layer.
"""

from __future__ import annotations

import json
import os
import secrets
import time
from collections import deque
from dataclasses import dataclass, replace

from . import crypto
from .crypto import ChainRatchet, DeviceIdentity
from .protocol import (
    BROADCAST_ID,
    CONTROL_CHANNEL,
    DEFAULT_TTL,
    FLAG_ACK_REQUESTED,
    MAX_PAYLOAD,
    LinkState,
    CycleState,
    MessageKind,
    NodeTrust,
    Packet,
    PolicyDenied,
    Priority,
    ProtocolError,
    attest_nodeinfo,
    describe,
    pack_nodeinfo,
    verify_nodeinfo,
)
from .routing import Forwarder, Proposer, Verifier
from .wire import VirtualWire

LINK_DEGRADED_SEC = 30.0
LINK_DOWN_SEC = 120.0
UNSEALED_INDEX = 0xFFFFFFFF
DISPATCH_BUDGET = 8
AUDIT_CAP = 2000


@dataclass
class _Peer:
    node_id: bytes
    long_name: str
    short_name: str
    link: LinkState = LinkState.UP
    identity_key: bytes = b""
    session_key: bytes = b""
    pair_channel: int = 0
    tx: ChainRatchet | None = None
    rx: ChainRatchet | None = None
    last_seen: float = 0.0


@dataclass
class _Pairing:
    peer_id: bytes
    psk: bytes
    role: str  # "initiator" | "responder"
    step: str
    Na: bytes = b""
    Nb: bytes = b""
    session: bytes = b""


@dataclass
class _DirectoryEntry:
    node_id: bytes
    long_name: str
    short_name: str
    trust: NodeTrust
    updated: float


@dataclass
class _Delivery:
    packet: Packet
    plaintext: bytes


@dataclass
class _OutboxItem:
    peer_id: bytes
    frame: bytes
    note: str


class ClearTower:
    """A CLEAR mesh tower node. Local-first, opt-in, loopback-only."""

    def __init__(
        self,
        name: str,
        data_dir: str,
        *,
        short_name: str | None = None,
        audit_enabled: bool = True,
        power_profile: str = "always",
    ):
        self.name = name
        self.short_name = short_name or name[:8]
        self.data_dir = data_dir
        self.identity: DeviceIdentity = crypto.load_device(data_dir)
        self.peers: dict[bytes, _Peer] = {}
        self.directory: dict[bytes, _DirectoryEntry] = {}
        self.channels: dict[int, bytes] = {}  # channel_id -> channel key
        self.outbox: dict[Priority, deque[_OutboxItem]] = {
            Priority.EMERGENCY: deque(),
            Priority.PRIORITY: deque(),
            Priority.NORMAL: deque(),
        }
        self.inbox: deque[bytes] = deque()
        self.delivered: list[_Delivery] = []
        self.wire: VirtualWire | None = None
        self.audit_enabled = audit_enabled
        self.power_profile = power_profile
        self.cycle_override: CycleState | None = None
        self.stats = {"sent": 0, "relayed": 0, "dropped": 0, "delivered": 0}
        self._seq = 0
        self._pairings: dict[bytes, _Pairing] = {}
        self._forwarder = Forwarder()
        self._proposer = Proposer()
        self._verifier = Verifier()
        self._audit_lines: list[str] = []
        os.makedirs(data_dir, exist_ok=True)
        self._write_manifest()
        self._audit("tower-boot", f"{self.name} id={self.node_id.hex()}")

    @property
    def node_id(self) -> bytes:
        return self.identity.node_id

    # ------------------------------------------------------------------ setup

    def _write_manifest(self) -> None:
        manifest = {
            "name": self.name,
            "node_id": self.node_id.hex(),
            "protocol": "CLRM/1",
            "transport_policy": "loopback-only (127.0.0.1) — wide-area peering gated",
            "pairing": "explicit opt-in on both sides",
            "audit_enabled": self.audit_enabled,
            "power_profile": self.power_profile,
            "note": "No cloud relay in the data path. No hidden channels: "
            "every packet kind is declared in protocol.MessageKind.",
        }
        with open(os.path.join(self.data_dir, "manifest.json"), "w") as fh:
            json.dump(manifest, fh, indent=2)

    def attach_wire(self, wire: VirtualWire) -> None:
        wire.attach(self)

    def set_power_profile(self, profile: str) -> None:
        if profile not in ("always", "saver"):
            raise PolicyDenied(f"unknown power profile {profile!r}")
        self.power_profile = profile
        self._audit("power-profile", profile)

    def set_cycle_override(self, state: CycleState | None) -> None:
        """Owner control of the radio cycle — SLEEP is the honest 'off'."""
        self.cycle_override = state
        self._audit("cycle-override", str(state))

    def _cycle_state(self, now: float | None = None) -> CycleState:
        if self.cycle_override is not None:
            return self.cycle_override
        if self.power_profile == "always":
            return CycleState.ACTIVE
        hour = time.gmtime(now if now is not None else time.time()).tm_hour
        return CycleState.ACTIVE if hour % 2 == 0 else CycleState.LISTEN

    # ---------------------------------------------------------------- pairing

    def expect_pairing(self, peer_id: bytes, psk: bytes) -> None:
        """Owner opt-in: this tower will answer a HELLO from peer_id."""
        peer_id = bytes(peer_id)
        self._check_psk(psk)
        self._pairings[peer_id] = _Pairing(
            peer_id=peer_id, psk=bytes(psk), role="responder", step="expecting"
        )
        self._audit("pairing-expected", f"will answer HELLO from {peer_id.hex()}")

    def initiate_pairing(self, peer_id: bytes, psk: bytes) -> None:
        """Owner opt-in: begin the pairing ceremony with peer_id."""
        peer_id = bytes(peer_id)
        self._check_psk(psk)
        if peer_id in self.peers:
            raise PolicyDenied("already paired with this tower")
        Na = secrets.token_bytes(32)
        self._pairings[peer_id] = _Pairing(
            peer_id=peer_id, psk=bytes(psk), role="initiator", Na=Na, step="hello-sent"
        )
        payload = Na + pack_nodeinfo(self.node_id, self.name, self.short_name)
        pkt = Packet(
            kind=MessageKind.HELLO,
            priority=Priority.PRIORITY,
            flags=0,
            src=self.node_id,
            dst=peer_id,
            channel=CONTROL_CHANNEL,
            seq=self._next_seq(),
            ttl=1,
            payload=payload,
        )
        self._emit_control(peer_id, pkt, psk)
        self._audit("pairing-initiated", f"HELLO -> {peer_id.hex()}")

    @staticmethod
    def _check_psk(psk: bytes) -> None:
        if len(psk) < crypto.MIN_PAIRING_PSK_LEN:
            raise PolicyDenied("pairing PSK must be at least 16 bytes")

    def _register_peer(
        self,
        peer_id: bytes,
        identity_key: bytes,
        session_key: bytes,
        long_name: str,
        short_name: str,
    ) -> _Peer:
        pair_channel = crypto.pair_channel_id(self.node_id, peer_id)
        chan_key = crypto.pair_channel_key(session_key)
        peer = _Peer(
            node_id=bytes(peer_id),
            long_name=long_name,
            short_name=short_name,
            link=LinkState.UP,
            identity_key=bytes(identity_key),
            session_key=bytes(session_key),
            pair_channel=pair_channel,
            tx=ChainRatchet(crypto.direction_key(session_key, self.node_id, peer_id)),
            rx=ChainRatchet(crypto.direction_key(session_key, peer_id, self.node_id)),
            last_seen=time.time(),
        )
        self.peers[bytes(peer_id)] = peer
        self.channels[pair_channel] = chan_key
        self._audit(
            "peer-registered",
            f"{peer_id.hex()} ({long_name}) pair-channel={pair_channel}",
        )
        return peer

    # ---------------------------------------------------------------- channels

    def join_channel(self, channel_id: int, channel_key: bytes) -> None:
        """Owner opt-in: join a channel (e.g. the neighborhood commons)."""
        if len(channel_key) < 16:
            raise PolicyDenied("channel key must be at least 16 bytes")
        self.channels[int(channel_id)] = bytes(channel_key)
        self._audit("channel-joined", f"ch={channel_id}")

    def leave_channel(self, channel_id: int) -> None:
        self.channels.pop(int(channel_id), None)
        self._audit("channel-left", f"ch={channel_id}")

    # ------------------------------------------------------------------ send

    def send_data(
        self,
        dst_id: bytes,
        plaintext: bytes,
        priority: Priority = Priority.NORMAL,
        channel: int | None = None,
        ack: bool = False,
    ) -> None:
        dst_id = bytes(dst_id)
        plaintext = bytes(plaintext)
        if len(plaintext) + 4 > MAX_PAYLOAD:
            raise PolicyDenied("plaintext exceeds maximum payload")
        if channel is None:
            if dst_id == BROADCAST_ID:
                raise PolicyDenied("broadcast requires an explicit channel")
            peer = self.peers.get(dst_id)
            if peer is None:
                raise PolicyDenied("no paired session and no channel — opt-in required")
            channel = peer.pair_channel
        key = self.channels.get(channel)
        if key is None:
            raise PolicyDenied(f"channel {channel} not joined")

        seq = self._next_seq()
        peer = self.peers.get(dst_id)
        if (
            peer is not None
            and peer.session_key
            and channel == peer.pair_channel
            and peer.tx is not None
        ):
            index, msg_key = peer.tx.send_key()
            nonce = (
                channel.to_bytes(4, "big")
                + seq.to_bytes(4, "big")
                + index.to_bytes(4, "big")
            )
            payload = index.to_bytes(4, "big") + crypto.seal(msg_key, nonce, plaintext)
        else:
            payload = UNSEALED_INDEX.to_bytes(4, "big") + plaintext

        pkt = Packet(
            kind=MessageKind.DATA,
            priority=priority,
            flags=FLAG_ACK_REQUESTED if ack else 0,
            src=self.node_id,
            dst=dst_id,
            channel=channel,
            seq=seq,
            ttl=DEFAULT_TTL,
            payload=payload,
        )
        frame = pkt.encode(key)
        if dst_id == BROADCAST_ID:
            targets = [
                pid for pid, p in self.peers.items() if p.link is not LinkState.DOWN
            ]
            if not targets:
                raise PolicyDenied("no live peers to broadcast to")
            for pid in targets:
                self._emit(pid, frame, priority, "broadcast")
        elif dst_id in self.peers:
            self._emit(dst_id, frame, priority, "data")
        else:
            plan = self._proposer.propose(
                pkt, {pid: p.link for pid, p in self.peers.items()}
            )
            if plan is None:
                raise PolicyDenied("no route to destination")
            self._verifier.verify(plan, pkt, channel_joined=True, loopback_ok=True)
            self._emit(plan.next_hop, frame, priority, f"originate via {plan.note}")

    def broadcast(self, channel_id: int, plaintext: bytes) -> None:
        """Emergency broadcast primitive — reserved airtime, protocol-level."""
        self.send_data(
            BROADCAST_ID, plaintext, priority=Priority.EMERGENCY, channel=channel_id
        )
        self._audit("emergency-broadcast", f"ch={channel_id} len={len(plaintext)}")

    def send_nodeinfo(self, peer_id: bytes) -> None:
        peer = self.peers.get(bytes(peer_id))
        if peer is None or not peer.session_key:
            raise PolicyDenied("not paired")
        attested = attest_nodeinfo(
            self.identity.identity_key, self.node_id, self.name, self.short_name
        )
        pkt = Packet(
            kind=MessageKind.NODEINFO,
            priority=Priority.NORMAL,
            flags=0,
            src=self.node_id,
            dst=peer.node_id,
            channel=peer.pair_channel,
            seq=self._next_seq(),
            ttl=1,
            payload=attested,
        )
        self._emit(
            peer.node_id,
            pkt.encode(self.channels[peer.pair_channel]),
            Priority.NORMAL,
            "nodeinfo",
        )

    def heartbeat_all(self) -> None:
        for peer in self.peers.values():
            if not peer.session_key:
                continue
            pkt = Packet(
                kind=MessageKind.HEARTBEAT,
                priority=Priority.PRIORITY,
                flags=0,
                src=self.node_id,
                dst=peer.node_id,
                channel=peer.pair_channel,
                seq=self._next_seq(),
                ttl=1,
                payload=b"",
            )
            self._emit(
                peer.node_id,
                pkt.encode(self.channels[peer.pair_channel]),
                Priority.PRIORITY,
                "heartbeat",
            )

    def sweep(self, now: float | None = None) -> None:
        """Tri-state link maintenance from heartbeat freshness."""
        now = time.time() if now is None else now
        for peer in self.peers.values():
            age = now - peer.last_seen
            if age >= LINK_DOWN_SEC and peer.link is not LinkState.DOWN:
                peer.link = LinkState.DOWN
                self._audit("peer-down", f"{peer.node_id.hex()} silent {age:.0f}s")
            elif age >= LINK_DEGRADED_SEC and peer.link is LinkState.UP:
                peer.link = LinkState.DEGRADED
                self._audit("peer-degraded", f"{peer.node_id.hex()} silent {age:.0f}s")

    def revoke_peer(self, peer_id: bytes) -> None:
        """Owner action: revoke a peer — its attestations are dead here."""
        peer_id = bytes(peer_id)
        peer = self.peers.pop(peer_id, None)
        if peer is not None:
            self.channels.pop(peer.pair_channel, None)
        self.directory[peer_id] = _DirectoryEntry(
            node_id=peer_id,
            long_name=peer.long_name if peer else "?",
            short_name=peer.short_name if peer else "?",
            trust=NodeTrust.REVOKED,
            updated=time.time(),
        )
        self._audit("peer-revoked", peer_id.hex())

    # ------------------------------------------------------------ main loop

    def tick(self) -> None:
        cycle = self._cycle_state()
        if cycle is CycleState.SLEEP:
            self._audit("tick-held", "SLEEP — radio off, inbox accumulating")
            return
        while self.inbox:
            self._process_frame(self.inbox.popleft())
        if cycle is CycleState.ACTIVE:
            self.dispatch()
        # LISTEN: inbox processed, nothing transmitted.

    def dispatch(self, budget: int = DISPATCH_BUDGET) -> int:
        """Priority scheduler with reserved emergency airtime.

        EMERGENCY is always drained first and is guaranteed at least half
        the budget whenever it is non-empty — reserved airtime is physics
        in the scheduler, not a feature in an app.
        """
        sent = 0
        emergency = self.outbox[Priority.EMERGENCY]
        reserve = max(1, budget // 2)
        while emergency and sent < reserve:
            self._transmit(emergency.popleft())
            sent += 1
        remaining = budget - sent
        for pri in (Priority.EMERGENCY, Priority.PRIORITY, Priority.NORMAL):
            queue = self.outbox[pri]
            while queue and remaining > 0:
                self._transmit(queue.popleft())
                sent += 1
                remaining -= 1
        return sent

    # --------------------------------------------------------------- internals

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _emit(
        self, peer_id: bytes, frame: bytes, priority: Priority, note: str
    ) -> None:
        self.outbox[priority].append(
            _OutboxItem(peer_id=bytes(peer_id), frame=bytes(frame), note=note)
        )

    def _emit_control(self, peer_id: bytes, pkt: Packet, psk: bytes) -> None:
        self._emit(peer_id, pkt.encode(psk), pkt.priority, f"control/{pkt.kind.name}")

    def _transmit(self, item: _OutboxItem) -> None:
        if self.wire is None:
            self._audit("tx-no-wire", "no wire attached — frame held")
            return
        ok = self.wire.transmit(self.node_id, item.peer_id, item.frame)
        self.stats["sent"] += 1
        if not ok:
            self.stats["dropped"] += 1
            self._audit("tx-no-endpoint", f"{item.peer_id.hex()} unreachable")

    def _process_frame(self, frame: bytes) -> None:
        try:
            header = Packet.decode_unverified(frame)
        except ProtocolError as exc:
            self.stats["dropped"] += 1
            self._audit("malformed", f"{type(exc).__name__}: {exc}")
            return
        if header.channel == CONTROL_CHANNEL:
            self._process_control(frame, header)
            return
        key = self.channels.get(header.channel)
        if key is None:
            self.stats["dropped"] += 1
            self._audit("unknown-channel", f"ch={header.channel} — not a member")
            return
        try:
            pkt = Packet.decode_and_verify(frame, key)
        except ProtocolError as exc:
            self.stats["dropped"] += 1
            self._audit("mac-mismatch", f"from {header.src.hex()}: {exc}")
            return
        self._process_data_packet(pkt, key)

    # --------------------------------------------------------------- handshake

    def _process_control(self, frame: bytes, header: Packet) -> None:
        pairing = self._pairings.get(header.src)
        if pairing is None:
            self.stats["dropped"] += 1
            self._audit(
                "unsolicited-control",
                f"{header.kind.name} from {header.src.hex()} — no opt-in, ignored",
            )
            return
        try:
            pkt = Packet.decode_and_verify(frame, pairing.psk)
        except ProtocolError as exc:
            self.stats["dropped"] += 1
            self._audit("control-auth-failed", f"{header.src.hex()}: {exc}")
            return
        if pkt.ttl != 1:
            self.stats["dropped"] += 1
            self._audit("control-relayed", "handshake packets never relay — dropped")
            return
        handler = {
            (MessageKind.HELLO, "responder", "expecting"): self._on_hello,
            (MessageKind.CHALLENGE, "initiator", "hello-sent"): self._on_challenge,
            (MessageKind.RESPONSE, "responder", "challenged"): self._on_response,
            (MessageKind.PAIRCONFIRM, "initiator", "responded"): self._on_pairconfirm,
        }.get((pkt.kind, pairing.role, pairing.step))
        if handler is None:
            self.stats["dropped"] += 1
            self._audit(
                "control-out-of-order",
                f"{pkt.kind.name} in state {pairing.role}/{pairing.step}",
            )
            return
        handler(pkt, pairing)

    def _on_hello(self, pkt: Packet, pairing: _Pairing) -> None:
        Na = pkt.payload[:32]
        # Names in HELLO are UNVERIFIED by construction — never trusted,
        # never written to the directory. Attested nodeinfo arrives later.
        pairing.Na = Na
        pairing.Nb = secrets.token_bytes(32)
        pairing.step = "challenged"
        proof = crypto.mac(
            pairing.psk, b"clearnet-proof-b", Na, pairing.Nb, pkt.src, self.node_id
        )
        challenge = Packet(
            kind=MessageKind.CHALLENGE,
            priority=Priority.PRIORITY,
            flags=0,
            src=self.node_id,
            dst=pkt.src,
            channel=CONTROL_CHANNEL,
            seq=self._next_seq(),
            ttl=1,
            payload=pairing.Nb + proof,
        )
        self._emit_control(pkt.src, challenge, pairing.psk)
        self._audit("challenge-sent", f"-> {pkt.src.hex()}")

    def _on_challenge(self, pkt: Packet, pairing: _Pairing) -> None:
        Nb, proof_b = pkt.payload[:32], pkt.payload[32:64]
        expect = crypto.mac(
            pairing.psk, b"clearnet-proof-b", pairing.Na, Nb, self.node_id, pkt.src
        )
        if not secrets.compare_digest(expect, proof_b):
            self.stats["dropped"] += 1
            self._audit("pairing-failed", f"{pkt.src.hex()}: bad challenge proof")
            pairing.step = "failed"
            return
        pairing.Nb = Nb
        session = crypto.session_key_for(pairing.psk, pairing.Na, Nb)
        pairing.session = session
        nonce = crypto.pair_nonce(pairing.Na, Nb, b"clearnet-seal-id-a")
        sealed_id = crypto.seal(session, nonce, self.identity.identity_key)
        proof_a = crypto.mac(
            pairing.psk, b"clearnet-proof-a", pairing.Na, Nb, self.node_id, pkt.src
        )
        response = Packet(
            kind=MessageKind.RESPONSE,
            priority=Priority.PRIORITY,
            flags=0,
            src=self.node_id,
            dst=pkt.src,
            channel=CONTROL_CHANNEL,
            seq=self._next_seq(),
            ttl=1,
            payload=proof_a + sealed_id,
        )
        self._emit_control(pkt.src, response, pairing.psk)
        pairing.step = "responded"
        self._audit("response-sent", f"-> {pkt.src.hex()}")

    def _on_response(self, pkt: Packet, pairing: _Pairing) -> None:
        proof_a, sealed = pkt.payload[:32], pkt.payload[32:64]
        expect = crypto.mac(
            pairing.psk,
            b"clearnet-proof-a",
            pairing.Na,
            pairing.Nb,
            pkt.src,
            self.node_id,
        )
        if not secrets.compare_digest(expect, proof_a):
            self.stats["dropped"] += 1
            self._audit("pairing-failed", f"{pkt.src.hex()}: bad response proof")
            pairing.step = "failed"
            return
        session = crypto.session_key_for(pairing.psk, pairing.Na, pairing.Nb)
        pairing.session = session
        nonce = crypto.pair_nonce(pairing.Na, pairing.Nb, b"clearnet-seal-id-a")
        identity_key_a = crypto.unseal(session, nonce, sealed)
        self._register_peer(pkt.src, identity_key_a, session, "?", "?")
        nonce_b = crypto.pair_nonce(pairing.Na, pairing.Nb, b"clearnet-seal-id-b")
        sealed_b = crypto.seal(session, nonce_b, self.identity.identity_key)
        attested = attest_nodeinfo(
            self.identity.identity_key, self.node_id, self.name, self.short_name
        )
        confirm = Packet(
            kind=MessageKind.PAIRCONFIRM,
            priority=Priority.PRIORITY,
            flags=0,
            src=self.node_id,
            dst=pkt.src,
            channel=CONTROL_CHANNEL,
            seq=self._next_seq(),
            ttl=1,
            payload=sealed_b + attested,
        )
        self._emit_control(pkt.src, confirm, pairing.psk)
        pairing.step = "done"
        self._audit(
            "pairing-complete", f"<-> {pkt.src.hex()} (awaiting attested nodeinfo)"
        )

    def _on_pairconfirm(self, pkt: Packet, pairing: _Pairing) -> None:
        sealed_b, attested = pkt.payload[:32], pkt.payload[32:]
        nonce_b = crypto.pair_nonce(pairing.Na, pairing.Nb, b"clearnet-seal-id-b")
        identity_key_b = crypto.unseal(pairing.session, nonce_b, sealed_b)
        try:
            long_name, short_name = verify_nodeinfo(attested, identity_key_b, pkt.src)
        except ProtocolError as exc:
            self.stats["dropped"] += 1
            self._audit("pairing-failed", f"{pkt.src.hex()}: {exc}")
            pairing.step = "failed"
            return
        self._register_peer(
            pkt.src, identity_key_b, pairing.session, long_name, short_name
        )
        self.directory[bytes(pkt.src)] = _DirectoryEntry(
            node_id=bytes(pkt.src),
            long_name=long_name,
            short_name=short_name,
            trust=NodeTrust.ATTESTED,
            updated=time.time(),
        )
        pairing.step = "done"
        self._audit("pairing-complete", f"<-> {pkt.src.hex()} ({long_name}) ATTESTED")
        self.send_nodeinfo(pkt.src)

    # ------------------------------------------------------------ data path

    def _process_data_packet(self, pkt: Packet, key: bytes) -> None:
        entry = self.directory.get(pkt.src)
        if entry is not None and entry.trust is NodeTrust.REVOKED:
            self.stats["dropped"] += 1
            self._audit("revoked-sender", f"packet from {pkt.src.hex()} refused")
            return
        if pkt.dst == self.node_id:
            self._consume(pkt)
        elif pkt.is_broadcast:
            if self._forwarder.seen(pkt.src, pkt.seq):
                self._audit("duplicate", f"broadcast {pkt.src.hex()}#{pkt.seq} ignored")
                return
            self._forwarder.mark(pkt.src, pkt.seq)
            self._consume(pkt)
            self._flood(pkt, key)
        else:
            self._relay(pkt, key)

    def _consume(self, pkt: Packet) -> None:
        peer = self.peers.get(pkt.src)
        if pkt.kind is MessageKind.DATA:
            if len(pkt.payload) < 4:
                self.stats["dropped"] += 1
                self._audit("short-payload", describe(pkt))
                return
            index = int.from_bytes(pkt.payload[:4], "big")
            body = pkt.payload[4:]
            if index == UNSEALED_INDEX:
                plaintext = body
            else:
                if peer is None or peer.rx is None:
                    self.stats["dropped"] += 1
                    self._audit("unknown-sender", f"sealed DATA from {pkt.src.hex()}")
                    return
                try:
                    msg_key = peer.rx.recv_key(index)
                except ProtocolError as exc:
                    self.stats["dropped"] += 1
                    self._audit("ratchet-refused", f"{pkt.src.hex()}: {exc}")
                    return
                nonce = (
                    pkt.channel.to_bytes(4, "big")
                    + pkt.seq.to_bytes(4, "big")
                    + index.to_bytes(4, "big")
                )
                plaintext = crypto.unseal(msg_key, nonce, body)
            self.delivered.append(_Delivery(packet=pkt, plaintext=plaintext))
            self.stats["delivered"] += 1
            self._audit("delivered", describe(pkt))
            if pkt.ack_requested and peer is not None and peer.session_key:
                self._send_ack(peer, pkt)
        elif pkt.kind is MessageKind.ACK:
            seq = (
                int.from_bytes(pkt.payload[:4], "big") if len(pkt.payload) >= 4 else -1
            )
            self._audit("ack-received", f"from {pkt.src.hex()} seq={seq}")
        elif pkt.kind is MessageKind.HEARTBEAT:
            if peer is not None:
                peer.last_seen = time.time()
                if peer.link is not LinkState.UP:
                    peer.link = LinkState.UP
                    self._audit("peer-up", peer.node_id.hex())
        elif pkt.kind is MessageKind.NODEINFO:
            if peer is None or not peer.identity_key:
                self.stats["dropped"] += 1
                self._audit("nodeinfo-unpaired", f"from {pkt.src.hex()} — ignored")
                return
            try:
                long_name, short_name = verify_nodeinfo(
                    pkt.payload, peer.identity_key, pkt.src
                )
            except ProtocolError as exc:
                self.stats["dropped"] += 1
                self._audit("nodeinfo-rejected", f"{pkt.src.hex()}: {exc}")
                return
            peer.long_name, peer.short_name = long_name, short_name
            self.directory[bytes(pkt.src)] = _DirectoryEntry(
                node_id=bytes(pkt.src),
                long_name=long_name,
                short_name=short_name,
                trust=NodeTrust.ATTESTED,
                updated=time.time(),
            )
            self._audit("nodeinfo-accepted", f"{pkt.src.hex()} ({long_name}) ATTESTED")
        elif pkt.kind is MessageKind.GOODBYE:
            if peer is not None:
                peer.link = LinkState.DOWN
                self._audit("peer-goodbye", peer.node_id.hex())

    def _send_ack(self, peer: _Peer, pkt: Packet) -> None:
        ack = Packet(
            kind=MessageKind.ACK,
            priority=Priority.PRIORITY,
            flags=0,
            src=self.node_id,
            dst=peer.node_id,
            channel=pkt.channel,
            seq=self._next_seq(),
            ttl=1,
            payload=pkt.seq.to_bytes(4, "big"),
        )
        self._emit(
            peer.node_id,
            ack.encode(self.channels[pkt.channel]),
            Priority.PRIORITY,
            "ack",
        )

    def _relay(self, pkt: Packet, key: bytes) -> None:
        if self._forwarder.seen(pkt.src, pkt.seq):
            self._audit("duplicate", f"{pkt.src.hex()}#{pkt.seq} already forwarded")
            return
        self._forwarder.mark(pkt.src, pkt.seq)
        plan = self._proposer.propose(
            pkt, {pid: p.link for pid, p in self.peers.items()}
        )
        if plan is None:
            self.stats["dropped"] += 1
            self._audit("no-route", describe(pkt))
            return
        try:
            self._verifier.verify(plan, pkt, channel_joined=True, loopback_ok=True)
        except PolicyDenied as exc:
            self.stats["dropped"] += 1
            self._audit("relay-refused", f"{describe(pkt)}: {exc}")
            return
        fwd = replace(pkt, ttl=pkt.ttl - 1)
        self._emit(plan.next_hop, fwd.encode(key), pkt.priority, f"relay {plan.note}")
        self.stats["relayed"] += 1
        self._audit("relayed", f"{describe(fwd)} via {plan.next_hop.hex()}")

    def _flood(self, pkt: Packet, key: bytes) -> None:
        if pkt.ttl <= 1:
            self._audit("flood-held", "hop budget exhausted at flood")
            return
        fwd = replace(pkt, ttl=pkt.ttl - 1)
        frame = fwd.encode(key)
        for pid, peer in self.peers.items():
            if pid == pkt.src or peer.link is LinkState.DOWN:
                continue
            self._emit(pid, frame, pkt.priority, "flood")
            self.stats["relayed"] += 1
        self._audit("flooded", describe(fwd))

    # ----------------------------------------------------------------- audit

    def _audit(self, event: str, detail: str = "") -> None:
        line = f"{time.strftime('%H:%M:%S')} {event} {detail}".rstrip()
        self._audit_lines.append(line)
        if len(self._audit_lines) > AUDIT_CAP:
            del self._audit_lines[: len(self._audit_lines) - AUDIT_CAP]
        if self.audit_enabled:
            path = os.path.join(self.data_dir, "audit.jsonl")
            record = {"t": time.time(), "event": event, "detail": detail}
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")

    def audit_text(self) -> str:
        """The whole tower, legible — the clear network is auditable."""
        return "\n".join(self._audit_lines)


__all__ = [
    "ClearTower",
    "LINK_DEGRADED_SEC",
    "LINK_DOWN_SEC",
    "DISPATCH_BUDGET",
    "UNSEALED_INDEX",
]
