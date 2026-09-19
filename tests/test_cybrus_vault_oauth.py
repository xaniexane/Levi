"""Hermetic tests for the Cybrus OAuth vault layer and the platform router.

``LEVI_HOME`` is monkeypatched to ``tmp_path`` for every test — no network,
no daemons, no user HOME writes.
"""

from __future__ import annotations

import json
import time

import pytest

from levi.cybrus import (
    AutoLockVault,
    IdentityStore,
    IdentityVault,
    OAuthError,
    OAuthVault,
    RouteError,
    RouteRefused,
    RouteRegistry,
    VaultError,
    VaultLockedError,
    generate_password,
)
from levi.cybrus.audit import AuditEngine


@pytest.fixture(autouse=True)
def _levi_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    yield tmp_path


def _audit_events():
    ok, _ = AuditEngine().verify()
    assert ok, "audit chain must verify"
    return [
        (rec["event"], rec["actor"], json.dumps(rec.get("details", {})))
        for rec in AuditEngine().tail(200)
    ]


# -- password generation -----------------------------------------------------


def test_generate_password_strength_and_uniqueness():
    pw = generate_password()
    assert len(pw) == 24
    assert any(c.islower() for c in pw)
    assert any(c.isupper() for c in pw)
    assert any(c.isdigit() for c in pw)
    assert any(not c.isalnum() for c in pw)
    # unambiguous alphabet: no l, I, O, 0, 1
    assert not set(pw) & set("lIO01")
    assert generate_password() != generate_password()
    assert len(generate_password(48)) == 48


def test_generate_password_rejects_short():
    with pytest.raises(VaultError):
        generate_password(8)
    with pytest.raises(VaultError):
        generate_password("24")  # type: ignore[arg-type]


# -- OAuth vault round-trip --------------------------------------------------


def test_oauth_store_get_round_trip():
    ov = OAuthVault("master-pw")
    meta = ov.store_token(
        "github",
        "alice",
        "access-123",
        refresh_token="refresh-456",
        scopes=["repo", "read:user"],
        expires_in=3600,
    )
    assert meta["provider"] == "github"
    assert meta["refresh_count"] == 0
    assert "access_token" not in meta  # metadata only

    record = ov.get_token("github", "alice", requester="alice")
    assert record["access_token"] == "access-123"
    assert record["refresh_token"] == "refresh-456"
    assert record["scopes"] == ["repo", "read:user"]
    assert record["identity"] == "alice"
    assert not OAuthVault.is_expired(record)


def test_oauth_expiry_detection():
    ov = OAuthVault("master-pw")
    ov.store_token("svc", "alice", "tok", expires_in=3600)
    record = ov.get_token("svc", "alice", requester="alice")
    assert not OAuthVault.is_expired(record)
    record["expires_at"] = time.time() - 10
    assert OAuthVault.is_expired(record)
    # records without expiry never expire
    ov.store_token("svc2", "alice", "tok2")
    record2 = ov.get_token("svc2", "alice", requester="alice")
    assert not OAuthVault.is_expired(record2)


def test_oauth_refresh_tracks_metadata():
    ov = OAuthVault("master-pw")
    ov.store_token("github", "alice", "old-access", refresh_token="old-refresh",
                   scopes=["repo"], expires_in=3600)
    meta = ov.record_refresh(
        "github", "alice", requester="alice",
        new_access_token="new-access", expires_in=7200,
    )
    assert meta["refresh_count"] == 1
    record = ov.get_token("github", "alice", requester="alice")
    assert record["access_token"] == "new-access"
    assert record["refresh_token"] == "old-refresh"  # kept when not replaced
    assert record["last_refreshed_at"] is not None
    assert record["refresh_count"] == 1
    meta2 = ov.record_refresh(
        "github", "alice", requester="alice",
        new_access_token="newer", new_refresh_token="newer-refresh",
    )
    assert meta2["refresh_count"] == 2
    record2 = ov.get_token("github", "alice", requester="alice")
    assert record2["refresh_token"] == "newer-refresh"


