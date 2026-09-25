"""Tests for levi.cybrus.sync — platform-sync protocol (hermetic).

Proof, named honestly: invariant tests, not formal proof. Each test pins
one protocol invariant: pairing needs both humans, every envelope is
sealed and replay-protected, tampering fails closed, rotation destroys the
old epoch, unpairing destroys the keys, and sync stays off until enabled.

Hermetic: endpoints get isolated ``home=`` dirs (no real HOME writes), no
network — the LoopbackPair is the only transport. The router-admission
test monkeypatches LEVI_HOME to a tmp dir.
"""

import json

import pytest

from levi.cybrus import sync
from levi.cybrus.sync import (
    LoopbackPair,
    PairingError,
    PairingRefused,
    ReplayError,
    SyncEndpoint,
    SyncError,
    admit_standalone,
    build_manifest,
    decode_message,
    revoke_admission,
    verify_manifest,
)


@pytest.fixture()
def homes(tmp_path):
    return tmp_path / "standalone-home", tmp_path / "platform-home"


@pytest.fixture()
def pair(homes):
    s_home, p_home = homes
    s = SyncEndpoint("standalone", home=s_home)
    p = SyncEndpoint("platform", home=p_home)
    s.enable()
    p.enable()
    return s, p, LoopbackPair(s, p)


def do_handshake(s, p, link):
    """Drive the full pairing ceremony over the loopback transport."""
    offer = s.begin_pairing()
    link.send(p, p.join_pairing(offer))  # platform -> standalone (bytes)
    # NOTE: in the real ceremony the standalone human reads this summary
    # off their own screen and compares the fingerprint out of band.
    summary = s.receive_pair_request(link.recv(s))
    assert summary["platform_id"] == p.public_identity()["id"]
    link.send(s, s.confirm_pairing(True))  # standalone -> platform
    done = p.receive_pair_accept(link.recv(p))
    assert done["id"] == s.public_identity()["id"]
    assert link.pending(s) == 0 and link.pending(p) == 0
    return offer


def _choke_context():
    """Seed the choke-point stack for the sync organ: a service token with
    the service.call scope, a rate-limit tier, and the allow rules
    (seed policy is default-deny — without these the choke point
    refuses)."""
    from levi.cybrus import rate_limits
    from levi.cybrus.tokens import TokenEngine

    _, token = TokenEngine().issue(
        scopes=["service.call"], ttl_seconds=3600, kind="api", label="sync tests"
    )
    rate_limits.set_tier("levi.cybrus.sync", "starter")
    sync.seed_sync_policy()
    return token


# -- L2: pairing needs both humans -------------------------------------------


def test_pairing_handshake_success(pair):
    s, p, link = pair
    do_handshake(s, p, link)
    assert [x["peer_id"] for x in s.status()["peers"]] == [p.public_identity()["id"]]
    assert [x["peer_id"] for x in p.status()["peers"]] == [s.public_identity()["id"]]
    # Single-use bootstrap: the pairing state is gone on both sides.
    assert s.store.load("pairing") is None
    assert p.store.load("pairing") is None


def test_pairing_refused_without_confirmation(pair):
    s, p, link = pair
    offer = s.begin_pairing()
    link.send(p, p.join_pairing(offer))
    s.receive_pair_request(link.recv(s))
    with pytest.raises(PairingRefused):
        s.confirm_pairing(False)
    # Refusal aborts: no session, no pending state left behind.
    assert s.status()["peers"] == []
    assert s.store.load("pairing") is None


def test_pairing_confirm_without_request_refused(pair):
    s, p, link = pair
    s.begin_pairing()
    with pytest.raises(PairingError):
        s.confirm_pairing(True)  # no verified request yet


def test_pairing_wrong_code_fails_closed(pair):
    s, p, link = pair
    offer = s.begin_pairing()
    bad = dict(offer)
    # A single changed code char must not authenticate.
    code = bad["code"]
    bad["code"] = ("1" if code[0] != "1" else "2") + code[1:]
    link.send(p, p.join_pairing(bad))
    with pytest.raises(PairingError):
        s.receive_pair_request(link.recv(s))
    assert s.status()["peers"] == []


