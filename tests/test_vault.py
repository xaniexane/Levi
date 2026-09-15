"""Vault seal encrypt/decrypt round-trip in a tmp dir.

Skipped with a clear message when ``cryptography`` isn't installed — the
seal is fail-closed by design (no XOR fallback), so nothing is testable
without it.
"""
import pytest

cryptography = pytest.importorskip(
    "cryptography",
    reason=(
        "cryptography is not installed; VaultSeal is fail-closed without it "
        "(install with: pip install cryptography)"
    ),
)

from levi.vault.seal import VaultSeal  # noqa: E402


def test_vault_encrypt_decrypt_bytes_roundtrip(tmp_path):
    seal = VaultSeal(passphrase="test-passphrase", directory=tmp_path / "vault")
    token = seal.encrypt_bytes(b"top secret notes")
    assert seal.decrypt_bytes(token) == b"top secret notes"


def test_vault_put_get_roundtrip(tmp_path):
    seal = VaultSeal(passphrase="test-passphrase", directory=tmp_path / "vault")
    seal.put("journal", "hello, hermetic vault")
    assert seal.get("journal") == "hello, hermetic vault"
    assert "journal" in seal.list_names()


def test_vault_files_are_owner_only(tmp_path):
    import stat

    seal = VaultSeal(passphrase="test-passphrase", directory=tmp_path / "vault")
    path = seal.put("perms", "x")
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600, f"expected 0o600, got {oct(mode)}"


def test_vault_salt_is_unique_per_vault(tmp_path):
    import stat

    a = VaultSeal(passphrase="same-passphrase", directory=tmp_path / "a")
    b = VaultSeal(passphrase="same-passphrase", directory=tmp_path / "b")
    assert a.encrypt_bytes(b"same plaintext") != b.encrypt_bytes(b"same plaintext")
    salt_path = tmp_path / "a" / ".salt"
    assert salt_path.exists()
    assert stat.S_IMODE(salt_path.stat().st_mode) == 0o600
    # Reopening the same vault reuses the salt: data stays readable.
    a2 = VaultSeal(passphrase="same-passphrase", directory=tmp_path / "a")
    assert a2.decrypt_bytes(a.encrypt_bytes(b"roundtrip")) == b"roundtrip"


def test_vault_wrong_passphrase_raises_vault_error(tmp_path):
    from levi.vault.seal import VaultError

    seal = VaultSeal(passphrase="correct", directory=tmp_path / "vault")
    token = seal.encrypt_bytes(b"secret")
    # Fresh vault dir => fresh salt, but the v2 key is wrong regardless;
    # also covers the legacy fallback path failing cleanly.
    wrong = VaultSeal(passphrase="wrong", directory=tmp_path / "other")
    with pytest.raises(VaultError):
        wrong.decrypt_bytes(token)


def test_vault_legacy_v1_seals_still_open(tmp_path):
    """Seals written by the original unsalted-SHA256 scheme remain readable."""
    import base64
    import hashlib
    from cryptography.fernet import Fernet

    legacy_key = hashlib.sha256(b"old-passphrase").digest()
    legacy = Fernet(base64.urlsafe_b64encode(legacy_key))
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "legacy.seal").write_bytes(legacy.encrypt(b"v1 data"))

    seal = VaultSeal(passphrase="old-passphrase", directory=vault_dir)
    assert seal.get("legacy") == "v1 data"


def test_vault_entry_names_are_sanitized(tmp_path):
    from levi.vault.seal import VaultError

    seal = VaultSeal(passphrase="pw", directory=tmp_path / "vault")
    for bad in ("../evil", "..", "a/b", "", "has space", ".hidden", "x" * 65):
        with pytest.raises(VaultError):
            seal.put(bad, "nope")
        with pytest.raises(VaultError):
            seal.get(bad)
    # Nothing escaped the vault directory.
    assert not (tmp_path / "evil.seal").exists()
    seal.put("ok-name_1", "fine")
    assert seal.get("ok-name_1") == "fine"


def test_vault_corrupt_salt_refuses_loudly(tmp_path):
    from levi.vault.seal import VaultError

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / ".salt").write_bytes(b"too-short")
    with pytest.raises(VaultError):
        VaultSeal(passphrase="pw", directory=vault_dir)
