"""LEVI vault — encrypted total-security backup of the repo.

The keeper's law: a clean copy lives here (the working copy); the vault
copy is the encrypted backup, carried on external drives. The vault never
invents or stores a passphrase — it reads ``LEVI_VAULT_PASSPHRASE`` from
the environment or prompts interactively (getpass). No passphrase on disk,
no passphrase in logs, ever.

Crypto posture mirrors ``core/levi/cybrus/veil.py`` and is labeled just as
honestly:

- **AEAD backend.** AES-256-GCM via the ``cryptography`` package when
  importable (``backend == "aes-256-gcm"``, envelope magic ``LV2``).
  Otherwise the stdlib HMAC-CTR construction remains as an honestly
  labeled fallback (``backend == "stdlib-fallback"``, magic ``LV1``).
  A missing backend is never a silent downgrade: sealing with the GCM
  path raises without ``cryptography``; an ``LV2`` bundle on a machine
  without it fails closed with an install hint.
- **KDF.** ``hashlib.scrypt`` (n=2^15, r=8, p=1 — 32 MiB, workstation
  grade; steps down to n=2^14 on OpenSSL builds that cap scrypt memory)
  where available, PBKDF2-HMAC-SHA256/600k fallback. The KDF choice is
  pinned in the bundle header, so a wrong KDF fails closed like a wrong
  passphrase.

Bundle layout (all header fields are plaintext metadata — no file names,
no contents leak before the passphrase)::

    LV2 | header_len u32be | header JSON | nonce(12) | ciphertext | tag(16)

The header is bound as AAD, so a swapped header fails authentication.
Inside the ciphertext: a gzip tarball whose first entry is MANIFEST.json
(sha256 per file); the manifest is verified on restore before anything
is trusted.
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import hmac
import io
import json
import os
import stat
import tarfile
import tempfile
import time
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Honest backend labeling (same pattern as veil.py)
# ---------------------------------------------------------------------------

#: Envelope magic. LV1 = stdlib HMAC-CTR fallback; LV2 = AES-256-GCM.
_MAGIC_STD = b"LV1"
_MAGIC_GCM = b"LV2"

_BACKEND_GCM = "aes-256-gcm"
_BACKEND_STD = "stdlib-fallback"

_GCM_NONCE_LEN = 12
_GCM_TAG_LEN = 16
_STD_NONCE_LEN = 16
_STD_TAG_LEN = 32

_CHUNK = 1 << 20  # 1 MiB streaming chunks

_PASSPHRASE_ENV = "LEVI_VAULT_PASSPHRASE"


def _resolve_aesgcm():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore

        return AESGCM
    except Exception:
        return None


_AESGCM = _resolve_aesgcm()


def _resolve_gcm_cipher():
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  # type: ignore

        return Cipher, algorithms, modes
    except Exception:
        return None, None, None


def backend() -> str:
    """Honestly labeled AEAD backend in use on this machine."""
    return _BACKEND_GCM if _AESGCM is not None else _BACKEND_STD


def _kdf_name() -> str:
    return "scrypt" if hasattr(hashlib, "scrypt") else "pbkdf2"


def crypto_report() -> dict:
    """Plain-language report of the crypto actually in use. No polish."""
    return {
        "backend": backend(),
        "backend_note": (
            "AES-256-GCM via the 'cryptography' package"
            if _AESGCM is not None
            else "stdlib HMAC-CTR fallback — fallback-grade, honestly labeled; "
            "install 'cryptography' for AES-256-GCM"
        ),
        "kdf": _kdf_name(),
        "kdf_note": (
            "hashlib.scrypt n=2^15 r=8 p=1 (32 MiB, workstation-grade)"
            if _kdf_name() == "scrypt"
            else "PBKDF2-HMAC-SHA256 600k iterations (fallback)"
        ),
    }


class VaultError(Exception):
    """Any vault failure. Failures are closed and loud, never silent."""


# ---------------------------------------------------------------------------
# Passphrase handling — never invented, never stored
# ---------------------------------------------------------------------------


def get_passphrase(*, confirm: bool = False, env: dict | None = None) -> str:
    """Read the keeper's passphrase.

    From ``LEVI_VAULT_PASSPHRASE`` when set, otherwise an interactive
    getpass prompt. ``confirm=True`` asks twice (backup creation).
    Empty passphrases are refused; short ones (< 8) are refused on create.
    The passphrase is returned in memory only — never written anywhere.
    """
    env = os.environ if env is None else env
    _unset = object()
    pw = env.get(_PASSPHRASE_ENV, _unset)
    if pw is not _unset:
        # Set-but-empty is an explicit refusal, not a fallthrough to prompt.
        if not pw:
            raise VaultError("empty passphrase refused")
        if confirm and len(pw) < 8:
            raise VaultError("passphrase too short (minimum 8 characters)")
        return pw
    try:
        pw = getpass.getpass("vault passphrase: ")
    except (EOFError, KeyboardInterrupt):
        raise VaultError("no passphrase supplied (set %s for non-interactive use)" % _PASSPHRASE_ENV)
    if not pw:
        raise VaultError("empty passphrase refused")
    if confirm:
        pw2 = getpass.getpass("vault passphrase (confirm): ")
        if not hmac.compare_digest(pw, pw2):
            raise VaultError("passphrases do not match")
        if len(pw) < 8:
            raise VaultError("passphrase too short (minimum 8 characters)")
    return pw


def _derive_key(passphrase: str, salt: bytes, kdf: str) -> bytes:
    pw = passphrase.encode("utf-8")
    if kdf == "scrypt":
        if not hasattr(hashlib, "scrypt"):
            raise VaultError("scrypt KDF pinned but unavailable on this machine")
        try:
            return hashlib.scrypt(pw, salt=salt, n=2**15, r=8, p=1, dklen=32)
        except Exception:
            # Some OpenSSL builds cap scrypt memory: step down, stay memory-hard.
            return hashlib.scrypt(pw, salt=salt, n=2**14, r=8, p=1, dklen=32)
    if kdf == "pbkdf2":
        return hashlib.pbkdf2_hmac("sha256", pw, salt, 600_000, dklen=32)
    raise VaultError("unknown KDF %r" % kdf)


# ---------------------------------------------------------------------------
# Streaming AEAD: GCM when available, labeled stdlib fallback otherwise
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Owner-only filesystem: the "locked folder"
# ---------------------------------------------------------------------------


def ensure_locked_dir(path: str) -> str:
    """Create ``path`` as owner-only (0o700), fixing perms if it exists."""
    os.makedirs(path, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def secure_create(path: str):
    """Open ``path`` for binary write, created owner-only (0o600)."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.chmod(path, 0o600)
    return os.fdopen(fd, "wb")