def test_pairing_tampered_request_fails_closed(pair):
    s, p, link = pair
    offer = s.begin_pairing()
    raw = p.join_pairing(offer)
    msg = decode_message(raw)
    msg["salt_p"] = "A" * 24  # attacker swaps the platform salt
    link.send(p, sync.encode_message(msg))
    with pytest.raises(PairingError):
        s.receive_pair_request(link.recv(s))


def test_pairing_tampered_accept_fails_closed(pair):
    s, p, link = pair
    offer = s.begin_pairing()
    link.send(p, p.join_pairing(offer))
    s.receive_pair_request(link.recv(s))
    raw = s.confirm_pairing(True)
    msg = decode_message(raw)
    msg["nonce_s"] = "A" * 24
    link.send(s, sync.encode_message(msg))
    with pytest.raises(PairingError):
        p.receive_pair_accept(link.recv(p))
    assert p.status()["peers"] == []


def test_pairing_offer_expiry(pair):
    s, p, link = pair
    offer = s.begin_pairing(ttl_seconds=1)
    # Expire the stored offer out from under the handshake.
    pending = s.store.load("pairing")
    pending["expires_at"] = 1.0  # 1970 — long dead
    s.store.save("pairing", pending)
    link.send(p, p.join_pairing(offer))
    with pytest.raises(PairingError):
        s.receive_pair_request(link.recv(s))


def test_pairing_wrong_role_refused(pair):
    s, p, link = pair
    with pytest.raises(SyncError):
        p.begin_pairing()  # platform cannot open a pairing
    offer = s.begin_pairing()
    with pytest.raises(SyncError):
        s.join_pairing(offer)  # standalone cannot join one


# -- L3: sealed, replay-protected channel -------------------------------------


def test_channel_message_exchange_both_directions(pair):
    s, p, link = pair
    do_handshake(s, p, link)
    s_id, p_id = s.public_identity()["id"], p.public_identity()["id"]

    link.send(s, s.send(p_id, b"hello from standalone"))
    got = p.receive(link.recv(p))
    assert got["type"] == "message"
    assert got["plaintext"] == b"hello from standalone"
    assert got["peer_id"] == s_id
    assert got["seq"] == 1

    link.send(p, p.send(s_id, b"hello from platform"))
    got2 = s.receive(link.recv(s))
    assert got2["plaintext"] == b"hello from platform"
    assert got2["seq"] == 1  # per-direction sequence spaces


def test_envelope_tamper_fails_closed(pair):
    s, p, link = pair
    do_handshake(s, p, link)
    raw = s.send(p.public_identity()["id"], b"secret payload")
    msg = decode_message(raw)
    blob = bytearray(sync._b64d(msg["blob"]))
    blob[10] ^= 0xFF  # flip a ciphertext bit
    msg["blob"] = sync._b64e(bytes(blob))
    with pytest.raises(SyncError):
        p.receive(sync.encode_message(msg))


def test_envelope_forged_attestation_fails_closed(pair):
    s, p, link = pair
    do_handshake(s, p, link)
    raw = s.send(p.public_identity()["id"], b"secret payload")
    msg = decode_message(raw)
    msg["attest"] = "0" * 64  # forged attestation tag
    with pytest.raises(SyncError):
        p.receive(sync.encode_message(msg))


def test_envelope_header_swap_fails_closed(pair):
    s, p, link = pair
    do_handshake(s, p, link)
    raw = s.send(p.public_identity()["id"], b"secret payload")
    msg = decode_message(raw)
    msg["seq"] = 999  # header tampering breaks the AAD binding
    with pytest.raises(SyncError):
        p.receive(sync.encode_message(msg))


def test_replay_rejected(pair):
    s, p, link = pair
    do_handshake(s, p, link)
    raw = s.send(p.public_identity()["id"], b"once only")
    link.send(s, raw)
    assert p.receive(link.recv(p))["plaintext"] == b"once only"
    link.send(s, raw)  # attacker replays the exact bytes
    with pytest.raises(ReplayError):
        p.receive(link.recv(p))


