"""Tests for the LEVI vault (vault/vault.py).

The passphrase below is TEST-ONLY fixture material. It is not the
keeper's passphrase, never was, and must never be mistaken for one.
"""
import os
import stat
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vault"))

import vault as V

# TEST-ONLY fixture passphrase. Not the keeper's. Never the keeper's.
_TEST_PW = "test-only-fixture-passphrase-0123456789"


@pytest.fixture()
def tree(tmp_path):
    src = tmp_path / "src"
    (src / "core").mkdir(parents=True)
    (src / "core" / "a.py").write_text("print('levi')\n")
    (src / "core" / "b.bin").write_bytes(bytes(range(256)) * 64)
    (src / "README.md").write_text("# test\n")
    (src / "node_modules").mkdir()
    (src / "node_modules" / "huge.js").write_text("x" * 1000)  # must be excluded
    (src / "__pycache__").mkdir()
    (src / "__pycache__" / "a.pyc").write_bytes(b"\x00" * 10)  # excluded
    os.symlink("a.py", src / "core" / "link.py")
    return str(src)


@pytest.fixture()
def vdir(tmp_path):
    return str(tmp_path / "vault")


def _make(tree, vdir, label="t"):
    return V.create_snapshot(tree, vdir, label, _TEST_PW)


def test_create_labels_backend_honestly(tree, vdir):
    info = _make(tree, vdir)
    assert info.backend == V.backend()
    assert info.backend in ("aes-256-gcm", "stdlib-fallback")
    rep = V.crypto_report()
    assert rep["backend"] == info.backend
    assert "honestly labeled" in rep["backend_note"] or "cryptography" in rep["backend_note"]
    assert rep["kdf"] in ("scrypt", "pbkdf2")


def test_locked_folder_perms(tree, vdir):
    info = _make(tree, vdir)
    snaps = os.path.dirname(info.path)
    assert V.check_locked(snaps)["locked"] is True
    assert V.check_locked(snaps)["mode"] == "0o700"
    assert V.check_locked(info.path)["locked"] is True
    assert V.check_locked(info.path)["mode"] == "0o600"


def test_excludes_regenerable_heavies(tree, vdir):
    info = _make(tree, vdir)
    rep = V.verify_snapshot(info.path, _TEST_PW)
    assert rep["files_verified"] == 3  # a.py, b.bin, README.md (+1 symlink, not a file)


def test_list_needs_no_passphrase(tree, vdir):
    info = _make(tree, vdir)
    infos = V.list_snapshots(vdir)
    assert len(infos) == 1
    assert infos[0].label == "t"
    assert infos[0].backend == info.backend


def test_verify_roundtrip(tree, vdir):
    info = _make(tree, vdir)
    rep = V.verify_snapshot(info.path, _TEST_PW)
    assert rep["ok"] is True
    assert rep["files_verified"] == 3


def test_restore_roundtrip_byte_identical(tree, vdir, tmp_path):
    info = _make(tree, vdir)
    dest = str(tmp_path / "out")
    rep = V.restore_snapshot(info.path, dest, _TEST_PW)
    assert rep["ok"] is True
    assert open(os.path.join(dest, "core", "a.py")).read() == "print('levi')\n"
    assert open(os.path.join(dest, "core", "b.bin"), "rb").read() == bytes(range(256)) * 64
    assert os.path.islink(os.path.join(dest, "core", "link.py"))
    assert not os.path.exists(os.path.join(dest, "node_modules"))
    assert not os.path.exists(os.path.join(dest, "__pycache__"))


def test_wrong_passphrase_fails_closed(tree, vdir):
    info = _make(tree, vdir)
    with pytest.raises(V.VaultError):
        V.verify_snapshot(info.path, "wrong-passphrase-not-the-keepers-either")


def test_tampered_bundle_fails(tree, vdir):
    info = _make(tree, vdir)
    data = bytearray(open(info.path, "rb").read())
    data[len(data) // 2] ^= 0x01  # flip a ciphertext bit
    bad = info.path + ".bad"
    with open(bad, "wb") as f:
        f.write(bytes(data))
    os.chmod(bad, 0o600)
    with pytest.raises(V.VaultError):
        V.verify_snapshot(bad, _TEST_PW)


def test_tampered_header_fails(tree, vdir):
    info = _make(tree, vdir)
    data = bytearray(open(info.path, "rb").read())
    data[10] ^= 0x01  # inside the plaintext header (AAD-bound)
    bad = info.path + ".bad2"
    with open(bad, "wb") as f:
        f.write(bytes(data))
    os.chmod(bad, 0o600)
    with pytest.raises(V.VaultError):
        V.verify_snapshot(bad, _TEST_PW)


def test_bad_magic_fails(tree, vdir):
    info = _make(tree, vdir)
    data = bytearray(open(info.path, "rb").read())
    data[0:3] = b"XXX"
    bad = info.path + ".bad3"
    with open(bad, "wb") as f:
        f.write(bytes(data))
    os.chmod(bad, 0o600)
    with pytest.raises(V.VaultError):
        V.verify_snapshot(bad, _TEST_PW)


def test_restore_refuses_nonempty_dest(tree, vdir, tmp_path):
    info = _make(tree, vdir)
    dest = str(tmp_path / "out")
    os.makedirs(dest)
    open(os.path.join(dest, "existing.txt"), "w").write("mine")
    with pytest.raises(V.VaultError):
        V.restore_snapshot(info.path, dest, _TEST_PW)
    rep = V.restore_snapshot(info.path, dest, _TEST_PW, force=True)
    assert rep["ok"] is True


def test_passphrase_from_env(tree, vdir, monkeypatch):
    monkeypatch.setenv("LEVI_VAULT_PASSPHRASE", _TEST_PW)
    assert V.get_passphrase() == _TEST_PW


def test_empty_passphrase_refused(monkeypatch):
    monkeypatch.setenv("LEVI_VAULT_PASSPHRASE", "")
    with pytest.raises(V.VaultError):
        V.get_passphrase()


def test_short_passphrase_refused_on_create(monkeypatch):
    monkeypatch.setenv("LEVI_VAULT_PASSPHRASE", "short")
    with pytest.raises(V.VaultError):
        V.get_passphrase(confirm=True)


def test_stdlib_fallback_is_labeled_not_silent(tree, vdir, monkeypatch, tmp_path):
    monkeypatch.setattr(V, "_AESGCM", None)
    assert V.backend() == "stdlib-fallback"
    info = V.create_snapshot(tree, vdir, "fallback", _TEST_PW)
    assert info.backend == "stdlib-fallback"
    assert open(info.path, "rb").read(3) == b"LV1"
    rep = V.verify_snapshot(info.path, _TEST_PW)
    assert rep["ok"] is True
    dest = str(tmp_path / "out")
    r = V.restore_snapshot(info.path, dest, _TEST_PW)
    assert r["ok"] is True


def test_gcm_bundle_without_cryptography_fails_closed_loudly(tree, vdir, monkeypatch):
    info = _make(tree, vdir)
    if not open(info.path, "rb").read(3) == b"LV2":
        pytest.skip("GCM backend not available on this machine")
    monkeypatch.setattr(V, "_AESGCM", None)
    with pytest.raises(V.VaultError, match="cryptography"):
        V.verify_snapshot(info.path, _TEST_PW)
