"""Tests for the checksum plugin — honest stdlib file integrity."""

import hashlib

import pytest

from levi.plugins.checksum import ChecksumConnector, hash_file, verify_file
from levi.plugins.registry import (
    InvalidParams,
    get_connector,
    list_connectors,
)


@pytest.fixture()
def sample(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_bytes(b"levi checksum fixture\n")
    return str(f), [str(tmp_path)]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_hash_known_content(sample):
    path, roots = sample
    out = hash_file(path, "sha256", roots)
    assert out["digest"] == _sha256(b"levi checksum fixture\n")
    assert out["algorithm"] == "sha256"
    assert out["bytes"] == len(b"levi checksum fixture\n")
    assert out["path"].endswith("sample.txt")


def test_hash_sha512_length(sample):
    path, roots = sample
    out = hash_file(path, "sha512", roots)
    assert len(out["digest"]) == 128


def test_verify_match(sample):
    path, roots = sample
    want = _sha256(b"levi checksum fixture\n")
    out = verify_file(path, want, "sha256", roots)
    assert out["match"] is True
    assert out["actual"] == want


def test_verify_mismatch(sample):
    path, roots = sample
    out = verify_file(path, "0" * 64, "sha256", roots)
    assert out["match"] is False
    assert out["actual"] == _sha256(b"levi checksum fixture\n")


def test_deny_closed_relative_path(sample):
    _path, roots = sample
    with pytest.raises(InvalidParams):
        hash_file("relative/path.txt", "sha256", roots)


def test_deny_closed_outside_roots(sample):
    path, _roots = sample
    with pytest.raises(InvalidParams):
        hash_file(path, "sha256", ["/definitely/not/allowed"])


def test_deny_closed_directory(tmp_path):
    with pytest.raises(InvalidParams):
        hash_file(str(tmp_path), "sha256", [str(tmp_path)])


def test_deny_closed_missing_file(tmp_path):
    with pytest.raises(InvalidParams):
        hash_file(str(tmp_path / "nope.txt"), "sha256", [str(tmp_path)])


def test_deny_closed_unknown_algorithm(sample):
    path, roots = sample
    with pytest.raises(InvalidParams):
        hash_file(path, "md5-fancy", roots)


def test_deny_closed_bad_expected_hex(sample):
    path, roots = sample
    with pytest.raises(InvalidParams):
        verify_file(path, "not-hex-at-all", "sha256", roots)
    with pytest.raises(InvalidParams):
        verify_file(path, "abcd", "sha256", roots)  # wrong length


def test_connector_registered():
    c = get_connector("checksum")
    assert isinstance(c, ChecksumConnector)
    assert any(x.id == "checksum" for x in list_connectors())
    # read-only connector: no write capability can ever flip confirmation
    assert c.requires_confirmation is False
    assert c.credential() == "public"


def test_execute_hash_ok(sample):
    path, roots = sample
    c = get_connector("checksum")
    result = c.execute(
        "hash", {"path": path, "algorithm": "sha256", "allowed_roots": roots}
    )
    assert result.ok is True
    assert result.data["digest"] == _sha256(b"levi checksum fixture\n")


def test_execute_verify_ok(sample):
    path, roots = sample
    c = get_connector("checksum")
    result = c.execute(
        "verify",
        {
            "path": path,
            "expected": _sha256(b"levi checksum fixture\n"),
            "allowed_roots": roots,
        },
    )
    assert result.ok is True
    assert result.data["match"] is True


def test_execute_unknown_operation_denied(sample):
    path, roots = sample
    c = get_connector("checksum")
    result = c.execute("explode", {"path": path, "allowed_roots": roots})
    assert result.ok is False


def test_execute_refusal_is_not_ok(sample):
    path, _roots = sample
    c = get_connector("checksum")
    result = c.execute(
        "hash", {"path": path, "allowed_roots": ["/definitely/not/allowed"]}
    )
    assert result.ok is False
    assert result.status == "invalid_params"
