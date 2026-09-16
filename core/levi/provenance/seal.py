"""LEVI Origin Seal — signed, anchored releases.

Provenance, not promises. Every LEVI release is hashed file-by-file into a
canonical manifest, bound to a release descriptor (name, origin chain,
date of invention, owner), and signed with Chauncey's ed25519 origin key.
The manifest digest can be anchored to a public OpenTimestamps calendar so
the release date is provable to anyone, forever.

What this makes unreplicable: anyone can copy public code, but only the
origin keyholder can produce a seal that verifies against the in-repo
``origin.pub``. Copies are detectably not the origin.

Key layout:
  private key : ``~/.levi/seal/origin.key`` (0600, dir 0700) — never leaves the machine
  public key  : ``core/levi/provenance/origin.pub`` (hex, committed) — the trust anchor

``cryptography`` is already a LEVI dependency (vault); everything else is stdlib.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Identity constants — the origin chain, oldest first.
# ---------------------------------------------------------------------------

PRODUCT_NAME = "LEVI"
ORIGIN_CHAIN = ["DemandPulse", "Nexus", "Alpha", "Omega", "LEVI"]
DATE_OF_INVENTION = "2026-04-24"
OWNER = "Chauncey Logan"

SEAL_FORMAT = "levi-origin-seal/1"
SEAL_FILENAME = ".levi-seal.json"

# OpenTimestamps public calendars (tried in order).
OTS_CALENDARS = [
    "https://a.pool.opentimestamps.org",
    "https://b.pool.opentimestamps.org",
    "https://c.pool.opentimestamps.org",
]

# Tree walk skips: build junk, VCS, caches, and seal artifacts themselves
# (the seal and anchor receipts live in the tree but must not move the manifest).
SKIP_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".eggs",
        "dist",
        "build",
        "node_modules",
        ".venv",
        "venv",
        ".idea",
        ".vscode",
    }
)
SKIP_SUFFIXES = (".pyc", ".pyo", ".swp", ".swo")
SKIP_NAMES = frozenset({".DS_Store", SEAL_FILENAME})


def _skip_file(name: str) -> bool:
    if name in SKIP_NAMES:
        return True
    if name.endswith(".ots") or name.endswith(".ots.request"):
        return True
    return name.endswith(SKIP_SUFFIXES)


# ---------------------------------------------------------------------------
# Canonical encoding — one byte layout, everywhere, forever.
# ---------------------------------------------------------------------------


def canonical(obj: Any) -> bytes:
    """Deterministic JSON bytes: sorted keys, no whitespace, UTF-8."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def build_manifest(root: str | os.PathLike) -> dict:
    """Walk ``root``, SHA-256 every file, return the canonical manifest dict.

    Deterministic: paths sorted POSIX-style, digests hex. Skips VCS, caches,
    build junk, and seal/anchor artifacts.
    """
    root = Path(root).resolve()
    files: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if _skip_file(name):
                continue
            full = Path(dirpath) / name
            rel = full.relative_to(root).as_posix()
            h = hashlib.sha256()
            with open(full, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            files[rel] = h.hexdigest()
    manifest = {"version": 1, "files": files}
    manifest["manifest_sha256"] = sha256_hex(canonical({"version": 1, "files": files}))
    return manifest


# ---------------------------------------------------------------------------
# Release descriptor
# ---------------------------------------------------------------------------


@dataclass
class ReleaseDescriptor:
    name: str = PRODUCT_NAME
    origin_chain: list = field(default_factory=lambda: list(ORIGIN_CHAIN))
    date_of_invention: str = DATE_OF_INVENTION
    owner: str = OWNER
    released_at: str = ""
    manifest_sha256: str = ""
    notes: str = ""


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------


def default_key_dir() -> Path:
    """Private key home. Overridable via LEVI_SEAL_DIR (tests use this)."""
    return Path(os.environ.get("LEVI_SEAL_DIR") or Path.home() / ".levi" / "seal")


def _priv_path(key_dir: Optional[Path] = None) -> Path:
    base = Path(key_dir) if key_dir else default_key_dir()
    return base / "origin.key"


def repo_pubkey_path() -> Path:
    """In-repo trust anchor."""
    return Path(__file__).resolve().parent / "origin.pub"


def fingerprint(pub_raw: bytes) -> str:
    return sha256_hex(pub_raw)


def init_keypair(key_dir: Optional[Path] = None) -> dict:
    """Generate the ed25519 origin keypair. Refuses to overwrite an existing key.

    Raises FileExistsError if a private key already exists — rotation is a
    deliberate manual act (delete the key file), never an accident.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key_dir = Path(key_dir) if key_dir else default_key_dir()
    priv = key_dir / "origin.key"
    if priv.exists():
        raise FileExistsError(
            f"origin key already exists at {priv} — refusing to overwrite"
        )
    key_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(key_dir, 0o700)
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes_raw()
    fd = os.open(priv, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, raw)
    finally:
        os.close(fd)
    os.chmod(priv, 0o600)
    pub_raw = key.public_key().public_bytes_raw()
    write_repo_pubkey(pub_raw)
    return {"private_key": str(priv), "fingerprint": fingerprint(pub_raw)}


def write_repo_pubkey(pub_raw: bytes) -> Path:
    """(Re)write the in-repo public trust anchor from private-key-derived bytes.

    Safe: the public key is derived, never destructive to the private key.
    """
    path = repo_pubkey_path()
    path.write_text(pub_raw.hex() + "\n", encoding="utf-8")
    return path


def load_private_key(key_dir: Optional[Path] = None):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    priv = _priv_path(key_dir)
    if not priv.exists():
        raise FileNotFoundError(f"no origin key at {priv} — run `levi seal init` first")
    return Ed25519PrivateKey.from_private_bytes(priv.read_bytes())


def load_trusted_pubkey(explicit: Optional[bytes] = None) -> bytes:
    """Trust anchor for verification: explicit bytes, else in-repo origin.pub."""
    if explicit is not None:
        return explicit
    path = repo_pubkey_path()
    if not path.exists():
        raise FileNotFoundError(
            f"no trust anchor at {path} — run `levi seal init` and commit origin.pub"
        )
    return bytes.fromhex(path.read_text(encoding="utf-8").strip())


# ---------------------------------------------------------------------------
# Sign
# ---------------------------------------------------------------------------


def sign_release(
    root: str | os.PathLike,
    key_dir: Optional[Path] = None,
    notes: str = "",
    out: Optional[str | os.PathLike] = None,
) -> dict:
    """Build manifest + descriptor, sign, write the .levi-seal.json envelope."""
    root = Path(root).resolve()
    manifest = build_manifest(root)
    descriptor = ReleaseDescriptor(
        released_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        manifest_sha256=manifest["manifest_sha256"],
        notes=notes,
    )
    payload = canonical({"descriptor": asdict(descriptor), "manifest": manifest})
    key = load_private_key(key_dir)
    signature = key.sign(payload).hex()
    pub_raw = key.public_key().public_bytes_raw()
    envelope = {
        "format": SEAL_FORMAT,
        "descriptor": asdict(descriptor),
        "manifest": manifest,
        "signature": signature,
        "signer_pubkey_fingerprint": fingerprint(pub_raw),
        "signer_pubkey_hex": pub_raw.hex(),
    }
    out_path = Path(out) if out else root / SEAL_FILENAME
    out_path.write_text(
        json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {"seal": str(out_path), "envelope": envelope}


# ---------------------------------------------------------------------------
# Verify — fails loudly on any tamper.
# ---------------------------------------------------------------------------


@dataclass
class VerifyResult:
    ok: bool
    errors: list = field(default_factory=list)
    tampered: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    added: list = field(default_factory=list)
    files_checked: int = 0


def verify_release(
    root: str | os.PathLike,
    seal_path: str | os.PathLike,
    trusted_pubkey: Optional[bytes] = None,
) -> VerifyResult:
    """Verify a seal against the tree. Any mismatch => ok=False with details."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    root = Path(root).resolve()
    res = VerifyResult(ok=False)
    try:
        envelope = json.loads(Path(seal_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        res.errors.append(f"cannot read seal: {exc}")
        return res

    if envelope.get("format") != SEAL_FORMAT:
        res.errors.append(f"unknown seal format: {envelope.get('format')!r}")
        return res

    descriptor = envelope.get("descriptor") or {}
    manifest = envelope.get("manifest") or {}
    signature_hex = envelope.get("signature") or ""

    # 1. Trust anchor: the signer must be the origin keyholder.
    try:
        trusted = load_trusted_pubkey(trusted_pubkey)
    except (FileNotFoundError, ValueError) as exc:
        res.errors.append(str(exc))
        return res
    if envelope.get("signer_pubkey_fingerprint") != fingerprint(trusted):
        res.errors.append(
            "signer fingerprint does not match the trusted origin public key"
        )
        return res

    # 2. Signature over the canonical descriptor+manifest.
    payload = canonical({"descriptor": descriptor, "manifest": manifest})
    try:
        signature = bytes.fromhex(signature_hex)
        Ed25519PublicKey.from_public_bytes(trusted).verify(signature, payload)
    except (ValueError, InvalidSignature) as exc:
        res.errors.append(f"SIGNATURE INVALID: {exc}")
        return res

    # 3. Re-hash the tree and diff against the sealed manifest.
    sealed_files = manifest.get("files") or {}
    live = build_manifest(root)
    live_files = live.get("files") or {}
    res.files_checked = len(live_files)

    for path, digest in sealed_files.items():
        if path not in live_files:
            res.missing.append(path)
        elif live_files[path] != digest:
            res.tampered.append(path)
    for path in live_files:
        if path not in sealed_files:
            res.added.append(path)

    if live.get("manifest_sha256") != descriptor.get("manifest_sha256"):
        res.errors.append("descriptor manifest_sha256 does not match sealed manifest")
    if res.tampered:
        res.errors.append(f"TAMPERED files: {len(res.tampered)}")
    if res.missing:
        res.errors.append(f"MISSING files: {len(res.missing)}")
    if res.added:
        res.errors.append(f"ADDED files: {len(res.added)}")

    res.ok = not res.errors
    return res


# ---------------------------------------------------------------------------
# Anchor — OpenTimestamps. Honest about offline: pending file, never fake success.
# ---------------------------------------------------------------------------


def anchor_digest(
    digest_hex: str,
    calendars: Optional[list] = None,
    out_dir: Optional[str | os.PathLike] = None,
    timeout: int = 15,
) -> dict:
    """Submit a manifest digest to a public OpenTimestamps calendar.

    Returns {"status": "anchored", ...} on success (attestation still pending
    — OTS needs a Bitcoin block; upgrade the .ots later), or
    {"status": "pending", ...} with a .ots.request file on ANY failure.
    Never reports success it did not get.
    """
    digest = bytes.fromhex(digest_hex)
    if len(digest) != 32:
        raise ValueError("digest must be 32 bytes hex")
    out_dir = Path(out_dir) if out_dir else Path.cwd()
    last_error = "no calendars configured"
    for cal in calendars or OTS_CALENDARS:
        url = cal.rstrip("/") + "/digest"
        try:
            req = urllib.request.Request(
                url, data=digest, headers={"Content-Type": "application/octet-stream"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
            if resp.status == 200 and len(body) > 32:
                ots_path = out_dir / f"{digest_hex}.ots"
                ots_path.write_bytes(body)
                return {
                    "status": "anchored",
                    "calendar": cal,
                    "ots": str(ots_path),
                    "note": "submitted; attestation pending Bitcoin confirmation — "
                    "upgrade the .ots file later to complete the proof",
                }
            last_error = f"{cal}: bad response (http {resp.status}, {len(body)} bytes)"
        except Exception as exc:  # network down, DNS, TLS, proxy — all honest pending
            last_error = f"{cal}: {type(exc).__name__}: {exc}"
    pending = out_dir / f"{digest_hex}.ots.request"
    pending.write_text(
        json.dumps(
            {
                "digest_sha256": digest_hex,
                "calendars_tried": calendars or OTS_CALENDARS,
                "requested_at": datetime.now(timezone.utc).isoformat(
                    timespec="seconds"
                ),
                "last_error": last_error,
                "how": "re-run `levi seal anchor` when online; the digest is unchanged",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "status": "pending",
        "pending_request": str(pending),
        "last_error": last_error,
        "note": "anchor NOT completed — no success faked; retry when online",
    }


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def default_root() -> Path:
    """Repo root, derived from this file's location."""
    return Path(__file__).resolve().parents[3]
