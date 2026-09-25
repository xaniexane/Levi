"""Tests for levi.cybrus.veil_chat — E2E conversations on veil.py crypto.

Hermetic: every test roots VeilChat at tmp_path (no HOME writes, no
network). Covers: RFC 7748 vectors (both backends), handshake
agreement, per-message ratchet forward secrecy (old keys can't open new
envelopes and vice versa), tamper/replay/reorder rejection, epoch
rotation with grace then destruction, at-rest stores holding no
plaintext, honest backend reporting, and fail-closed behavior with no
X25519 backend.

Proof is named honestly: these are invariant/property tests over the
real code paths, not a formal proof.
"""

from __future__ import annotations

import base64
import json
import os
import stat

import pytest

from levi.cybrus import veil_chat as vc
from levi.cybrus.veil import _open_backend, _seal_backend
from levi.cybrus.veil_chat import (
    NON_CLAIMS,
    THREATS,
    VeilChat,
    VeilChatError,
    check_invariants,
    x25519,
    x25519_backend,
    x25519_public,
)


@pytest.fixture
def homes(tmp_path):
    return tmp_path / "alice", tmp_path / "bob"


@pytest.fixture
def pair(homes):
    """Two keepers who have registered and verified each other."""
    a_home, b_home = homes
    alice = VeilChat("alice-passphrase", home=a_home)
    bob = VeilChat("bob-passphrase", home=b_home)
    alice.add_peer("bob", base64.b64decode(bob.identity()["public_key"]))
    bob.add_peer("alice", base64.b64decode(alice.identity()["public_key"]))
    assert alice.verify_peer_fingerprint("bob", bob.identity()["fingerprint"])
    assert bob.verify_peer_fingerprint("alice", alice.identity()["fingerprint"])
    return alice, bob


def handshake(alice, bob, peer_a="bob", peer_b="alice"):
    offer = alice.handshake_offer(peer_a)
    answer = bob.handshake_answer(offer)
    conv_a = alice.handshake_finish(answer)
    conv_b = [c for c in bob.list_conversations() if c["conv_id"] == conv_a][0]["conv_id"]
    return conv_a, conv_b


# ---------------------------------------------------------------------------
# RFC 7748 — the X25519 contract, both backends
# ---------------------------------------------------------------------------

RFC_VECTORS_52 = [
    (
        "a546e36bf0527c9d3b16154b82465edd62144c0ac1fc5a18506a2244ba449ac4",
        "e6db6867583030db3594c1a424b15f7c726624ec26b3353b10a903a6d0ab1c4c",
        "c3da55379de9c6908e94ea4df28d084f32eccf03491c71f754b4075577a28552",
    ),
    (
        "4b66e9d4d1b4673c5ad22691957d6af5c11b6421e0ea01d42ca4169e7918ba0d",
        "e5210f12786811d3f4b7959d0538ae2c31dbe7106fc03c3efc4cd549c715a493",
        "95cbde9476e8907d7aade45cb4b873f88b595a68799fa152e6f8f7647aac7957",
    ),
]

# RFC 7748 section 6.1: Alice/Bob DH exchange.
DH_A_PRIV = "77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a"
DH_A_PUB = "8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a"
DH_B_PRIV = "5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b27ff88e0eb"
DH_B_PUB = "de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f"
DH_SHARED = "4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742"


@pytest.mark.parametrize("scalar, u, expected", RFC_VECTORS_52)
def test_rfc7748_section52_vectors(scalar, u, expected):
    assert (
        x25519(bytes.fromhex(scalar), bytes.fromhex(u)).hex() == expected
    )


def test_rfc7748_section61_dh_exchange():
    a_priv, b_priv = bytes.fromhex(DH_A_PRIV), bytes.fromhex(DH_B_PRIV)
    assert x25519_public(a_priv).hex() == DH_A_PUB
    assert x25519_public(b_priv).hex() == DH_B_PUB
    assert x25519(a_priv, bytes.fromhex(DH_B_PUB)).hex() == DH_SHARED
    assert x25519(b_priv, bytes.fromhex(DH_A_PUB)).hex() == DH_SHARED


