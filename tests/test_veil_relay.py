"""Tests for levi.cybrus.veil_relay — the ciphertext-only Veil relay broker.

Hermetic: no network, no HOME writes. Each law from the module docstring
is machine-checked here:

- L1 CIPHERTEXT-ONLY: the relay never sees plaintext (queue-bytes scan),
  accepts crypto-garbage it cannot validate, and has no open/decrypt path.
- L2 BYTE-IDENTICAL: accept -> poll round-trips the envelope dict exactly;
  a tampered envelope fails at the recipient's Veil open, never at relay.
- L3 FOUNDER-GATE: founder relays cross-keeper; non-founder is limited to
  its own keeper's devices; anything else raises RelayGateError.
- L4 METADATA-ONLY LOGS: plaintext and blobs never appear in relay logs.
- L5 FAIL-CLOSED: malformed / oversized / wrong-version / unregistered /
  revoked envelopes are all refused at accept.
- L6 NO NETWORK: the module imports no socket/http machinery.
"""

import json
import logging

import pytest

from levi.cybrus import veil_relay
from levi.cybrus.veil import Veil, VeilError
from levi.cybrus.veil_relay import (
    RelayError,
    RelayGateError,
    VeilRelay,
    check_invariants,
)


@pytest.fixture
def keeper_vb(tmp_path):
    """One keeper's Veil with two devices (phone + laptop)."""
    vb = Veil("keeper-passphrase", home=tmp_path / "vb")
    alice = vb.create_device("alice-phone")
    bob = vb.create_device("bob-laptop")
    return vb, alice["device_id"], bob["device_id"]


@pytest.fixture
def founder_relay(keeper_vb):
    _, alice_id, bob_id = keeper_vb
    relay = VeilRelay("chauncey")  # founder identity
    relay.register_keeper("chauncey", [alice_id, bob_id])
    return relay


def seal(keeper_vb, text: bytes):
    vb, alice_id, bob_id = keeper_vb
    return vb.seal_message("conv-1", alice_id, bob_id, text)


# ---------------------------------------------------------------------------
# L2: byte-identical forwarding, end to end
# ---------------------------------------------------------------------------


def test_roundtrip_seal_relay_poll_open(keeper_vb, founder_relay):
    vb, alice_id, bob_id = keeper_vb
    env = seal(keeper_vb, b"hello veil relay")
    receipt = founder_relay.accept(env)
    assert receipt["accepted"] is True
    assert receipt["message_id"] == env["message_id"]

    got = founder_relay.poll(bob_id)
    assert len(got) == 1
    assert got[0] == env  # bit-for-bit identical (L2)

    opened = vb.open_message(got[0])
    assert opened["plaintext"] == b"hello veil relay"


def test_tampered_envelope_fails_at_recipient_not_relay(keeper_vb, founder_relay):
    vb, alice_id, bob_id = keeper_vb
    env = seal(keeper_vb, b"tamper me")
    founder_relay.accept(env)
    (got,) = founder_relay.poll(bob_id)
    # Flip one character of the opaque blob after the relay handled it.
    blob = got["blob"]
    got["blob"] = ("A" if blob[0] != "A" else "B") + blob[1:]
    with pytest.raises(VeilError):
        vb.open_message(got)


def test_poll_only_delivers_to_recipient(keeper_vb, founder_relay):
    _, alice_id, bob_id = keeper_vb
    founder_relay.accept(seal(keeper_vb, b"for bob"))
    assert founder_relay.poll(alice_id) == []  # not hers
    assert len(founder_relay.poll(bob_id)) == 1


def test_queue_bound_drops_oldest():
    relay = VeilRelay("chauncey", max_queue=2)
    relay.register_keeper("chauncey", ["d1", "d2"])

    def env(i):
        return {
            "protocol_version": 1,
            "message_id": "m%d" % i,
            "conversation_id": "c",
            "sender": "d1",
            "recipient": "d2",
            "timestamp": "t",
            "seq": i,
            "key_version": 1,
            "epoch": 1,
            "blob": "YmxvYg==",
            "attestation": "a" * 64,
        }

    relay.accept(env(1))
    relay.accept(env(2))
    relay.accept(env(3))  # queue full: oldest dropped (his original semantics)
    got = relay.poll("d2")
    assert [e["message_id"] for e in got] == ["m2", "m3"]
    assert relay.health()["dropped_full"] == 1


# ---------------------------------------------------------------------------
# L1: ciphertext-only — the relay never sees plaintext
# ---------------------------------------------------------------------------


def test_relay_queue_never_contains_plaintext(keeper_vb, founder_relay):
    marker = b"PLAINTEXT_MARKER_XYZ_123"
    founder_relay.accept(seal(keeper_vb, marker))
    raw_queue = b"".join(raw for _, raw in founder_relay._queue)
    assert marker not in raw_queue


def test_relay_accepts_crypto_garbage_it_cannot_validate(founder_relay):
    """The relay moves opaque bytes; it cannot tell valid crypto from
    garbage — proof it never inspects payloads (L1)."""
    env = {
        "protocol_version": 1,
        "message_id": "garbage-1",
        "conversation_id": "c",
        "sender": "alice-phone-x",
        "recipient": "bob-laptop-x",
        "timestamp": "t",
        "seq": 1,
        "key_version": 1,
        "epoch": 1,
        "blob": "bm90LXJlYWwtY3J5cHRv",
        "attestation": "b" * 64,
    }
    relay = VeilRelay("chauncey")
    relay.register_keeper("chauncey", ["alice-phone-x", "bob-laptop-x"])
    assert relay.accept(env)["accepted"] is True  # no crypto checked


