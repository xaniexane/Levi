"""API keys for LEVI-as-cloud (LEVI-original).

Multi-user auth for :mod:`levi.agent.server`: the server owner holds a
master token (``LEVI_AGENT_TOKEN``); other users get per-user API keys
created via ``levi cloud keys create <name>``.

Security properties (binding):

* A key is printed **once** at creation. It is never stored raw —
  ``keys.json`` holds only the SHA-256 hex digest, so a disk read of
  the key store does not disclose any usable credential.
* Verification hashes the presented bearer value and compares digests
  with :func:`hmac.compare_digest` (constant time).
* The store file is ``0o600`` inside a ``0o700`` directory
  (``LEVI_CLOUD_DIR`` or ``~/.levi/cloud``). Raw keys are never logged;
  only the short public prefix (``levi_sk_…``) appears in logs/metering.
* Keys are bearer secrets: whoever holds one can call the API as that
  user until it is revoked. There is no per-key scope narrower than
  the cloud-safe tool profile (see :mod:`levi.cloud.profile`).

A revoked key stays in the store with ``revoked: true`` (audit trail);
it can never authenticate again.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

KEY_SCHEME = "levi_sk_"
_KEY_ENTROPY_BYTES = 32  # secrets.token_urlsafe(32) -> 43 chars
_PREFIX_LEN = 12  # public, log-safe: "levi_sk_" + 4 chars
_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


class KeyError(ValueError):
    """An API-key operation failed (bad name, duplicate, unknown key).

    Subclasses ValueError so identifier validation is catchable as such;
    existing ``except apikeys.KeyError`` handlers keep working unchanged.
    """


def cloud_dir() -> Path:
    """``LEVI_CLOUD_DIR`` or ``~/.levi/cloud`` (created ``0o700``)."""
    override = os.environ.get("LEVI_CLOUD_DIR", "").strip()
    d = Path(override).expanduser() if override else Path.home() / ".levi" / "cloud"
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


def keys_path() -> Path:
    return cloud_dir() / "keys.json"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _validate_name(name: str) -> str:
    if not isinstance(name, str):
        raise KeyError("key name must be a string, got %s" % type(name).__name__)
    name = name.strip()
    if not _NAME_RE.match(name):
        raise KeyError("invalid key name %r: use 1-64 chars of [A-Za-z0-9_-]" % (name,))
    return name


def _validate_ident(name_or_prefix: str) -> str:
    if not isinstance(name_or_prefix, str):
        raise KeyError(
            "key identifier must be a string, got %s" % type(name_or_prefix).__name__
        )
    ident = name_or_prefix.strip()
    if not ident:
        raise KeyError("a key name or prefix is required")
    return ident


def _load() -> list[dict]:
    path = keys_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise KeyError("key store is unreadable: %s" % (exc,)) from exc
    if not isinstance(data, list):
        raise KeyError("key store is corrupt (expected a JSON list)")
    return [r for r in data if isinstance(r, dict)]


def _save(records: list[dict]) -> None:
    path = keys_path()
    tmp = path.with_suffix(".json.tmp")
    # Owner-only from creation: never a window with default permissions.
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(records, fh, indent=2)
            fh.write("\n")
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    os.replace(tmp, path)


def _digest(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_key(name: str, *, learn: bool = True) -> tuple[str, dict]:
    """Create a key. Returns ``(raw_key, record)`` — the raw key is
    returned **once** and never stored; only its SHA-256 goes to disk.

    ``learn`` controls cross-user growth learning for this key's
    sessions (``levi cloud keys create <name> --no-learn`` opts out).
    Opted-out keys' sessions are never even opened by the harvester.
    """
    name = _validate_name(name)
    records = _load()
    if any(r.get("name") == name and not r.get("revoked") for r in records):
        raise KeyError("an active key named %r already exists" % (name,))
    raw = KEY_SCHEME + secrets.token_urlsafe(_KEY_ENTROPY_BYTES)
    record = {
        "name": name,
        "key_hash": _digest(raw),
        "prefix": raw[:_PREFIX_LEN],
        "created": _utcnow(),
        "revoked": False,
        "revoked_at": None,
        "learn": bool(learn),
    }
    records.append(record)
    _save(records)
    return raw, {k: v for k, v in record.items() if k != "key_hash"}


def set_learn(name_or_prefix: str, learn: bool) -> dict:
    """Toggle growth-learning consent for a key. Returns metadata."""
    ident = _validate_ident(name_or_prefix)
    records = _load()
    for r in records:
        if r.get("revoked"):
            continue
        if r.get("name") == ident or r.get("prefix") == ident:
            r["learn"] = bool(learn)
            _save(records)
            return {k: v for k, v in r.items() if k != "key_hash"}
    raise KeyError("no active key matching %r" % (ident,))


def list_keys(*, include_revoked: bool = True) -> list[dict]:
    """Key metadata. Hashes are never returned."""
    records = _load()
    if not include_revoked:
        records = [r for r in records if not r.get("revoked")]
    return [{k: v for k, v in r.items() if k != "key_hash"} for r in records]


def revoke_key(name_or_prefix: str) -> dict:
    """Revoke by name or by key prefix. Returns the revoked metadata."""
    ident = _validate_ident(name_or_prefix)
    records = _load()
    for r in records:
        if r.get("revoked"):
            continue
        if r.get("name") == ident or r.get("prefix") == ident:
            r["revoked"] = True
            r["revoked_at"] = _utcnow()
            _save(records)
            return {k: v for k, v in r.items() if k != "key_hash"}
    raise KeyError("no active key matching %r" % (ident,))


def find_key(raw: str) -> dict | None:
    """Return the active key record for a presented bearer value, or
    None. Comparison is constant-time over stored digests; the raw
    value is never persisted or logged."""
    if not isinstance(raw, str) or not raw or not raw.startswith(KEY_SCHEME):
        return None
    candidate = _digest(raw)
    for r in _load():
        if r.get("revoked"):
            continue
        stored = r.get("key_hash") or ""
        if hmac.compare_digest(candidate, stored):
            return r
    return None