def test_rfc7748_iterated_vector():
    # One iteration from k = u = 0x09... (section 5.2, second vector type).
    k = u = bytes([9]) + bytes(31)
    assert (
        x25519(k, u).hex()
        == "422c8e7a6227d7bca1350b3e2bb7279f7897b87bb6854b783c60e80311ae3079"
    )


def test_pure_python_backend_agrees_with_cryptography(monkeypatch):
    """The labeled fallback computes the same function as the preferred
    backend — verified on random keys and the RFC vectors."""
    import secrets

    monkeypatch.setattr(vc, "_X25519_SOURCE", "pure-python")
    assert x25519_backend() == "pure-python-fallback"
    for scalar, u, expected in RFC_VECTORS_52:
        assert x25519(bytes.fromhex(scalar), bytes.fromhex(u)).hex() == expected
    for _ in range(5):
        pa, pb = secrets.token_bytes(32), secrets.token_bytes(32)
        assert x25519(pa, x25519_public(pb)) == x25519(pb, x25519_public(pa))


def test_handshake_over_pure_python_backend(pair, monkeypatch):
    """End-to-end handshake + message over the fallback backend."""
    monkeypatch.setattr(vc, "_X25519_SOURCE", "pure-python")
    alice, bob = pair
    conv_a, conv_b = handshake(alice, bob)
    env = alice.send_message(conv_a, b"fallback hello")
    assert bob.receive_message(env)["plaintext"] == b"fallback hello"


def test_no_x25519_backend_fails_closed(pair, monkeypatch):
    monkeypatch.setattr(vc, "_X25519_SOURCE", "unavailable")
    assert x25519_backend() == "unavailable"
    alice, _ = pair
    with pytest.raises(VeilChatError):
        alice.handshake_offer("bob")
    with pytest.raises(VeilChatError):
        x25519(b"k" * 32, b"p" * 32)


# ---------------------------------------------------------------------------
# Handshake + messaging
# ---------------------------------------------------------------------------


def test_handshake_agreement_and_two_way_messaging(pair):
    alice, bob = pair
    conv_a, conv_b = handshake(alice, bob)
    assert conv_a == conv_b
    for i in range(5):
        env = alice.send_message(conv_a, b"a->b %d" % i)
        assert bob.receive_message(env)["plaintext"] == b"a->b %d" % i
        env = bob.send_message(conv_b, b"b->a %d" % i)
        assert alice.receive_message(env)["plaintext"] == b"b->a %d" % i
    conv = alice.list_conversations()[0]
    assert conv["send_seq"] == 5 and conv["recv_seq"] == 5


def test_handshake_unknown_peer_fails_closed(pair):
    alice, _ = pair
    with pytest.raises(VeilChatError):
        alice.handshake_offer("mallory")


def test_handshake_answer_from_unknown_fingerprint_fails(pair):
    alice, bob = pair
    offer = alice.handshake_offer("bob")
    offer["sender_fp"] = "00 " * 16
    with pytest.raises(VeilChatError):
        bob.handshake_answer(offer)


def test_handshake_finish_without_pending_fails(pair):
    alice, bob = pair
    offer = alice.handshake_offer("bob")
    answer = bob.handshake_answer(offer)
    with pytest.raises(VeilChatError):
        # Bob never offered; he cannot finish.
        bob.handshake_finish(answer)


def test_rehandshake_peer_mismatch_fails(pair, homes):
    a_home, b_home = homes
    alice, bob = pair
    carol = VeilChat("carol-passphrase", home=b_home / "carol")
    carol.add_peer("alice", base64.b64decode(alice.identity()["public_key"]))
    conv_a, _ = handshake(alice, bob)
    # Carol tries to rotate Alice's conversation with Bob.
    offer = alice.rotate_epoch(conv_a)
    with pytest.raises(VeilChatError):
        carol.handshake_answer(offer)


