"""
LEVI life-pack bundles — the portable, tamper-evident, optionally
encrypted shipping format for a life pack (Megazord axis 10).

This module is an *adapter* over :mod:`levi.lifepack.pack`: it reuses
``export_pack`` (the read-only v2 pack builder), ``validate_pack``,
``preview_import`` and ``import_pack`` (the write path). Nothing in
``pack.py`` is rewritten or duplicated here.

Bundle layout::

    life-pack bundles are one of:
      - an unencrypted ``.tar.gz`` holding exactly two members:
          pack.json      — the life pack dict (pack.py v2 format)
          MANIFEST.json  — SHA-256 of every file in the bundle
      - an encrypted JSON envelope (``.tar.gz.enc`` by convention):
          {"format": "levi-lifepack-bundle", "encrypted": true,
           "kdf": {...}, "cipher": {...}, "payload": "<base64 Fernet token>"}
        whose decrypted payload is the same ``.tar.gz`` as above.

Format is detected by magic bytes (gzip ``1f 8b`` vs JSON ``{``), so the
file extension never decides anything.

Crypto (no home-rolled anything):
  - key derivation: PBKDF2-HMAC-SHA256, 600_000 iterations, random 16-byte
    salt stored in the envelope (OWASP's current PBKDF2-SHA256 guidance).
  - encryption: Fernet from the ``cryptography`` package (AES-128-CBC +
    HMAC-SHA256, authenticated — a wrong passphrase fails loudly).
  - integrity: MANIFEST.json carries SHA-256 of every other member, plus a
    ``manifest_integrity`` self-hash (computed with the field blanked) so
    the manifest itself cannot be edited either. Import verifies hashes
    BEFORE parsing pack.json, and fails closed on any mismatch.

Deliberately *not* in the bundle (same exclusions as pack.py, enforced
again at bundle-build time because a bundle is a portable artifact):
  - weights: model weights (``.pt`` / ``.gguf`` / … bytes) are never
    included — the pack carries a manifest/reference at most. The builder
    refuses to write a bundle whose pack mentions a weight filename.
  - secrets/credentials: the same ``looks_secret`` filter import applies is
    applied on export too — secret-looking settings keys and memory
    content are scrubbed from the bundle and reported.
  - ephemeral/device state: ``pack.py`` never exports those; the bundle
    only ever wraps what ``export_pack`` produced.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import gzip
import hashlib
import hmac
import io
import json
import os
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from levi import __version__ as LEVI_VERSION
from levi.lifepack import pack as _pack
from levi.lifepack.pack import (
    LifepackError,
    export_pack,
    import_pack,
    looks_secret,
    preview_import,
    validate_pack,
)

BUNDLE_FORMAT = "levi-lifepack-bundle"
BUNDLE_VERSION = 1

PACK_FILENAME = "pack.json"
MANIFEST_FILENAME = "MANIFEST.json"
_BUNDLE_MEMBERS = frozenset({PACK_FILENAME, MANIFEST_FILENAME})

#: KDF parameters. 600k iterations follows current OWASP guidance for
#: PBKDF2-HMAC-SHA256; the salt is random per bundle and stored alongside.
KDF_NAME = "pbkdf2-hmac-sha256"
KDF_ITERATIONS = 600_000
KDF_SALT_BYTES = 16

#: File suffixes that mark model-weight bytes. The builder refuses a pack
#: that references any of these, so weights can never ride in a bundle.
WEIGHT_SUFFIXES = (".pt", ".pth", ".gguf", ".ggml", ".bin", ".safetensors", ".onnx")

_GZIP_MAGIC = b"\x1f\x8b"

UNENCRYPTED_WARNING = (
    "WARNING: writing an UNENCRYPTED life-pack bundle. "
    "This bundle contains personal state — identity, settings, durable "
    "memory. Anyone who can read this file can read your LEVI's mind. "
    "Re-run with a passphrase (levi pack export --passphrase-env VAR) "
    "to encrypt it."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# ── key derivation / encryption (cryptography package only) ──────────


def _derive_fernet_key(passphrase: str, salt: bytes) -> bytes:
    """PBKDF2-HMAC-SHA256 → Fernet key. Raises LifepackError on bad input."""
    if not passphrase:
        raise LifepackError("passphrase must be non-empty")
    if len(salt) < KDF_SALT_BYTES:
        raise LifepackError("KDF salt is too short — refusing")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def _encrypt_tar(tar_bytes: bytes, passphrase: str) -> Dict[str, Any]:
    salt = os.urandom(KDF_SALT_BYTES)
    token = Fernet(_derive_fernet_key(passphrase, salt)).encrypt(tar_bytes)
    return {
        "format": BUNDLE_FORMAT,
        "bundle_version": BUNDLE_VERSION,
        "encrypted": True,
        "kdf": {
            "name": KDF_NAME,
            "iterations": KDF_ITERATIONS,
            "salt": base64.b64encode(salt).decode("ascii"),
        },
        "cipher": {
            "name": "fernet",
            "note": (
                "AES-128-CBC + HMAC-SHA256, authenticated, via the "
                "'cryptography' package — no home-rolled crypto"
            ),
        },
        "payload": base64.b64encode(token).decode("ascii"),
    }


def _decrypt_tar(envelope: Dict[str, Any], passphrase: Optional[str]) -> bytes:
    if not passphrase:
        raise LifepackError(
            "this bundle is encrypted: supply the passphrase "
            "(--passphrase-env VAR or an interactive prompt)"
        )
    kdf_info = envelope.get("kdf") or {}
    if kdf_info.get("name") != KDF_NAME:
        raise LifepackError(
            f"unsupported KDF {kdf_info.get('name')!r} (this LEVI speaks {KDF_NAME!r})"
        )
    try:
        salt = base64.b64decode(kdf_info["salt"])
        token = base64.b64decode(envelope["payload"])
    except Exception as exc:
        raise LifepackError(f"encrypted bundle envelope is malformed: {exc}") from exc
    key = _derive_fernet_key(passphrase, salt)
    try:
        return Fernet(key).decrypt(token)
    except InvalidToken:
        raise LifepackError(
            "wrong passphrase or corrupted bundle: authentication failed"
        ) from None


# ── bundle construction ─────────────────────────────────────────────


def _scrub_pack_for_bundle(pack: Dict[str, Any]) -> Dict[str, Any]:
    """Apply the import-time secret filter at export time too.

    A bundle is a portable artifact (USB sticks, email, cloud drives), so
    secret-looking settings keys and memory content are scrubbed *before*
    they ever land in ``pack.json`` — the same rules ``import_pack``
    applies, reported the same way. ``pack.py`` itself is untouched.
    """
    sections = pack["sections"]
    report: Dict[str, Any] = {"settings_skipped": [], "memory_skipped": []}

    settings = sections.get("settings")
    if isinstance(settings, dict):
        clean, skipped = _pack._strip_secrets(settings)  # noqa: SLF001
        sections["settings"] = clean
        report["settings_skipped"] = skipped

    memory = sections.get("memory")
    if isinstance(memory, list):
        kept = []
        for entry in memory:
            content = entry.get("content", "") if isinstance(entry, dict) else ""
            if isinstance(content, str) and looks_secret(content or ""):
                report["memory_skipped"].append(
                    entry.get("id") if isinstance(entry, dict) else "?"
                )
            else:
                kept.append(entry)
        sections["memory"] = kept
    return report


def _assert_no_weight_bytes(pack: Dict[str, Any]) -> None:
    """Fail closed if the pack references model-weight files.

    Weights are never bytes in a JSON pack, but a belt-and-braces scan
    refuses even a *filename* reference, so weights can never ride along
    by accident (or by a future pack.py change this adapter would inherit).
    """

    def walk(value: Any, trail: str) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                walk(v, f"{trail}.{k}" if trail else str(k))
        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(v, f"{trail}[{i}]")
        elif isinstance(value, str):
            lowered = value.lower()
            if lowered.endswith(WEIGHT_SUFFIXES):
                raise LifepackError(
                    f"refusing bundle: weight file reference at {trail!r} "
                    f"({value!r}) — weights never travel in a life pack"
                )

    walk(pack, "")


def _pack_json_bytes(pack: Dict[str, Any]) -> bytes:
    # Canonical serialization: sorted keys, stable hashes.
    return json.dumps(pack, indent=2, sort_keys=True, ensure_ascii=False).encode(
        "utf-8"
    )


def _manifest_bytes(pack_sha256: str, pack_size: int, encrypted: bool) -> bytes:
    manifest: Dict[str, Any] = {
        "bundle_format": BUNDLE_FORMAT,
        "bundle_version": BUNDLE_VERSION,
        "created_at": _utc_now(),
        "levi_version": LEVI_VERSION,
        "encrypted": encrypted,
        "files": {
            PACK_FILENAME: {"sha256": pack_sha256, "bytes": pack_size},
        },
        "manifest_integrity": "",
    }
    if not encrypted:
        manifest["unencrypted_warning"] = UNENCRYPTED_WARNING
    # Self-hash with the field blanked, so the manifest itself is covered.
    canonical = json.dumps(
        manifest, indent=2, sort_keys=True, ensure_ascii=False
    ).encode("utf-8")
    manifest["manifest_integrity"] = hashlib.sha256(canonical).hexdigest()
    return json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False).encode(
        "utf-8"
    )


def _tar_bytes(pack_json: bytes, manifest_json: bytes) -> bytes:
    """Deterministic tar.gz with exactly the two bundle members."""
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for name, data in (
                (PACK_FILENAME, pack_json),
                (MANIFEST_FILENAME, manifest_json),
            ):
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mode = 0o600
                tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.chmod(tmp, 0o600)  # bundles hold personal state — owner-only
    tmp.replace(path)


def default_bundle_name(encrypted: bool) -> str:
    base = f"levi-lifepack-{_utc_stamp()}.tar.gz"
    return base + (".enc" if encrypted else "")


def export_bundle(
    home: Optional[Path] = None,
    dest_path: Optional[Path] = None,
    passphrase: Optional[str] = None,
) -> Dict[str, Any]:
    """Export ``home`` to a life-pack bundle file.

    Builds the pack via ``export_pack`` (read-only), scrubs secret-looking
    material, refuses weight references, then writes ``pack.json`` +
    ``MANIFEST.json`` (SHA-256 of every file) into a ``.tar.gz``.

    Args:
        home: LEVI home to export (defaults to ``~/.levi``).
        dest_path: where to write the bundle. Defaults to
            ``./levi-lifepack-<utc>.tar.gz`` (``.tar.gz.enc`` when encrypted).
        passphrase: when given, the bundle is encrypted (Fernet, PBKDF2
            key). When omitted, the bundle is written UNENCRYPTED with a
            LOUD warning — the bundle contains personal state.

    Returns a report dict (path, encrypted, sha256, scrubbed, …).
    """
    pack = export_pack(home)
    scrub_report = _scrub_pack_for_bundle(pack)
    _assert_no_weight_bytes(pack)
    validate_pack(pack)

    encrypted = passphrase is not None
    if encrypted and not passphrase:
        raise LifepackError("passphrase must be non-empty")

    pack_json = _pack_json_bytes(pack)
    manifest_json = _manifest_bytes(
        hashlib.sha256(pack_json).hexdigest(), len(pack_json), encrypted
    )
    tar_data = _tar_bytes(pack_json, manifest_json)

    if encrypted:
        assert passphrase is not None  # noqa: S101 — checked above
        payload = json.dumps(
            _encrypt_tar(tar_data, passphrase), indent=2, ensure_ascii=False
        ).encode("utf-8")
        dest = Path(dest_path) if dest_path else Path(default_bundle_name(True))
        _atomic_write_bytes(dest, payload)
    else:
        dest = Path(dest_path) if dest_path else Path(default_bundle_name(False))
        _atomic_write_bytes(dest, tar_data)
        # LOUD, explicit, on stderr so it survives `> /dev/null` redirection.
        print(UNENCRYPTED_WARNING, file=sys.stderr)
        print(f"bundle path: {dest}", file=sys.stderr)

    return {
        "path": str(dest),
        "encrypted": encrypted,
        "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
        "bytes": dest.stat().st_size,
        "pack_version": pack["version"],
        "memory_entries": len(pack["sections"]["memory"]),
        "scrubbed": scrub_report,
    }


# ── bundle import ───────────────────────────────────────────────────


def _read_tar_bytes(bundle_path: Path, passphrase: Optional[str]) -> Tuple[bytes, bool]:
    """Read a bundle file → (tar.gz bytes, encrypted?)."""
    raw = bundle_path.read_bytes()
    if raw[:2] == _GZIP_MAGIC:
        return raw, False
    try:
        envelope = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise LifepackError(
            f"{bundle_path} is neither a gzip bundle nor an encrypted envelope: {exc}"
        ) from exc
    if not isinstance(envelope, dict) or envelope.get("format") != BUNDLE_FORMAT:
        raise LifepackError(f"{bundle_path} is not a life-pack bundle")
    version = envelope.get("bundle_version")
    if version != BUNDLE_VERSION:
        raise LifepackError(
            f"unsupported bundle version {version!r} "
            f"(this LEVI speaks bundle version {BUNDLE_VERSION})"
        )
    if not envelope.get("encrypted"):
        raise LifepackError("bundle envelope is malformed: 'encrypted' is not true")
    return _decrypt_tar(envelope, passphrase), True


def _extract_verified_members(tar_data: bytes) -> Tuple[bytes, bytes]:
    """Pull pack.json + MANIFEST.json out of the tar, nothing else.

    Members are read into memory only — nothing is ever extracted to disk.
    """
    buf = io.BytesIO(tar_data)
    try:
        tar = tarfile.open(fileobj=buf, mode="r:gz")
    except Exception as exc:
        raise LifepackError(f"bundle tar is unreadable: {exc}") from exc
    with tar:
        members = tar.getmembers()
        names = [m.name for m in members]
        if set(names) != _BUNDLE_MEMBERS:
            raise LifepackError(
                f"bundle must contain exactly {sorted(_BUNDLE_MEMBERS)}, "
                f"found {sorted(names)}"
            )
        out: Dict[str, bytes] = {}
        for member in members:
            # Belt-and-braces: no traversal, no links, regular files only.
            if (
                not member.isfile()
                or member.name.startswith("/")
                or ".." in Path(member.name).parts
            ):
                raise LifepackError(f"bundle member {member.name!r} is unsafe")
            fobj = tar.extractfile(member)
            if fobj is None:
                raise LifepackError(f"cannot read bundle member {member.name!r}")
            out[member.name] = fobj.read()
    return out[PACK_FILENAME], out[MANIFEST_FILENAME]


def _verify_manifest(pack_json: bytes, manifest_json: bytes) -> Dict[str, Any]:
    """Verify MANIFEST.json BEFORE anything else. Fail closed on mismatch."""
    try:
        manifest = json.loads(manifest_json.decode("utf-8"))
    except Exception as exc:
        raise LifepackError(f"bundle MANIFEST.json is not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise LifepackError("bundle MANIFEST.json must be a JSON object")
    if manifest.get("bundle_format") != BUNDLE_FORMAT:
        raise LifepackError(
            f"bundle manifest format={manifest.get('bundle_format')!r} "
            f"(expected {BUNDLE_FORMAT!r})"
        )

    # 1. The manifest's own self-hash (computed with the field blanked).
    claimed = manifest.get("manifest_integrity")
    if not isinstance(claimed, str) or not claimed:
        raise LifepackError("bundle MANIFEST.json has no manifest_integrity")
    check = dict(manifest)
    check["manifest_integrity"] = ""
    canonical = json.dumps(check, indent=2, sort_keys=True, ensure_ascii=False).encode(
        "utf-8"
    )
    actual = hashlib.sha256(canonical).hexdigest()
    if not hmac.compare_digest(actual, claimed):
        raise LifepackError(
            "MANIFEST.json integrity check FAILED — the bundle was tampered with"
        )

    # 2. SHA-256 (and size) of every file in the bundle.
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise LifepackError("bundle MANIFEST.json has no 'files' table")
    entry = files.get(PACK_FILENAME)
    if not isinstance(entry, dict):
        raise LifepackError(f"bundle manifest has no entry for {PACK_FILENAME!r}")
    digest = hashlib.sha256(pack_json).hexdigest()
    if not hmac.compare_digest(digest, str(entry.get("sha256", ""))):
        raise LifepackError(
            f"{PACK_FILENAME} hash MISMATCH — the bundle was tampered with"
        )
    if entry.get("bytes") != len(pack_json):
        raise LifepackError(
            f"{PACK_FILENAME} size mismatch — the bundle was tampered with"
        )
    return manifest


def import_bundle(
    bundle_path: Path,
    home: Optional[Path] = None,
    passphrase: Optional[str] = None,
    confirm: bool = False,
) -> Dict[str, Any]:
    """Import a life-pack bundle into ``home``.

    Order of operations (fail closed):
      1. detect + decrypt (if encrypted),
      2. verify MANIFEST.json self-hash, then pack.json's SHA-256,
      3. parse + ``validate_pack`` (pack version gate),
      4. Plan → Preview → Permission: without ``confirm=True`` nothing is
         written — the preview diff is returned instead.

    The actual write reuses ``import_pack`` unchanged.
    """
    bundle_path = Path(bundle_path)
    if not bundle_path.is_file():
        raise LifepackError(f"bundle not found: {bundle_path}")

    tar_data, encrypted = _read_tar_bytes(bundle_path, passphrase)
    pack_json, manifest_json = _extract_verified_members(tar_data)
    manifest = _verify_manifest(pack_json, manifest_json)

    try:
        pack = json.loads(pack_json.decode("utf-8"))
    except Exception as exc:
        raise LifepackError(f"bundle pack.json is not valid JSON: {exc}") from exc
    validate_pack(pack)

    preview_lines = preview_import(pack, home)
    if not confirm:
        return {
            "written": False,
            "encrypted": encrypted,
            "manifest": {
                "created_at": manifest.get("created_at"),
                "levi_version": manifest.get("levi_version"),
            },
            "preview": preview_lines,
        }
    summary = import_pack(pack, home, confirm=True)
    return {"written": True, "encrypted": encrypted, "summary": summary}


# ── passphrase plumbing (never a CLI arg — never in shell history) ──


def resolve_passphrase(
    passphrase_env: Optional[str],
    *,
    prompt: bool,
    confirm_entry: bool = False,
) -> Optional[str]:
    """Passphrase from an env var, or an interactive prompt.

    The passphrase is NEVER taken as a CLI argument: argv lands in shell
    history and process tables. ``--passphrase-env VAR`` names an
    environment variable; otherwise (TTY only) ``getpass`` prompts.
    """
    if passphrase_env:
        value = os.environ.get(passphrase_env)
        if not value:
            raise LifepackError(
                f"passphrase env var {passphrase_env!r} is unset or empty"
            )
        return value
    if prompt and sys.stdin.isatty():
        first = getpass.getpass("Bundle passphrase: ")
        if confirm_entry:
            second = getpass.getpass("Confirm bundle passphrase: ")
            if first != second:
                raise LifepackError("passphrases do not match")
        if not first:
            raise LifepackError("passphrase must be non-empty")
        return first
    return None


# ── CLI entry point (wired by cli/main.py; kept here so it is testable) ──


def cmd_pack(args: argparse.Namespace, home: Optional[Path] = None) -> int:
    """``levi pack export`` / ``levi pack import`` — bundle CLI."""
    from levi.lifepack.pack import _resolve_home  # noqa: SLF001

    home = _resolve_home(home)
    action = getattr(args, "pack_action", None)

    if action == "export":
        no_encrypt = bool(getattr(args, "no_encrypt", False))
        passphrase: Optional[str] = None
        if not no_encrypt:
            try:
                passphrase = resolve_passphrase(
                    getattr(args, "passphrase_env", None),
                    prompt=True,
                    confirm_entry=True,
                )
            except LifepackError as exc:
                print(f"export refused: {exc}", file=sys.stderr)
                return 1
            if passphrase is None:
                print(
                    "export refused: no passphrase available (non-interactive). "
                    "Set --passphrase-env VAR or pass --no-encrypt to write "
                    "an unencrypted bundle.",
                    file=sys.stderr,
                )
                return 1
        try:
            report = export_bundle(
                home, getattr(args, "output", None), passphrase=passphrase
            )
        except LifepackError as exc:
            print(f"export failed: {exc}", file=sys.stderr)
            return 1
        print(f"Wrote life-pack bundle → {report['path']}")
        print(
            "  encrypted: %s | pack v%s | %d memory entries | %s"
            % (
                "yes (Fernet, PBKDF2-HMAC-SHA256)"
                if report["encrypted"]
                else "NO — unencrypted",
                report["pack_version"],
                report["memory_entries"],
                report["sha256"][:16] + "…",
            )
        )
        scrubbed = report["scrubbed"]
        if scrubbed["settings_skipped"] or scrubbed["memory_skipped"]:
            print(
                "  secrets scrubbed before bundling: "
                f"{len(scrubbed['settings_skipped'])} settings keys, "
                f"{len(scrubbed['memory_skipped'])} memory entries"
            )
        return 0

    if action == "import":
        bundle = Path(getattr(args, "bundle", "") or "")
        if not bundle.is_file():
            print(f"bundle not found: {bundle}", file=sys.stderr)
            return 1
        # Peek at the magic: only prompt for a passphrase when encrypted.
        try:
            encrypted = bundle.read_bytes()[:2] != _GZIP_MAGIC
        except OSError as exc:
            print(f"cannot read bundle: {exc}", file=sys.stderr)
            return 1
        passphrase = None
        if encrypted:
            try:
                passphrase = resolve_passphrase(
                    getattr(args, "passphrase_env", None), prompt=True
                )
            except LifepackError as exc:
                print(f"import refused: {exc}", file=sys.stderr)
                return 1
            if passphrase is None:
                print(
                    "import refused: bundle is encrypted and no passphrase is "
                    "available (non-interactive). Set --passphrase-env VAR.",
                    file=sys.stderr,
                )
                return 1

        if getattr(args, "preview", False):
            try:
                result = import_bundle(bundle, home, passphrase=passphrase)
            except LifepackError as exc:
                print(f"import failed: {exc}", file=sys.stderr)
                return 1
            for line in result["preview"]:
                print(line)
            print("(preview only — verified, nothing was written)")
            return 0

        if not getattr(args, "yes", False):
            # Plan → Preview → Permission: show the diff, then ask.
            try:
                result = import_bundle(bundle, home, passphrase=passphrase)
            except LifepackError as exc:
                print(f"import failed: {exc}", file=sys.stderr)
                return 1
            for line in result["preview"]:
                print(line)
            if sys.stdin.isatty():
                answer = input(
                    "Import will overwrite identity/settings/memory in this home. "
                    "Type IMPORT to confirm: "
                ).strip()
                if answer != "IMPORT":
                    print("aborted.", file=sys.stderr)
                    return 1
            else:
                print(
                    "refusing: import needs explicit confirmation "
                    "(pass --yes or run on a TTY)",
                    file=sys.stderr,
                )
                return 1

        try:
            result = import_bundle(bundle, home, passphrase=passphrase, confirm=True)
        except LifepackError as exc:
            print(f"import failed: {exc}", file=sys.stderr)
            return 1
        summary = result["summary"]
        mem = summary["memory"]
        print("Import summary:")
        print(
            f"  identity: {'updated ' + str(summary['identity']['fields']) if summary['identity']['changed'] else 'unchanged'}"
        )
        print(f"  settings: {summary['settings']['files'] or 'unchanged'}")
        print(
            f"  memory: +{mem['added']} added, {mem['changed_entries']} changed"
            + (
                f", {len(mem['secrets_skipped'])} secret-like skipped"
                if mem["secrets_skipped"]
                else ""
            )
        )
        return 0

    print("usage: levi pack {export|import} ...", file=sys.stderr)
    return 2


__all__ = [
    "BUNDLE_FORMAT",
    "BUNDLE_VERSION",
    "PACK_FILENAME",
    "MANIFEST_FILENAME",
    "KDF_NAME",
    "KDF_ITERATIONS",
    "UNENCRYPTED_WARNING",
    "LifepackError",
    "default_bundle_name",
    "export_bundle",
    "import_bundle",
    "resolve_passphrase",
    "cmd_pack",
]