def test_oauth_containment_no_cross_identity_read():
    ov = OAuthVault("master-pw")
    ov.store_token("github", "alice", "alice-token")
    with pytest.raises(OAuthError):
        ov.get_token("github", "alice", requester="bob")
    with pytest.raises(OAuthError):
        ov.record_refresh("github", "alice", requester="bob",
                          new_access_token="x")
    with pytest.raises(OAuthError):
        ov.revoke("github", "alice", requester="bob")
    # unknown token fails closed
    with pytest.raises(OAuthError):
        ov.get_token("nope", "alice", requester="alice")


def test_oauth_revoke_and_list_metadata_only():
    ov = OAuthVault("master-pw")
    ov.store_token("github", "alice", "tok", scopes=["repo"], expires_in=60)
    ov.store_token("gitlab", "alice", "tok2")
    listed = ov.list_tokens(identity="alice")
    assert {(t["provider"], t["identity"]) for t in listed} == {
        ("github", "alice"), ("gitlab", "alice")
    }
    # metadata only — no token values anywhere in the listing
    blob = json.dumps(listed)
    assert "tok" not in blob
    ov.revoke("github", "alice", requester="alice")
    assert [t["provider"] for t in ov.list_tokens(identity="alice")] == ["gitlab"]
    with pytest.raises(OAuthError):
        ov.revoke("github", "alice", requester="alice")  # already gone


def test_oauth_validation():
    ov = OAuthVault("master-pw")
    with pytest.raises(OAuthError):
        ov.store_token("github", "alice", "")  # empty access token
    with pytest.raises(OAuthError):
        ov.store_token("github", "alice", "tok", expires_in=-5)
    with pytest.raises(OAuthError):
        ov.store_token("github", "alice", "tok", scopes=["ok", ""])  # empty scope
    with pytest.raises(OAuthError):
        ov.store_token("bad provider!", "alice", "tok")


def test_oauth_audit_never_logs_token_values():
    ov = OAuthVault("master-pw")
    ov.store_token("github", "alice", "SECRET-ACCESS-XYZ", refresh_token="SECRET-REFRESH-XYZ",
                   scopes=["repo"])
    ov.get_token("github", "alice", requester="alice")
    ov.record_refresh("github", "alice", requester="alice", new_access_token="NEW-SECRET")
    events = _audit_events()
    kinds = {e for e, _, _ in events}
    assert "oauth.stored" in kinds
    assert "oauth.accessed" in kinds
    assert "oauth.refreshed" in kinds
    for event, actor, details in events:
        assert "SECRET-ACCESS-XYZ" not in details
        assert "SECRET-REFRESH-XYZ" not in details
        assert "NEW-SECRET" not in details


# -- identity scoping + founder containment ----------------------------------


def test_identity_vault_scoping_by_construction():
    alice = IdentityVault("master-pw", "alice")
    bob = IdentityVault("master-pw", "bob")
    alice.store("gmail", "alice.user", "s3cret")
    assert alice.get("gmail", "alice.user") == "s3cret"
    assert alice.list_services() == ["gmail"]
    # bob's namespace is disjoint — nothing of alice's is addressable
    assert bob.list_services() == []
    with pytest.raises(KeyError):
        bob.get("gmail", "alice.user")


def test_founder_containment_flagged_and_no_share_path():
    store = IdentityStore()
    store.create("chauncey", tier="founder")
    store.create("guest", tier="starter")
    founder_vault = IdentityVault("master-pw", "chauncey")
    founder_vault.store("platform", "root", "founder-secret")
    # another identity cannot reach it — containment by namespace
    guest_vault = IdentityVault("master-pw", "guest")
    with pytest.raises(KeyError):
        guest_vault.get("platform", "root")
    # metadata flags the founder ownership
    from levi.cybrus._paths import load_json_store, store_path

    meta = load_json_store(store_path("vault_identity_meta"))
    assert meta["cybrus.id.chauncey"]["founder_owned"] is True
    assert meta["cybrus.id.guest"]["founder_owned"] is False
    # and the vault exposes no share/copy/export path at all
    for obj in (founder_vault, OAuthVault("master-pw")):
        for attr in ("share", "export", "copy_to", "move_to", "grant_access"):
            assert not hasattr(obj, attr), attr


def test_identity_vault_audit_metadata_only():
    v = IdentityVault("master-pw", "alice")
    v.store("svc", "user", "TOP-SECRET-VALUE")
    v.get("svc", "user")
    for event, actor, details in _audit_events():
        if event.startswith("vault."):
            assert "TOP-SECRET-VALUE" not in details
            assert actor == "alice"


