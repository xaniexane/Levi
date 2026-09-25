"""Tests for the CLEAR network reference (KFX2 MESH milestone 0.1).

Hermetic: VirtualWire is in-process; LoopbackPair is TCP on 127.0.0.1
only. No wide-area networking anywhere in this file.
"""

import struct
import time

import pytest

from levi.clearnet import (
    BROADCAST_ID,
    DEFAULT_TTL,
    MAX_PAYLOAD,
    ChainRatchet,
    ClearTower,
    CycleState,
    LinkState,
    LoopbackPair,
    MessageKind,
    NetworkExposureError,
    NodeTrust,
    Packet,
    PolicyDenied,
    Priority,
    ProtocolError,
    VirtualWire,
    assert_loopback,
    attest_nodeinfo,
    describe,
    loopback_connect,
    provision_device,
    verify_nodeinfo,
)
from levi.clearnet import crypto
from levi.clearnet.protocol import (
    HEADER_LEN,
    MAC_LEN,
    PROTOCOL_MAGIC,
    PROTOCOL_VERSION,
    MacMismatch,
    UnknownKind,
)
from levi.clearnet.routing import Forwarder, Proposer, RoutePlan, Verifier
from levi.clearnet.wire import LOOPBACK_HOSTS

PSK = b"0123456789abcdef"  # 16 bytes
COMMONS = 4242
COMMONS_KEY = b"commons-channel-key-32-bytes!!!!"


def make_tower(name, tmp_path):
    return ClearTower(name, str(tmp_path / name))


def make_wire(*towers):
    wire = VirtualWire()
    for tower in towers:
        wire.attach(tower)
    return wire


def pair(a, b, psk=PSK):
    """Drive a full pairing ceremony over the shared wire."""
    b.expect_pairing(a.node_id, psk)
    a.initiate_pairing(b.node_id, psk)
    for _ in range(30):
        a.tick()
        b.tick()
        if (
            b.node_id in a.directory
            and a.directory[b.node_id].trust is NodeTrust.ATTESTED
            and a.node_id in b.directory
            and b.directory[a.node_id].trust is NodeTrust.ATTESTED
        ):
            break
    assert b.node_id in a.peers, "pairing did not complete (a side)"
    assert a.node_id in b.peers, "pairing did not complete (b side)"


def pump(*towers, rounds=10):
    for _ in range(rounds):
        for tower in towers:
            tower.tick()


# ------------------------------------------------------------- provisioning


def test_first_boot_provisions_unique_identities(tmp_path):
    a = make_tower("alpha", tmp_path)
    b = make_tower("beta", tmp_path)
    assert a.node_id != b.node_id
    assert len(a.node_id) == 8
    assert (tmp_path / "alpha" / "identity.json").exists()


def test_golden_image_refused(tmp_path):
    make_tower("alpha", tmp_path)
    with pytest.raises(crypto.GoldenImageError):
        provision_device(str(tmp_path / "alpha"))


def test_entropy_gate_rejects_weak_secret():
    with pytest.raises(crypto.EntropyGateError):
        crypto._entropy_gate(b"\x00" * 64)
    with pytest.raises(crypto.EntropyGateError):
        crypto._entropy_gate(b"\xab" * 64)


def test_hkdf_deterministic():
    assert crypto.hkdf(b"ikm", info=b"x") == crypto.hkdf(b"ikm", info=b"x")
    assert crypto.hkdf(b"ikm", info=b"x") != crypto.hkdf(b"ikm", info=b"y")


def test_seal_roundtrip():
    key = b"k" * 32
    nonce = b"n" * 12
    ct = crypto.seal(key, nonce, b"secret payload")
    assert ct != b"secret payload"
    assert crypto.unseal(key, nonce, ct) == b"secret payload"


# ------------------------------------------------------------------ packets


