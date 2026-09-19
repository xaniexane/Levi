"""Tests for levi.cybrus.veil — Veil, the keeper's sealed messenger.

Hermetic: every test gets a fresh Veil rooted at tmp_path (no HOME
writes, no network). Tamper/replay/revocation paths are all exercised —
Veil fails closed, and the tests prove it.
"""

import hashlib
import hmac
import json
import stat

import pytest

from levi.cybrus import veil
from levi.cybrus.veil import (
    NON_CLAIMS,
    THREATS,
    Veil,
    VeilError,
    check_invariants,
    fingerprint,
)


@pytest.fixture
def vb(tmp_path):
    return Veil("keeper-passphrase", home=tmp_path / "vb")


@pytest.fixture
def pair(vb):
    alice = vb.create_device("alice-phone")
    bob = vb.create_device("bob-laptop")
    return vb, alice, bob


# ---------------------------------------------------------------------------
# Primitives: fingerprint + AEAD layout
# ---------------------------------------------------------------------------


def test_fingerprint_is_stable_and_grouped():
    a = fingerprint(b"device-token-bytes")
    b = fingerprint(b"device-token-bytes")
    assert a == b
    assert " " in a
    parts = a.split(" ")
    assert all(len(p) == 4 for p in parts)
    assert len(parts) == 16  # 64 hex chars in groups of 4


def test_seal_open_roundtrip():
    key = b"k" * 32
    nonce = b"n" * 16
    blob = veil._seal(key, nonce, b"hello void", b"conv-1")
    assert blob.startswith(b"VB1")
    assert veil._open(key, blob, b"conv-1") == b"hello void"


def test_seal_tampered_blob_fails():
    key = b"k" * 32
    blob = bytearray(veil._seal(key, b"n" * 16, b"secret", b"aad"))
    blob[-1] ^= 0x01  # flip a tag bit
    with pytest.raises(VeilError):
        veil._open(key, bytes(blob), b"aad")


def test_seal_wrong_key_fails():
    blob = veil._seal(b"k" * 32, b"n" * 16, b"secret", b"aad")
    with pytest.raises(VeilError):
        veil._open(b"z" * 32, blob, b"aad")


def test_seal_wrong_aad_fails():
    blob = veil._seal(b"k" * 32, b"n" * 16, b"secret", b"aad-a")
    with pytest.raises(VeilError):
        veil._open(b"k" * 32, blob, b"aad-b")


def test_seal_bad_magic_fails():
    blob = b"BAD" + b"\x00" * 60
    with pytest.raises(VeilError):
        veil._open(b"k" * 32, blob, b"aad")


def test_seal_nonce_uniqueness():
    key = b"k" * 32
    import secrets as _secrets

    b1 = veil._seal(key, _secrets.token_bytes(16), b"same", b"aad")
    b2 = veil._seal(key, _secrets.token_bytes(16), b"same", b"aad")
    assert b1 != b2  # different nonces -> different blobs


# ---------------------------------------------------------------------------
# Keeper-held keys: init, lock, unlock, permissions
# ---------------------------------------------------------------------------


def test_init_creates_owner_only_state(tmp_path):
    home = tmp_path / "vb"
    Veil("keeper-passphrase", home=home)
    assert stat.S_IMODE(home.stat().st_mode) == 0o700
    cfg = home / "config.json"
    assert stat.S_IMODE(cfg.stat().st_mode) == 0o600
    data = json.loads(cfg.read_text())
    assert "salt" in data and "verifier" in data
    # No key material in the config.
    assert "master" not in json.dumps(data).lower()


def test_wrong_passphrase_fails_closed(tmp_path):
    home = tmp_path / "vb"
    Veil("right-phrase", home=home)
    with pytest.raises(VeilError):
        Veil("wrong-phrase", home=home)


def test_empty_passphrase_rejected(tmp_path):
    with pytest.raises(VeilError):
        Veil("", home=tmp_path / "vb")


def test_lock_unlock_cycle(vb, tmp_path):
    vb.create_device("alice")
    vb.lock()
    assert vb.is_locked
    with pytest.raises(VeilError):
        vb.create_device("bob")
    with pytest.raises(VeilError):
        vb.unlock("wrong-phrase")
    vb.unlock("keeper-passphrase")
    assert not vb.is_locked
    vb.create_device("bob")  # works again


# ---------------------------------------------------------------------------
# Device identity: fingerprints, attestation, rotation, revocation
# ---------------------------------------------------------------------------