def test_out_of_order_rejected(pair):
    s, p, link = pair
    do_handshake(s, p, link)
    first = s.send(p.public_identity()["id"], b"first")
    second = s.send(p.public_identity()["id"], b"second")
    link.send(s, second)
    assert p.receive(link.recv(p))["plaintext"] == b"second"
    link.send(s, first)  # older seq after a newer one
    with pytest.raises(ReplayError):
        p.receive(link.recv(p))


def test_unknown_envelope_rejected(pair):
    s, p, _link = pair
    with pytest.raises(SyncError):
        s.receive(sync.encode_message({"v": 1, "kind": "msg"}))


# -- capability advertisement + router admission -------------------------------


def test_capability_manifest_signature(pair):
    s, p, link = pair
    do_handshake(s, p, link)
    p_id = p.public_identity()["id"]
    link.send(s, s.advertise_capabilities(p_id))
    got = p.receive(link.recv(p))
    assert got["type"] == "capabilities"
    manifest = got["manifest"]
    verified = p.verify_peer_manifest(s.public_identity()["id"], manifest)
    assert verified["offers"] == ["vault", "veil", "router", "messenger"]
    assert verified["identity"]["id"] == s.public_identity()["id"]


def test_capability_manifest_tamper_fails_closed(pair):
    s, p, link = pair
    do_handshake(s, p, link)
    p_id = p.public_identity()["id"]
    link.send(s, s.advertise_capabilities(p_id))
    manifest = p.receive(link.recv(p))["manifest"]
    manifest["offers"].append("everything-ever")  # tamper after signing
    with pytest.raises(SyncError):
        p.verify_peer_manifest(s.public_identity()["id"], manifest)


def test_manifest_wrong_peer_rejected(pair, homes):
    s, p, link = pair
    do_handshake(s, p, link)
    # A second standalone's manifest must not verify as the first peer's.
    s2 = SyncEndpoint("standalone", home=homes[0] / "impostor")
    s2.enable()
    peer = s._find_peer(p.public_identity()["id"])
    subkeys = s._subkeys(peer, 0)
    forged = build_manifest(s2.public_identity(), subkeys["attest_s"])
    with pytest.raises(SyncError):
        p.verify_peer_manifest(s.public_identity()["id"], forged)


def test_admit_standalone_registers_external_route(pair, tmp_path, monkeypatch):
    from levi.cybrus.router import RouteRegistry

    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "platform-levi-home"))
    token = _choke_context()
    s, p, link = pair
    do_handshake(s, p, link)
    p_id = p.public_identity()["id"]
    link.send(s, s.advertise_capabilities(p_id))
    manifest = p.receive(link.recv(p))["manifest"]
    peer = p._find_peer(s.public_identity()["id"])
    attest_key = p._subkeys(peer, 0)["attest_s"]

    registry = RouteRegistry()
    admitted = admit_standalone(
        registry,
        manifest,
        attest_key,
        approved_by="chauncey",
        reason="admit my standalone cybrus as a routed sync endpoint",
        cybrus_credential=token,
    )
    provider = admitted["route"]["provider"]
    assert provider.startswith("cybrus-standalone-")
    assert admitted["route"]["scope"] == "cybrus.sync"
    assert admitted["route"]["approved_by"] == "chauncey"
    # The route resolves through the normal router machinery.
    decision = registry.resolve(provider + ".vault")
    assert decision["kind"] == "external"
    assert decision["crosses_boundary"] is True
    revoke_admission(registry, provider, by="chauncey", cybrus_credential=token)
    assert all(
        r["provider"] != provider or r["status"] != "active"
        for r in registry.external_routes(include_removed=True)
    )


def test_admit_tampered_manifest_refused(pair, tmp_path, monkeypatch):
    from levi.cybrus.router import RouteRegistry

    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "platform-levi-home"))
    s, p, link = pair
    do_handshake(s, p, link)
    p_id = p.public_identity()["id"]
    link.send(s, s.advertise_capabilities(p_id))
    manifest = p.receive(link.recv(p))["manifest"]
    manifest["wants"] = ["levi.everything"]  # tamper after signing
    peer = p._find_peer(s.public_identity()["id"])
    attest_key = p._subkeys(peer, 0)["attest_s"]
    with pytest.raises(SyncError):
        admit_standalone(
            RouteRegistry(),
            manifest,
            attest_key,
            approved_by="chauncey",
            reason="should never land",
        )


