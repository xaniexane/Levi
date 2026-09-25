"""Token engine — scoped, expiring API tokens (LEVI-original).

Lifecycle: ``issue`` -> ``validate`` -> ``rotate``/``revoke``.

- Tokens are ``secrets.token_urlsafe(32)`` values (256 bits of entropy).
- Only SHA-256 hashes of tokens are persisted; the plaintext token is
  returned EXACTLY ONCE at issuance and at rotation. There is no API to
  recover a token's plaintext later — a lost token is rotated, not read.
- ``validate(token)`` returns the token's payload dict (id, label, scopes,
  issued_at, expires_at) or ``None`` for unknown / revoked / expired tokens.
  Lookups use ``hmac.compare_digest`` against stored hashes.
- ``rotate(token_id)`` revokes the old token and issues a fresh one,
  returning the new plaintext exactly once.
- Default TTL is 24 hours; per-token TTLs are honored at validation time.

Persisted as JSON under ``~/.levi/cybrus/tokens.json`` (``LEVI_HOME``
override honored): atomic writes, owner-only (0o600). No network, no
telemetry — tokens are bearer credentials for LEVI's own local services.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import uuid
from typing import Optional

from levi.cybrus._paths import (
    load_json_store,
    save_json_store,
    store_lock,
    store_path,
)

_STORE_NAME = "tokens"

DEFAULT_TTL_SECONDS = 24 * 3600  # 24 hours
_TOKEN_BYTES = 32  # 256 bits of entropy

#: Token kinds. ``session`` = issued by gateway auth; ``api`` = general
#: bearer tokens (default, preserves the original semantics); ``revenue``
#: = paper-only value-tracking tokens (honesty guardrail: no real money —
#: revenue tokens REQUIRE a memo + basis note and are labeled paper).
TOKEN_KINDS = ("session", "api", "revenue")


class TokenError(Exception):
    """Raised for invalid token requests (unknown id, bad scopes, ...)."""


def _now() -> int:
    return int(time.time())


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _check_scopes(scopes) -> list[str]:
    if not isinstance(scopes, (list, tuple)) or not scopes:
        raise TokenError("scopes must be a non-empty list of strings")
    clean = []
    for scope in scopes:
        if not isinstance(scope, str) or not scope.strip():
            raise TokenError(f"invalid scope {scope!r}")
        clean.append(scope.strip())
    return clean


def _check_kind(kind: str) -> str:
    if kind not in TOKEN_KINDS:
        raise TokenError(f"unknown token kind {kind!r}; valid: {list(TOKEN_KINDS)}")
    return kind


class TokenEngine:
    """Issues, validates, rotates, and revokes scoped bearer tokens.

    Mutating operations (issue/rotate/revoke/purge) run under the store
    lock with a fresh reload, so concurrent processes cannot interleave —
    e.g. two simultaneous ``rotate`` calls cannot both mint a successor
    for the same token: the loser sees ``revoked`` and fails closed.
    """

    def __init__(self):
        self._path = store_path(_STORE_NAME)
        data = load_json_store(self._path)
        self._records: list[dict] = data if isinstance(data, list) else []

    # -- persistence -----------------------------------------------------

    def _reload(self) -> None:
        """Reload records from disk. Call with the store lock held."""
        data = load_json_store(self._path)
        self._records = data if isinstance(data, list) else []

    def _save(self) -> None:
        save_json_store(self._path, self._records)

    def _find(self, token_id: str) -> Optional[dict]:
        for rec in self._records:
            if rec["id"] == token_id:
                return rec
        return None

    # -- issuance ----------------------------------------------------------

    def issue(
        self,
        scopes,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        label: Optional[str] = None,
        kind: str = "api",
        memo: Optional[str] = None,
        basis: Optional[str] = None,
    ) -> tuple[str, str]:
        """Issue a token. Returns ``(token_id, plaintext_token)`` — the
        plaintext is returned exactly once; only its SHA-256 is stored.

        ``kind`` is one of ``"session"`` / ``"api"`` (default) /
        ``"revenue"``. Revenue tokens are paper-only value trackers: they
        REQUIRE a ``memo`` and a ``basis`` note, and are labeled
        ``paper=True`` — no real money is ever represented.
        """
        scopes = _check_scopes(scopes)
        kind = _check_kind(kind)
        if not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
            raise TokenError("ttl_seconds must be a positive integer")
        if label is not None and (not isinstance(label, str) or not label.strip()):
            raise TokenError("label must be a non-empty string when given")
        if kind == "revenue":
            if not isinstance(memo, str) or not memo.strip():
                raise TokenError("revenue tokens require a non-empty memo")
            if not isinstance(basis, str) or not basis.strip():
                raise TokenError("revenue tokens require a non-empty basis note")
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        with store_lock(self._path):
            self._reload()
            rec = self._mint_unlocked(
                token, scopes, ttl_seconds, label, kind, memo, basis
            )
            self._save()
        return rec["id"], token

    def _mint_unlocked(
        self, token: str, scopes: list, ttl_seconds: int, label, kind: str, memo, basis
    ) -> dict:
        """Build and append a token record. Caller must hold the store
        lock and have reloaded; does NOT save (caller saves)."""
        now = _now()
        rec = {
            "id": uuid.uuid4().hex,
            "token_hash": _hash_token(token),
            "label": label.strip() if label else None,
            "kind": kind,
            "memo": memo.strip() if isinstance(memo, str) and memo.strip() else None,
            "basis": basis.strip()
            if isinstance(basis, str) and basis.strip()
            else None,
            "paper": kind == "revenue",
            "scopes": scopes,
            "issued_at": now,
            "expires_at": now + ttl_seconds,
            "revoked": False,
        }
        self._records.append(rec)
        return rec

    def _issue_unlocked(
        self, scopes, ttl_seconds: int = DEFAULT_TTL_SECONDS, label=None
    ) -> tuple[str, str]:
        """Mint a plain ``api`` token without validation or locking — for
        internal reuse (e.g. ``rotate``) when the caller already holds the
        store lock. Does NOT save (caller saves)."""
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        rec = self._mint_unlocked(
            token, list(scopes), ttl_seconds, label, "api", None, None
        )
        return rec["id"], token

    # -- validation ---------------------------------------------------------

    def validate(self, token: str) -> Optional[dict]:
        """Return the token payload (id, label, kind, memo, basis, paper,
        scopes, issued_at, expires_at) or ``None`` when the token is
        unknown, revoked, or expired. The presented token itself is never
        logged or stored."""
        if not isinstance(token, str) or not token:
            return None
        presented = _hash_token(token)
        now = _now()
        with store_lock(self._path):
            self._reload()
            for rec in self._records:
                if not hmac.compare_digest(rec["token_hash"], presented):
                    continue
                if rec.get("revoked"):
                    return None
                if rec.get("expires_at", 0) <= now:
                    return None
                return {
                    "id": rec["id"],
                    "label": rec.get("label"),
                    "kind": rec.get("kind", "api"),
                    "memo": rec.get("memo"),
                    "basis": rec.get("basis"),
                    "paper": bool(rec.get("paper", False)),
                    "scopes": list(rec["scopes"]),
                    "issued_at": rec["issued_at"],
                    "expires_at": rec["expires_at"],
                }
        return None

    # -- rotation & revocation -----------------------------------------------

    def rotate(
        self, token_id: str, ttl_seconds: int = DEFAULT_TTL_SECONDS
    ) -> tuple[str, str]:
        """Revoke the old token and issue a fresh one for the same scopes/
        label. Returns ``(new_token_id, new_plaintext_token)`` — once only.
        The old token stops validating immediately.

        Runs under the store lock: two concurrent rotations of the same
        token cannot both succeed — the loser sees ``revoked`` and fails
        closed instead of minting a second live successor.
        """
        with store_lock(self._path):
            self._reload()
            rec = self._find(token_id)
            if rec is None:
                raise TokenError(f"unknown token id: {token_id!r}")
            if rec.get("revoked"):
                raise TokenError("token is already revoked; cannot rotate")
            rec["revoked"] = True
            new_id, new_token = self._issue_unlocked(
                rec["scopes"], ttl_seconds=ttl_seconds, label=rec.get("label")
            )
            self._records = [r for r in self._records if r["id"] != token_id]
            new_rec = self._find(new_id)
            if new_rec is not None:
                new_rec["rotated_from"] = token_id
            self._save()
            return new_id, new_token

    def revoke(self, token_id: str) -> None:
        """Revoke a token by id. The token stops validating immediately.
        Raises :class:`TokenError` for unknown ids."""
        with store_lock(self._path):
            self._reload()
            rec = self._find(token_id)
            if rec is None:
                raise TokenError(f"unknown token id: {token_id!r}")
            rec["revoked"] = True
            self._save()

    # -- housekeeping ---------------------------------------------------------

    def list(self, *, include_revoked: bool = False) -> list[dict]:
        """Token metadata (never token hashes, never plaintext)."""
        out = []
        with store_lock(self._path):
            self._reload()
            for rec in self._records:
                if rec.get("revoked") and not include_revoked:
                    continue
                out.append(
                    {
                        "id": rec["id"],
                        "label": rec.get("label"),
                        "kind": rec.get("kind", "api"),
                        "memo": rec.get("memo"),
                        "basis": rec.get("basis"),
                        "paper": bool(rec.get("paper", False)),
                        "scopes": list(rec["scopes"]),
                        "issued_at": rec["issued_at"],
                        "expires_at": rec["expires_at"],
                        "revoked": bool(rec.get("revoked")),
                        "expired": rec["expires_at"] <= _now(),
                    }
                )
        return out

    def purge_expired(self) -> int:
        """Delete expired records. Returns the number removed."""
        with store_lock(self._path):
            self._reload()
            now = _now()
            before = len(self._records)
            self._records = [r for r in self._records if r["expires_at"] > now]
            removed = before - len(self._records)
            if removed:
                self._save()
            return removed
