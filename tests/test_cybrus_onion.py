"""Tests for levi.cybrus.onion — onion-routed transport over the keeper's
own relay network (in-process simulator).

Hermetic: no network, no HOME writes. Covers: signed relay directory
(tamper/rogue/expiry rejection), telescoping 3-hop circuit build with
hop-key agreement, layered peel correctness, fixed cell geometry,
L4 (relays learn only prev/next, never plaintext), E2E-sealed payloads
staying sealed through the exit, tampered cells and prev-hop spoofing
failing closed, honest backend reporting.

Proof is named honestly: invariant/property tests over the protocol
logic, not a formal proof — and not a network deployment.
"""

from __future__ import annotations

import base64
import json
import secrets

import pytest

from levi.cybrus import onion
from levi.cybrus.onion import (
    CELL_SIZE,
    NON_CLAIMS,
    THREATS,
    OnionError,
    OperatorKey,
    RelayDirectory,
    RelayNode,
    SimulatedNetwork,
    build_cell,
    check_invariants,
    onion_peel,
    onion_wrap,
    parse_cell,
    sign_descriptor,
    verify_descriptor,
)
from levi.cybrus.veil_chat import VeilChat


@pytest.fixture
def net():
    network = SimulatedNetwork()
    relays = [network.add_relay(name) for name in ("guard", "middle", "exit")]
    return network, relays


@pytest.fixture
def circuit(net):
    network, relays = net
    return network, network.open_circuit([r.relay_id for r in relays])


# ---------------------------------------------------------------------------
# Relay directory: his relays, his signature, nothing else admitted
# ---------------------------------------------------------------------------


def test_descriptor_round_trip_and_tamper_rejection():
    opkey = OperatorKey.generate()
    desc = sign_descriptor(opkey, "relay-1", "guard", secrets.token_bytes(32))
    assert verify_descriptor(desc, opkey)
    tampered = dict(desc)
    tampered["name"] = "mallory"
    assert not verify_descriptor(tampered, opkey)


def test_descriptor_from_another_operator_rejected(net):
    network, _ = net
    rogue_key = OperatorKey.generate()
    rogue = sign_descriptor(rogue_key, "rogue", "rogue", secrets.token_bytes(32))
    with pytest.raises(OnionError):
        network.directory.add_descriptor(rogue)


def test_expired_descriptor_rejected(net):
    network, _ = net
    desc = sign_descriptor(
        network.opkey, "old", "old", secrets.token_bytes(32), ttl_days=-1
    )
    assert not verify_descriptor(desc, network.opkey)
    with pytest.raises(OnionError):
        network.directory.add_descriptor(desc)


def test_directory_verify_all(net):
    network, _ = net
    assert network.directory.verify_all()
    assert len(network.directory.relay_ids()) == 3


def test_circuit_requires_three_distinct_known_relays(net):
    network, relays = net
    with pytest.raises(OnionError):
        network.open_circuit([relays[0].relay_id, relays[1].relay_id])
    with pytest.raises(OnionError):
        network.open_circuit(
            [relays[0].relay_id, relays[0].relay_id, relays[1].relay_id]
        )
    with pytest.raises(OnionError):
        network.open_circuit([relays[0].relay_id, relays[1].relay_id, "nope"])


# ---------------------------------------------------------------------------
# Circuit build: telescoping ECDH, hop-key agreement both sides
# ---------------------------------------------------------------------------


def test_hop_keys_agree_initiator_and_relays(circuit, net):
    network, relays = net
    circuit_obj = circuit[1]
    for relay, (rid, initiator_key) in zip(relays, circuit_obj.hops):
        assert rid == relay.relay_id
        entry = relay.circuit_table[circuit_obj.circuit_id.hex()]
        assert entry["key"] == initiator_key


def test_relay_learns_only_prev_and_next(circuit, net):
    network, relays = net
    circuit_obj = circuit[1]
    cid = circuit_obj.circuit_id.hex()
    assert relays[0].circuit_table[cid]["prev"] == "local"
    assert relays[0].circuit_table[cid]["next"] == relays[1].relay_id
    assert relays[1].circuit_table[cid]["prev"] == relays[0].relay_id
    assert relays[1].circuit_table[cid]["next"] == relays[2].relay_id
    assert relays[2].circuit_table[cid]["prev"] == relays[1].relay_id
    assert relays[2].circuit_table[cid]["next"] is None
    # Table entries are routing state ONLY — never message content.
    for relay in relays:
        assert set(relay.circuit_table[cid]) == {"key", "prev", "next"}