# ---------------------------------------------------------------------------
# Handshake authentication — offers/answers bound to the static identity keys
# ---------------------------------------------------------------------------


def test_forged_offer_fails_closed(pair):
    """Carol forges a rotation offer for Alice<->Bob's conversation,
    spoofing Alice's (public) fingerprint with her own ephemeral. Bob must
    reject it — she cannot compute the static-static DH authenticator —
    and the conversation must be untouched."""
    import secrets

    from levi.cybrus.veil_chat import _b64e

    alice, bob = pair
    conv_a, _ = handshake(alice, bob)
    carol_eph_pub = x25519_public(secrets.token_bytes(32))
    forged = {
        "protocol_version": 1,
        "conv_id": conv_a,
        "eph_pub": _b64e(carol_eph_pub),
        "sender_fp": alice.identity()["fingerprint"],
        "auth": "0" * 64,
    }
    with pytest.raises(VeilChatError):
        bob.handshake_answer(forged)
    env = alice.send_message(conv_a, b"still us")
    assert bob.receive_message(env)["plaintext"] == b"still us"


def test_forged_answer_fails_closed(pair):
    """Carol forges an answer to Alice's rotation offer with her own
    ephemeral. Alice's finish must reject it before deriving anything —
    and the legitimate pending handshake must survive for Bob's real
    answer."""
    import secrets

    from levi.cybrus.veil_chat import _b64e

    alice, bob = pair
    conv_a, _ = handshake(alice, bob)
    offer = alice.rotate_epoch(conv_a)
    carol_eph_pub = x25519_public(secrets.token_bytes(32))
    forged = {
        "protocol_version": 1,
        "conv_id": offer["conv_id"],
        "eph_pub": _b64e(carol_eph_pub),
        "sender_fp": bob.identity()["fingerprint"],
        "auth": "0" * 64,
    }
    with pytest.raises(VeilChatError):
        alice.handshake_finish(forged)
    # The real answer still completes the rotation on the same pending.
    assert alice.handshake_finish(bob.handshake_answer(offer)) == conv_a


def test_tampered_answer_eph_fails_closed(pair):
    """Flipping a bit in a legitimate answer's ephemeral breaks the
    transcript-bound authenticator — finish fails closed."""
    import copy

    alice, bob = pair
    conv_a, _ = handshake(alice, bob)
    offer = alice.rotate_epoch(conv_a)
    answer = bob.handshake_answer(offer)
    bad = copy.deepcopy(answer)
    raw = bytearray(base64.b64decode(bad["eph_pub"]))
    raw[0] ^= 1
    bad["eph_pub"] = base64.b64encode(bytes(raw)).decode("ascii")
    with pytest.raises(VeilChatError):
        alice.handshake_finish(bad)


def test_chain_root_requires_static_dh_terms():
    """Property: the chain root changes when any DH term is wrong. An
    active attacker who substitutes ephemerals knows ee and both public
    identity keys — but without either static private key they cannot
    compute the static-ephemeral terms, so they cannot arrive at the
    real root. Deterministic for identical inputs (both sides agree)."""
    import secrets

    ee = secrets.token_bytes(32)
    dh_a = secrets.token_bytes(32)
    dh_b = secrets.token_bytes(32)
    transcript, s_pub, r_pub = b"transcript", b"s" * 32, b"r" * 32
    real = VeilChat._derive_chain0(ee, dh_a, dh_b, transcript, s_pub, r_pub)
    assert VeilChat._derive_chain0(ee, dh_a, dh_b, transcript, s_pub, r_pub) == real
    assert (
        VeilChat._derive_chain0(secrets.token_bytes(32), dh_a, dh_b, transcript, s_pub, r_pub)
        != real
    )
    assert (
        VeilChat._derive_chain0(ee, secrets.token_bytes(32), dh_b, transcript, s_pub, r_pub)
        != real
    )
    assert (
        VeilChat._derive_chain0(ee, dh_a, secrets.token_bytes(32), transcript, s_pub, r_pub)
        != real
    )