def test_packet_roundtrip():
    pkt = Packet(
        kind=MessageKind.DATA,
        priority=Priority.NORMAL,
        flags=0,
        src=b"12345678",
        dst=b"87654321",
        channel=7,
        seq=42,
        ttl=DEFAULT_TTL,
        payload=b"hello mesh",
    )
    raw = pkt.encode(b"channel-key-16b!")
    back = Packet.decode_and_verify(raw, b"channel-key-16b!")
    assert back == pkt


def test_mac_tamper_rejected():
    pkt = Packet(
        kind=MessageKind.DATA,
        priority=Priority.NORMAL,
        flags=0,
        src=b"12345678",
        dst=b"87654321",
        channel=7,
        seq=1,
        ttl=8,
        payload=b"untampered",
    )
    raw = bytearray(pkt.encode(b"channel-key-16b!"))
    raw[HEADER_LEN + 2] ^= 0xFF  # flip a payload byte
    with pytest.raises(MacMismatch):
        Packet.decode_and_verify(bytes(raw), b"channel-key-16b!")


def test_unknown_kind_rejected():
    header = struct.pack(
        "!4sBBBB8s8sIIBH",
        PROTOCOL_MAGIC,
        PROTOCOL_VERSION,
        99,  # not in the registry
        int(Priority.NORMAL),
        0,
        b"12345678",
        b"87654321",
        7,
        1,
        8,
        3,
    )
    raw = header + b"abc" + b"\x00" * MAC_LEN
    with pytest.raises(UnknownKind):
        Packet.decode_unverified(raw)


def test_describe_is_human_readable():
    pkt = Packet(
        kind=MessageKind.HEARTBEAT,
        priority=Priority.PRIORITY,
        flags=0,
        src=b"12345678",
        dst=BROADCAST_ID,
        channel=0,
        seq=3,
        ttl=1,
        payload=b"",
    )
    line = describe(pkt)
    assert "HEARTBEAT" in line and "broadcast" in line


# ------------------------------------------------------------------ pairing


def test_pairing_two_towers(tmp_path):
    a, b = make_tower("alpha", tmp_path), make_tower("beta", tmp_path)
    make_wire(a, b)
    pair(a, b)
    assert a.peers[b.node_id].link is LinkState.UP
    assert b.peers[a.node_id].link is LinkState.UP
    assert a.directory[b.node_id].long_name == "beta"
    assert b.directory[a.node_id].long_name == "alpha"
    # both sides derived the same session key
    assert a.peers[b.node_id].session_key == b.peers[a.node_id].session_key
    assert "pairing-complete" in a.audit_text()


def test_pairing_wrong_psk_fails(tmp_path):
    a, b = make_tower("alpha", tmp_path), make_tower("beta", tmp_path)
    make_wire(a, b)
    b.expect_pairing(a.node_id, b"wrong-psk-0000000")
    a.initiate_pairing(b.node_id, PSK)
    pump(a, b)
    assert b.node_id not in a.peers
    assert a.node_id not in b.peers
    assert "control-auth-failed" in b.audit_text()


def test_unsolicited_hello_ignored(tmp_path):
    a, b = make_tower("alpha", tmp_path), make_tower("beta", tmp_path)
    make_wire(a, b)
    # b never opted in — a's HELLO must die silently
    a.initiate_pairing(b.node_id, PSK)
    pump(a, b)
    assert a.node_id not in b.peers
    assert "unsolicited-control" in b.audit_text()


def test_pairing_psk_too_short_rejected(tmp_path):
    a = make_tower("alpha", tmp_path)
    with pytest.raises(PolicyDenied):
        a.initiate_pairing(b"12345678", b"short")


# ---------------------------------------------------------------- nodeinfo


def test_spoofed_nodeinfo_rejected_at_protocol_layer(tmp_path):
    a, b = make_tower("alpha", tmp_path), make_tower("beta", tmp_path)
    make_wire(a, b)
    pair(a, b)
    # attacker forges nodeinfo claiming to be b, keyed with the WRONG key
    forged = attest_nodeinfo(
        b"wrong-identity-key-00000000000000", b.node_id, "evil-tower", "evil"
    )
    with pytest.raises(ProtocolError):
        verify_nodeinfo(forged, a.peers[b.node_id].identity_key, b.node_id)