# ---------------------------------------------------------------------------
# Delivery: 3-hop peel correctness + L4
# ---------------------------------------------------------------------------


def test_three_hop_delivery(circuit):
    network, circuit_obj = circuit
    for msg in (b"a", b"hello world", b"x" * 400):
        report = network.send(circuit_obj, msg)
        assert report["delivered"] == msg


def test_message_length_hidden_by_padding(circuit):
    """Different-length messages produce identical cell sizes at every
    hop position — length is fully hidden."""
    network, circuit_obj = circuit
    keys = [k for _, k in circuit_obj.hops]
    cid = circuit_obj.circuit_id
    sizes = {
        len(build_cell(3, cid, onion_wrap(keys, cid, msg)))
        for msg in (b"a", b"mid-length message", b"z" * 400)
    }
    assert sizes == {CELL_SIZE}


def test_l4_relays_learn_only_prev_next_never_plaintext(circuit, net):
    network, relays = net
    network_obj, circuit_obj = circuit
    report = network_obj.send(circuit_obj, b"layered secret")
    obs = report["observations"]
    for relay in relays[:2]:
        for entry in obs[relay.relay_id]:
            assert entry["saw_plaintext"] is False
            assert entry["next"] is not None
    # The exit delivers — and its observation is the delivery record.
    assert any(e["saw_plaintext"] for e in obs[relays[2].relay_id])


def test_e2e_payload_stays_sealed_through_exit(tmp_path, circuit):
    """The point of layering E2E over onion: even the exit relay only
    ever sees the sealed E2E envelope — content stays dark."""
    network, circuit_obj = circuit
    a_home, b_home = tmp_path / "a", tmp_path / "b"
    alice = VeilChat("alice-pass", home=a_home)
    bob = VeilChat("bob-pass", home=b_home)
    alice.add_peer("bob", base64.b64decode(bob.identity()["public_key"]))
    bob.add_peer("alice", base64.b64decode(alice.identity()["public_key"]))
    offer = alice.handshake_offer("bob")
    conv = alice.handshake_finish(bob.handshake_answer(offer))

    secret = b"the exit must never read this"
    envelope = alice.send_message(conv, secret)
    payload = json.dumps(envelope).encode("utf-8")
    report = network.send(circuit_obj, payload)

    delivered = report["delivered"]
    assert delivered == payload  # exact bytes, still sealed
    opened = json.loads(delivered.decode("utf-8"))
    assert "blob" in opened  # the E2E sealed blob survived the trip
    assert secret not in delivered  # plaintext never on the wire
    # And the peer at the far end opens it normally.
    assert bob.receive_message(opened)["plaintext"] == secret


def test_layered_wrap_peel_round_trip_pure():
    keys = [secrets.token_bytes(32) for _ in range(3)]
    cid = secrets.token_bytes(16)
    wrapped = onion_wrap(keys, cid, b"ping")
    layer = wrapped
    for key in keys:
        layer = onion_peel(key, cid, layer)
    from levi.cybrus.onion import _unpack_inner, _DATA_MAGIC

    assert _unpack_inner(layer) == _DATA_MAGIC + b"ping"


# ---------------------------------------------------------------------------
# Fail-closed transport
# ---------------------------------------------------------------------------


def test_tampered_cell_dropped_not_forwarded(circuit, net):
    network, relays = net
    _, circuit_obj = circuit
    keys = [k for _, k in circuit_obj.hops]
    cell = build_cell(
        3, circuit_obj.circuit_id, onion_wrap(keys, circuit_obj.circuit_id, b"boom")
    )
    bad = bytearray(cell)
    bad[100] ^= 1
    # Circuit construction already recorded observations; the dropped cell
    # must add none.
    before = list(relays[0].observations)
    with pytest.raises(OnionError):
        relays[0].handle_cell("local", bytes(bad))
    # The relay recorded nothing new for the dropped cell.
    assert relays[0].observations == before


def test_prev_hop_spoofing_fails_closed(circuit, net):
    network, relays = net
    _, circuit_obj = circuit
    keys = [k for _, k in circuit_obj.hops]
    cell = build_cell(
        3, circuit_obj.circuit_id, onion_wrap(keys, circuit_obj.circuit_id, b"boom")
    )
    with pytest.raises(OnionError):
        relays[0].handle_cell("mallory", cell)


def test_unknown_circuit_fails_closed(net):
    network, relays = net
    with pytest.raises(OnionError):
        relays[0].handle_cell("local", b"\x03" + b"\x00" * 16 + b"\x00" * 573)


def test_malformed_cell_fails_closed(net):
    network, relays = net
    with pytest.raises(OnionError):
        relays[0].handle_cell("local", b"too short")