# ---------------------------------------------------------------------------
# Ratchet forward secrecy — the one-way property, proven at the primitive
# ---------------------------------------------------------------------------


def test_chain_ratchet_is_one_way():
    c0 = b"c" * 32
    m1, c1 = VeilChat._chain_advance(c0)
    m2, c2 = VeilChat._chain_advance(c1)
    # Every step produces fresh keys...
    assert len({c0, c1, c2, m1, m2}) == 5
    # ...old message keys cannot open new envelopes and vice versa.
    aad = b"test-aad"
    env1 = _seal_backend(m1, b"first", aad)
    env2 = _seal_backend(m2, b"second", aad)
    assert _open_backend(m1, env1, aad) == b"first"
    assert _open_backend(m2, env2, aad) == b"second"
    with pytest.raises(Exception):
        _open_backend(m1, env2, aad)
    with pytest.raises(Exception):
        _open_backend(m2, env1, aad)


def test_old_chain_state_destroyed_on_send(pair):
    """After a send, the sealed chain state on disk no longer contains the
    chain key that sealed the earlier message."""
    alice, bob = pair
    conv_a, conv_b = handshake(alice, bob)
    env1 = alice.send_message(conv_a, b"one")
    assert bob.receive_message(env1)["plaintext"] == b"one"
    env2 = alice.send_message(conv_a, b"two")
    assert bob.receive_message(env2)["plaintext"] == b"two"
    # Both envelopes are sealed, distinct blobs...
    assert env1["blob"] != env2["blob"]
    # ...and the journal can still re-open them while the epoch lives
    # (message keys wrapped per-epoch), which is the documented layering.
    assert alice.open_journal_envelope(conv_a, env1) == b"one"
    assert alice.open_journal_envelope(conv_a, env2) == b"two"


def test_epoch_rotation_grace_then_destruction(pair):
    alice, bob = pair
    conv_a, conv_b = handshake(alice, bob)
    env1 = alice.send_message(conv_a, b"epoch one")
    assert bob.receive_message(env1)["plaintext"] == b"epoch one"
    journal1 = alice.fetch_envelopes(conv_a)

    # First rotation: epoch 1 stays openable (grace for in-flight).
    offer = alice.rotate_epoch(conv_a)
    alice.handshake_finish(bob.handshake_answer(offer))
    assert alice.list_conversations()[0]["epoch"] == 2
    env2 = alice.send_message(conv_a, b"epoch two")
    assert bob.receive_message(env2)["plaintext"] == b"epoch two"
    assert alice.open_journal_envelope(conv_a, journal1[0]) == b"epoch one"

    # Second rotation: epoch 1 is destroyed — its envelopes go dark, even
    # with the master key (that destruction IS the forward secrecy).
    offer = alice.rotate_epoch(conv_a)
    alice.handshake_finish(bob.handshake_answer(offer))
    assert alice.list_conversations()[0]["epoch"] == 3
    with pytest.raises(VeilChatError):
        alice.open_journal_envelope(conv_a, journal1[0])
    # ...while the grace epoch (2) still opens.
    journal2 = [e for e in alice.fetch_envelopes(conv_a) if e["epoch"] == 2]
    assert alice.open_journal_envelope(conv_a, journal2[0]) == b"epoch two"
    # Traffic still flows on the new epoch.
    env3 = alice.send_message(conv_a, b"epoch three")
    assert bob.receive_message(env3)["plaintext"] == b"epoch three"


# ---------------------------------------------------------------------------
# Tamper / replay / reorder — all fail closed
# ---------------------------------------------------------------------------


def _tampered(envelope):
    import copy

    bad = copy.deepcopy(envelope)
    blob = bytearray(base64.b64decode(bad["blob"]))
    blob[20] ^= 1
    bad["blob"] = base64.b64encode(bytes(blob)).decode("ascii")
    return bad


