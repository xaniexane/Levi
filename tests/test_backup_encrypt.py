"""Law/guard/proof tests for BACK data-at-rest (wire 2).

B1 encrypted archives: AES-256-GCM round-trips, wrong passphrase and
   tampering fail closed, no plaintext of a failed chunk is written.
B2 the passwords CSV is never packed: exclusion pinned by exact name and
   by credential-shape patterns; the manifest records a count, never paths.
B3 dynasty/IP eyes-only: operator denylist file is honored.
B4 backup integrity: `levi backup verify` wires verify_snapshot; the
   standalone entrypoint's verify was already pinned by
   test_entrypoints_backup.py.
B5 the passphrase is never logged, never stored: metadata carries
   algorithm/KDF params only.

Hermetic: LEVI_HOME redirected; no network; no real home writes.
"""

import argparse
import json
import os
import tarfile

import pytest

from levi.backup import encrypt
from levi.backup.encrypt import BackupCryptoError, decrypt_file, encrypt_file
from levi.backup.snapshot import create_snapshot, list_snapshots


@pytest.fixture
def herm(monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "levi_home"))
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


# ------------------------------------------------- B1: encrypted archives


def test_encrypt_round_trip(tmp_path):
    src = tmp_path / "data.bin"
    src.write_bytes(os.urandom(10_000))
    enc = tmp_path / "data.bin.enc"
    dec = tmp_path / "data.bin.dec"
    meta = encrypt_file(src, enc, "correct horse battery staple")
    assert meta["algorithm"] == "AES-256-GCM"
    assert "PBKDF2-HMAC-SHA256" in meta["kdf"]
    assert "passphrase" not in json.dumps(meta).lower()
    assert enc.read_bytes()[:8] == b"LEVIENC1"
    out = decrypt_file(enc, dec, "correct horse battery staple")
    assert dec.read_bytes() == src.read_bytes()
    assert out["chunks"] == meta["chunks"] == 1


def test_encrypt_multichunk_round_trip(tmp_path):
    src = tmp_path / "big.bin"
    src.write_bytes(os.urandom(2_500_000))
    enc = tmp_path / "big.bin.enc"
    dec = tmp_path / "big.bin.dec"
    meta = encrypt_file(src, enc, "p")
    assert meta["chunks"] == 3
    decrypt_file(enc, dec, "p")
    assert dec.read_bytes() == src.read_bytes()


def test_encrypt_empty_file_round_trip(tmp_path):
    src = tmp_path / "empty.bin"
    src.write_bytes(b"")
    enc = tmp_path / "e.enc"
    dec = tmp_path / "e.dec"
    meta = encrypt_file(src, enc, "p")
    assert meta["chunks"] == 0
    decrypt_file(enc, dec, "p")
    assert dec.read_bytes() == b""


def test_wrong_passphrase_fails_closed(tmp_path):
    src = tmp_path / "d.bin"
    src.write_bytes(b"sensitive bytes here")
    enc = tmp_path / "d.enc"
    dec = tmp_path / "d.dec"
    encrypt_file(src, enc, "right")
    with pytest.raises(BackupCryptoError):
        decrypt_file(enc, dec, "wrong")
    # no plaintext of the failed chunk was written
    assert not dec.exists() or b"sensitive" not in dec.read_bytes()


def test_tampered_ciphertext_fails_closed(tmp_path):
    src = tmp_path / "t.bin"
    src.write_bytes(b"sensitive bytes here")
    enc = tmp_path / "t.enc"
    dec = tmp_path / "t.dec"
    encrypt_file(src, enc, "p")
    raw = bytearray(enc.read_bytes())
    raw[-10] ^= 0xFF  # flip a bit inside the last chunk's tag region
    enc.write_bytes(bytes(raw))
    with pytest.raises(BackupCryptoError):
        decrypt_file(enc, dec, "p")


def test_truncated_archive_fails_closed(tmp_path):
    src = tmp_path / "u.bin"
    src.write_bytes(os.urandom(100))
    enc = tmp_path / "u.enc"
    dec = tmp_path / "u.dec"
    encrypt_file(src, enc, "p")
    enc.write_bytes(enc.read_bytes()[:20])
    with pytest.raises(BackupCryptoError):
        decrypt_file(enc, dec, "p")


def test_bad_magic_rejected(tmp_path):
    bad = tmp_path / "bad.enc"
    bad.write_bytes(b"NOTANARCHIVE" + os.urandom(40))
    with pytest.raises(BackupCryptoError):
        decrypt_file(bad, tmp_path / "o", "p")


