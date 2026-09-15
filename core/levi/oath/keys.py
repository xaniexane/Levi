"""GPG key management for LEVI Oath.

All operations run against an isolated keyring — ``$LEVI_OATH_GNUPGHOME``
or ``<oath home>/gnupg`` — never the user's default ``~/.gnupg``.  The
module is defensive-only: it imports, generates, lists and verifies keys;
it never exfiltrates private key material anywhere.

Key generation uses ``gpg --batch --quick-generate-key`` so tests can mint
throwaway keys hermetically (``--pinentry-mode loopback`` with an empty
passphrase for unattended operation).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from levi.oath import gnupg_home
from levi.oath.trust import gpg_available

__all__ = [
    "GpgError",
    "KeyInfo",
    "ensure_gnupg_home",
    "gpg_sign_args",
    "run_gpg",
    "generate_key",
    "import_key",
    "list_keys",
    "fingerprint_of",
    "delete_key",
]

_FPR_RE = re.compile(r"^[0-9A-Fa-f]{40}$|^[0-9A-Fa-f]{64}$")


class GpgError(RuntimeError):
    """Raised when a ``gpg`` invocation fails unexpectedly."""


@dataclass(frozen=True)
class KeyInfo:
    """A public key in the Oath keyring."""

    fingerprint: str
    uids: tuple[str, ...]
    created: str = ""
    expires: str = ""


def ensure_gnupg_home() -> Path:
    """Create the isolated GNUPGHOME with owner-only permissions.

    Returns the path.  ``gpg`` refuses to operate on a homedir that is
    group/world-accessible, so this enforces ``0o700``.
    """
    home = gnupg_home()
    home.mkdir(parents=True, exist_ok=True)
    try:
        home.chmod(0o700)
    except OSError:
        pass  # best effort on exotic filesystems
    return home


def gpg_sign_args() -> list[str]:
    """Extra ``gpg`` args for non-interactive signing.

    Returned only when ``$LEVI_OATH_UNATTENDED=1`` (tests, and unattended
    owner keys with empty passphrases).  Never enabled by default: the
    real sign ceremony goes through the owner's pinentry.
    """
    if os.environ.get("LEVI_OATH_UNATTENDED") == "1":
        return ["--pinentry-mode", "loopback", "--passphrase", ""]
    return []


def run_gpg(*args: str, input_bytes: Optional[bytes] = None, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run ``gpg`` against the Oath keyring.

    Always passes ``--batch --no-tty --homedir <oath gnupg>``.  Raises
    :class:`RuntimeError` when ``gpg`` is not installed and
    :class:`GpgError` on non-zero exit.
    """
    if not gpg_available():
        raise RuntimeError("gpg is not installed")
    ensure_gnupg_home()
    cmd = [
        "gpg",
        "--batch",
        "--no-tty",
        "--homedir",
        str(gnupg_home()),
        *args,
    ]
    try:
        proc = subprocess.run(
            cmd,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GpgError(f"gpg failed to run: {exc}") from exc
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        raise GpgError(f"gpg exited {proc.returncode}: {err[:500]}")
    return proc


def normalise_fingerprint(fpr: str) -> str:
    """Normalise a fingerprint to upper-case with no whitespace.

    Raises :class:`ValueError` when it does not look like a v4/v5
    fingerprint.
    """
    norm = re.sub(r"\s+", "", fpr or "").upper()
    if not _FPR_RE.match(norm):
        raise ValueError(f"not a valid OpenPGP fingerprint: {fpr!r}")
    return norm


def generate_key(uid: str, *, expire: str = "0") -> KeyInfo:
    """Generate a throwaway key with ``--quick-generate-key``.

    ``uid`` is e.g. ``"Oath Owner <owner@example.com>"``.  The key has no
    passphrase (``--pinentry-mode loopback``) because the Oath keyring is
    unattended by design; the GNUPGHOME itself is mode ``0o700`` and the
    threat model assumes the local machine is trusted.  ``expire`` is a
    gpg expiry spec such as ``"0"`` (never), ``"1y"``, ``"30d"``.

    Returns :class:`KeyInfo` for the new key.
    """
    before = {k.fingerprint for k in list_keys()}
    run_gpg(
        "--pinentry-mode",
        "loopback",
        "--passphrase",
        "",
        "--quick-generate-key",
        uid,
        "default",
        "default",
        expire,
    )
    fresh = [k for k in list_keys() if k.fingerprint not in before]
    if not fresh:
        raise GpgError("key generation produced no new keys")
    return fresh[0]


def import_key(armored: bytes) -> list[KeyInfo]:
    """Import an armored public (or private) key block into the Oath keyring.

    Returns the list of keys now present.  The caller decides what to pin;
    import alone grants no authority.
    """
    before = {k.fingerprint for k in list_keys()}
    run_gpg("--import", input_bytes=armored)
    return [k for k in list_keys() if k.fingerprint not in before] or list_keys()


def list_keys() -> list[KeyInfo]:
    """List public keys in the Oath keyring via ``--with-colons``."""
    try:
        proc = run_gpg("--with-colons", "--list-keys")
    except GpgError as exc:
        if "No public key" in str(exc) or "public key" in str(exc).lower():
            return []
        raise
    keys: list[KeyInfo] = []
    current_fpr: Optional[str] = None
    fpr_seen = False  # only the first fpr: line per pub: is the primary key
    uids: list[str] = []
    created = ""
    expires = ""
    for line in proc.stdout.decode("utf-8", "replace").splitlines():
        fields = line.split(":")
        if fields[0] == "pub":
            if current_fpr:
                keys.append(KeyInfo(current_fpr, tuple(uids), created, expires))
            uids, created, expires = [], fields[4] if len(fields) > 4 else "", ""
            current_fpr = None
            fpr_seen = False
        elif fields[0] == "fpr" and len(fields) > 9 and not fpr_seen:
            current_fpr = fields[9]
            fpr_seen = True
        elif fields[0] == "uid" and len(fields) > 9:
            uids.append(fields[9])
    if current_fpr:
        keys.append(KeyInfo(current_fpr, tuple(uids), created, expires))
    return keys


def fingerprint_of(pattern: str) -> Optional[str]:
    """Return the full fingerprint of the first key matching ``pattern``
    (fingerprint fragment, key id, or uid substring), or ``None``."""
    for key in list_keys():
        if pattern.upper().replace(" ", "") in key.fingerprint:
            return key.fingerprint
        if any(pattern.lower() in uid.lower() for uid in key.uids):
            return key.fingerprint
    return None


def delete_key(fingerprint: str) -> None:
    """Delete a key (public and, if present, secret part) from the Oath keyring."""
    fpr = normalise_fingerprint(fingerprint)
    run_gpg("--batch", "--yes", "--delete-secret-keys", fpr)
    run_gpg("--batch", "--yes", "--delete-keys", fpr)
