"""Cybrus OAuth login — authorization-code + PKCE state machine (LEVI-original).

Chauncey's design, from his own docs (binding):
- ``docs/CYBRUS_STANDALONE_PRODUCTION.md``: "OAuth2 authorization-code +
  PKCE flows through platform OAuth layers"; "Per-action per-hour and
  per-day sliding windows (OAuth initiation tighter per hour than OAuth
  refresh)"; "One in-flight OAuth flow per user at a time; the reservation
  releases on completion, abandonment, or initialization failure";
  "Chauncey (founder) is quota-exempt; every attempt still logged";
  "The OAuth engine runs the protocol state machine; the human operator
  completes external logins."
- ``docs/CYBRUS_VAULT.md``: "The OAuth vault records token metadata; it
  performs **no network calls**." Founder containment: founder-owned
  entries have no share/copy/export path.

This module is the login half: Cybrus itself acts as the authorization
server for keeper login. Third-party provider token storage is the
sibling lane (``vault.OAuthVault``) and brokered account creation is the
🔐 broker lane — this module never duplicates them.

LAWS (invariants — declared before implementation):
1. A token is never valid without keeper identity binding. Every issued
   token carries its owning identity; ``validate`` returns it.
2. Forged or tampered tokens fail closed. Tokens are HMAC-sealed with a
   keeper-held key; any mutation breaks the seal and validates to None.
3. Full capability is founder-only. Non-founder identities cannot mint
   tokens carrying founder-only scopes (``broker:*``, ``vault:seal``,
   ``admin:*``) — the request is refused loud. Limited scopes are
   available to everyone. (Chauncey's ruling: other users don't get the
   full broker, or it is limited.)
4. One in-flight OAuth flow per identity. A second ``begin`` while one is
   open raises; the reservation releases on complete/abandon/failure.
5. Initiation is rate-limited tighter than refresh (his mechanical rule).
6. No network, ever. The state machine runs locally; the human operator
   completes external logins.
7. Audit records metadata only — identity, scopes, timestamps. Token
   values and verifiers are never written to the audit log.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from typing import Optional

from levi.cybrus import rate_limits
from levi.cybrus._paths import (
    load_json_store,
    save_json_store,
    store_lock,
    store_path,
)
from levi.cybrus.audit import AuditEngine
from levi.cybrus.identity import is_founder_identity

__all__ = [
    "OAuthError",
    "OAuthDenied",
    "OAuthLogin",
    "FOUNDER_ONLY_SCOPE_PREFIXES",
    "LIMITED_DEFAULT_SCOPES",
]

_STORE_NAME = "oauth_flows"
_KEY_STORE_NAME = "oauth_hmac_key"

#: Scopes that require the founder tier. Anything else is limited-tier-able.
FOUNDER_ONLY_SCOPE_PREFIXES = ("broker:", "vault:seal", "admin:")

#: Scopes any identity may hold.
LIMITED_DEFAULT_SCOPES = ("login", "vault:read", "messenger:send")

_TOKEN_TTL_SECONDS = 12 * 3600  # 12 hours
_FLOW_TTL_SECONDS = 10 * 60  # authorization codes live 10 minutes


class OAuthError(Exception):
    """Base error for the OAuth login state machine."""


class OAuthDenied(OAuthError):
    """Raised when the flow is refused: bad gate, bad PKCE, replay, ..."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _now() -> int:
    return int(time.time())


def _check_identity(identity: str) -> str:
    if not isinstance(identity, str) or not identity.strip():
        raise OAuthDenied("identity must be a non-empty string")
    return identity.strip()


def _check_scopes(scopes) -> list[str]:
    if not isinstance(scopes, (list, tuple)) or not scopes:
        raise OAuthDenied("scopes must be a non-empty list of strings")
    clean = []
    for scope in scopes:
        if not isinstance(scope, str) or not scope.strip():
            raise OAuthDenied(f"invalid scope {scope!r}")
        clean.append(scope.strip())
    return clean


def _gate_scopes(identity: str, scopes: list[str]) -> list[str]:
    """Enforce LAW 3: founder-only scopes need the founder identity."""
    if is_founder_identity(identity):
        return scopes
    forbidden = [s for s in scopes if s.startswith(FOUNDER_ONLY_SCOPE_PREFIXES)]
    if forbidden:
        raise OAuthDenied(
            f"scopes {forbidden} require the founder identity; "
            f"{identity!r} is not the founder"
        )
    return scopes


