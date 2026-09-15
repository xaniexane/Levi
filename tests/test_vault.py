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