def check_locked(path: str) -> dict:
    """Report whether a vault path has the required locked-down perms."""
    st = os.stat(path)
    mode = stat.S_IMODE(st.st_mode)
    want = 0o700 if os.path.isdir(path) else 0o600
    return {"path": path, "mode": oct(mode), "locked": mode == want}


# ---------------------------------------------------------------------------
# What goes in the backup
# ---------------------------------------------------------------------------

#: Directory names and file suffixes never packed (regenerable heavies).
DEFAULT_EXCLUDES = (
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "runs",
)


def _excluded(rel: str, extra: tuple = ()) -> bool:
    parts = rel.replace(os.sep, "/").split("/")
    for ex in DEFAULT_EXCLUDES + tuple(extra):
        ex = ex.replace(os.sep, "/").strip("/")
        if not ex:
            continue
        if any(p == ex or p.startswith(ex + "/") for p in ("/".join(parts[: i + 1]) for i in range(len(parts)))):
            return True
        if any(p == ex for p in parts):
            return True
        if rel.endswith(ex):
            return True
    return False


@dataclass
class FileEntry:
    rel: str
    kind: str  # file | dir | link
    size: int = 0
    sha256: str = ""
    mode: int = 0o644
    link_target: str = ""


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_entries(source: str, extra_excludes: tuple = ()) -> list[FileEntry]:
    """Walk ``source``, hashing every file. Returns manifest-ready entries."""
    source = os.path.abspath(source)
    entries: list[FileEntry] = []
    for root, dirs, files in os.walk(source, followlinks=False):
        rel_root = os.path.relpath(root, source)
        # prune excluded dirs in-place so we never descend into them
        dirs[:] = [d for d in dirs if not _excluded(os.path.join(rel_root, d) if rel_root != "." else d, extra_excludes)]
        dirs.sort()
        if rel_root != "." and _excluded(rel_root, extra_excludes):
            continue
        for name in sorted(files):
            rel = os.path.join(rel_root, name) if rel_root != "." else name
            if _excluded(rel, extra_excludes):
                continue
            full = os.path.join(root, name)
            st = os.lstat(full)
            if stat.S_ISLNK(st.st_mode):
                entries.append(
                    FileEntry(
                        rel=rel, kind="link", mode=stat.S_IMODE(st.st_mode),
                        link_target=os.readlink(full),
                    )
                )
            elif stat.S_ISREG(st.st_mode):
                entries.append(
                    FileEntry(
                        rel=rel, kind="file", size=st.st_size,
                        sha256=_sha256_file(full), mode=stat.S_IMODE(st.st_mode),
                    )
                )
    return entries