# -- forward-secure rotation ----------------------------------------------------


def test_rekey_rotates_and_destroys_old_epoch(pair):
    s, p, link = pair
    do_handshake(s, p, link)
    s_peer_id = s.public_identity()["id"]
    p_peer_id = p.public_identity()["id"]

    old_secret_s = s._get_secret(s._find_peer(p_peer_id), 0)
    link.send(s, s.begin_rekey(p_peer_id))
    assert s._find_peer(p_peer_id)["pending_rekey"]["epoch"] == 1

    got = p.receive(link.recv(p))
    assert got["type"] == "rekey" and got["epoch"] == 1
    # Responder rotated; epoch 0 is now a GRACE epoch — still openable for
    # in-flight envelopes, destroyed on first new-epoch traffic.
    p_peer = p._find_peer(s_peer_id)
    assert p_peer["epoch"] == 1
    assert p_peer["grace_epochs"] == [0]
    assert "0" in p_peer["epoch_secrets"]

    # The ack (sealed under the NEW epoch) lets the initiator promote too;
    # its epoch 0 becomes grace as well.
    link.send(p, got["ack"])
    acked = s.receive(link.recv(s))
    assert acked["type"] == "rekey-acked" and acked["epoch"] == 1
    s_peer = s._find_peer(p_peer_id)
    assert s_peer["epoch"] == 1
    assert s_peer["grace_epochs"] == [0]
    new_secret_s = s._get_secret(s._find_peer(p_peer_id), 1)
    assert new_secret_s != old_secret_s

    # The channel keeps working under the new epoch — and the first
    # new-epoch envelope destroys the grace epoch on the receiver.
    link.send(s, s.send(p_peer_id, b"post-rotation"))
    assert p.receive(link.recv(p))["plaintext"] == b"post-rotation"
    p_peer = p._find_peer(s_peer_id)
    assert "0" not in p_peer["epoch_secrets"]
    assert p_peer["grace_epochs"] == []
    with pytest.raises(SyncError):
        p._get_secret(p._find_peer(s_peer_id), 0)


def test_rekey_out_of_sequence_rejected(pair):
    s, p, link = pair
    do_handshake(s, p, link)
    p_peer_id = p.public_identity()["id"]
    link.send(s, s.begin_rekey(p_peer_id))
    got = p.receive(link.recv(p))
    assert got["type"] == "rekey"
    # A second rekey offer for the same epoch is not a valid rotation.
    with pytest.raises(SyncError):
        s.begin_rekey(p_peer_id)


# -- L5: unpair destroys the keys -----------------------------------------------


def test_unpair_destroys_keys(pair):
    s, p, link = pair
    do_handshake(s, p, link)
    p_id = p.public_identity()["id"]
    link.send(s, s.send(p_id, b"before"))
    assert p.receive(link.recv(p))["plaintext"] == b"before"

    assert s.unpair(p_id) == {"unpaired": p_id}
    assert s.status()["peers"] == []
    assert s.store.load("peers") == []
    # In-memory copies zeroized.
    assert not [k for k in s._cache if k[0] == p_id]
    # The peer is unknown now: send and receive both refuse.
    with pytest.raises(SyncError):
        s.send(p_id, b"after")
    stale = p.send(s.public_identity()["id"], b"stale")
    with pytest.raises(SyncError):
        s.receive(stale)


# -- L1: offline by default -------------------------------------------------------