def test_create_device_public_identity(vb):
    ident = vb.create_device("alice-phone")
    assert ident["name"] == "alice-phone"
    assert ident["key_version"] == 1
    assert len(ident["fingerprint"].split(" ")) == 16
    assert ident["revoked"] is False


def test_duplicate_device_name_rejected(vb):
    vb.create_device("alice")
    with pytest.raises(VeilError):
        vb.create_device("alice")


def test_unknown_device_rejected(vb):
    with pytest.raises(VeilError):
        vb.identity("nope")


def test_fingerprint_ceremony(vb):
    ident = vb.create_device("alice")
    assert vb.verify_fingerprint(ident["device_id"], ident["fingerprint"])
    # Case/whitespace tolerant...
    assert vb.verify_fingerprint(ident["device_id"], ident["fingerprint"].upper())
    # ...but a wrong fingerprint fails.
    assert not vb.verify_fingerprint(ident["device_id"], "aaaa " * 16)
    assert not vb.verify_fingerprint("unknown", ident["fingerprint"])


def test_attest_verify_roundtrip(vb):
    ident = vb.create_device("alice")
    tag = vb.attest(ident["device_id"], b"message bytes")
    assert vb.verify_attestation(ident["device_id"], b"message bytes", tag)
    assert not vb.verify_attestation(ident["device_id"], b"tampered", tag)
    assert not vb.verify_attestation(ident["device_id"], b"message bytes", "00" * 32)


def test_rotate_bumps_version_with_grace(vb):
    ident = vb.create_device("alice")
    old_tag = vb.attest(ident["device_id"], b"in-flight")
    rotated = vb.rotate_device(ident["device_id"])
    assert rotated["key_version"] == 2
    assert rotated["fingerprint"] != ident["fingerprint"]
    # Previous version still verifies: in-flight material survives rotation.
    assert vb.verify_attestation(ident["device_id"], b"in-flight", old_tag)
    # New attestations use the new token.
    new_tag = vb.attest(ident["device_id"], b"after")
    assert vb.verify_attestation(ident["device_id"], b"after", new_tag)


def test_revoke_kills_attestation(vb):
    ident = vb.create_device("alice")
    vb.revoke_device(ident["device_id"], reason="lost phone")
    assert vb.is_revoked(ident["device_id"])
    assert vb.identity(ident["device_id"])["revoked"] is True
    with pytest.raises(VeilError):
        vb.attest(ident["device_id"], b"nope")
    assert not vb.verify_attestation(ident["device_id"], b"m", "00" * 32)
    with pytest.raises(VeilError):
        vb.revoke_device(ident["device_id"])
    with pytest.raises(VeilError):
        vb.rotate_device(ident["device_id"])


def test_revocation_ledger_chain_verifies(vb):
    a = vb.create_device("a")
    b = vb.create_device("b")
    assert vb.verify_ledger()  # empty ledger is valid
    vb.revoke_device(a["device_id"])
    vb.revoke_device(b["device_id"], reason="retired")
    assert vb.verify_ledger()
    # Tamper with one entry: chain breaks.
    path = vb._path("revocations.jsonl")
    lines = path.read_text().splitlines()
    tampered = lines[0].replace("GENESIS", "GENESIX", 1)
    assert tampered != lines[0]
    path.write_text(tampered + "\n" + "\n".join(lines[1:]) + "\n")
    assert not vb.verify_ledger()


# ---------------------------------------------------------------------------
# Sealed messaging: tamper-evidence + replay protection
# ---------------------------------------------------------------------------


def test_message_roundtrip(pair):
    vb, alice, bob = pair
    env = vb.seal_message("conv-1", alice["device_id"], bob["device_id"], b"hello void")
    assert env["protocol_version"] == 1
    assert env["seq"] == 1
    opened = vb.open_message(env)
    assert opened["plaintext"] == b"hello void"
    assert opened["sender"] == alice["device_id"]
    # Sequences advance per (conversation, sender).
    env2 = vb.seal_message("conv-1", alice["device_id"], bob["device_id"], b"again")
    assert env2["seq"] == 2


def test_message_tampered_blob_fails(pair):
    vb, alice, bob = pair
    env = vb.seal_message("conv-1", alice["device_id"], bob["device_id"], b"secret")
    raw = bytearray(veil._b64d(env["blob"]))
    raw[-1] ^= 0x01
    env["blob"] = veil._b64e(bytes(raw))
    with pytest.raises(VeilError):
        vb.open_message(env)