def test_forged_nodeinfo_frame_dropped_by_tower(tmp_path):
    a, b = make_tower("alpha", tmp_path), make_tower("beta", tmp_path)
    make_wire(a, b)
    pair(a, b)
    peer = a.peers[b.node_id]
    forged = attest_nodeinfo(
        b"wrong-identity-key-00000000000000", b.node_id, "evil-tower", "evil"
    )
    pkt = Packet(
        kind=MessageKind.NODEINFO,
        priority=Priority.NORMAL,
        flags=0,
        src=b.node_id,
        dst=a.node_id,
        channel=peer.pair_channel,
        seq=999,
        ttl=1,
        payload=forged,
    )
    a.inbox.append(pkt.encode(a.channels[peer.pair_channel]))
    a.tick()
    assert a.directory[b.node_id].long_name == "beta"  # unchanged
    assert "nodeinfo-rejected" in a.audit_text()


# ------------------------------------------------------------------- data


def test_data_delivery_with_ack(tmp_path):
    a, b = make_tower("alpha", tmp_path), make_tower("beta", tmp_path)
    make_wire(a, b)
    pair(a, b)
    a.send_data(b.node_id, b"hello tower", ack=True)
    pump(a, b)
    assert b.delivered
    assert b.delivered[-1].plaintext == b"hello tower"
    assert b.delivered[-1].packet.priority is Priority.NORMAL
    assert "ack-received" in a.audit_text()


def test_ratchet_forward_secrecy():
    tx = ChainRatchet(b"chain-key-32-bytes-for-testing")
    rx = ChainRatchet(b"chain-key-32-bytes-for-testing")
    idx0, k0 = tx.send_key()
    idx1, k1 = tx.send_key()
    assert rx.recv_key(idx0) == k0
    assert rx.recv_key(idx1) == k1
    # old keys are gone: replay refused
    with pytest.raises(ProtocolError):
        rx.recv_key(idx0)
    # bounded reorder window honored
    idx2, k2 = tx.send_key()
    for _ in range(3):
        tx.send_key()
    idx_late, k_late = tx.send_key()
    assert rx.recv_key(idx_late) == k_late  # gap of 4 skipped cleanly
    # gap beyond the window refused
    for _ in range(20):
        tx.send_key()
    idx_far, _ = tx.send_key()
    with pytest.raises(ProtocolError):
        rx.recv_key(idx_far)


def test_multihop_relay(tmp_path):
    a, t, b = (make_tower(n, tmp_path) for n in ("alpha", "tower", "beta"))
    make_wire(a, t, b)
    pair(a, t)
    pair(t, b)
    for tower in (a, t, b):
        tower.join_channel(COMMONS, COMMONS_KEY)
    a.send_data(b.node_id, b"via relay", channel=COMMONS)
    pump(a, t, b, rounds=15)
    assert b.delivered
    assert b.delivered[-1].plaintext == b"via relay"
    assert t.stats["relayed"] > 0
    assert "relayed" in t.audit_text()


def test_ttl_exhausted_packet_dies(tmp_path):
    a, t, b = (make_tower(n, tmp_path) for n in ("alpha", "tower", "beta"))
    make_wire(a, t, b)
    pair(a, t)
    pair(t, b)
    for tower in (a, t, b):
        tower.join_channel(COMMONS, COMMONS_KEY)
    pkt = Packet(
        kind=MessageKind.DATA,
        priority=Priority.NORMAL,
        flags=0,
        src=a.node_id,
        dst=b.node_id,
        channel=COMMONS,
        seq=777,
        ttl=0,  # no hop budget left
        payload=(0xFFFFFFFF).to_bytes(4, "big") + b"dead",
    )
    t.inbox.append(pkt.encode(COMMONS_KEY))
    t.tick()
    assert not b.delivered
    assert "relay-refused" in t.audit_text()