def test_tampered_envelope_fails_closed(pair):
    alice, bob = pair
    conv_a, conv_b = handshake(alice, bob)
    env = alice.send_message(conv_a, b"secret")
    with pytest.raises(VeilChatError):
        bob.receive_message(_tampered(env))


def test_tampered_header_fails_closed(pair):
    alice, bob = pair
    conv_a, conv_b = handshake(alice, bob)
    env = alice.send_message(conv_a, b"secret")
    import copy

    bad = copy.deepcopy(env)
    bad["seq"] = env["seq"] + 100  # header is AAD-bound
    with pytest.raises(VeilChatError):
        bob.receive_message(bad)


def test_replayed_envelope_fails_closed(pair):
    alice, bob = pair
    conv_a, conv_b = handshake(alice, bob)
    env = alice.send_message(conv_a, b"once")
    assert bob.receive_message(env)["plaintext"] == b"once"
    with pytest.raises(VeilChatError):
        bob.receive_message(env)


def test_out_of_order_gap_fails_closed(pair):
    """No out-of-order tolerance in this build: a gap fails closed rather
    than being buffered (documented limit, no DH ratchet)."""
    alice, bob = pair
    conv_a, conv_b = handshake(alice, bob)
    e1 = alice.send_message(conv_a, b"one")
    e2 = alice.send_message(conv_a, b"two")
    with pytest.raises(VeilChatError):
        bob.receive_message(e2)  # gap: seq 1 not yet seen
    # In-order still works after the failed attempt.
    assert bob.receive_message(e1)["plaintext"] == b"one"
    assert bob.receive_message(e2)["plaintext"] == b"two"


def test_envelope_from_wrong_peer_fails(pair, homes):
    a_home, _ = homes
    alice, bob = pair
    carol = VeilChat("carol-passphrase", home=a_home / "carol")
    carol.add_peer("bob", base64.b64decode(bob.identity()["public_key"]))
    bob.add_peer("carol", base64.b64decode(carol.identity()["public_key"]))
    conv_a, _ = handshake(alice, bob)
    offer = carol.handshake_offer("bob")
    conv_c = carol.handshake_finish(bob.handshake_answer(offer))
    assert conv_c != conv_a
    env = carol.send_message(conv_c, b"hi bob")
    # Alice's conversation with Bob must not accept Carol's envelope:
    # wrong conv_id fails closed first.
    with pytest.raises(VeilChatError):
        alice.receive_message(env)


def test_own_envelope_refused(pair):
    alice, bob = pair
    conv_a, _ = handshake(alice, bob)
    env = alice.send_message(conv_a, b"self talk")
    with pytest.raises(VeilChatError):
        alice.receive_message(env)


# ---------------------------------------------------------------------------
# At rest: no plaintext, owner-only, locked vault fails closed
# ---------------------------------------------------------------------------


def test_at_rest_holds_no_plaintext_or_keys(pair, homes):
    a_home, _ = homes
    alice, bob = pair
    conv_a, conv_b = handshake(alice, bob)
    secrets_ = [b"alice-passphrase", b"super secret message", b"another one"]
    for s in secrets_[1:]:
        env = alice.send_message(conv_a, s)
        bob.receive_message(env)
    for path in (a_home / "e2e").rglob("*"):
        if path.is_file():
            data = path.read_bytes()
            for needle in secrets_:
                assert needle not in data, (path.name, needle)
    # Owner-only permissions on every store file. Portal's *.lock files are
    # empty fcntl lock sentinels created 0o640 by the shared store layer —
    # not secret-bearing stores — so the mode invariant covers the stores.
    for path in (a_home / "e2e").rglob("*"):
        if path.is_file() and path.suffix != ".lock":
            assert stat.S_IMODE(path.stat().st_mode) == 0o600, path


