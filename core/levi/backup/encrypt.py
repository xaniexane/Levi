"""AES-256-GCM file encryption for data-at-rest backup archives.

Binary format (v1), all big-endian:
  magic      8  bytes  "LEVIENC1"
  salt       16 bytes  random (PBKDF2 salt)
  base_nonce 12 bytes  random; per-chunk nonce = base_nonce with the last
                       4 bytes XORed with the chunk counter
  then repeated per 1 MiB plaintext chunk:
    chunk_len 4 bytes  length of the following ciphertext chunk
    ciphertext         AES-256-GCM(chunk_plaintext), tag appended (16 B)

Key: PBKDF2-HMAC-SHA256(passphrase_utf8, salt, 600_000 iterations) -> 32 B.

Passphrase sourcing is the caller's job. The CLI uses getpass for
interactive runs or --passphrase-env VAR for automation. The passphrase
is never logged, never written to any manifest — manifests record the
algorithm and KDF parameters only.

Tampering or a wrong passphrase fails fast: the first chunk's GCM tag
check raises BackupCryptoError before a single plaintext byte is
written to the destination.

Honest limits: this is at-rest protection for local archives. It does
not replace the rclone crypt remote on the off-machine leg, and it is
only as strong as the passphrase and the machine it runs on.
"""

from __future__ import annotations

import os
import struct
from pathlib import Path
from typing import BinaryIO, Dict, Union

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b"LEVIENC1"
VERSION_NOTE = "AES-256-GCM / PBKDF2-HMAC-SHA256(600000)"
KDF_ITERATIONS = 600_000
SALT_LEN = 16
NONCE_LEN = 12
CHUNK_PLAINTEXT = 1024 * 1024  # 1 MiB
_TAG_LEN = 16
_LEN_STRUCT = struct.Struct(">I")


class BackupCryptoError(ValueError):
    """Raised when encryption/decryption cannot be honored."""


def _check_passphrase(passphrase: Union[str, bytes]) -> bytes:
    if isinstance(passphrase, str):
        raw = passphrase.encode("utf-8")
    elif isinstance(passphrase, (bytes, bytearray)):
        raw = bytes(passphrase)
    else:
        raise BackupCryptoError(
            f"passphrase must be str or bytes, got {type(passphrase).__name__}"
        )
    if not raw:
        raise BackupCryptoError("passphrase must not be empty")
    return raw


def derive_key(passphrase: Union[str, bytes], salt: bytes) -> bytes:
    """PBKDF2-HMAC-SHA256(passphrase, salt, 600k) -> 32-byte key."""
    raw = _check_passphrase(passphrase)
    if not isinstance(salt, (bytes, bytearray)) or len(salt) != SALT_LEN:
        raise BackupCryptoError(f"salt must be {SALT_LEN} bytes")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=bytes(salt),
        iterations=KDF_ITERATIONS,
    )
    return kdf.derive(raw)


def _chunk_nonce(base: bytes, counter: int) -> bytes:
    if counter >= 2**32:
        raise BackupCryptoError("archive too large: chunk counter overflow")
    prefix, ctr = base[:8], struct.unpack(">I", base[8:])[0]
    return prefix + struct.pack(">I", ctr ^ counter)


def encrypt_file(
    src: Union[str, Path], dst: Union[str, Path], passphrase: Union[str, bytes]
) -> Dict[str, object]:
    """Encrypt ``src`` to ``dst`` (AES-256-GCM, chunked). Returns metadata.

    Metadata carries algorithm/KDF parameters and sizes only — never key
    material, never the passphrase. The plaintext ``src`` is left in
    place; deletion is the caller's decision, never this module's.
    """
    src_p, dst_p = Path(src), Path(dst)
    if not src_p.is_file():
        raise BackupCryptoError(f"source not a file: {src_p}")
    salt = os.urandom(SALT_LEN)
    base_nonce = os.urandom(NONCE_LEN)
    aesgcm = AESGCM(derive_key(passphrase, salt))
    chunks = 0
    plain_bytes = 0
    with src_p.open("rb") as fin, dst_p.open("wb") as fout:
        fout.write(MAGIC)
        fout.write(salt)
        fout.write(base_nonce)
        while True:
            plain = fin.read(CHUNK_PLAINTEXT)
            if not plain:
                break
            ct = aesgcm.encrypt(_chunk_nonce(base_nonce, chunks), plain, None)
            fout.write(_LEN_STRUCT.pack(len(ct)))
            fout.write(ct)
            chunks += 1
            plain_bytes += len(plain)
    return {
        "algorithm": "AES-256-GCM",
        "kdf": f"PBKDF2-HMAC-SHA256({KDF_ITERATIONS})",
        "chunks": chunks,
        "plaintext_bytes": plain_bytes,
        "ciphertext_bytes": dst_p.stat().st_size,
    }


def _read_exact(fin: BinaryIO, n: int) -> bytes:
    data = fin.read(n)
    if len(data) != n:
        raise BackupCryptoError("truncated archive header")
    return data


def decrypt_file(
    src: Union[str, Path], dst: Union[str, Path], passphrase: Union[str, bytes]
) -> Dict[str, object]:
    """Decrypt ``src`` to ``dst``. Raises BackupCryptoError on wrong
    passphrase, tampering, or truncation — before any plaintext of a
    failed chunk is written."""
    src_p, dst_p = Path(src), Path(dst)
    if not src_p.is_file():
        raise BackupCryptoError(f"source not a file: {src_p}")
    with src_p.open("rb") as fin:
        if _read_exact(fin, len(MAGIC)) != MAGIC:
            raise BackupCryptoError("not a LEVIENC1 archive (bad magic)")
        salt = _read_exact(fin, SALT_LEN)
        base_nonce = _read_exact(fin, NONCE_LEN)
        aesgcm = AESGCM(derive_key(passphrase, salt))
        tmp = dst_p.with_suffix(dst_p.suffix + ".tmp")
        chunks = 0
        plain_bytes = 0
        try:
            with tmp.open("wb") as fout:
                while True:
                    len_bytes = fin.read(_LEN_STRUCT.size)
                    if not len_bytes:
                        break
                    if len(len_bytes) != _LEN_STRUCT.size:
                        raise BackupCryptoError("truncated chunk length")
                    (ct_len,) = _LEN_STRUCT.unpack(len_bytes)
                    if ct_len < _TAG_LEN or ct_len > CHUNK_PLAINTEXT + _TAG_LEN + 64:
                        raise BackupCryptoError(
                            f"implausible chunk length: {ct_len}"
                        )
                    ct = fin.read(ct_len)
                    if len(ct) != ct_len:
                        raise BackupCryptoError("truncated chunk ciphertext")
                    try:
                        plain = aesgcm.decrypt(
                            _chunk_nonce(base_nonce, chunks), ct, None
                        )
                    except InvalidTag as exc:
                        raise BackupCryptoError(
                            "authentication failed: wrong passphrase or "
                            "tampered archive"
                        ) from exc
                    fout.write(plain)
                    chunks += 1
                    plain_bytes += len(plain)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    os.replace(tmp, dst_p)
    return {
        "algorithm": "AES-256-GCM",
        "chunks": chunks,
        "plaintext_bytes": plain_bytes,
    }