# -- auto-lock ---------------------------------------------------------------


def test_auto_lock_after_inactivity():
    av = AutoLockVault(idle_seconds=0.05).unlock("master-pw")
    assert not av.is_locked
    av.store("svc", "user", "secret")
    assert av.get("svc", "user") == "secret"
    time.sleep(0.08)
    assert av.is_locked
    with pytest.raises(VaultLockedError):
        av.get("svc", "user")
    # re-unlock with the passphrase restores access
    av.unlock("master-pw")
    assert not av.is_locked
    assert av.get("svc", "user") == "secret"


def test_auto_lock_explicit_lock_and_wrong_passphrase():
    av = AutoLockVault(idle_seconds=900).unlock("master-pw")
    av.store("svc", "user", "secret")
    av.lock()
    assert av.is_locked
    with pytest.raises(VaultLockedError):
        av.list_services()
    with pytest.raises(VaultError):
        AutoLockVault(idle_seconds=900).unlock("wrong-pw").get("svc", "user")


def test_auto_lock_rejects_bad_idle():
    with pytest.raises(VaultError):
        AutoLockVault(idle_seconds=0)
    with pytest.raises(VaultError):
        AutoLockVault(idle_seconds=-3)


# -- router ------------------------------------------------------------------


def test_router_internal_preferred():
    reg = RouteRegistry()
    hit = reg.resolve("levi.jobs")
    assert hit["kind"] == "internal"
    assert hit["crosses_boundary"] is False
    # dotted sub-targets resolve to the internal parent
    hit2 = reg.resolve("levi.cybrus.vault")
    assert hit2["kind"] == "internal" and hit2["route"] == "levi.cybrus"


def test_router_refuses_unregistered_external():
    reg = RouteRegistry()
    with pytest.raises(RouteRefused) as excinfo:
        reg.resolve("github.com")
    assert "add-external" in str(excinfo.value)


def test_router_external_special_request_only():
    reg = RouteRegistry()
    record = reg.add_external(
        "github", scope="repo.read", approved_by="chauncey",
        reason="mirror public skill catalog",
    )
    assert record["crosses_boundary"] is True
    assert record["approved_by"] == "chauncey"
    hit = reg.resolve("github.com")
    assert hit["kind"] == "external"
    assert hit["crosses_boundary"] is True
    assert hit["scope"] == "repo.read"
    # internal still wins over external on name collision
    reg.register_internal("github", "internal mirror service")
    hit2 = reg.resolve("github")
    assert hit2["kind"] == "internal"


def test_router_duplicate_and_remove():
    reg = RouteRegistry()
    reg.add_external("acme", scope="data", approved_by="chauncey", reason="ingest")
    with pytest.raises(RouteError):
        reg.add_external("acme", scope="data", approved_by="chauncey", reason="again")
    reg.remove_external("acme", by="chauncey")
    with pytest.raises(RouteRefused):
        reg.resolve("acme")
    # removal is recorded, not erased
    removed = reg.external_routes(include_removed=True)
    assert any(r["provider"] == "acme" and r["status"] == "removed" for r in removed)
    assert reg.external_routes() == []


def test_router_list_marks_external():
    reg = RouteRegistry()
    reg.add_external("acme", scope="data", approved_by="chauncey", reason="ingest")
    table = reg.list_routes()
    assert any(r["name"] == "levi.cybrus" for r in table["internal"])
    assert len(table["external"]) == 1
    ext = table["external"][0]
    assert ext["crosses_boundary"] is True
    assert ext["approved_by"] == "chauncey"
    assert "reason" in ext and "added_at" in ext


def test_router_crossing_is_audit_logged():
    reg = RouteRegistry()
    reg.add_external("acme", scope="data", approved_by="chauncey", reason="ingest")
    reg.resolve("acme")
    events = _audit_events()
    assert any(e == "route.external.added" for e, _, _ in events)
    assert any(e == "route.crossing" for e, _, _ in events)


def test_router_rejects_bad_names():
    reg = RouteRegistry()
    with pytest.raises(RouteError):
        reg.add_external("", scope="x", approved_by="y", reason="z")
    with pytest.raises(RouteError):
        reg.add_external("evil provider!", scope="x", approved_by="y", reason="z")
    with pytest.raises(RouteError):
        reg.resolve("")
