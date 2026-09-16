"""Hermetic tests for the Cybrus identity/vault/token core.

No network, no daemons, no user HOME writes: ``LEVI_HOME`` is monkeypatched
to ``tmp_path`` for every test, so all state lives in the pytest temp dir.
"""

from __future__ import annotations

import base64
import json
import stat

import pytest

import levi.cybrus.factory as factory_mod
import levi.cybrus.vault as vault_mod
from levi.cybrus import (
    AccountFactory,
    CredentialVault,
    IdentityStore,
    TierError,
    TokenEngine,
    TokenError,
    VaultError,
    cybrus_dir,
)


@pytest.fixture(autouse=True)
def _levi_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    yield tmp_path


# -- paths / permissions ---------------------------------------------------


def test_cybrus_dir_is_owner_only(tmp_path):
    d = cybrus_dir()
    assert d == tmp_path / ".levi" / "cybrus"
    assert stat.S_IMODE(d.stat().st_mode) == 0o700


def test_stores_written_owner_only():
    IdentityStore().create("alice")
    for name in ("identities.json",):
        p = cybrus_dir() / name
        assert stat.S_IMODE(p.stat().st_mode) == 0o600
    CredentialVault("pw").store("svc", "user", "secret")
    p = cybrus_dir() / "vault" / "entries.enc"
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    TokenEngine().issue(["read"])
    p = cybrus_dir() / "tokens.json"
    assert stat.S_IMODE(p.stat().st_mode) == 0o600


# -- vault -----------------------------------------------------------------


def test_vault_round_trip_fernet():
    v = CredentialVault("correct-horse-battery")
    assert v.backend == "fernet"  # cryptography is installed in this repo
    v.store("github", "alice", "s3cr3t-value")
    assert v.get("github", "alice") == "s3cr3t-value"
    assert v.list_services() == ["github"]
    # re-open from disk with the same passphrase
    v2 = CredentialVault("correct-horse-battery")
    assert v2.get("github", "alice") == "s3cr3t-value"


def test_vault_round_trip_stdlib_fallback(monkeypatch):
    monkeypatch.setattr(vault_mod, "_try_fernet", lambda: (None, None))
    v = CredentialVault("fallback-pass")
    assert v.backend == "stdlib-fallback"
    v.store("svc", "u", "top-secret")
    assert v.get("svc", "u") == "top-secret"
    # blob written by the fallback opens under the fallback too
    v2 = CredentialVault("fallback-pass")
    assert v2.backend == "stdlib-fallback"
    assert v2.get("svc", "u") == "top-secret"


def test_vault_wrong_password_fails_closed():
    CredentialVault("right-pass").store("svc", "u", "data")
    wrong = CredentialVault("wrong-pass")
    with pytest.raises(VaultError):
        wrong.get("svc", "u")
    with pytest.raises(VaultError):
        wrong.list_services()