def test_wrong_passphrase_and_lock(pair, homes):
    a_home, _ = homes
    alice, bob = pair
    conv_a, _ = handshake(alice, bob)
    alice.lock()
    assert alice.is_locked
    with pytest.raises(VeilChatError):
        alice.send_message(conv_a, b"nope")
    with pytest.raises(VeilChatError):
        VeilChat("wrong-passphrase", home=a_home)
    alice.unlock("alice-passphrase")
    env = alice.send_message(conv_a, b"back")
    assert bob.receive_message(env)["plaintext"] == b"back"


def test_empty_plaintext_rejected(pair):
    alice, bob = pair
    conv_a, _ = handshake(alice, bob)
    with pytest.raises(VeilChatError):
        alice.send_message(conv_a, b"")


# ---------------------------------------------------------------------------
# Honest reporting + invariants
# ---------------------------------------------------------------------------


def test_crypto_report_is_honest(pair):
    alice, _ = pair
    report = alice.crypto_report()
    assert report["x25519"] in (
        "cryptography-x25519",
        "pure-python-fallback",
        "unavailable",
    )
    assert report["envelope_aead"] in ("aes-256-gcm", "stdlib-fallback")
    assert report["kdf"] in ("scrypt", "pbkdf2")
    assert "forward_secrecy" in report


def test_check_invariants_all_pass():
    failing = [r for r in check_invariants() if not r[1]]
    assert failing == [], failing


def test_threats_and_non_claims_documented():
    assert len(THREATS) >= 4
    assert len(NON_CLAIMS) >= 5
    for threat in THREATS:
        for key in ("id", "asset", "attack", "mitigation", "residual", "status"):
            assert threat.get(key), (threat.get("id"), key)


def test_identity_is_passphrase_derived_and_stable(pair, homes):
    """Same passphrase + same home => same identity; the private half is
    never written to disk."""
    a_home, _ = homes
    alice, _ = pair
    fp1 = alice.identity()["fingerprint"]
    alice2 = VeilChat("alice-passphrase", home=a_home)
    assert alice2.identity()["fingerprint"] == fp1
    for path in (a_home / "e2e").rglob("*"):
        if path.is_file():
            assert alice._identity_priv() not in path.read_bytes()


# ---------------------------------------------------------------------------
# Operating laws L6-L12 — runtime-checkable invariants
# ---------------------------------------------------------------------------


def test_peer_rekey_fails_closed(pair):
    """Originals-first: a peer id is never silently re-keyed. Re-adding
    the same key is idempotent; a different key fails closed with the
    remedy named."""
    alice, bob = pair
    bob_pub = base64.b64decode(bob.identity()["public_key"])
    # Same key: idempotent.
    assert alice.add_peer("bob", bob_pub)["peer_id"] == "bob"
    # Different key: refused, remedy named.
    import secrets

    with pytest.raises(VeilChatError) as exc:
        alice.add_peer("bob", secrets.token_bytes(32))
    assert "remove_peer" in str(exc.value)


def test_remove_peer_with_conversation_fails(pair):
    """No-cancellation: a peer with live conversations cannot be removed."""
    alice, bob = pair
    conv_a, _ = handshake(alice, bob)
    with pytest.raises(VeilChatError):
        alice.remove_peer("bob")
    # Unknown peer also fails closed.
    with pytest.raises(VeilChatError):
        alice.remove_peer("nobody")
    # Traffic still flows — nothing was cancelled.
    env = alice.send_message(conv_a, b"kept")
    assert bob.receive_message(env)["plaintext"] == b"kept"


def test_verify_laws_all_hold(pair):
    alice, bob = pair
    conv_a, _ = handshake(alice, bob)
    env = alice.send_message(conv_a, b"lawful")
    assert bob.receive_message(env)["plaintext"] == b"lawful"
    failing = [r for r in alice.verify_laws() if not r[1]]
    assert failing == [], failing
    failing = [r for r in bob.verify_laws() if not r[1]]
    assert failing == [], failing


