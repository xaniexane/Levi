"""Hermetic tests for the Cybrus OAuth login state machine (oauth.py).

Laws under test:
1. Tokens never valid without keeper identity binding.
2. Forged/tampered tokens fail closed.
3. Full capability is founder-only; others limited.
4. One in-flight OAuth flow per identity.
5. Initiation rate-limited tighter than refresh.
6. No network (by construction — module imports no socket/http).
7. Audit records metadata only, never token values.

``LEVI_HOME`` is monkeypatched to ``tmp_path`` — no user HOME writes.
"""

from __future__ import annotations

import json

import pytest

from levi.cybrus import rate_limits
from levi.cybrus.audit import AuditEngine
from levi.cybrus.oauth import (
    LIMITED_DEFAULT_SCOPES,
    OAuthDenied,
    OAuthLogin,
)


@pytest.fixture(autouse=True)
def _levi_home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    yield tmp_path


@pytest.fixture()
def login():
    return OAuthLogin()


def _begin(login, identity="alice", scopes=("login",)):
    rate_limits.set_tier(identity, "starter")
    return login.begin(identity, list(scopes))


def _audit_text():
    return json.dumps(
        [(rec["event"], rec["actor"], rec.get("details", {})) for rec in AuditEngine().tail(200)]
    )


# -- LAW 1: identity binding --------------------------------------------------


def test_complete_binds_token_to_identity(login):
    pkt = _begin(login)
    token_id, token = login.complete(pkt["flow_id"], pkt["code_verifier"])
    payload = login.validate(token)
    assert payload is not None
    assert payload["token_id"] == token_id
    assert payload["identity"] == "alice"
    assert payload["scopes"] == ["login"]


def test_unknown_token_is_invalid(login):
    assert login.validate("v1.bogus.bogus") is None
    assert login.validate("") is None
    assert login.validate(None) is None


# -- LAW 2: tamper fails closed ----------------------------------------------


def test_tampered_token_fails_closed(login):
    pkt = _begin(login)
    _, token = login.complete(pkt["flow_id"], pkt["code_verifier"])
    version, body, sig = token.split(".")
    # Flip the last character of the sealed body: seal must break.
    tampered_body = body[:-1] + ("A" if body[-1] != "A" else "B")
    assert login.validate(f"{version}.{tampered_body}.{sig}") is None
    # Wrong signature also fails.
    assert login.validate(f"{version}.{body}.{'A' * len(sig)}") is None


def test_wrong_pkce_verifier_denied(login):
    pkt = _begin(login)
    with pytest.raises(OAuthDenied):
        login.complete(pkt["flow_id"], "wrong-verifier")
    login.abandon(pkt["flow_id"], "alice")


def test_flow_replay_refused(login):
    pkt = _begin(login)
    login.complete(pkt["flow_id"], pkt["code_verifier"])
    with pytest.raises(OAuthDenied):
        login.complete(pkt["flow_id"], pkt["code_verifier"])


# -- LAW 3: founder-only full capability --------------------------------------


def test_non_founder_denied_founder_scopes(login):
    with pytest.raises(OAuthDenied):
        _begin(login, identity="mallory", scopes=("login", "broker:create"))
    with pytest.raises(OAuthDenied):
        _begin(login, identity="mallory", scopes=("vault:seal",))
    with pytest.raises(OAuthDenied):
        _begin(login, identity="mallory", scopes=("admin:quotas",))


def test_non_founder_limited_scopes_allowed(login):
    pkt = _begin(login, identity="bob", scopes=list(LIMITED_DEFAULT_SCOPES))
    _, token = login.complete(pkt["flow_id"], pkt["code_verifier"])
    payload = login.validate(token)
    assert payload["identity"] == "bob"
    assert payload["founder"] is False


def test_founder_mints_full_scopes(login):
    pkt = _begin(
        login, identity="chauncey", scopes=("login", "broker:create", "vault:seal")
    )
    _, token = login.complete(pkt["flow_id"], pkt["code_verifier"])
    payload = login.validate(token)
    assert payload["identity"] == "chauncey"
    assert payload["founder"] is True
    assert "broker:create" in payload["scopes"]


# -- LAW 4: one in-flight flow per identity -----------------------------------


def test_second_begin_while_inflight_denied(login):
    pkt = _begin(login)
    with pytest.raises(OAuthDenied):
        login.begin("alice", ["login"])
    login.abandon(pkt["flow_id"], "alice")


def test_abandon_releases_reservation(login):
    pkt = _begin(login)
    login.abandon(pkt["flow_id"], "alice")
    pkt2 = _begin(login)  # must succeed after abandon
    login.abandon(pkt2["flow_id"], "alice")


def test_complete_releases_reservation(login):
    pkt = _begin(login)
    login.complete(pkt["flow_id"], pkt["code_verifier"])
    pkt2 = _begin(login)  # must succeed after complete
    login.abandon(pkt2["flow_id"], "alice")


# -- LAW 5: initiation tighter than refresh -----------------------------------


def test_initiation_quota_tighter_than_refresh(login):
    identity = "carol"
    rate_limits.set_tier(identity, "starter")  # 5/hr initiate, 50/hr refresh
    for _ in range(5):
        pkt = login.begin(identity, ["login"])
        _, token = login.complete(pkt["flow_id"], pkt["code_verifier"])
    # 6th initiation inside the hour is denied ...
    with pytest.raises(Exception):
        login.begin(identity, ["login"])
    # ... while refresh quota (50/hr) still allows a refresh.
    _, new_token = login.refresh(token)
    assert login.validate(new_token)["identity"] == identity


# -- refresh / revoke ---------------------------------------------------------


def test_refresh_revokes_old_token(login):
    pkt = _begin(login)
    old_id, old_token = login.complete(pkt["flow_id"], pkt["code_verifier"])
    new_id, new_token = login.refresh(old_token)
    assert new_id != old_id
    assert login.validate(old_token) is None  # old dies immediately
    assert login.validate(new_token)["identity"] == "alice"


def test_refresh_invalid_token_denied(login):
    with pytest.raises(OAuthDenied):
        login.refresh("v1.bogus.bogus")


def test_revoke_kills_token(login):
    pkt = _begin(login)
    token_id, token = login.complete(pkt["flow_id"], pkt["code_verifier"])
    assert login.validate(token) is not None
    login.revoke(token_id, "alice")
    assert login.validate(token) is None


def test_expired_flow_denied(login, monkeypatch):
    import levi.cybrus.oauth as oauth_mod

    pkt = _begin(login)
    real_now = oauth_mod._now
    monkeypatch.setattr(oauth_mod, "_now", lambda: real_now() + 20 * 60)
    with pytest.raises(OAuthDenied):
        login.complete(pkt["flow_id"], pkt["code_verifier"])


# -- LAW 7: audit metadata only -----------------------------------------------


def test_audit_never_records_token_values(login):
    pkt = _begin(login)
    _, token = login.complete(pkt["flow_id"], pkt["code_verifier"])
    text = _audit_text()
    assert token not in text
    assert pkt["code_verifier"] not in text
    # But the metadata events are present.
    events = [rec["event"] for rec in AuditEngine().tail(200)]
    assert "oauth.flow_begun" in events
    assert "oauth.token_issued" in events