def test_vault_tamper_detected():
    v = CredentialVault("tamper-pass")
    v.store("svc", "u", "data")
    p = cybrus_dir() / "vault" / "entries.enc"
    raw = bytearray(p.read_bytes())
    raw[len(raw) // 2] ^= 0xFF  # flip a bit mid-blob
    p.write_bytes(bytes(raw))
    v2 = CredentialVault("tamper-pass")
    with pytest.raises(VaultError):
        v2.get("svc", "u")


def test_vault_tamper_detected_stdlib(monkeypatch):
    monkeypatch.setattr(vault_mod, "_try_fernet", lambda: (None, None))
    CredentialVault("p1").store("svc", "u", "data")
    p = cybrus_dir() / "vault" / "entries.enc"
    blob = json.loads(p.read_text())
    ct = bytearray(base64.b64decode(blob["ciphertext"]))
    ct[0] ^= 0x01
    blob["ciphertext"] = base64.b64encode(bytes(ct)).decode("ascii")
    p.write_text(json.dumps(blob))
    with pytest.raises(VaultError):
        CredentialVault("p1").get("svc", "u")


def test_vault_change_master_password():
    v = CredentialVault("old-pass")
    v.store("svc", "u", "data")
    v.change_master_password("new-pass")
    assert v.get("svc", "u") == "data"
    # old passphrase no longer opens the vault
    with pytest.raises(VaultError):
        CredentialVault("old-pass").get("svc", "u")
    # new passphrase works on a fresh instance
    assert CredentialVault("new-pass").get("svc", "u") == "data"


def test_vault_delete_and_missing():
    v = CredentialVault("pw")
    v.store("a", "u1", "s1")
    v.store("a", "u2", "s2")
    v.delete("a", "u1")
    with pytest.raises(KeyError):
        v.get("a", "u1")
    assert v.get("a", "u2") == "s2"
    v.delete("a", "u2")
    assert v.list_services() == []
    with pytest.raises(KeyError):
        v.delete("a", "u2")


def test_vault_rejects_bad_names():
    v = CredentialVault("pw")
    with pytest.raises(VaultError):
        v.store("../evil", "u", "s")
    with pytest.raises(VaultError):
        v.store("svc", "", "s")


def test_stdlib_cipher_direct_wrong_key():
    c1 = vault_mod._StdlibCipher(b"\x01" * 32)
    blob = c1.encrypt(b"\x02" * 16, b"hello world")
    c2 = vault_mod._StdlibCipher(b"\x03" * 32)
    with pytest.raises(VaultError):
        c2.decrypt(b"\x02" * 16, blob)
    # right key round-trips
    assert c1.decrypt(b"\x02" * 16, blob) == b"hello world"


# -- identity store ----------------------------------------------------------


def test_identity_crud():
    store = IdentityStore()
    rec = store.create("alice", tier="pro")
    assert rec["name"] == "alice" and rec["tier"] == "pro"
    assert rec["status"] == "active" and rec["created_at"]
    # lookup by id and by name
    assert store.get(rec["id"])["name"] == "alice"
    assert store.get("alice")["id"] == rec["id"]
    assert store.get("nobody") is None
    # update
    store.update("alice", status="suspended")
    assert store.get("alice")["status"] == "suspended"
    store.reactivate("alice")
    assert store.get("alice")["status"] == "active"
    store.update("alice", name="alice2")
    assert store.get("alice2") is not None and store.get("alice") is None
    # list
    store.create("bob")
    names = {r["name"] for r in store.list()}
    assert names == {"alice2", "bob"}
    # delete
    store.delete("bob")
    assert store.get("bob") is None
    with pytest.raises(KeyError):
        store.delete("bob")


def test_identity_duplicate_name_rejected():
    store = IdentityStore()
    store.create("alice")
    with pytest.raises(ValueError):
        store.create("alice")
    with pytest.raises(ValueError):
        store.update("alice", nickname="x")  # unknown field
    with pytest.raises(ValueError):
        store.create("bad name!")


def test_tier_limits_enforced():
    store = IdentityStore()
    for i in range(5):
        store.create(f"starter-{i}", tier="starter")
    with pytest.raises(TierError):
        store.create("starter-5", tier="starter")
    # founder is unlimited
    for i in range(8):
        store.create(f"founder-{i}", tier="founder")
    # pro has its own quota
    for i in range(50):
        store.create(f"pro-{i}", tier="pro")
    with pytest.raises(TierError):
        store.create("pro-50", tier="pro")
    # unknown tier rejected
    with pytest.raises(TierError):
        store.create("x", tier="enterprise")
    # moving into a full tier is rejected too
    with pytest.raises(TierError):
        store.update("founder-0", tier="starter")


# -- account factory ---------------------------------------------------------


def _meets_policy(pw: str) -> bool:
    return (
        len(pw) >= 16
        and any(c.islower() for c in pw)
        and any(c.isupper() for c in pw)
        and any(c.isdigit() for c in pw)
        and any(not c.isalnum() for c in pw)
    )


def test_factory_uniqueness_200(monkeypatch):
    # 600k-iteration PBKDF2 x200 would be slow; uniqueness/policy do not need
    # the full work factor — the real iteration count is covered by the
    # round-trip test below.
    monkeypatch.setattr(factory_mod, "_PBKDF2_ITERATIONS", 1_000)
    fac = AccountFactory(IdentityStore())
    seen_users, seen_pw = set(), set()
    for _ in range(200):
        rec, password = fac.generate("svc-account", tier="founder")
        assert rec["name"] not in seen_users
        seen_users.add(rec["name"])
        assert password not in seen_pw  # 160-bit passwords: no collisions
        seen_pw.add(password)
        assert _meets_policy(password), password
    assert len(seen_users) == 200
    # collision handling produced suffixed names
    assert any("-" in u for u in seen_users)


def test_factory_password_never_persisted_plaintext():
    fac = AccountFactory(IdentityStore())
    rec, password = fac.generate("db-admin", tier="founder")
    raw = (cybrus_dir() / "identities.json").read_text()
    assert password not in raw
    cred = fac.store.get_credential("db-admin")
    assert cred["scheme"] == "pbkdf2-sha256"
    assert cred["iterations"] >= 600_000
    assert fac.verify("db-admin", password) is True
    assert fac.verify("db-admin", password + "x") is False
    assert fac.verify("nobody", password) is False
    # listings redact credential material
    listed = {r["name"]: r for r in fac.store.list()}
    assert listed["db-admin"]["credential"] is True  # presence flag only


def test_factory_generate_password_policy_floor():
    with pytest.raises(ValueError):
        factory_mod.generate_password(8)
    for _ in range(25):
        assert _meets_policy(factory_mod.generate_password())


# -- tokens ------------------------------------------------------------------


def test_token_lifecycle():
    eng = TokenEngine()
    tid, token = eng.issue(["read", "write"], label="ci")
    payload = eng.validate(token)
    assert payload is not None
    assert payload["id"] == tid
    assert payload["scopes"] == ["read", "write"]
    assert payload["label"] == "ci"
    # garbage token -> None
    assert eng.validate("not-a-real-token") is None
    assert eng.validate("") is None
    # rotation: old dies, new works, plaintext returned once
    new_id, new_token = eng.rotate(tid)
    assert new_id != tid and new_token != token
    assert eng.validate(token) is None
    assert eng.validate(new_token)["id"] == new_id
    # revocation
    eng.revoke(new_id)
    assert eng.validate(new_token) is None
    # unknown ids fail closed
    with pytest.raises(TokenError):
        eng.revoke("deadbeef")
    with pytest.raises(TokenError):
        eng.rotate("deadbeef")


def test_token_expired_rejected():
    eng = TokenEngine()
    tid, token = eng.issue(["read"], ttl_seconds=3600)
    assert eng.validate(token) is not None
    eng._records[0]["expires_at"] = 1  # force expiry in the past
    eng._save()
    eng2 = TokenEngine()  # reloaded from disk
    assert eng2.validate(token) is None
    assert eng2.purge_expired() == 1
    assert eng2.list() == []


def test_token_validation_rules():
    eng = TokenEngine()
    with pytest.raises(TokenError):
        eng.issue([])
    with pytest.raises(TokenError):
        eng.issue(["read"], ttl_seconds=0)
    with pytest.raises(TokenError):
        eng.issue(["read"], ttl_seconds=-5)


def test_token_plaintext_never_persisted():
    eng = TokenEngine()
    _, token = eng.issue(["read"])
    raw = (cybrus_dir() / "tokens.json").read_text()
    assert token not in raw
    assert "token_hash" in raw
    # metadata listing exposes no hashes or plaintext
    meta = eng.list()[0]
    assert "token_hash" not in meta and set(meta) <= {
        "id", "label", "kind", "memo", "basis", "paper",
        "scopes", "issued_at", "expires_at", "revoked", "expired",
    }


def test_tokens_persist_across_instances():
    eng = TokenEngine()
    tid, token = eng.issue(["admin"], ttl_seconds=7200)
    eng2 = TokenEngine()
    assert eng2.validate(token)["id"] == tid


# -- package surface ---------------------------------------------------------


def test_package_exports():
    import levi.cybrus as cy

    for name in ("AccountFactory", "CredentialVault", "IdentityStore",
                 "TierError", "TokenEngine", "TokenError", "VaultError",
                 "cybrus_dir"):
        assert name in cy.__all__
        assert hasattr(cy, name)


def test_levi_home_override_respected(tmp_path, monkeypatch):
    other = tmp_path / "elsewhere"
    monkeypatch.setenv("LEVI_HOME", str(other))
    IdentityStore().create("zed")
    assert (other / ".levi" / "cybrus" / "identities.json").exists()
    assert not (tmp_path / ".levi" / "cybrus" / "identities.json").exists()