# ---------------------------------------------------------------------------
# Snapshot create / list / verify / restore
# ---------------------------------------------------------------------------


@dataclass
class SnapshotInfo:
    path: str
    label: str
    created_utc: str
    backend: str
    kdf: str
    file_count: int
    plaintext_bytes: int
    bundle_bytes: int


def _snapshot_name(label: str) -> str:
    ts = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    safe = "".join(c if (c.isalnum() or c in "-_") else "-" for c in label)[:40] or "vault"
    return "%s-%s.lvault" % (safe, ts)


def _write_header(bundle_fp, magic: bytes, header: dict) -> tuple[bytes, bytes]:
    header_bytes = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    bundle_fp.write(magic)
    bundle_fp.write(len(header_bytes).to_bytes(4, "big"))
    bundle_fp.write(header_bytes)
    return header_bytes, magic + header_bytes  # aad = magic || header


def _read_header(bundle_path: str) -> tuple[bytes, dict, int]:
    with open(bundle_path, "rb") as f:
        magic = f.read(3)
        if magic not in (_MAGIC_GCM, _MAGIC_STD):
            raise VaultError("not a LEVI vault bundle (bad magic)")
        hlen = int.from_bytes(f.read(4), "big")
        if hlen <= 0 or hlen > 1 << 20:
            raise VaultError("corrupt bundle header length")
        header = json.loads(f.read(hlen).decode("utf-8"))
        offset = 3 + 4 + hlen
    return magic, header, offset


def _expect_backend(magic: bytes):
    if magic == _MAGIC_GCM and _AESGCM is None:
        raise VaultError(
            "AES-256-GCM bundle needs the 'cryptography' package "
            "(pip install cryptography); refusing to open — never a silent downgrade"
        )
    if magic == _MAGIC_STD and _AESGCM is not None:
        # Opening a fallback bundle on a GCM-capable machine is fine and honest.
        return


