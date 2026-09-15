"""Auth/token-path tests for the OAuth2 provider (backend/oauth/server.py).

Covers: RS256 PKCE issuance, JWKS public-only material, redirect_uri
validation, demo-mode gating, fail-closed startup, and token rejection
paths (expired / tampered / wrong-alg / wrong-audience / wrong type).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest

from conftest import BACKEND_DIR, TEST_CLIENT_SECRET, mint_hs256_token, tamper_payload


# ── JWKS / discovery ─────────────────────────────────────────────


def test_jwks_returns_only_public_key_material(oauth_client):
    resp = oauth_client.get("/oauth/jwks")
    assert resp.status_code == 200
    keys = resp.json()["keys"]
    assert len(keys) >= 1
    for k in keys:
        # Public RSA material only — the old code published the HMAC secret
        # as the "k" parameter (P1.3); it must never reappear.
        assert k["kty"] == "RSA"
        assert "n" in k and "e" in k
        assert "k" not in k  # symmetric secret
        assert "d" not in k  # private exponent
        assert "p" not in k and "q" not in k


def test_oidc_discovery(oauth_client):
    resp = oauth_client.get("/.well-known/openid-configuration")
    assert resp.status_code == 200
    doc = resp.json()
    assert doc["issuer"] == "http://localhost:8080"
    assert doc["jwks_uri"].endswith("/oauth/jwks")
    assert doc["code_challenge_methods_supported"] == ["S256"]
    assert doc["id_token_signing_alg_values_supported"] == ["RS256"]


# ── PKCE flow (happy path) ───────────────────────────────────────


def _authorize(
    oauth_mod,
    oauth_client,
    redirect_uri="http://localhost:8081/callback",
    username="chauncey",
    password="changeme",
    **extra,
):
    verifier = oauth_mod.create_code_verifier()
    challenge = oauth_mod.create_code_challenge(verifier)
    params = {
        "response_type": "code",
        "client_id": "vyve-messenger",
        "redirect_uri": redirect_uri,
        "scope": "openid profile",
        "state": "state-123",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "username": username,
        "password": password,
    }
    params.update(extra)
    resp = oauth_client.get("/oauth/authorize", params=params, follow_redirects=False)
    return resp, verifier


def _exchange_code(
    oauth_client, code, verifier, redirect_uri="http://localhost:8081/callback"
):
    return oauth_client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
            "client_id": "vyve-messenger",
            "client_secret": TEST_CLIENT_SECRET,
        },
    )


def test_pkce_flow_issues_rs256_tokens(oauth_mod, oauth_client):
    resp, verifier = _authorize(oauth_mod, oauth_client)
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith("http://localhost:8081/callback?code=")
    code = location.split("code=")[1].split("&")[0]
    assert "state=state-123" in location

    tok = _exchange_code(oauth_client, code, verifier)
    assert tok.status_code == 200
    body = tok.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"] and body["id_token"]

    # Access token is RS256 and decodes against the public key with all
    # required claims (the verifier's own decode path is the contract).
    claims = oauth_mod.decode_jwt(body["access_token"])
    assert claims["type"] == "access"
    assert claims["sub"] == "550e8400-e29b-41d4-a716-446655440000"
    id_claims = oauth_mod.decode_jwt(body["id_token"], required_type="id")
    assert id_claims["preferred_username"] == "chauncey"

    # userinfo works with the issued access token
    me = oauth_client.get(
        "/oauth/userinfo", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["sub"] == "550e8400-e29b-41d4-a716-446655440000"


def test_pkce_wrong_verifier_rejected(oauth_mod, oauth_client):
    resp, _ = _authorize(oauth_mod, oauth_client)
    code = resp.headers["location"].split("code=")[1].split("&")[0]
    tok = _exchange_code(oauth_client, code, "wrong-verifier")
    assert tok.status_code == 400
    assert tok.json()["detail"] == "invalid_code_verifier"


def test_authorization_code_reuse_revokes(oauth_mod, oauth_client):
    resp, verifier = _authorize(oauth_mod, oauth_client)
    code = resp.headers["location"].split("code=")[1].split("&")[0]
    first = _exchange_code(oauth_client, code, verifier)
    assert first.status_code == 200
    # Reusing the same code must be detected and rejected...
    second = _exchange_code(oauth_client, code, verifier)
    assert second.status_code == 400
    assert second.json()["detail"] == "code_already_used"
    # ...and the refresh token issued by the first exchange must be dead.
    rotated = oauth_client.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": first.json()["refresh_token"],
            "client_id": "vyve-messenger",
            "client_secret": TEST_CLIENT_SECRET,
        },
    )
    assert rotated.status_code == 401


def test_refresh_token_rotation(oauth_mod, oauth_client):
    resp, verifier = _authorize(oauth_mod, oauth_client)
    code = resp.headers["location"].split("code=")[1].split("&")[0]
    first = _exchange_code(oauth_client, code, verifier).json()

    second = oauth_client.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": first["refresh_token"],
            "client_id": "vyve-messenger",
            "client_secret": TEST_CLIENT_SECRET,
        },
    )
    assert second.status_code == 200
    body = second.json()
    assert body["refresh_token"] != first["refresh_token"]
    assert body["access_token"] != first["access_token"]

    # The old refresh token is now invalid (rotation, not reuse).
    stale = oauth_client.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": first["refresh_token"],
            "client_id": "vyve-messenger",
            "client_secret": TEST_CLIENT_SECRET,
        },
    )
    assert stale.status_code == 401


# ── redirect_uri validation ──────────────────────────────────────


def test_unregistered_redirect_uri_returns_400(oauth_mod, oauth_client):
    resp, _ = _authorize(
        oauth_mod, oauth_client, redirect_uri="https://evil.example/callback"
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "invalid_request"
    # Must NOT redirect to the attacker-controlled URI.
    assert "location" not in {k.lower() for k in resp.headers}


# ── demo-mode gating ─────────────────────────────────────────────


def test_demo_login_invalid_credentials_401(oauth_mod, oauth_client):
    resp, _ = _authorize(oauth_mod, oauth_client, password="wrong-password")
    assert resp.status_code == 401


def test_demo_mode_off_rejects_demo_login(oauth_mod_no_demo):
    from fastapi.testclient import TestClient

    assert oauth_mod_no_demo.DEMO_USERS == {}
    client = TestClient(oauth_mod_no_demo.app)
    verifier = oauth_mod_no_demo.create_code_verifier()
    challenge = oauth_mod_no_demo.create_code_challenge(verifier)
    resp = client.get(
        "/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": "vyve-messenger",
            "redirect_uri": "http://localhost:8081/callback",
            "scope": "openid profile",
            "state": "s",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "username": "chauncey",
            "password": "changeme",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 401  # no demo users exist with DEMO_MODE off


# ── fail-closed startup ──────────────────────────────────────────


def test_startup_fails_without_client_secret():
    """Importing the server without OAUTH_CLIENT_SECRET must raise."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("OAUTH_CLIENT_SECRET", "VYVE_DEMO_MODE")
    }
    code = "import sys; sys.path.insert(0, %r); import oauth.server" % BACKEND_DIR
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert proc.returncode != 0
    assert "OAUTH_CLIENT_SECRET" in proc.stderr


