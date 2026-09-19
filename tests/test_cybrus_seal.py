"""Tests for levi.cybrus.seal — SealedEnvelope (hermetic)."""

import hashlib

import pytest

from levi.cybrus.seal import SealError, SealedEnvelope


@pytest.fixture()
def seal(tmp_path):
    return SealedEnvelope("keeper-test-passphrase", directory=tmp_path / "env")


def test_roundtrip(seal):
    seal.seal_text("note1", "the quick brown fox")
    assert seal.open_text("note1") == "the quick brown fox"


def test_backend_reported(seal):
    assert seal.backend in ("fernet", "stdlib-fallback")


def test_wrong_passphrase_fails(tmp_path):
    s1 = SealedEnvelope("right", directory=tmp_path / "env")
    s1.seal_text("n", "secret")
    s2 = SealedEnvelope("wrong", directory=tmp_path / "env")
    with pytest.raises(SealError):
        s2.open_text("n")


def test_tampered_envelope_fails(seal, tmp_path):
    path = seal.seal_text("n", "secret")
    raw = bytearray(path.read_bytes())
    # Flip a byte in the tail (ciphertext region), keeping the header valid.
    raw[-1] ^= 0x01
    path.write_bytes(bytes(raw))
    with pytest.raises(SealError):
        seal.open_text("n")


def test_missing_envelope_raises(seal):
    with pytest.raises(FileNotFoundError):
        seal.open_text("does-not-exist")


def test_empty_passphrase_rejected(tmp_path):
    with pytest.raises(ValueError):
        SealedEnvelope("", directory=tmp_path)


def test_unsafe_names_rejected(seal):
    for bad in ("../x", "a/b", ".hidden", "", "x" * 70):
        with pytest.raises(ValueError):
            seal.seal_text(bad, "nope")


def test_list_names(seal):
    seal.seal_text("a", "1")
    seal.seal_text("b", "2")
    assert seal.list_names() == ["a", "b"]


def test_permissions_hardened(seal, tmp_path):
    import os

    path = seal.seal_text("n", "secret")
    assert oct(os.stat(path).st_mode & 0o777) == "0o600"
    assert oct(os.stat(seal.dir).st_mode & 0o777) == "0o700"


def test_legacy_x1_read_and_migrate(seal):
    key = hashlib.sha256(b"keeper-test-passphrase").digest()
    ct = bytes(b ^ key[i % len(key)] for i, b in enumerate(b"old keeper secret"))
    path = seal.dir / "legacy.envelope"
    path.write_bytes(b"X1" + ct)
    # Legacy blobs stay readable with the same passphrase.
    assert seal.open_text("legacy") == "old keeper secret"
    # migrate() re-seals into the current format.
    assert seal.migrate("legacy") is True
    assert not path.read_bytes().startswith(b"X1")
    assert seal.open_text("legacy") == "old keeper secret"
    # Non-legacy envelopes report False.
    seal.seal_text("fresh", "new")
    assert seal.migrate("fresh") is False


def test_unrecognized_format_rejected(seal):
    path = seal.seal_text("n", "secret")
    path.write_bytes(b"ZZ9-garbage")
    with pytest.raises(SealError):
        seal.open_text("n")


def test_cross_backend_self_describing(tmp_path):
    # A blob sealed by one backend opens under the other; headers differ.
    s = SealedEnvelope("pw", directory=tmp_path / "env")
    blob = s.seal_bytes(b"data")
    assert blob[:2] in (b"LS",) or blob[:4] == b"LSF1" or blob[:3] == b"LS1"
    assert s.open_bytes(blob) == b"data"