def test_sync_disabled_by_default(homes):
    s_home, p_home = homes
    s = SyncEndpoint("standalone", home=s_home)
    p = SyncEndpoint("platform", home=p_home)
    assert s.enabled is False and p.enabled is False
    with pytest.raises(SyncError):
        s.begin_pairing()
    with pytest.raises(SyncError):
        p.join_pairing({})
    with pytest.raises(SyncError):
        s.send("nobody", b"x")
    with pytest.raises(SyncError):
        s.receive(b"{}")
    # ...until the explicit opt-in.
    s.enable()
    assert s.enabled is True
    offer = s.begin_pairing()
    assert offer["code"]  # and the ceremony can start


def test_disable_blocks_protocol(homes):
    s_home, _ = homes
    s = SyncEndpoint("standalone", home=s_home)
    s.enable()
    s.disable()
    with pytest.raises(SyncError):
        s.begin_pairing()


# -- L4: no secrets in status, logs, or errors --------------------------------------


def test_status_exposes_no_secrets(pair):
    s, p, link = pair
    offer = s.begin_pairing()
    code = offer["code"]
    dumped = json.dumps(s.status())
    assert code not in dumped and code.replace("-", "") not in dumped
    do_handshake(s, p, link)
    dumped = json.dumps(s.status()) + json.dumps(p.status())
    for secret_word in ("epoch_secrets", "pending_rekey", "code_core", "sig"):
        assert secret_word not in dumped


def test_errors_never_echo_the_code(pair):
    s, p, link = pair
    offer = s.begin_pairing()
    bad = dict(offer)
    bad["code"] = "ZZZZ-ZZZZ"
    try:
        p.join_pairing(bad)
    except PairingError as exc:
        assert "ZZZZ" not in str(exc)
    else:  # noqa: SIM — join parses the code shape before any crypto
        pass
    raw = p.join_pairing(offer)
    msg = decode_message(raw)
    msg["sig"] = "0" * 64
    link.send(p, sync.encode_message(msg))
    try:
        s.receive_pair_request(link.recv(s))
        raise AssertionError("should have raised")
    except PairingError as exc:
        assert offer["code"] not in str(exc)


def test_loopback_pair_rejects_foreign_endpoint(pair):
    s, p, link = pair
    outsider = SyncEndpoint("standalone", home=pair[0].store.directory / "x")
    with pytest.raises(SyncError):
        link.send(outsider, b"hi")
    assert link.pending(s) == 0


# -- Operating laws L6-L12, built in ---------------------------------------------


def test_no_invented_primitives(pair):
    """L7 originals-first: every crypto construction is reused, named in
    _REUSED_PRIMITIVES, and identical to its source — nothing invented."""
    from levi.cybrus import veil

    assert len(sync._REUSED_PRIMITIVES) >= 4
    assert sync._veil_seal is veil._seal_backend
    assert sync._veil_open is veil._open_backend
    assert sync._veil_hkdf is veil._hkdf
    assert sync._veil_fingerprint is veil.fingerprint
    # No cipher/KDF/AEAD of its own anywhere in the module.
    import re

    src = open(sync.__file__).read()
    assert not re.search(r"class \w*(Cipher|AEAD|KDF)\w*", src)
    assert "def _aes" not in src and "def _chacha" not in src


def test_ambiguous_peer_refuses_to_guess(pair):
    """L6 clarify rule: two live pairings with the same peer_id must not
    silently pick one — addressing falls back to the explicit sync_id."""
    s, p, link = pair
    do_handshake(s, p, link)
    do_handshake(s, p, link)  # second pairing, same peer
    p_id = p.public_identity()["id"]
    with pytest.raises(SyncError):
        s.send(p_id, b"which session?")
    sync_ids = [x["sync_id"] for x in s.status()["peers"]]
    assert len(sync_ids) == 2 and sync_ids[0] != sync_ids[1]
    link.send(s, s.send(sync_ids[1], b"explicit session"))
    assert p.receive(link.recv(p))["plaintext"] == b"explicit session"