# ── password helpers (passlib → direct bcrypt migration contract) ─


def test_password_hash_verify_roundtrip(oauth_mod):
    hashed = oauth_mod.hash_password("s3cr3t-pw")
    assert hashed != "s3cr3t-pw"
    assert oauth_mod.verify_password("s3cr3t-pw", hashed) is True
    assert oauth_mod.verify_password("wrong-pw", hashed) is False


# ── token rejection paths ────────────────────────────────────────


def _authz(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_expired_access_token_rejected(oauth_mod, oauth_client, monkeypatch):
    monkeypatch.setattr(oauth_mod.config, "ACCESS_TOKEN_LIFETIME", -10)
    token = oauth_mod.create_jwt_token("u1", ["openid"], "access")
    resp = oauth_client.get("/oauth/userinfo", headers=_authz(token))
    assert resp.status_code == 401


def test_tampered_access_token_rejected(oauth_mod, oauth_client):
    token = oauth_mod.create_jwt_token("u1", ["openid"], "access")
    resp = oauth_client.get("/oauth/userinfo", headers=_authz(tamper_payload(token)))
    assert resp.status_code == 401


def test_hs256_token_rejected(oauth_mod, oauth_client):
    resp = oauth_client.get("/oauth/userinfo", headers=_authz(mint_hs256_token()))
    assert resp.status_code == 401


def test_wrong_audience_token_rejected(oauth_mod, oauth_client, monkeypatch):
    monkeypatch.setattr(oauth_mod.config, "CLIENT_ID", "other-audience")
    token = oauth_mod.create_jwt_token("u1", ["openid"], "access")
    monkeypatch.setattr(oauth_mod.config, "CLIENT_ID", "vyve-messenger")
    resp = oauth_client.get("/oauth/userinfo", headers=_authz(token))
    assert resp.status_code == 401


def test_wrong_token_type_rejected(oauth_mod, oauth_client):
    id_token = oauth_mod.create_jwt_token("u1", ["openid"], "id")
    resp = oauth_client.get("/oauth/userinfo", headers=_authz(id_token))
    assert resp.status_code == 401
    assert "type" in resp.json()["detail"]


def test_missing_auth_header_401(oauth_client):
    assert oauth_client.get("/oauth/userinfo").status_code == 401
    assert oauth_client.get("/me").status_code == 401


# ── device registration (token-scoped) ───────────────────────────


def test_device_registration_requires_valid_token(oauth_mod, oauth_client):
    token = oauth_mod.create_jwt_token(
        "550e8400-e29b-41d4-a716-446655440000", ["openid"], "access"
    )
    body = {
        "device_id": "d1",
        "device_name": "phone",
        "device_type": "android",
        "signing_key": "sig",
        "encryption_key": "enc",
    }
    ok = oauth_client.post("/me/devices", json=body, headers=_authz(token))
    assert ok.status_code == 201
    lst = oauth_client.get("/me/devices", headers=_authz(token))
    assert lst.json()["devices"][0]["device_id"] == "d1"
    # tampered token cannot register
    bad = oauth_client.post(
        "/me/devices", json=body, headers=_authz(tamper_payload(token))
    )
    assert bad.status_code == 401