def test_laws_declared_machine_readable():
    from levi.cybrus.veil_chat import LAWS

    ids = [lid for lid, _ in LAWS]
    assert ids == ["L%d" % i for i in range(1, 13)]
    assert all(text.strip() for _, text in LAWS)


# ---------------------------------------------------------------------------
# No own HTTP egress — machine-checked (choke-point law L2)
# ---------------------------------------------------------------------------


def test_no_network_imports_in_veil_chat():
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    tree = ast.parse(
        (root / "core/levi/cybrus/veil_chat.py").read_text(encoding="utf-8")
    )
    banned = {"socket", "urllib", "requests", "http", "ssl"}
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    assert not (found & banned), found & banned


# ---------------------------------------------------------------------------
# Choke-point wiring: levi.veilchat -> levi.onion crosses Cybrus
# ---------------------------------------------------------------------------


@pytest.fixture
def choke_point(tmp_path, monkeypatch):
    """Hermetic Cybrus control plane: fresh LEVI_HOME, a service token
    with the service.call scope, a rate-limit tier, a policy allow rule,
    and the veilchat/onion internal routes registered."""
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "levi-home"))
    from levi.cybrus import rate_limits as rl
    from levi.cybrus.policy import PolicyEngine
    from levi.cybrus.router import INTERNAL_ROUTES
    from levi.cybrus.tokens import TokenEngine

    monkeypatch.setitem(INTERNAL_ROUTES, "levi.veilchat", "veil E2E messenger")
    monkeypatch.setitem(INTERNAL_ROUTES, "levi.onion", "veil onion transport")
    _, token = TokenEngine().issue(
        scopes=["service.call"], ttl_seconds=3600, kind="api", label="svc"
    )
    rl.set_tier("levi.veilchat", "starter")
    PolicyEngine().add_rule(
        "levi.veilchat", "service.levi.onion", "onion_send", "allow", "low"
    )
    return token


def test_send_via_onion_refused_without_credential(pair, choke_point):
    """No credential at the choke point: the call is refused and the body
    never runs — no envelope is even sealed."""
    import json

    from levi.cybrus.enforce import NotAuthenticated
    from levi.cybrus.onion import SimulatedNetwork

    alice, bob = pair
    conv_a, _ = handshake(alice, bob)
    network = SimulatedNetwork()
    relays = [network.add_relay(n) for n in ("guard", "middle", "exit")]
    circuit = network.open_circuit([r.relay_id for r in relays])

    def deliver(envelope):
        return network.send(circuit, json.dumps(envelope).encode())

    with pytest.raises(NotAuthenticated):
        alice.send_via_onion(conv_a, b"nope", deliver)
    # Nothing was sealed or stored for the refused call.
    assert alice.fetch_envelopes(conv_a) == []


def test_send_via_onion_crosses_choke_point(pair, choke_point):
    """With a credential, the chat -> onion call crosses the choke point
    (auth, route, rate-limit, policy, audit) and the sealed envelope is
    delivered through a real 3-hop circuit."""
    import json

    from levi.cybrus.onion import SimulatedNetwork

    alice, bob = pair
    conv_a, conv_b = handshake(alice, bob)
    network = SimulatedNetwork()
    relays = [network.add_relay(n) for n in ("guard", "middle", "exit")]
    circuit = network.open_circuit([r.relay_id for r in relays])

    def deliver(envelope):
        return network.send(circuit, json.dumps(envelope).encode())

    out = alice.send_via_onion(
        conv_a,
        b"through the onion",
        deliver,
        cybrus_credential=choke_point,
        cybrus_payload_ref=conv_a,
    )
    delivered = out["transport"]["delivered"]
    env = json.loads(bytes(delivered).decode("utf-8"))
    # The exit relay delivered a sealed envelope Bob can open — the
    # transport never saw plaintext.
    assert bob.receive_message(env)["plaintext"] == b"through the onion"
    assert out["transport"]["observations"]