def test_unpair_only_cancels_its_own_session(homes, tmp_path):
    """L9 no-cancellation: unpairing one peer leaves the other's live
    session completely untouched."""
    s_home, _ = homes
    s = SyncEndpoint("standalone", home=s_home)
    p1 = SyncEndpoint("platform", home=tmp_path / "p1")
    p2 = SyncEndpoint("platform", home=tmp_path / "p2")
    for e in (s, p1, p2):
        e.enable()
    do_handshake(s, p1, LoopbackPair(s, p1))
    do_handshake(s, p2, LoopbackPair(s, p2))
    p1_id, p2_id = p1.public_identity()["id"], p2.public_identity()["id"]

    assert s.unpair(p1_id) == {"unpaired": p1_id}
    # p1 is gone...
    with pytest.raises(SyncError):
        s.send(p1_id, b"dead")
    # ...p2's session never noticed.
    link2 = LoopbackPair(s, p2)
    link2.send(p2, p2.send(s.public_identity()["id"], b"still here"))
    got = s.receive(link2.recv(s))
    assert got["plaintext"] == b"still here"
    assert got["peer_id"] == p2_id
    assert [x["peer_id"] for x in s.status()["peers"]] == [p2_id]


def test_unpair_archives_without_secrets(pair):
    """L10 nothing-thrown-away: the peer's public record is superseded
    into the archive — with zero key material in it."""
    import json as _json

    s, p, link = pair
    do_handshake(s, p, link)
    p_id = p.public_identity()["id"]
    s.unpair(p_id)
    archive = s.store.load_archive()
    entries = [e for e in archive if e["kind"] == "peer"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["reason"] == "unpaired"
    assert entry["peer_id"] == p_id
    assert entry["peer_fingerprint"] == p.public_identity()["fingerprint"]
    dumped = _json.dumps(entry)
    for secret_word in ("epoch_secrets", "secret", "code_core", "sig", "pending_rekey"):
        assert secret_word not in dumped


def test_pairing_archived_not_deleted(pair):
    """L10: a completed pairing retires its offer into the archive —
    superseded, never just deleted; and the live pairing file is gone."""
    s, p, link = pair
    do_handshake(s, p, link)
    assert s.store.load("pairing") is None
    assert p.store.load("pairing") is None
    kinds = [(e["kind"], e["reason"]) for e in s.store.load_archive()]
    assert ("pairing", "paired") in kinds
    kinds_p = [(e["kind"], e["reason"]) for e in p.store.load_archive()]
    assert ("pairing", "paired") in kinds_p


def test_refused_pairing_archived(pair):
    """L10: even a refused pairing leaves its public trace."""
    s, p, link = pair
    offer = s.begin_pairing()
    link.send(p, p.join_pairing(offer))
    s.receive_pair_request(link.recv(s))
    with pytest.raises(PairingRefused):
        s.confirm_pairing(False)
    reasons = [e["reason"] for e in s.store.load_archive() if e["kind"] == "pairing"]
    assert "refused" in reasons


def test_rekey_in_flight_does_not_wedge_channel(pair):
    """L11 forward-motion: a rekey whose ack never arrives leaves the
    live epoch fully usable — the stuck checkpoint never stops the work."""
    s, p, link = pair
    do_handshake(s, p, link)
    p_id = p.public_identity()["id"]
    link.send(s, s.begin_rekey(p_id))  # offer sent...
    # ...but the peer never answers. The channel still works on epoch 0.
    link.send(s, s.send(p_id, b"work continues"))
    assert p.receive(link.recv(p))["type"] == "rekey"  # the unanswered offer
    assert p.receive(link.recv(p))["plaintext"] == b"work continues"
    assert s._find_peer(p_id)["pending_rekey"]["epoch"] == 1


def test_abort_rekey_clears_stuck_rotation(pair):
    """L11: abort_rekey explicitly clears a stalled rotation so a fresh
    one can start — forward motion, named checkpoint."""
    s, p, link = pair
    do_handshake(s, p, link)
    p_id = p.public_identity()["id"]
    s.begin_rekey(p_id)
    with pytest.raises(SyncError):
        s.begin_rekey(p_id)  # already in flight
    assert s.abort_rekey(p_id)["rekey_aborted"] is True
    assert s._find_peer(p_id).get("pending_rekey") is None
    # A fresh rotation now completes end to end.
    link.send(s, s.begin_rekey(p_id))
    got = p.receive(link.recv(p))
    link.send(p, got["ack"])
    assert s.receive(link.recv(s))["type"] == "rekey-acked"
    with pytest.raises(SyncError):
        s.abort_rekey(p_id)  # nothing in flight anymore


def test_status_reports_transport_honestly(pair):
    """L12 honesty over polish: status names the transport as stubbed and
    reports the real envelope backend."""
    s, p, link = pair
    do_handshake(s, p, link)
    st = s.status()
    assert "no network transport" in st["transport"]
    assert "loopback" in st["transport"]
    assert st["envelope_backend"] in ("aes-256-gcm", "stdlib-fallback")
    assert st["archived_records"] >= 1  # the retired pairing offer


# -- choke-point wiring (Build 1) ------------------------------------------------


def _admit_manifest(pair):
    """Handshake + capability advertisement; returns (registry, manifest,
    attest_key) ready for admission."""
    from levi.cybrus.router import RouteRegistry

    s, p, link = pair
    do_handshake(s, p, link)
    p_id = p.public_identity()["id"]
    link.send(s, s.advertise_capabilities(p_id))
    manifest = p.receive(link.recv(p))["manifest"]
    peer = p._find_peer(s.public_identity()["id"])
    attest_key = p._subkeys(peer, 0)["attest_s"]
    return RouteRegistry(), manifest, attest_key


def test_seed_sync_policy_idempotent(tmp_path, monkeypatch):
    """The organ's allow rules seed once and never duplicate."""
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    first = sync.seed_sync_policy()
    assert len(first) == 2
    assert {r["action"] for r in first} == {
        "router.add_external",
        "router.remove_external",
    }
    assert sync.seed_sync_policy() == []


def test_admit_without_credential_refused(pair, tmp_path, monkeypatch):
    """Fail closed: admission without a platform credential is refused by
    the choke point, with the remedy named (L6)."""
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "platform-levi-home"))
    registry, manifest, attest_key = _admit_manifest(pair)
    with pytest.raises(SyncError) as excinfo:
        admit_standalone(
            registry,
            manifest,
            attest_key,
            approved_by="chauncey",
            reason="no credential presented",
        )
    assert "credential" in str(excinfo.value).lower()