def test_message_tampered_header_fails(pair):
    vb, alice, bob = pair
    env = vb.seal_message("conv-1", alice["device_id"], bob["device_id"], b"secret")
    env["seq"] = 999  # attacker bumps the sequence outside the seal
    with pytest.raises(VeilError):
        vb.open_message(env)


def test_message_replay_rejected(pair):
    vb, alice, bob = pair
    env = vb.seal_message("conv-1", alice["device_id"], bob["device_id"], b"once")
    assert vb.open_message(env)["plaintext"] == b"once"
    with pytest.raises(VeilError, match="replay"):
        vb.open_message(env)


def test_message_from_revoked_sender_fails(pair):
    vb, alice, bob = pair
    env = vb.seal_message("conv-1", alice["device_id"], bob["device_id"], b"before")
    vb.revoke_device(alice["device_id"])
    with pytest.raises(VeilError):
        vb.open_message(env)
    with pytest.raises(VeilError):
        vb.seal_message("conv-1", alice["device_id"], bob["device_id"], b"after")


def test_message_survives_sender_rotation(pair):
    vb, alice, bob = pair
    env = vb.seal_message("conv-1", alice["device_id"], bob["device_id"], b"in-flight")
    vb.rotate_device(alice["device_id"])
    opened = vb.open_message(env)  # grace window: previous token still verifies
    assert opened["plaintext"] == b"in-flight"


def test_message_unknown_version_rejected(pair):
    vb, alice, bob = pair
    env = vb.seal_message("conv-1", alice["device_id"], bob["device_id"], b"x")
    env["protocol_version"] = 999
    with pytest.raises(VeilError):
        vb.open_message(env)


def test_envelope_store_is_ciphertext_only(pair, tmp_path):
    vb, alice, bob = pair
    env = vb.seal_message("conv-1", alice["device_id"], bob["device_id"], b"top secret")
    vb.store_envelope(env)
    fetched = vb.fetch_envelopes("conv-1")
    assert len(fetched) == 1
    assert vb.open_message(fetched[0])["plaintext"] == b"top secret"
    raw = (tmp_path / "vb" / "conversations" / "conv-1.jsonl").read_text()
    assert "top secret" not in raw  # the store never sees plaintext


def test_seal_requires_plaintext_bytes(pair):
    vb, alice, bob = pair
    with pytest.raises(VeilError):
        vb.seal_message("c", alice["device_id"], bob["device_id"], b"")
    with pytest.raises(VeilError):
        vb.seal_message("c", alice["device_id"], bob["device_id"], "not-bytes")


# ---------------------------------------------------------------------------
# Threat register + invariants
# ---------------------------------------------------------------------------


def test_threats_fully_specified():
    required = ("id", "asset", "attack", "mitigation", "residual", "status")
    for threat in THREATS:
        for key in required:
            assert threat.get(key), f"threat {threat.get('id')} missing {key}"


def test_non_claims_documented():
    assert len(NON_CLAIMS) >= 5
    joined = " ".join(NON_CLAIMS).lower()
    assert "post-quantum" in joined
    # Forward secrecy graduated from non-claim to implemented (per-
    # conversation epoch ratchet) — with its bounds stated, not hidden.
    assert "no forward secrecy" not in joined
    threat_ids = " ".join(t["id"] for t in THREATS)
    assert "master-key-compromise-reads-history" in threat_ids


def test_check_invariants_all_green():
    results = check_invariants()
    assert results, "invariant list must not be empty"
    failures = [(name, detail) for name, ok, detail in results if not ok]
    assert not failures, f"invariant failures: {failures}"


def test_state_files_are_owner_only(vb, tmp_path):
    alice_id = vb.create_device("alice")["device_id"]
    carol_id = vb.create_device("carol")["device_id"]
    vb.revoke_device(vb.create_device("b")["device_id"])
    vb.seal_message("c", alice_id, carol_id, b"x")
    for rel in ("config.json", "devices.json", "revocations.jsonl", "seq.json",
                "ratchets.json"):
        p = tmp_path / "vb" / rel
        assert stat.S_IMODE(p.stat().st_mode) == 0o600, rel
    assert stat.S_IMODE((tmp_path / "vb").stat().st_mode) == 0o700