class OAuthLogin:
    """Authorization-code + PKCE login flow for Cybrus keeper identities.

    No network: the flow object is the protocol state machine. The human
    operator completes any external login; here the "provider" is Cybrus
    itself, binding the keeper identity to a sealed, scoped token.
    """

    def __init__(self) -> None:
        self._path = store_path(_STORE_NAME)
        self._audit = AuditEngine()

    # -- sealing key ------------------------------------------------------

    def _key(self) -> bytes:
        """Keeper-held HMAC key, generated once, owner-only on disk."""
        key_path = store_path(_KEY_STORE_NAME)
        if os.path.exists(key_path):
            with open(key_path, "rb") as fh:
                return fh.read()
        key = secrets.token_bytes(32)
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, key)
        finally:
            os.close(fd)
        return key

    # -- flow store --------------------------------------------------------

    def _load(self) -> dict:
        data = load_json_store(self._path)
        return data if isinstance(data, dict) else {"flows": {}, "revoked": []}

    def _save(self, data: dict) -> None:
        save_json_store(self._path, data)

    # -- begin -------------------------------------------------------------

    def begin(
        self,
        identity: str,
        scopes,
        provider: str = "cybrus",
    ) -> dict:
        """Open an authorization flow. Returns the public flow packet::

            {"flow_id", "code_challenge", "code_challenge_method": "S256",
             "state", "expires_at"}

        The ``code_verifier`` is returned alongside in ``"code_verifier"``
        for the local caller (it would travel with the user's agent in a
        real redirect dance; it is never persisted and never audited).
        """
        identity = _check_identity(identity)
        scopes = _gate_scopes(identity, _check_scopes(scopes))
        if not isinstance(provider, str) or not provider.strip():
            raise OAuthDenied("provider must be a non-empty string")

        # LAW 5: initiation rate-limited (tighter than refresh).
        try:
            rate_limits.check(identity, rate_limits.OAUTH_INITIATE)
        except rate_limits.RateLimitDenied as exc:
            raise OAuthDenied(f"OAuth initiation refused: {exc}") from exc
        # LAW 4: one in-flight flow per identity.
        try:
            rate_limits.acquire_flow(identity)
        except Exception as exc:
            raise OAuthDenied(f"an OAuth flow is already in flight: {exc}") from exc

        flow_id = uuid.uuid4().hex
        verifier = _b64url(secrets.token_bytes(32))
        challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
        state = _b64url(secrets.token_bytes(16))
        now = _now()
        record = {
            "flow_id": flow_id,
            "identity": identity,
            "provider": provider.strip(),
            "scopes": scopes,
            "code_challenge": challenge,
            "state": state,
            "created_at": now,
            "expires_at": now + _FLOW_TTL_SECONDS,
            "completed": False,
        }
        with store_lock(self._path):
            data = self._load()
            data["flows"][flow_id] = record
            self._save(data)
        self._audit.append(
            "oauth.flow_begun",
            identity,
            {"provider": provider.strip(), "scopes": scopes, "flow_id": flow_id},
        )
        packet = {
            "flow_id": flow_id,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "expires_at": record["expires_at"],
            "code_verifier": verifier,  # local-caller only; never stored
        }
        return packet

    def abandon(self, flow_id: str, identity: str) -> None:
        """Abandon an in-flight flow, releasing the reservation (LAW 4)."""
        identity = _check_identity(identity)
        with store_lock(self._path):
            data = self._load()
            rec = data["flows"].pop(flow_id, None)
            self._save(data)
        rate_limits.release_flow(identity)
        if rec:
            self._audit.append(
                "oauth.flow_abandoned", identity, {"flow_id": flow_id}
            )

    # -- complete ----------------------------------------------------------

    def _seal(self, payload: dict) -> str:
        body = _b64url(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        sig = _b64url(hmac.new(self._key(), body.encode("ascii"), hashlib.sha256).digest())
        return f"v1.{body}.{sig}"

    def _unseal(self, token: str) -> Optional[dict]:
        """LAW 2: any tamper fails closed -> None."""
        try:
            version, body, sig = token.split(".")
            if version != "v1":
                return None
            expected = _b64url(
                hmac.new(self._key(), body.encode("ascii"), hashlib.sha256).digest()
            )
            if not hmac.compare_digest(sig, expected):
                return None
            return json.loads(_b64url_decode(body).decode("utf-8"))
        except (ValueError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
            return None

    def complete(self, flow_id: str, code_verifier: str) -> tuple[str, str]:
        """Exchange a valid PKCE verifier for a sealed access token.

        Returns ``(token_id, plaintext_token)`` — the plaintext is
        returned exactly once and never logged or audited (LAW 7).
        """
        if not isinstance(flow_id, str) or not flow_id:
            raise OAuthDenied("flow_id required")
        if not isinstance(code_verifier, str) or not code_verifier:
            raise OAuthDenied("code_verifier required")

        with store_lock(self._path):
            data = self._load()
            rec = data["flows"].get(flow_id)
            if rec is None:
                raise OAuthDenied("unknown or expired flow")
            if rec.get("completed"):
                raise OAuthDenied("flow already completed (replay refused)")
            if rec["expires_at"] <= _now():
                data["flows"].pop(flow_id, None)
                self._save(data)
                rate_limits.release_flow(rec["identity"])
                raise OAuthDenied("flow expired")
            challenge = _b64url(
                hashlib.sha256(code_verifier.encode("ascii")).digest()
            )
            if not hmac.compare_digest(challenge, rec["code_challenge"]):
                raise OAuthDenied("PKCE verification failed")
            rec["completed"] = True
            data["flows"].pop(flow_id, None)
            self._save(data)

        rate_limits.release_flow(rec["identity"])
        now = _now()
        token_id = uuid.uuid4().hex
        payload = {
            "token_id": token_id,
            "identity": rec["identity"],
            "provider": rec["provider"],
            "scopes": rec["scopes"],
            "issued_at": now,
            "expires_at": now + _TOKEN_TTL_SECONDS,
            "founder": bool(is_founder_identity(rec["identity"])),
        }
        token = self._seal(payload)
        self._audit.append(
            "oauth.token_issued",
            rec["identity"],
            {
                "token_id": token_id,
                "provider": rec["provider"],
                "scopes": rec["scopes"],
                "founder": payload["founder"],
            },
        )
        return token_id, token

    # -- validate / refresh / revoke ---------------------------------------

    def validate(self, token: str) -> Optional[dict]:
        """LAW 1+2: return the bound payload (identity, scopes, ...) or
        None for forged, tampered, expired, or revoked tokens."""
        if not isinstance(token, str) or not token:
            return None
        payload = self._unseal(token)
        if not payload:
            return None
        if payload.get("expires_at", 0) <= _now():
            return None
        data = self._load()
        if payload.get("token_id") in data.get("revoked", []):
            return None
        return {
            "token_id": payload["token_id"],
            "identity": payload["identity"],
            "provider": payload.get("provider"),
            "scopes": list(payload.get("scopes", [])),
            "issued_at": payload["issued_at"],
            "expires_at": payload["expires_at"],
            "founder": bool(payload.get("founder")),
        }

    def refresh(self, token: str) -> tuple[str, str]:
        """Rotate a live token. LAW 5: refresh is rate-limited looser than
        initiation. The old token is revoked immediately."""
        payload = self.validate(token)
        if payload is None:
            raise OAuthDenied("cannot refresh an invalid token")
        identity = payload["identity"]
        try:
            rate_limits.check(identity, rate_limits.OAUTH_REFRESH)
        except rate_limits.RateLimitDenied as exc:
            raise OAuthDenied(f"OAuth refresh refused: {exc}") from exc
        self.revoke(payload["token_id"], identity)
        now = _now()
        token_id = uuid.uuid4().hex
        new_payload = {
            "token_id": token_id,
            "identity": identity,
            "provider": payload.get("provider"),
            "scopes": payload["scopes"],
            "issued_at": now,
            "expires_at": now + _TOKEN_TTL_SECONDS,
            "founder": payload["founder"],
        }
        new_token = self._seal(new_payload)
        self._audit.append(
            "oauth.token_refreshed",
            identity,
            {"token_id": token_id, "rotated_from": payload["token_id"]},
        )
        return token_id, new_token

    def revoke(self, token_id: str, identity: str) -> None:
        """Revoke a token by id. It stops validating immediately."""
        identity = _check_identity(identity)
        if not isinstance(token_id, str) or not token_id:
            raise OAuthDenied("token_id required")
        with store_lock(self._path):
            data = self._load()
            if token_id not in data["revoked"]:
                data["revoked"].append(token_id)
            self._save(data)
        self._audit.append("oauth.token_revoked", identity, {"token_id": token_id})