def test_revoke_without_credential_refused(pair, tmp_path, monkeypatch):
    """Fail closed: revocation without a credential is refused too."""
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "platform-levi-home"))
    token = _choke_context()
    registry, manifest, attest_key = _admit_manifest(pair)
    admitted = admit_standalone(
        registry,
        manifest,
        attest_key,
        approved_by="chauncey",
        reason="admit then try to revoke without credential",
        cybrus_credential=token,
    )
    provider = admitted["route"]["provider"]
    with pytest.raises(SyncError) as excinfo:
        revoke_admission(registry, provider, by="chauncey")
    assert "credential" in str(excinfo.value).lower()
    # The route is still active — the refused revocation changed nothing.
    assert registry.resolve(provider + ".vault")["kind"] == "external"


def test_admission_crosses_choke_point(pair, tmp_path, monkeypatch):
    """The admission is authenticated, policy-checked, and audit-logged
    (metadata only) — a choke-point ticket, not a direct call."""
    from levi.cybrus.audit import AuditEngine

    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "platform-levi-home"))
    token = _choke_context()
    registry, manifest, attest_key = _admit_manifest(pair)
    admit_standalone(
        registry,
        manifest,
        attest_key,
        approved_by="chauncey",
        reason="prove the choke-point crossing",
        cybrus_credential=token,
    )
    routed = [
        r for r in AuditEngine().tail(200) if r["event"] == "call.routed"
    ]
    assert routed, "expected a call.routed audit record"
    record = routed[-1]
    assert record["actor"] == "levi.cybrus.sync"
    details = record["details"]
    assert details["callee"] == "levi.cybrus"
    assert details["action"] == "router.add_external"
    assert details["auth"] == "service_token"
    # L4: metadata only — no payload, no secret, no credential anywhere.
    dumped = __import__("json").dumps(record)
    assert token not in dumped
    for word in ("manifest", "attest", "secret", "password"):
        assert word not in dumped.lower()