# ---------------------------------------------------------------------------
# Hardening: backend reporting, KDF selection, epoch ratchet, versioning
# ---------------------------------------------------------------------------


def test_backend_reports_honestly(vb):
    expect = "aes-256-gcm" if veil._AESGCM is not None else "stdlib-fallback"
    assert vb.backend == expect
    report = vb.crypto_report()
    assert report["backend"] == expect
    assert report["kdf"] == vb.kdf
    assert "envelope" in report and "forward_secrecy" in report
    assert report["protocol_version"] == 1


def test_kdf_reports_and_is_pinned(tmp_path):
    home = tmp_path / "vb"
    v = Veil("keeper-passphrase", home=home)
    assert v.kdf in ("scrypt", "pbkdf2")
    cfg = json.loads((home / "config.json").read_text())
    assert cfg["kdf"] == v.kdf  # pinned at creation
    # The pin survives lock/unlock cycles.
    v.lock()
    v.unlock("keeper-passphrase")
    assert v.kdf == cfg["kdf"]


def test_kdf_legacy_config_defaults_to_pbkdf2(tmp_path, monkeypatch):
    # Simulate a pre-hardening vault: created under PBKDF2, no "kdf" field.
    monkeypatch.setattr(veil, "_kdf_default", lambda: "pbkdf2")
    home = tmp_path / "vb"
    Veil("keeper-passphrase", home=home)
    cfg_path = home / "config.json"
    cfg = json.loads(cfg_path.read_text())
    assert cfg["kdf"] == "pbkdf2"
    del cfg["kdf"]
    cfg_path.write_text(json.dumps(cfg))
    reopened = Veil("keeper-passphrase", home=home)
    assert reopened.kdf == "pbkdf2"


def test_scrypt_and_pbkdf2_derive_different_masters():
    salt = b"s" * 16
    if hasattr(hashlib, "scrypt"):
        m_scrypt = veil._derive_master("same-phrase", salt, "scrypt")
        m_pbkdf2 = veil._derive_master("same-phrase", salt, "pbkdf2")
        assert m_scrypt != m_pbkdf2  # the KDF choice genuinely matters
        assert len(m_scrypt) == 32 and len(m_pbkdf2) == 32
    with pytest.raises(VeilError):
        veil._derive_master("x", salt, "argon2")


def test_fallback_backend_seals_v1_and_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(veil, "_AESGCM", None)
    v = Veil("keeper-passphrase", home=tmp_path / "vb")
    assert v.backend == "stdlib-fallback"
    assert v.crypto_report()["backend"] == "stdlib-fallback"
    a = v.create_device("a")["device_id"]
    b = v.create_device("b")["device_id"]
    env = v.seal_message("c", a, b, b"fallback hello")
    assert veil._b64d(env["blob"]).startswith(b"VB1")  # labeled fallback
    assert v.open_message(env)["plaintext"] == b"fallback hello"


def test_v2_envelope_fails_closed_without_cryptography(tmp_path, monkeypatch):
    if veil._AESGCM is None:
        pytest.skip("cryptography package not installed")
    v = Veil("keeper-passphrase", home=tmp_path / "vb")
    a = v.create_device("a")["device_id"]
    b = v.create_device("b")["device_id"]
    env = v.seal_message("c", a, b, b"gcm hello")
    assert veil._b64d(env["blob"]).startswith(b"VB2")
    monkeypatch.setattr(veil, "_AESGCM", None)
    # Loud failure with an install hint — never a silent open.
    with pytest.raises(VeilError, match="cryptography"):
        v.open_message(env)


def test_envelope_versioning_dispatch():
    key = b"k" * 32
    b1 = veil._seal(key, b"n" * 16, b"v1 hello", b"aad")
    assert b1.startswith(b"VB1")
    assert veil._open_backend(key, b1, b"aad") == b"v1 hello"
    if veil._AESGCM is not None:
        b2 = veil._seal_gcm(key, b"n" * 12, b"v2 hello", b"aad")
        assert b2.startswith(b"VB2")
        assert veil._open_backend(key, b2, b"aad") == b"v2 hello"
        assert b1[:3] != b2[:3]  # versions distinguishable on the wire
        with pytest.raises(VeilError):
            veil._open_backend(b"z" * 32, b2, b"aad")
    with pytest.raises(VeilError):
        veil._open_backend(key, b"BAD" + b"\x00" * 60, b"aad")