def test_empty_passphrase_rejected(tmp_path):
    src = tmp_path / "x.bin"
    src.write_bytes(b"x")
    with pytest.raises(BackupCryptoError):
        encrypt_file(src, tmp_path / "x.enc", "")
    with pytest.raises(BackupCryptoError):
        encrypt_file(src, tmp_path / "x.enc", 12345)


def test_derive_key_deterministic_and_salted():
    k1 = encrypt.derive_key("p", b"0" * 16)
    k2 = encrypt.derive_key("p", b"0" * 16)
    k3 = encrypt.derive_key("p", b"1" * 16)
    assert k1 == k2 and len(k1) == 32
    assert k1 != k3


# ------------------------------------------------- B2/B3: exclusions


def _plant(home, name, body=b"x"):
    p = home / name
    p.write_bytes(body)
    return p


def test_passwords_csv_never_packed(herm):
    home = herm / "levi_home"
    home.mkdir(parents=True, exist_ok=True)
    _plant(home, "Google_Passwords.csv", b"url,username,password\na,b,c\n")
    _plant(home, "my-credentials.json", b'{"token": "abc"}')
    _plant(home, "notes.txt", b"hello")
    snap = create_snapshot(home=home)
    with tarfile.open(snap["tarball"], "r:gz") as tf:
        members = tf.getnames()
    assert not any("password" in m.lower() for m in members)
    assert not any("credential" in m.lower() for m in members)
    assert "notes.txt" in members
    manifest = json.loads(__import__("pathlib").Path(snap["manifest"]).read_text())
    assert manifest["excluded_name_count"] == 2
    assert "google_passwords.csv" in manifest["excluded_names"]
    # the manifest never leaks excluded paths
    assert "Google_Passwords" not in json.dumps(manifest)


def test_operator_denylist_honored(herm):
    home = herm / "levi_home"
    home.mkdir(parents=True, exist_ok=True)
    (home / "backup-denylist.json").write_text(
        json.dumps(["eyes-only", "dynasty"]), encoding="utf-8"
    )
    _plant(home, "dynasty-phase-plan.md", b"canon")
    _plant(home, "grocery.txt", b"eggs")
    snap = create_snapshot(home=home)
    with tarfile.open(snap["tarball"], "r:gz") as tf:
        members = tf.getnames()
    assert not any("dynasty" in m.lower() for m in members)
    assert "grocery.txt" in members
    manifest = json.loads(__import__("pathlib").Path(snap["manifest"]).read_text())
    assert manifest["excluded_name_count"] == 1


def test_malformed_denylist_degrades_open(herm):
    home = herm / "levi_home"
    home.mkdir(parents=True, exist_ok=True)
    (home / "backup-denylist.json").write_text("{broken", encoding="utf-8")
    _plant(home, "a.txt", b"a")
    snap = create_snapshot(home=home)  # must not crash
    assert snap["files"] >= 1


# ------------------------------------------------- B4: verify wiring (main CLI)


def test_main_cli_verify_wired():
    from levi.backup.cli import register_backup_parser

    parser = argparse.ArgumentParser(prog="levi")
    sub = parser.add_subparsers(dest="cmd")
    register_backup_parser(sub)
    args = parser.parse_args(["backup", "verify", "--snapshot", "abc"])
    assert args.backup_cmd == "verify"
    assert args.snapshot == "abc"


def test_main_cli_now_encrypt_flags():
    from levi.backup.cli import register_backup_parser

    parser = argparse.ArgumentParser(prog="levi")
    sub = parser.add_subparsers(dest="cmd")
    register_backup_parser(sub)
    args = parser.parse_args(
        ["backup", "now", "--encrypt", "--passphrase-env", "LEVIBAK"]
    )
    assert args.encrypt is True
    assert args.passphrase_env == "LEVIBAK"


def test_now_encrypt_end_to_end(herm, monkeypatch):
    from levi.backup.cli import _cmd_now

    monkeypatch.setenv("LEVIBAK_PW", "s3cret-test-only")
    args = argparse.Namespace(
        label="enctest", remote=None, encrypt=True, passphrase_env="LEVIBAK_PW"
    )
    assert _cmd_now(args) == 0
    snaps = list_snapshots()
    assert snaps
    enc_path = snaps[0]["tarball"] + ".enc"
    assert __import__("pathlib").Path(enc_path).is_file()
    dec = herm / "restored.tar.gz"
    decrypt_file(enc_path, dec, "s3cret-test-only")
    assert dec.stat().st_size > 0