def test_oversize_message_fails_closed(circuit):
    network, circuit_obj = circuit
    with pytest.raises(OnionError):
        network.send(circuit_obj, b"z" * 1000)
    with pytest.raises(OnionError):
        network.send(circuit_obj, b"")


# ---------------------------------------------------------------------------
# Honest reporting + invariants
# ---------------------------------------------------------------------------


def test_crypto_report_is_honest(net):
    network, _ = net
    report = network.crypto_report()
    assert report["cell_aead"] in ("aes-256-gcm", "stdlib-fallback")
    assert report["x25519"] in (
        "cryptography-x25519",
        "pure-python-fallback",
        "unavailable",
    )
    assert report["descriptor_auth"] in ("ed25519", "hmac-attestation-fallback")
    assert report["hops"] == 3
    assert "NO real network" in report["transport"]


def test_check_invariants_all_pass():
    failing = [r for r in check_invariants() if not r[1]]
    assert failing == [], failing


def test_threats_and_non_claims_documented():
    assert len(THREATS) >= 4
    assert len(NON_CLAIMS) >= 5
    for threat in THREATS:
        for key in ("id", "asset", "attack", "mitigation", "residual", "status"):
            assert threat.get(key), (threat.get("id"), key)
    # The honest threat model names its limits out loud.
    text = " ".join(NON_CLAIMS)
    assert "NOT Tor" in text or "not Tor" in text


# ---------------------------------------------------------------------------
# Operating laws L6-L12 + the single sanctioned egress path
# ---------------------------------------------------------------------------


def test_laws_declared_machine_readable():
    from levi.cybrus.onion import LAWS

    ids = [lid for lid, _ in LAWS]
    assert ids == ["L%d" % i for i in range(1, 13)]
    assert all(text.strip() for _, text in LAWS)


def test_threat_model_is_explicit():
    from levi.cybrus.onion import threat_model

    tm = threat_model()
    assert tm["is_tor"] is False
    assert tm["global_passive_adversary_resistant"] is False
    assert "small by construction" in tm["anonymity_set"]
    assert "seized" in tm["collusion_limit"]
    assert tm["explicitly_not_claimed"]
    assert "choke point" in tm["network"]


def test_directory_has_no_removal_api():
    """No-cancellation / nothing-thrown-away: descriptors are add-only."""
    assert not any(
        hasattr(RelayDirectory, n) for n in ("remove", "delete", "purge", "clear")
    )


def test_no_network_imports_in_onion():
    """The transport module performs no network I/O of its own — the
    simulator is method calls, and production egress goes through
    request_forward_grant (the choke point)."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    tree = ast.parse((root / "core/levi/cybrus/onion.py").read_text(encoding="utf-8"))
    banned = {"socket", "urllib", "requests", "http", "ssl"}
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    assert not (found & banned), found & banned


def test_forward_grant_refused_without_credential(tmp_path, monkeypatch):
    """request_forward_grant is the choke point's egress path: without a
    credential it refuses — a relay can never roll its own egress."""
    from levi.cybrus.enforce import NotAuthenticated
    from levi.cybrus.onion import request_forward_grant

    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "levi-home"))
    with pytest.raises(NotAuthenticated):
        request_forward_grant("levi.onion", "relay-1", "onion cell forward")


def test_e2e_payload_stays_sealed_through_exit(net, tmp_path):
    """The full stack: a veil_chat sealed envelope through a 3-hop
    circuit — the exit delivers ciphertext it cannot open."""
    import json

    from levi.cybrus.veil_chat import VeilChat

    network, relays = net
    circuit = network.open_circuit([r.relay_id for r in relays])
    alice = VeilChat("alice-passphrase", home=tmp_path / "e2e-alice")
    bob = VeilChat("bob-passphrase", home=tmp_path / "e2e-bob")
    alice.add_peer("bob", base64.b64decode(bob.identity()["public_key"]))
    bob.add_peer("alice", base64.b64decode(alice.identity()["public_key"]))
    offer = alice.handshake_offer("bob")
    alice.handshake_finish(bob.handshake_answer(offer))
    envelope = alice.send_message(
        alice.list_conversations()[0]["conv_id"], b"sealed end to end"
    )
    report = network.send(circuit, json.dumps(envelope).encode())
    delivered_env = json.loads(bytes(report["delivered"]).decode("utf-8"))
    # Ciphertext on the wire; only Bob's chain opens it.
    assert delivered_env["blob"] != base64.b64encode(b"sealed end to end").decode()
    assert bob.receive_message(delivered_env)["plaintext"] == b"sealed end to end"