def test_module_has_no_decrypt_path():
    src = open(veil_relay.__file__, encoding="utf-8").read()
    body = src.split("def check_invariants", 1)[0]  # exclude the check's own token list
    for token in ("open_message", "_open_backend", "_open_gcm"):
        assert token not in body


# ---------------------------------------------------------------------------
# L3: the founder gate — full broker is founder-only
# ---------------------------------------------------------------------------


def test_founder_relays_cross_keeper(keeper_vb):
    vb, alice_id, bob_id = keeper_vb
    relay = VeilRelay("Chauncey")  # case-insensitive founder
    relay.register_keeper("chauncey", [alice_id])
    relay.register_keeper("husband", [bob_id])
    env = vb.seal_message("conv-1", alice_id, bob_id, b"cross keeper")
    assert relay.accept(env)["accepted"] is True  # full broker ability


def test_nonfounder_limited_to_own_devices(keeper_vb):
    vb, alice_id, bob_id = keeper_vb
    relay = VeilRelay("someone")
    relay.register_keeper("someone", [alice_id, bob_id])
    env = vb.seal_message("conv-1", alice_id, bob_id, b"own devices")
    assert relay.accept(env)["accepted"] is True  # limited: allowed


def test_nonfounder_cross_keeper_denied(keeper_vb):
    vb, alice_id, bob_id = keeper_vb
    relay = VeilRelay("someone")
    relay.register_keeper("someone", [alice_id])
    relay.register_keeper("husband", [bob_id])
    env = vb.seal_message("conv-1", alice_id, bob_id, b"not yours")
    with pytest.raises(RelayGateError):
        relay.accept(env)


def test_nonfounder_unregistered_own_keeper_denied(keeper_vb):
    vb, alice_id, bob_id = keeper_vb
    relay = VeilRelay("someone")  # never registered any keeper
    env = vb.seal_message("conv-1", alice_id, bob_id, b"nope")
    with pytest.raises(RelayError):
        relay.accept(env)


def test_empty_operator_identity_denied():
    with pytest.raises(RelayError):
        VeilRelay("  ")


# ---------------------------------------------------------------------------
# L5: fail-closed validation
# ---------------------------------------------------------------------------


def test_missing_fields_rejected(founder_relay):
    with pytest.raises(RelayError):
        founder_relay.accept({"message_id": "x"})


def test_empty_blob_rejected(founder_relay, keeper_vb):
    env = seal(keeper_vb, b"x")
    env["blob"] = ""
    with pytest.raises(RelayError):
        founder_relay.accept(env)


def test_wrong_protocol_version_rejected(founder_relay, keeper_vb):
    env = seal(keeper_vb, b"x")
    env["protocol_version"] = 999
    with pytest.raises(RelayError):
        founder_relay.accept(env)


def test_oversized_envelope_rejected(founder_relay, keeper_vb):
    env = seal(keeper_vb, b"x")
    env["blob"] = "A" * (veil_relay.MAX_ENVELOPE_BYTES + 1)
    with pytest.raises(RelayError):
        founder_relay.accept(env)


def test_unregistered_device_rejected(founder_relay, keeper_vb):
    env = seal(keeper_vb, b"x")
    env["recipient"] = "ghost-device"
    with pytest.raises(RelayError):
        founder_relay.accept(env)


def test_revoked_sender_rejected(founder_relay, keeper_vb):
    _, alice_id, bob_id = keeper_vb
    founder_relay.revoke_device(alice_id)
    with pytest.raises(RelayError):
        founder_relay.accept(seal(keeper_vb, b"revoked"))


def test_poll_unregistered_recipient_rejected(founder_relay):
    with pytest.raises(RelayError):
        founder_relay.poll("ghost-device")


# ---------------------------------------------------------------------------
# L4: metadata-only logs
# ---------------------------------------------------------------------------


def test_logs_carry_no_content(keeper_vb):
    _, alice_id, bob_id = keeper_vb
    relay = VeilRelay("chauncey")
    relay.register_keeper("chauncey", [alice_id, bob_id])
    records = []

    class Cap(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = logging.getLogger("levi.cybrus.veil_relay")
    handler = Cap()
    logger.addHandler(handler)
    try:
        marker = "LOG_MARKER_QQZ_987"
        vb = keeper_vb[0]
        env = vb.seal_message("conv-1", alice_id, bob_id, marker.encode())
        relay.accept(env)
        relay.poll(bob_id)
    finally:
        logger.removeHandler(handler)
    text = "\n".join(r.getMessage() for r in records)
    assert marker not in text
    assert env["blob"] not in text


# ---------------------------------------------------------------------------
# L6: no network + structural invariants
# ---------------------------------------------------------------------------


def test_no_network_imports():
    src = open(veil_relay.__file__, encoding="utf-8").read()
    for token in ("import socket", "import http", "urllib", "websocket"):
        assert token not in src


def test_check_invariants_all_green():
    results = check_invariants()
    assert results, "no invariants checked"
    bad = [(n, d) for n, ok, d in results if not ok]
    assert not bad, "failed invariants: %r" % (bad,)


def test_health_is_metadata_only(founder_relay, keeper_vb):
    founder_relay.accept(seal(keeper_vb, b"health check"))
    h = founder_relay.health()
    assert h["queue_depth"] == 1
    assert h["accepted"] == 1
    assert h["founder_broker"] is True
    assert "plaintext" not in json.dumps(h)
