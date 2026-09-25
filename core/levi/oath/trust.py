"""Four-level message trust classification for LEVI Oath.

Trust levels (highest to lowest):

``TRUSTED``
    Fully-validated chain: a cryptographically valid signature from a key
    whose fingerprint the owner has *pinned* to a known contact.
``VERIFIED``
    A cryptographically valid PGP signature from a key that is not (yet)
    pinned to any contact.
``UNTRUSTED``
    A signature was present but cryptographic verification failed
    (bad signature, tampered content, unknown algorithm, expired key).
``UNVERIFIED``
    No signature at all.

Honest note on Proton: Proton's proprietary end-to-end encryption is not
verifiable by third-party tooling — there is no way for this module to
prove a "Proton-to-Proton" claim without Proton's own stack.  The
implemented path is PGP/MIME (``multipart/signed``), which is exactly what
Proton Bridge produces for signed mail, plus clear-signed bodies as a
convenience.  A message only reaches ``TRUSTED`` here when its signature
verifies *and* the signing fingerprint is pinned to a known contact —
that pinned chain is what stands in for the "fully-validated" claim.

Verification is done by shelling out to ``gpg --verify`` (with
``--status-fd`` machine parsing) against the isolated Oath GNUPGHOME.
"""

from __future__ import annotations

import email
import email.message
import email.policy
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, Optional

from levi.oath import gnupg_home

__all__ = [
    "TRUSTED",
    "VERIFIED",
    "UNTRUSTED",
    "UNVERIFIED",
    "TRUST_ORDER",
    "Classification",
    "gpg_available",
    "extract_signed_parts",
    "verify_detached",
    "classify_message",
]

TRUSTED = "TRUSTED"
VERIFIED = "VERIFIED"
UNTRUSTED = "UNTRUSTED"
UNVERIFIED = "UNVERIFIED"

#: Ordered from lowest to highest trust; useful for floor comparisons.
TRUST_ORDER = (UNVERIFIED, UNTRUSTED, VERIFIED, TRUSTED)

_CLEARSIGN_RE = re.compile(
    rb"-----BEGIN PGP SIGNED MESSAGE-----\r?\n.*?"
    rb"-----BEGIN PGP SIGNATURE-----\r?\n.*?-----END PGP SIGNATURE-----",
    re.DOTALL,
)


class Classification:
    """Result of classifying one message.

    Attributes
    ----------
    level:
        One of ``TRUSTED`` / ``VERIFIED`` / ``UNTRUSTED`` / ``UNVERIFIED``.
    signer_fingerprint:
        Full fingerprint from the ``VALIDSIG`` status line, or ``None``.
    signer_uid:
        Human-readable uid (from ``GOODSIG``), or ``None``.
    detail:
        Short human/machine-readable explanation of the outcome.
    signed_bytes:
        The bytes that were actually verified (for downstream use as the
        mission's pipeline text).
    """

    def __init__(
        self,
        level: str,
        signer_fingerprint: Optional[str] = None,
        signer_uid: Optional[str] = None,
        detail: str = "",
        signed_bytes: bytes = b"",
    ) -> None:
        if level not in TRUST_ORDER:
            raise ValueError(f"unknown trust level: {level!r}")
        self.level = level
        self.signer_fingerprint = signer_fingerprint
        self.signer_uid = signer_uid
        self.detail = detail
        self.signed_bytes = signed_bytes

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"Classification(level={self.level!r}, "
            f"fingerprint={self.signer_fingerprint!r}, detail={self.detail!r})"
        )


def gpg_available() -> bool:
    """Return True when the ``gpg`` binary is on PATH."""
    return shutil.which("gpg") is not None


def _run_gpg_verify(
    sig_path: Path, data_path: Optional[Path]
) -> tuple[bool, Optional[str], Optional[str], str]:
    """Run ``gpg --verify`` and parse ``--status-fd`` output.

    Returns ``(valid, fingerprint, uid, detail)``.  ``valid`` is True only
    when a ``VALIDSIG`` status line is seen — cryptographic validity, not
    web-of-trust validity (Oath pins fingerprints explicitly instead).
    """
    cmd = ["gpg", "--batch", "--no-tty"]
    home = gnupg_home()
    if home:
        cmd += ["--homedir", str(home)]
    cmd += ["--status-fd", "1", "--verify", str(sig_path)]
    if data_path is not None:
        cmd.append(str(data_path))
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, None, None, f"gpg failed to run: {exc}"

    valid = False
    fingerprint: Optional[str] = None
    uid: Optional[str] = None
    for raw in proc.stdout.decode("utf-8", "replace").splitlines():
        if not raw.startswith("[GNUPG:] "):
            continue
        tag, _, rest = raw[len("[GNUPG:] ") :].partition(" ")
        if tag == "VALIDSIG":
            valid = True
            fingerprint = rest.split()[0] if rest else None
        elif tag == "GOODSIG":
            parts = rest.split(" ", 1)
            uid = parts[1] if len(parts) == 2 else None
    detail = "signature valid" if valid else "signature invalid or unverifiable"
    return valid, fingerprint, uid, detail