def test_duplicate_relay_suppressed(tmp_path):
    a, t, b = (make_tower(n, tmp_path) for n in ("alpha", "tower", "beta"))
    make_wire(a, t, b)
    pair(a, t)
    pair(t, b)
    for tower in (a, t, b):
        tower.join_channel(COMMONS, COMMONS_KEY)
    pkt = Packet(
        kind=MessageKind.DATA,
        priority=Priority.NORMAL,
        flags=0,
        src=a.node_id,
        dst=b.node_id,
        channel=COMMONS,
        seq=555,
        ttl=8,
        payload=(0xFFFFFFFF).to_bytes(4, "big") + b"once",
    )
    frame = pkt.encode(COMMONS_KEY)
    t.inbox.append(frame)
    t.inbox.append(frame)  # same frame twice
    pump(t, b, rounds=5)
    assert sum(1 for d in b.delivered if d.packet.seq == 555) == 1
    assert "duplicate" in t.audit_text()


def test_forwarder_dedupe_unit():
    fwd = Forwarder(capacity=4)
    assert not fwd.seen(b"12345678", 1)
    fwd.mark(b"12345678", 1)
    assert fwd.seen(b"12345678", 1)
    assert not fwd.seen(b"12345678", 2)


# --------------------------------------------------------------- priority


def test_emergency_gets_reserved_airtime(tmp_path):
    a, b = make_tower("alpha", tmp_path), make_tower("beta", tmp_path)
    wire = make_wire(a, b)
    pair(a, b)
    n_before = len(wire.transcript)
    for i in range(8):
        a.send_data(b.node_id, f"chatter {i}".encode())
    a.send_data(b.node_id, b"EMERGENCY", priority=Priority.EMERGENCY)
    a.tick()  # single dispatch, budget 8
    new_frames = [frame for _, _, frame in wire.transcript[n_before:]]
    assert new_frames, "nothing transmitted"
    first = Packet.decode_unverified(new_frames[0])
    assert first.priority is Priority.EMERGENCY


def test_broadcast_emergency_reaches_all(tmp_path):
    a, t, b = (make_tower(n, tmp_path) for n in ("alpha", "tower", "beta"))
    make_wire(a, t, b)
    pair(a, t)
    pair(t, b)
    for tower in (a, t, b):
        tower.join_channel(COMMONS, COMMONS_KEY)
    a.broadcast(COMMONS, b"flood warning")
    pump(a, t, b, rounds=15)
    assert any(d.plaintext == b"flood warning" for d in t.delivered)
    assert any(d.plaintext == b"flood warning" for d in b.delivered)


# ----------------------------------------------------------- tri-state links


def test_proposer_degraded_carries_emergency_only():
    proposer = Proposer()
    peer = b"peer0001"
    links = {peer: LinkState.DEGRADED}
    normal = Packet(
        kind=MessageKind.DATA,
        priority=Priority.NORMAL,
        flags=0,
        src=b"src00001",
        dst=b"dst00001",
        channel=1,
        seq=1,
        ttl=8,
        payload=b"x",
    )
    assert proposer.propose(normal, links) is None
    emergency = Packet(
        kind=MessageKind.DATA,
        priority=Priority.EMERGENCY,
        flags=0,
        src=b"src00001",
        dst=b"dst00001",
        channel=1,
        seq=2,
        ttl=8,
        payload=b"x",
    )
    plan = proposer.propose(emergency, links)
    assert plan is not None and plan.next_hop == peer


def test_heartbeat_degrade_and_down(tmp_path):
    a, b = make_tower("alpha", tmp_path), make_tower("beta", tmp_path)
    make_wire(a, b)
    pair(a, b)
    peer = a.peers[b.node_id]
    peer.last_seen = time.time() - 60
    a.sweep()
    assert peer.link is LinkState.DEGRADED
    assert "peer-degraded" in a.audit_text()
    peer.last_seen = time.time() - 300
    a.sweep()
    assert peer.link is LinkState.DOWN
    # heartbeats heal
    b.heartbeat_all()
    pump(a, b, rounds=3)
    assert a.peers[b.node_id].link is LinkState.UP
    assert "peer-up" in a.audit_text()


