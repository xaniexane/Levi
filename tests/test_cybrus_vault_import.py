"""Tests for levi.cybrus.vault_import — the proof gate for the importer laws.

L1 no-leak · L2 encrypted-rest · L3 atomic-batch · L4 keep-first ·
L5 safe-names · L6 local-only.

All CSVs here are synthetic, written to tmp_path. The real export at
``~/workspace/user/files/Google_Passwords.csv`` is NEVER opened, read,
logged, or copied by these tests.
"""

import csv
from pathlib import Path

import pytest

from levi.cybrus.vault import CredentialVault
from levi.cybrus.vault_import import (
    CsvImportError,
    _canonical_service,
    _canonical_username,
    import_google_csv,
    main,
)

PASS = "test-master-passphrase-1"


def _vault(tmp_path: Path) -> CredentialVault:
    return CredentialVault(PASS, directory=tmp_path / "vault")


def _write_csv(tmp_path: Path, rows, name="import.csv") -> Path:
    path = tmp_path / name
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["name", "url", "username", "password", "note"])
        writer.writerows(rows)
    return path


# -- L5: URL -> service mapping --------------------------------------------

@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://accounts.google.com/signin", "accounts.google.com"),
        ("https://Example.COM:8443/a/b?x=1", "example.com"),
        ("http://sub.domain.co.uk/", "sub.domain.co.uk"),
        ("example.org/no-scheme", "example.org"),  # bare host tolerated
        ("https://user:pass@host.io:1/x", "host.io"),  # userinfo/port stripped
    ],
)
def test_url_to_service_mapping(url, expected):
    assert _canonical_service(url) == expected


def test_service_fallback_is_deterministic():
    a = _canonical_service("not a url at all")
    b = _canonical_service("not a url at all")
    assert a == b
    assert a.startswith("csv-import-")
    assert len(a) == len("csv-import-") + 12
    # different garbage -> different service (sha1)
    assert _canonical_service("other garbage") != a


def test_service_long_host_truncated():
    long_host = "https://" + "a" * 200 + ".com/"
    svc = _canonical_service(long_host)
    assert len(svc) <= 64
    assert _canonical_service(long_host) == svc  # deterministic


# -- L5: username sanitization ----------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("user@example.com", "user_at_example.com"),
        ("plain-name_1", "plain-name_1"),
        ("weird!name#here", "weirdnamehere"),
        ("  spaced  ", "spaced"),
    ],
)
def test_username_sanitization(raw, expected):
    assert _canonical_username(raw) == expected


def test_username_empty_is_invalid():
    assert _canonical_username("") is None
    assert _canonical_username("   ") is None


def test_username_truncated_to_64():
    assert len(_canonical_username("u" * 200)) == 64


# -- import behavior --------------------------------------------------------

def test_import_counts_and_roundtrip(tmp_path):
    vault = _vault(tmp_path)
    path = _write_csv(
        tmp_path,
        [
            ["Google", "https://accounts.google.com/x", "me@gmail.com", "s3cret-one", ""],
            ["GitHub", "https://github.com/login", "dev", "s3cret-two", "note"],
            ["Bad", "https://bad.example/", "nouser", "", ""],  # no password -> invalid
        ],
    )
    counts = import_google_csv(path, vault)
    assert counts == {"imported": 2, "duplicates": 0, "invalid": 1, "services": 2}
    # Round-trip through the encrypted vault proves L2 storage path.
    assert vault.get("accounts.google.com", "me_at_gmail.com") == "s3cret-one"
    assert vault.get("github.com", "dev") == "s3cret-two"


def test_duplicates_keep_first_within_csv(tmp_path):
    vault = _vault(tmp_path)
    path = _write_csv(
        tmp_path,
        [
            ["A", "https://dup.example/", "user", "first-secret", ""],
            ["B", "https://dup.example/", "user", "second-secret", ""],
        ],
    )
    counts = import_google_csv(path, vault)
    assert counts["imported"] == 1
    assert counts["duplicates"] == 1
    assert vault.get("dup.example", "user") == "first-secret"  # L4: first wins


def test_duplicates_keep_first_against_vault(tmp_path):
    vault = _vault(tmp_path)
    vault.store("dup.example", "user", "vault-secret")
    path = _write_csv(tmp_path, [["A", "https://dup.example/", "user", "csv-secret", ""]])
    counts = import_google_csv(path, vault)
    assert counts["imported"] == 0
    assert counts["duplicates"] == 1
    assert vault.get("dup.example", "user") == "vault-secret"


