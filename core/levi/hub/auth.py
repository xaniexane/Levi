"""hub.auth: local auth. pbkdf2_hmac + opaque tokens in sqlite3.

The original used python-jose JWT + bcrypt. Ours is stdlib: scrypt-free
pbkdf2_hmac (sha256, 200k rounds) for passwords, ``secrets``-generated
opaque bearer tokens stored server-side. No sessions, no cookies, no
third-party anything. Single-user local — there is no billing, no tiers,
no monetization fiction.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from . import store

_ITERATIONS = 200_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _ITERATIONS
    ).hex()


def register(
    username: str, password: str, *, path: Optional[Path] = None
) -> Dict[str, Any]:
    """Create a local user. Raises ValueError on bad input or duplicates."""
    username = (username or "").strip()
    if not username or len(username) > 64:
        raise ValueError("username must be 1-64 chars")
    if not password or len(password) < 8:
        raise ValueError("password must be at least 8 chars")
    salt = secrets.token_bytes(16)
    conn = store.connect(path)
    try:
        cur = conn.execute(
            "INSERT INTO users (username, pw_hash, salt, created) VALUES (?, ?, ?, ?)",
            (username, _hash(password, salt), salt.hex(), _now()),
        )
        conn.commit()
        return {"ok": True, "user_id": cur.lastrowid, "username": username}
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise ValueError(f"user {username!r} already exists") from exc
        raise
    finally:
        conn.close()


def login(
    username: str, password: str, *, label: str = "", path: Optional[Path] = None
) -> Dict[str, Any]:
    """Verify credentials; return an opaque bearer token."""
    conn = store.connect(path)
    try:
        row = conn.execute(
            "SELECT id, pw_hash, salt FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row is None:
            raise ValueError("bad username or password")
        expect = _hash(password, bytes.fromhex(row["salt"]))
        if not hmac.compare_digest(expect, row["pw_hash"]):
            raise ValueError("bad username or password")
        token = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO tokens (token, user_id, label, created) VALUES (?, ?, ?, ?)",
            (token, row["id"], label, _now()),
        )
        conn.commit()
        return {"ok": True, "token": token, "username": username}
    finally:
        conn.close()


def verify_token(
    token: str, *, path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Return the user for a bearer token, or None."""
    if not token:
        return None
    conn = store.connect(path)
    try:
        row = conn.execute(
            "SELECT u.id, u.username, t.label FROM tokens t "
            "JOIN users u ON u.id = t.user_id WHERE t.token = ?",
            (token,),
        ).fetchone()
        if row is None:
            return None
        return {
            "user_id": row["id"],
            "username": row["username"],
            "label": row["label"],
        }
    finally:
        conn.close()


def logout(token: str, *, path: Optional[Path] = None) -> Dict[str, Any]:
    conn = store.connect(path)
    try:
        cur = conn.execute("DELETE FROM tokens WHERE token = ?", (token,))
        conn.commit()
        return {"ok": True, "revoked": cur.rowcount}
    finally:
        conn.close()


def user_count(*, path: Optional[Path] = None) -> int:
    conn = store.connect(path)
    try:
        row = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
        return int(row["n"])
    finally:
        conn.close()