def test_verifier_refusals():
    verifier = Verifier()
    pkt = Packet(
        kind=MessageKind.DATA,
        priority=Priority.NORMAL,
        flags=0,
        src=b"src00001",
        dst=b"dst00001",
        channel=1,
        seq=1,
        ttl=0,
        payload=b"x",
    )
    with pytest.raises(PolicyDenied):
        verifier.verify(
            RoutePlan(b"dst00001", "x"), pkt, channel_joined=True, loopback_ok=True
        )
    with pytest.raises(PolicyDenied):
        verifier.verify(
            RoutePlan(b"dst00001", "x"), pkt, channel_joined=False, loopback_ok=True
        )


def test_cycle_sleep_holds_radio(tmp_path):
    a, b = make_tower("alpha", tmp_path), make_tower("beta", tmp_path)
    wire = make_wire(a, b)
    pair(a, b)
    a.set_cycle_override(CycleState.SLEEP)
    n_before = len(wire.transcript)
    a.send_data(b.node_id, b"held")
    a.tick()
    assert len(wire.transcript) == n_before  # radio off: nothing moved
    a.set_cycle_override(None)
    a.tick()
    assert len(wire.transcript) > n_before


# ------------------------------------------------------------------ wire


def test_loopback_guard():
    assert_loopback("127.0.0.1")
    assert_loopback("localhost")
    for host in ("0.0.0.0", "192.168.1.1", "example.com"):
        with pytest.raises(NetworkExposureError):
            loopback_connect(host, 1)
    assert "127.0.0.1" in LOOPBACK_HOSTS


def test_loopback_pair_carries_protocol():
    pair_ = LoopbackPair()
    try:
        pkt = Packet(
            kind=MessageKind.HEARTBEAT,
            priority=Priority.PRIORITY,
            flags=0,
            src=b"12345678",
            dst=b"87654321",
            channel=9,
            seq=11,
            ttl=1,
            payload=b"",
        )
        key = b"loopback-test-key!"
        pair_.send_a(pkt.encode(key))
        raw = pair_.recv_b()
        back = Packet.decode_and_verify(raw, key)
        assert back == pkt
    finally:
        pair_.close()


# ------------------------------------------------------------------ policy


def test_no_route_without_opt_in(tmp_path):
    a = make_tower("alpha", tmp_path)
    make_wire(a)
    with pytest.raises(PolicyDenied):
        a.send_data(b"unknown!", b"nope")


def test_oversize_plaintext_refused(tmp_path):
    a = make_tower("alpha", tmp_path)
    with pytest.raises(PolicyDenied):
        a.send_data(b"12345678", b"x" * (MAX_PAYLOAD + 1))


def test_revoked_peer_refused(tmp_path):
    a, b = make_tower("alpha", tmp_path), make_tower("beta", tmp_path)
    make_wire(a, b)
    pair(a, b)
    for tower in (a, b):
        tower.join_channel(COMMONS, COMMONS_KEY)
    a.revoke_peer(b.node_id)
    assert a.directory[b.node_id].trust is NodeTrust.REVOKED
    b.send_data(a.node_id, b"from the revoked", channel=COMMONS)
    pump(a, b, rounds=5)
    assert not a.delivered
    assert "revoked-sender" in a.audit_text()


def test_manifest_discloses_policy(tmp_path):
    import json

    make_tower("alpha", tmp_path)
    manifest = json.loads((tmp_path / "alpha" / "manifest.json").read_text())
    assert manifest["transport_policy"].startswith("loopback-only")
    assert manifest["pairing"] == "explicit opt-in on both sides"
    assert manifest["audit_enabled"] is True