def test_counts_add_up(tmp_path):
    vault = _vault(tmp_path)
    rows = [
        ["A", "https://a.example/", "u1", "p1", ""],
        ["B", "https://b.example/", "u2", "p2", ""],
        ["C", "https://a.example/", "u1", "p3", ""],  # duplicate
        ["D", "https://d.example/", "u4", "", ""],  # invalid: no password
        ["E", "https://e.example/", "", "p5", ""],  # invalid: no username
    ]
    counts = import_google_csv(_write_csv(tmp_path, rows), vault)
    assert counts["imported"] + counts["duplicates"] + counts["invalid"] == len(rows)
    assert counts == {"imported": 2, "duplicates": 1, "invalid": 2, "services": 2}


def test_unknown_duplicate_mode_rejected(tmp_path):
    vault = _vault(tmp_path)
    path = _write_csv(tmp_path, [["A", "https://a.example/", "u", "p", ""]])
    with pytest.raises(ValueError):
        import_google_csv(path, vault, on_duplicate="overwrite")


# -- L3: atomicity — failure leaves the vault unchanged ---------------------

def test_bad_header_leaves_vault_untouched(tmp_path):
    vault = _vault(tmp_path)
    vault.store("pre.example", "keeper", "keep-me")  # pre-existing entry
    bad = tmp_path / "bad.csv"
    bad.write_text("name,url,username,note\nA,https://x.example/,u,n\n", encoding="utf-8")
    with pytest.raises(CsvImportError):
        import_google_csv(bad, vault)
    # Vault unchanged: original entry intact, nothing new.
    assert vault.list_services() == ["pre.example"]
    assert vault.get("pre.example", "keeper") == "keep-me"


def test_missing_file_leaves_vault_untouched(tmp_path):
    vault = _vault(tmp_path)
    with pytest.raises(CsvImportError):
        import_google_csv(tmp_path / "nope.csv", vault)
    assert vault.list_services() == []


def test_non_utf8_file_rejected(tmp_path):
    vault = _vault(tmp_path)
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"name,url,username,password,note\n\xff\xfe invalid\n")
    with pytest.raises(CsvImportError):
        import_google_csv(bad, vault)
    assert vault.list_services() == []


# -- L2: no plaintext at rest ------------------------------------------------

def test_no_plaintext_password_in_blob(tmp_path):
    vault = _vault(tmp_path)
    secret = "SuperSecretPW-987654321"
    path = _write_csv(tmp_path, [["A", "https://a.example/", "u", secret, ""]])
    import_google_csv(path, vault)
    blob = (tmp_path / "vault" / "entries.enc").read_bytes()
    assert secret.encode() not in blob


# -- L1: counts-only reporting ----------------------------------------------

def test_cli_prints_counts_only(tmp_path, capsys, monkeypatch):
    secret = "CliSecret-13579"
    username = "cliuser@example.com"
    url = "https://cli.example/login"
    path = _write_csv(tmp_path, [["Site", url, username, secret, "note"]])
    monkeypatch.setattr(
        "levi.cybrus.vault_import.getpass.getpass", lambda prompt="": PASS
    )
    rc = main([str(path), "--vault-dir", str(tmp_path / "vault")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "imported=1 duplicates=0 invalid=0 services=1" in out
    # L1: no credential material in stdout.
    for leak in (secret, username, url, "cli.example", PASS):
        assert leak not in out


def test_cli_reports_import_failure_without_values(tmp_path, capsys, monkeypatch):
    bad = tmp_path / "bad.csv"
    bad.write_text("name,url\nA,B\n", encoding="utf-8")
    monkeypatch.setattr(
        "levi.cybrus.vault_import.getpass.getpass", lambda prompt="": PASS
    )
    rc = main([str(bad), "--vault-dir", str(tmp_path / "vault")])
    assert rc == 1
    out = capsys.readouterr().out
    assert "error: import failed" in out


def test_return_dict_contains_no_secrets(tmp_path):
    vault = _vault(tmp_path)
    secret = "ReturnSecret-24680"
    path = _write_csv(tmp_path, [["A", "https://r.example/", "ruser", secret, ""]])
    counts = import_google_csv(path, vault)
    flat = repr(counts)
    assert secret not in flat
    assert "ruser" not in flat
    assert set(counts) == {"imported", "duplicates", "invalid", "services"}