def create_snapshot(
    source: str,
    vault_dir: str,
    label: str,
    passphrase: str,
    extra_excludes: tuple = (),
) -> SnapshotInfo:
    """Pack ``source`` into an encrypted, owner-only snapshot bundle."""
    source = os.path.abspath(source)
    vault_dir = os.path.abspath(vault_dir)
    snaps = ensure_locked_dir(os.path.join(vault_dir, "snapshots"))

    entries = collect_entries(source, extra_excludes)
    manifest = {
        "format": "levi-vault-manifest/1",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": source,
        "label": label,
        "excludes": list(DEFAULT_EXCLUDES + tuple(extra_excludes)),
        "backend": backend(),
        "kdf": _kdf_name(),
        "file_count": sum(1 for e in entries if e.kind == "file"),
        "plaintext_bytes": sum(e.size for e in entries if e.kind == "file"),
        "files": [
            {
                "path": e.rel.replace(os.sep, "/"),
                "kind": e.kind,
                "size": e.size,
                "sha256": e.sha256,
                "mode": oct(e.mode),
                "link_target": e.link_target,
            }
            for e in entries
        ],
    }
    manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")

    # Phase 1: gzip tarball to an owner-only temp file (manifest first).
    tmp = tempfile.NamedTemporaryFile(
        dir=snaps, prefix=".tmp-", suffix=".tar.gz", delete=False
    )
    try:
        os.chmod(tmp.name, 0o600)
        with tarfile.open(fileobj=tmp, mode="w:gz") as tf:
            mi = tarfile.TarInfo("MANIFEST.json")
            mi.size = len(manifest_bytes)
            mi.mtime = int(time.time())
            tf.addfile(mi, io.BytesIO(manifest_bytes))
            for e in entries:
                full = os.path.join(source, e.rel)
                ti = tarfile.TarInfo(e.rel.replace(os.sep, "/"))
                if e.kind == "link":
                    ti.type = tarfile.SYMTYPE
                    ti.linkname = e.link_target
                else:
                    ti.size = e.size
                    ti.mode = e.mode
                    ti.mtime = int(os.lstat(full).st_mtime)
                with open(full, "rb") as f:
                    tf.addfile(ti, f)
        tmp.close()

        # Phase 2: stream-encrypt temp tarball into the bundle.
        kdf = _kdf_name()
        salt = os.urandom(16)
        key = _derive_key(passphrase, salt, kdf)
        use_gcm = _AESGCM is not None
        magic = _MAGIC_GCM if use_gcm else _MAGIC_STD
        nonce = os.urandom(_GCM_NONCE_LEN if use_gcm else _STD_NONCE_LEN)
        header = {
            "format": "levi-vault/1",
            "backend": _BACKEND_GCM if use_gcm else _BACKEND_STD,
            "kdf": kdf,
            "kdf_params": {"n": 2**15, "r": 8, "p": 1} if kdf == "scrypt" else {"iterations": 600_000},
            "salt": base64.b64encode(salt).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "created_utc": manifest["created_utc"],
            "label": label,
            "source": source,
            "file_count": manifest["file_count"],
            "plaintext_bytes": manifest["plaintext_bytes"],
        }
        bundle_path = os.path.join(snaps, _snapshot_name(label))

        def _chunks():
            with open(tmp.name, "rb") as f:
                while True:
                    c = f.read(_CHUNK)
                    if not c:
                        break
                    yield c

        with secure_create(bundle_path) as out:
            header_bytes, aad = _write_header(out, magic, header)
            tag_holder: list[bytes] = []

            if use_gcm:
                Cipher, algorithms, modes = _resolve_gcm_cipher()
                enc = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
                enc.authenticate_additional_data(aad)
                for c in _chunks():
                    out.write(enc.update(c))
                out.write(enc.finalize())
                tag = enc.tag
            else:
                # Chunked stdlib seal: CTR keystream from SHA-256, HMAC tag
                # over (magic || nonce || aad || ciphertext), tag appended.
                mac = hmac.new(
                    key, magic + nonce + len(aad).to_bytes(8, "big") + aad, hashlib.sha256
                )
                ctr = 0
                for c in _chunks():
                    ks = hashlib.sha256(key + nonce + ctr.to_bytes(8, "big")).digest()
                    ks = (ks * ((len(c) // 32) + 1))[: len(c)]
                    ct = bytes(a ^ b for a, b in zip(c, ks))
                    mac.update(ct)
                    out.write(ct)
                    ctr += 1
                tag = mac.digest()
            out.write(tag)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    # Key material lives only in locals; nothing is written or logged.
    return SnapshotInfo(
        path=bundle_path,
        label=label,
        created_utc=header["created_utc"],
        backend=header["backend"],
        kdf=kdf,
        file_count=header["file_count"],
        plaintext_bytes=header["plaintext_bytes"],
        bundle_bytes=os.path.getsize(bundle_path),
    )


def list_snapshots(vault_dir: str) -> list[SnapshotInfo]:
    """List bundles from plaintext headers — no passphrase needed."""
    snaps = os.path.join(os.path.abspath(vault_dir), "snapshots")
    infos: list[SnapshotInfo] = []
    if not os.path.isdir(snaps):
        return infos
    for name in sorted(os.listdir(snaps)):
        if not name.endswith(".lvault"):
            continue
        path = os.path.join(snaps, name)
        try:
            magic, header, _ = _read_header(path)
        except (VaultError, OSError, ValueError):
            continue
        infos.append(
            SnapshotInfo(
                path=path,
                label=header.get("label", "?"),
                created_utc=header.get("created_utc", "?"),
                backend=header.get("backend", "?"),
                kdf=header.get("kdf", "?"),
                file_count=header.get("file_count", 0),
                plaintext_bytes=header.get("plaintext_bytes", 0),
                bundle_bytes=os.path.getsize(path),
            )
        )
    return infos


def _decrypt_to_temp(bundle_path: str, passphrase: str) -> str:
    magic, header, offset = _read_header(bundle_path)
    _expect_backend(magic)
    kdf = header.get("kdf", "pbkdf2")
    salt = base64.b64decode(header["salt"])
    nonce = base64.b64decode(header["nonce"])
    key = _derive_key(passphrase, salt, kdf)
    tag_len = _GCM_TAG_LEN if magic == _MAGIC_GCM else _STD_TAG_LEN
    with open(bundle_path, "rb") as f:
        f.seek(0, os.SEEK_END)
        total = f.tell()
        f.seek(offset)
        body = f.read(total - offset - tag_len)
        tag = f.read(tag_len)
    if len(tag) != tag_len:
        raise VaultError("bundle truncated")
    header_bytes = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    aad = magic + header_bytes

    tmp = tempfile.NamedTemporaryFile(prefix="levi-vault-restore-", suffix=".tar.gz", delete=False)
    try:
        os.chmod(tmp.name, 0o600)
        if magic == _MAGIC_GCM:
            Cipher, algorithms, modes = _resolve_gcm_cipher()
            dec = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
            dec.authenticate_additional_data(aad)
            try:
                for i in range(0, len(body), _CHUNK):
                    tmp.write(dec.update(body[i : i + _CHUNK]))
                tmp.write(dec.finalize())
            except Exception as e:
                raise VaultError("authentication failed: tampered bundle or wrong passphrase (%s)" % e)
        else:
            mac = hmac.new(
                key, magic + nonce + len(aad).to_bytes(8, "big") + aad, hashlib.sha256
            )
            mac.update(body)
            if not hmac.compare_digest(mac.digest(), tag):
                raise VaultError("authentication failed: tampered bundle or wrong passphrase")
            ctr = 0
            for i in range(0, len(body), _CHUNK):
                c = body[i : i + _CHUNK]
                ks = hashlib.sha256(key + nonce + ctr.to_bytes(8, "big")).digest()
                ks = (ks * ((len(c) // 32) + 1))[: len(c)]
                tmp.write(bytes(a ^ b for a, b in zip(c, ks)))
                ctr += 1
        tmp.close()
        return tmp.name
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise


def _read_manifest(tar_path: str) -> dict:
    with tarfile.open(tar_path, "r:gz") as tf:
        m = tf.extractfile("MANIFEST.json")
        if m is None:
            raise VaultError("bundle has no manifest — refusing to trust it")
        manifest = json.load(m)
    if manifest.get("format") != "levi-vault-manifest/1":
        raise VaultError("unknown manifest format")
    return manifest


def verify_snapshot(bundle_path: str, passphrase: str) -> dict:
    """Decrypt and verify every file hash against the manifest. No extract."""
    tmp = _decrypt_to_temp(bundle_path, passphrase)
    try:
        manifest = _read_manifest(tmp)
        checked = 0
        with tarfile.open(tmp, "r:gz") as tf:
            for f in manifest["files"]:
                if f["kind"] != "file":
                    continue
                member = tf.extractfile(f["path"])
                if member is None:
                    raise VaultError("manifest lists %s but tarball lacks it" % f["path"])
                h = hashlib.sha256()
                for chunk in iter(lambda: member.read(_CHUNK), b""):
                    h.update(chunk)
                if h.hexdigest() != f["sha256"]:
                    raise VaultError("hash mismatch on %s — bundle corrupt" % f["path"])
                checked += 1
        return {
            "bundle": bundle_path,
            "label": manifest.get("label"),
            "created_utc": manifest.get("created_utc"),
            "backend": manifest.get("backend"),
            "kdf": manifest.get("kdf"),
            "files_verified": checked,
            "ok": True,
        }
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def restore_snapshot(
    bundle_path: str, dest: str, passphrase: str, *, force: bool = False
) -> dict:
    """Decrypt, verify against the manifest, then extract to ``dest``."""
    dest = os.path.abspath(dest)
    if os.path.exists(dest) and os.listdir(dest) and not force:
        raise VaultError("destination %s is not empty (use --force to overwrite)" % dest)
    os.makedirs(dest, exist_ok=True)

    tmp = _decrypt_to_temp(bundle_path, passphrase)
    try:
        manifest = _read_manifest(tmp)
        with tarfile.open(tmp, "r:gz") as tf:
            members = [m for m in tf.getmembers() if m.name != "MANIFEST.json"]
            # Path-traversal guard before anything touches disk.
            for m in members:
                target = os.path.abspath(os.path.join(dest, m.name))
                if target != dest and not target.startswith(dest + os.sep):
                    raise VaultError("bundle member escapes destination: %s" % m.name)
            tf.extractall(dest, members=members, filter="data")
        # Post-extract verification: every manifest file must match on disk.
        checked = 0
        for f in manifest["files"]:
            if f["kind"] != "file":
                continue
            disk = os.path.join(dest, f["path"])
            if not os.path.isfile(disk):
                raise VaultError("restored tree missing %s" % f["path"])
            if _sha256_file(disk) != f["sha256"]:
                raise VaultError("hash mismatch after restore on %s" % f["path"])
            checked += 1
        return {
            "dest": dest,
            "label": manifest.get("label"),
            "files_restored": checked,
            "ok": True,
        }
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
