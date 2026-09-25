"""Shared pytest fixtures and helpers for the VYVE backend auth/token tests.

Both servers read configuration from the environment AT IMPORT TIME
(`config = Config()` and `DEMO_USERS` population happen at module level),
so each fixture gets a *fresh* module import with the desired env vars set.
Keys are generated into a tmp dir (VYVE_KEY_DIR) so tests never touch
``~/.vyve`` and never share keys between test cases.
"""

from __future__ import annotations

import base64
import json
import os
import sys

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_CLIENT_SECRET = "test-client-secret-for-pytest"

_MODULE_NAMES = (
    "oauth",
    "oauth.server",
    "messaging",
    "messaging.server",
    "shared",
    "shared.jwt_keys",
)


def _purge_server_modules() -> None:
    for name in list(sys.modules):
        if name in _MODULE_NAMES or name.startswith(
            ("oauth.", "messaging.", "shared.")
        ):
            del sys.modules[name]


def load_server(
    package: str, monkeypatch: pytest.MonkeyPatch, tmp_path, demo_mode: bool
):
    """Import ``<package>.server`` fresh, with a clean env + tmp key dir."""
    if BACKEND_DIR not in sys.path:
        sys.path.insert(0, BACKEND_DIR)
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", TEST_CLIENT_SECRET)
    monkeypatch.setenv("VYVE_KEY_DIR", str(tmp_path / "keys"))
    monkeypatch.setenv("OAUTH_ISSUER", "http://localhost:8080")
    monkeypatch.setenv("OAUTH_CLIENT_ID", "vyve-messenger")
    # P3.3: each test gets a fresh in-memory SQLite DB (StaticPool, see
    # shared/db.py) so the suite runs without Postgres and tests stay
    # isolated from each other and from any dev ./vyve.db file.
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    if demo_mode:
        monkeypatch.setenv("VYVE_DEMO_MODE", "true")
    else:
        monkeypatch.delenv("VYVE_DEMO_MODE", raising=False)
    _purge_server_modules()
    return __import__(f"{package}.server", fromlist=["server"])


@pytest.fixture()
def oauth_mod(monkeypatch, tmp_path):
    """Fresh ``oauth.server`` module with demo mode ON."""
    return load_server("oauth", monkeypatch, tmp_path, demo_mode=True)


@pytest.fixture()
def oauth_mod_no_demo(monkeypatch, tmp_path):
    """Fresh ``oauth.server`` module with demo mode OFF (no demo users)."""
    return load_server("oauth", monkeypatch, tmp_path, demo_mode=False)


@pytest.fixture()
def msg_mod(monkeypatch, tmp_path):
    """Fresh ``messaging.server`` module."""
    return load_server("messaging", monkeypatch, tmp_path, demo_mode=False)


@pytest.fixture()
def oauth_client(oauth_mod):
    from fastapi.testclient import TestClient

    return TestClient(oauth_mod.app)


@pytest.fixture()
def msg_client(msg_mod):
    from fastapi.testclient import TestClient

    return TestClient(msg_mod.app)


# ── Token-minting / tampering helpers (library-agnostic) ──────────


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def tamper_payload(token: str) -> str:
    """Flip a bit of the payload WITHOUT re-signing (invalid signature)."""
    header, payload, signature = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
    claims["scope"] = "admin:v1"
    bad_payload = _b64u(json.dumps(claims).encode())
    return f"{header}.{bad_payload}.{signature}"


def mint_hs256_token(audience: str = "vyve-messenger") -> str:
    """Craft an HS256 token (must be REJECTED — servers are RS256-only)."""
    import time

    header = _b64u(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64u(
        json.dumps(
            {
                "iss": "http://localhost:8080",
                "sub": "someone",
                "aud": audience,
                "exp": int(time.time()) + 3600,
                "iat": int(time.time()),
                "type": "access",
                "scope": "openid",
            }
        ).encode()
    )
    signature = _b64u(b"fake-hs256-signature")
    return f"{header}.{payload}.{signature}"
