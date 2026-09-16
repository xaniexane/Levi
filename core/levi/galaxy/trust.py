"""Galaxy install trust: hash-pinning verification + optional Oath/GPG hook.

Primary mechanism is hash-pinning: at install time the package tree's
SHA-256 root hash is recorded in the install record; :func:`verify_install`
re-hashes the installed tree and raises :class:`TamperError` on ANY
mismatch (fail-closed). This needs no keys, no network, no daemons.

GPG is an OPTIONAL extra, not a second implementation: when the isolated
Oath keyring holds keys and the install record carries a detached
signature, :func:`verify_oath_signature` defers entirely to
:mod:`levi.oath.trust` (``verify_detached``) — no GPG code is duplicated
here. It returns ``None`` when GPG is unavailable or the record has no
signature, so callers treat "no GPG verdict" as "no extra assurance",
never as failure.

ADAPTER NOTE for sibling builders: the canonical signed payload is::

    "galaxy-install-v1" + "\\n" + id + "\\n" + version + "\\n" + root_sha256

A signer produces a detached signature over those exact bytes; the
hex-or-base64 signature may be stored on the install record under the
``"signature"`` key. Verification re-derives the payload from the record
and checks the signature against the Oath keyring.
"""

from __future__ import annotations

import base64
import binascii
import os
from pathlib import Path
from typing import Any, Optional, Union

from levi.galaxy.install import hash_tree
from levi.galaxy.registry import GalaxyRegistry

__all__ = [
    "TamperError",
    "pin",
    "install_dir",
    "verify_install",
    "signature_payload",
    "verify_oath_signature",
]

PathLike = Union[str, os.PathLike]

_SIGNATURE_DOMAIN = "galaxy-install-v1"


class TamperError(Exception):
    """The installed tree does not match its pinned hash (or is missing)."""


def pin(record: dict[str, Any]) -> str:
    """Return the pinned root hash for an install record."""
    try:
        digest = record["root_sha256"]
    except (KeyError, TypeError) as exc:
        raise TamperError("install record carries no root_sha256 pin") from exc
    if not isinstance(digest, str) or not digest:
        raise TamperError("install record has an invalid root_sha256 pin")
    return digest


def install_dir(home: PathLike, record: dict[str, Any]) -> Path:
    """Filesystem location of an installed package."""
    try:
        package_id = record["id"]
        version = record["version"]
    except (KeyError, TypeError) as exc:
        raise TamperError("install record is missing id/version") from exc
    return Path(home).expanduser() / "galaxy" / "packages" / package_id / version


def verify_install(home: PathLike, record: dict[str, Any]) -> bool:
    """Re-hash the installed tree and compare against the pin.

    Returns True on a match. Raises :class:`TamperError` on ANY mismatch —
    altered file, added file, removed file, or a missing install dir.
    """
    target = install_dir(home, record)
    if not target.is_dir():
        raise TamperError(f"installed package dir is missing: {target}")
    expected = pin(record)
    actual = hash_tree(target)
    # hmac.compare_digest is used for its constant-time comparison, not for
    # keyed MAC semantics: both digests are hex strings, never secrets.
    import hmac as _hmac

    if not _hmac.compare_digest(actual, expected):
        raise TamperError(
            f"tamper detected in {record.get('id', '?')}: "
            f"installed tree hashes to {actual[:16]}..., "
            f"record pins {expected[:16]}..."
        )
    return True


def verify_record_in_registry(
    home: PathLike, package_id: str
) -> bool:
    """Verify the registry's own record for ``package_id``. Convenience."""
    registry = GalaxyRegistry(home)
    record = registry.get(package_id)
    if record is None:
        raise TamperError(f"no install record for {package_id!r}")
    return verify_install(home, record)


# ---------------------------------------------------------------------------
# Optional Oath/GPG adapter hook (no GPG code duplicated here)
# ---------------------------------------------------------------------------


def signature_payload(record: dict[str, Any]) -> bytes:
    """Canonical bytes a detached GPG signature must cover (see module note)."""
    return (
        _SIGNATURE_DOMAIN
        + "\n"
        + str(record["id"])
        + "\n"
        + str(record["version"])
        + "\n"
        + pin(record)
    ).encode("utf-8")


def _decode_signature(raw: Any) -> Optional[bytes]:
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    if isinstance(raw, str):
        text = raw.strip()
        # try hex, then base64
        try:
            return binascii.unhexlify(text)
        except (binascii.Error, ValueError):
            pass
        try:
            padded = text + "=" * (-len(text) % 4)
            return base64.b64decode(padded, validate=False)
        except (binascii.Error, ValueError):
            return None
    return None


def verify_oath_signature(record: dict[str, Any]) -> Optional[bool]:
    """Optional GPG verification of an install record's detached signature.

    Returns:
      - True  — signature present, GPG available, signature valid
      - False — signature present, GPG available, signature INVALID
      - None  — no signature on the record, or GPG/oath unavailable

    Never raises: this is an advisory hook, and hash-pinning in
    :func:`verify_install` remains the primary (mandatory) trust check.
    All GPG work is delegated to :mod:`levi.oath.trust`; nothing is
    reimplemented here.
    """
    raw_sig = record.get("signature") if isinstance(record, dict) else None
    if not raw_sig:
        return None
    signature = _decode_signature(raw_sig)
    if signature is None:
        return None
    try:
        from levi.oath.trust import gpg_available, verify_detached
    except ImportError:
        return None
    try:
        if not gpg_available():
            return None
        ok, _fingerprint, _uid, _detail = verify_detached(
            signature, signature_payload(record)
        )
    except Exception:
        return None
    return bool(ok)