def verify_detached(
    signature: bytes, data: bytes
) -> tuple[bool, Optional[str], Optional[str], str]:
    """Verify a detached PGP signature over ``data``.

    Returns ``(valid, fingerprint, uid, detail)``.  Raises
    :class:`RuntimeError` when ``gpg`` is not installed.
    """
    if not gpg_available():
        raise RuntimeError("gpg is not installed; cannot verify signatures")
    with tempfile.TemporaryDirectory(prefix="oath-verify-") as tmp:
        sig_path = Path(tmp) / "sig.asc"
        data_path = Path(tmp) / "data.bin"
        sig_path.write_bytes(signature)
        data_path.write_bytes(data)
        return _run_gpg_verify(sig_path, data_path)


def verify_clearsigned(text: bytes) -> tuple[bool, Optional[str], Optional[str], str]:
    """Verify a clear-signed (``-----BEGIN PGP SIGNED MESSAGE-----``) blob."""
    if not gpg_available():
        raise RuntimeError("gpg is not installed; cannot verify signatures")
    with tempfile.TemporaryDirectory(prefix="oath-verify-") as tmp:
        msg_path = Path(tmp) / "msg.asc"
        msg_path.write_bytes(text)
        return _run_gpg_verify(msg_path, None)


def _crlf(data: bytes) -> bytes:
    """Canonicalise to CRLF line endings (RFC 3156, section 5)."""
    return data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


def extract_signed_parts(msg: email.message.Message) -> list[tuple[bytes, bytes]]:
    """Extract ``(signed_bytes, signature_bytes)`` pairs from an email.

    Handles two shapes:

    * ``multipart/signed`` with ``protocol="application/pgp-signature"``
      (what Proton Bridge emits): the first part is the signed content
      (canonicalised to CRLF per RFC 3156), the second part is the
      detached signature.
    * A clear-signed body (``text/plain`` starting with
      ``-----BEGIN PGP SIGNED MESSAGE-----``): returned as a single pair
      ``(cleartext_bytes, cleartext_bytes)`` where verification treats the
      blob as a whole via :func:`verify_clearsigned`.

    Returns an empty list when no signed parts are found.
    """
    found: list[tuple[bytes, bytes]] = []

    def _walk(part: email.message.Message) -> None:
        ctype = (part.get_content_type() or "").lower()
        if part.is_multipart():
            if ctype == "multipart/signed":
                payload = part.get_payload()
                if isinstance(payload, list) and len(payload) >= 2:
                    data_part, sig_part = payload[0], payload[1]
                    data = data_part.get_payload(decode=True)
                    if data is None:
                        data = str(data_part.get_payload()).encode("utf-8", "replace")
                    sig = sig_part.get_payload(decode=True)
                    if sig is None:
                        sig = str(sig_part.get_payload()).encode("utf-8", "replace")
                    found.append((_crlf(bytes(data)), bytes(sig)))
                return
            for sub in part.get_payload():
                if isinstance(sub, email.message.Message):
                    _walk(sub)
            return
        payload = part.get_payload(decode=True)
        raw = bytes(payload) if payload is not None else b""
        if _CLEARSIGN_RE.search(raw):
            # Whole blob verifies as a clear-signed message.
            found.append((raw, raw))

    _walk(msg)
    return found


def _sender_addresses(msg: email.message.Message) -> list[str]:
    """Return the From/Sender/Reply-To addresses, lower-cased."""
    addrs: list[str] = []
    for header in ("From", "Sender", "Reply-To"):
        for _name, addr in email.utils.getaddresses(msg.get_all(header, [])):
            addr = (addr or "").strip().lower()
            if addr:
                addrs.append(addr)
    return addrs


def classify_message(
    msg: email.message.Message,
    pins: Optional[Iterable[str]] = None,
) -> Classification:
    """Classify ``msg`` into the four-level trust ladder.

    Parameters
    ----------
    msg:
        A parsed :class:`email.message.Message`.
    pins:
        Fingerprints (any case, spaces tolerated) pinned to the sender's
        contact.  A cryptographically valid signature from a pinned key
        upgrades ``VERIFIED`` to ``TRUSTED`` — the fully-validated chain.

    Never raises on malformed mail; worst case is ``UNVERIFIED``.  Raises
    :class:`RuntimeError` only when ``gpg`` is missing *and* a signature
    is present (we refuse to guess about cryptography).
    """
    pinned = {(p or "").upper().replace(" ", "") for p in (pins or [])}
    parts = extract_signed_parts(msg)
    if not parts:
        return Classification(UNVERIFIED, detail="no PGP signature found in message")

    signed_bytes, sig_bytes = parts[0]
    clearsigned = signed_bytes == sig_bytes
    if clearsigned:
        valid, fpr, uid, detail = verify_clearsigned(signed_bytes)
    else:
        valid, fpr, uid, detail = verify_detached(sig_bytes, signed_bytes)

    if not valid:
        return Classification(
            UNTRUSTED,
            detail=f"signature present but verification failed: {detail}",
            signed_bytes=signed_bytes,
        )
    norm = (fpr or "").upper().replace(" ", "")
    if norm and norm in pinned:
        return Classification(
            TRUSTED,
            signer_fingerprint=fpr,
            signer_uid=uid,
            detail="valid signature from a pinned contact key",
            signed_bytes=signed_bytes,
        )
    return Classification(
        VERIFIED,
        signer_fingerprint=fpr,
        signer_uid=uid,
        detail="valid signature from an unpinned key",
        signed_bytes=signed_bytes,
    )
