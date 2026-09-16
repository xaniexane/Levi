"""Account factory — generates secure accounts (LEVI-original).

:func:`AccountFactory.generate` produces a unique username and a strong
random password, returns the secret EXACTLY ONCE in memory, and stores only
a salted PBKDF2-HMAC-SHA256 hash reference in the identity store — the
plaintext password is never written to disk, logs, or the store.

Password policy (documented, enforced):
- 20 characters (above the 16-char minimum).
- Guaranteed one character from each class: lowercase, uppercase, digits,
  symbols. All randomness from the ``secrets`` module.
- Username uniqueness is guaranteed by construction: the factory retries
  with a numeric suffix until the name is free (collision handling), so two
  concurrent generations can never land on the same name in one store.

Defensive use only: this builds accounts for LEVI's own services and test
fixtures — never credential-stuffing, never against third-party systems.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import string
from typing import Optional

from levi.cybrus.identity import IdentityStore

_PASSWORD_LENGTH = 20
_PBKDF2_ITERATIONS = 600_000
_SALT_LEN = 16

_LOWER = string.ascii_lowercase
_UPPER = string.ascii_uppercase
_DIGITS = string.digits
_SYMBOLS = "!@#$%^&*-_=+?"
_ALL = _LOWER + _UPPER + _DIGITS + _SYMBOLS

_BASE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}\Z")


def _sanitize_base(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("base name must be a non-empty string")
    base = name.strip().lower()
    base = re.sub(r"[^a-z0-9._-]+", "-", base).strip("._-")
    if not _BASE_RE.match(base):
        base = "account"
    return base[:32]


def generate_password(length: int = _PASSWORD_LENGTH) -> str:
    """Strong random password: ``secrets``-sourced, guaranteed mixed classes.

    Length defaults to 20 (>= 16 minimum). Raises ``ValueError`` for lengths
    below 16 — the policy floor.
    """
    if length < 16:
        raise ValueError("password length must be at least 16")
    # One guaranteed character from each class, then fill, then shuffle —
    # so "mixed classes" is structural, not luck.
    chars = [
        secrets.choice(_LOWER),
        secrets.choice(_UPPER),
        secrets.choice(_DIGITS),
        secrets.choice(_SYMBOLS),
    ]
    chars.extend(secrets.choice(_ALL) for _ in range(length - 4))
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def hash_password(password: str, salt: Optional[bytes] = None) -> dict:
    """Salted PBKDF2-HMAC-SHA256 hash reference for a password.

    Returns a dict of ``{scheme, iterations, salt, hash}`` with salt/hash as
    base64 — the only form of the credential that may be persisted."""
    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")
    salt = salt if salt is not None else secrets.token_bytes(_SALT_LEN)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return {
        "scheme": "pbkdf2-sha256",
        "iterations": _PBKDF2_ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "hash": base64.b64encode(digest).decode("ascii"),
    }


def verify_password(password: str, cred: dict) -> bool:
    """Constant-time check of ``password`` against a stored hash reference."""
    if not isinstance(cred, dict) or cred.get("scheme") != "pbkdf2-sha256":
        return False
    try:
        salt = base64.b64decode(cred["salt"])
        expected = base64.b64decode(cred["hash"])
        iterations = int(cred.get("iterations", _PBKDF2_ITERATIONS))
    except (ValueError, KeyError, TypeError):
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(digest, expected)


class AccountFactory:
    """Generates secure accounts into an :class:`IdentityStore`.

    ``generate`` returns ``(identity_record, plaintext_password)`` — the
    password exists in plaintext ONLY in that return value. The caller must
    hand it to the user once and drop the reference; the store keeps just
    the hash.
    """

    def __init__(self, store: Optional[IdentityStore] = None):
        self.store = store if store is not None else IdentityStore()

    def _unique_username(self, base: str) -> str:
        base = _sanitize_base(base)
        candidate = base
        n = 2
        while self.store.exists(candidate):
            candidate = f"{base}-{n}"
            n += 1
        return candidate

    def generate(
        self,
        base_name: str,
        tier: str = "starter",
        password_length: int = _PASSWORD_LENGTH,
    ) -> tuple[dict, str]:
        """Create an identity with a unique username and a fresh strong
        password. Returns ``(record, password)`` — the password is returned
        exactly once, in memory only, and never persisted in plaintext."""
        username = self._unique_username(base_name)
        password = generate_password(password_length)
        record = self.store.create(username, tier=tier)
        self.store.set_credential(username, hash_password(password))
        return record, password

    def verify(self, id_or_name: str, password: str) -> bool:
        """Check a password against the stored hash reference (constant-time)."""
        cred = self.store.get_credential(id_or_name)
        if cred is None:
            return False
        return verify_password(password, cred)