def test_ratchet_forward_secrecy(pair):
    vb, alice, bob = pair
    e1 = vb.seal_message("conv-1", alice["device_id"], bob["device_id"], b"first")
    assert e1["epoch"] == 1  # new conversations start ratcheted
    r = vb.rotate_conversation("conv-1")
    assert r["epoch"] == 2 and r["previous_epoch"] == 1
    e2 = vb.seal_message("conv-1", alice["device_id"], bob["device_id"], b"second")
    assert e2["epoch"] == 2
    # Grace window: the previous epoch still opens in-flight envelopes.
    assert vb.open_message(e1)["plaintext"] == b"first"
    assert vb.open_message(e2)["plaintext"] == b"second"
    # Rotate again: epoch 1 is destroyed — new keys can't read old traffic.
    vb.rotate_conversation("conv-1")
    with pytest.raises(VeilError, match="rotated away"):
        vb.open_message(e1)
    # Epoch 2 still opens under the grace window; epoch 3 seals fresh.
    e3 = vb.seal_message("conv-1", alice["device_id"], bob["device_id"], b"third")
    assert e3["epoch"] == 3
    assert vb.open_message(e3)["plaintext"] == b"third"


def test_old_epoch_key_cannot_open_new_blob(pair):
    # Direct proof of isolation: epoch-1 key bytes cannot decrypt epoch-2
    # traffic, even with the right AAD.
    vb, alice, bob = pair
    vb.seal_message("c", alice["device_id"], bob["device_id"], b"first")
    old_key = vb._epoch_key("c", 1)
    vb.rotate_conversation("c")
    env2 = vb.seal_message("c", alice["device_id"], bob["device_id"], b"second")
    header = {
        k: env2[k]
        for k in (
            "protocol_version", "message_id", "conversation_id", "sender",
            "recipient", "timestamp", "seq", "key_version", "epoch",
        )
    }
    aad = veil.Veil._header_aad(header)
    with pytest.raises(VeilError):
        veil._open_backend(old_key, veil._b64d(env2["blob"]), aad)
    # ...while the live epoch key opens it through the real path.
    assert vb.open_message(env2)["plaintext"] == b"second"


def test_epoch_tampering_fails_aad(pair):
    vb, alice, bob = pair
    env = vb.seal_message("c", alice["device_id"], bob["device_id"], b"x")
    env["epoch"] = env["epoch"] + 1  # attacker transplants across epochs
    with pytest.raises(VeilError):
        vb.open_message(env)


def test_legacy_pre_ratchet_envelope_opens(pair):
    # A pre-upgrade envelope: no epoch field, VB1 blob, master-derived
    # epoch-0 key. The upgrade must not strand old traffic.
    vb, alice, bob = pair
    header = {
        "protocol_version": 1,
        "message_id": "legacy-envelope-1",
        "conversation_id": "conv-1",
        "sender": alice["device_id"],
        "recipient": bob["device_id"],
        "timestamp": "2026-01-01T00:00:00+00:00",
        "seq": 1,
        "key_version": 1,
    }
    aad = veil.Veil._header_aad(header)
    key = vb._conversation_key("conv-1")  # epoch-0 legacy key
    blob = veil._seal(key, b"n" * 16, b"legacy hello", aad)
    token = vb._device_token(alice["device_id"], alice["key_version"])
    att = hmac.new(
        token, veil._DOMAIN_ATTEST + aad + blob, hashlib.sha256
    ).hexdigest()
    env = dict(header)
    env["blob"] = veil._b64e(blob)
    env["attestation"] = att
    opened = vb.open_message(env)
    assert opened["plaintext"] == b"legacy hello"


def test_ratchet_state_is_owner_only_and_sealed(pair, tmp_path):
    vb, alice, bob = pair
    vb.seal_message("c", alice["device_id"], bob["device_id"], b"x")
    vb.rotate_conversation("c")
    p = tmp_path / "vb" / "ratchets.json"
    assert p.exists()
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    raw = p.read_bytes()
    data = json.loads(raw)
    assert set(data["conversations"]["c"]["live"]) == {"1", "2"}
    # Sealed epoch keys only — the live key never appears in cleartext.
    assert vb._epoch_key("c", 2) not in raw


def test_rotate_conversation_rejects_locked(vb):
    vb.lock()
    with pytest.raises(VeilError):
        vb.rotate_conversation("c")


def test_rotate_conversation_rejects_bad_name(vb):
    with pytest.raises(VeilError):
        vb.rotate_conversation("../escape")
