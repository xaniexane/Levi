"""Tests for the Cybrus CLI ``vault import-csv`` / ``vault import-receipt``
wiring in ``levi.cybrus.__main__`` — the proof gate for the CLI-layer laws.

LAWS (invariants; these tests are the machine-checkable proof gate —
never called "formal proof"):

  C1 counts-only:   on success ``import-csv`` prints exactly one line —
                    ``imported=%d duplicates=%d invalid=%d services=%d`` —
                    and nothing else. On failure it prints one
                    ``error: import failed:`` line and returns 1.
  C2 no-leak:       no stdout from either command ever contains a
                    password, a username, or a URL. Error lines name row
                    numbers/reasons only (inherited from the importer),
                    never values.
  C3 getpass-only:  the master passphrase is never taken via argv. Tests
                    drive ``_cmd_vault`` with argparse namespaces and
                    monkeypatch the vault open — no argv secret path exists.
  C4 receipt-meta:  ``import-receipt`` prints counts plus service names
                    (one per line, same as ``list``), read-only. NEVER
                    usernames, NEVER secrets.
  C5 fail-clean:    a bad CSV returns 1 with an ``error: import failed:``
                    line — and leaks nothing.

All CSVs here are synthetic, written to tmp_path. The real export at
``~/workspace/user/files/Google_Passwords.csv`` is NEVER opened, read,
logged, or copied by these tests.
"""

import argparse
import csv
from pathlib import Path

import pytest

import levi.cybrus.__main__ as cli
from levi.cybrus.vault import CredentialVault

PASS = "test-master-passphrase-1"

# Deliberately synthetic secrets; assertions below prove they never leak.
PW_1 = "synth-hunter2-alpha-001"
PW_2 = "synth-hunter2-beta-002"
PW_3 = "synth-hunter2-gamma-003"
USER_1 = "alice.synth@example.com"
USER_2 = "bob.synth@example.com"
URL_1 = "https://portal.synth.example/login"
URL_2 = "https://mail.synth.example/inbox"
SECRET_TOKENS = (PW_1, PW_2, PW_3, USER_1, USER_2, URL_1, URL_2)


@pytest.fixture
def vault(tmp_path: Path) -> CredentialVault:
    return CredentialVault(PASS, directory=tmp_path / "vault")


@pytest.fixture
def cli_vault(monkeypatch, vault):
    """Point the CLI's vault open at the tmp vault — never the real one."""
    monkeypatch.setattr(cli, "_open_vault", lambda: (vault, PASS))
    return vault


def _write_csv(tmp_path: Path, rows, name="import.csv") -> Path:
    path = tmp_path / name
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["name", "url", "username", "password", "note"])
        writer.writerows(rows)
    return path


def _run(vault_cmd, **kwargs) -> int:
    args = argparse.Namespace(vault_cmd=vault_cmd, **kwargs)
    return cli._cmd_vault(args)


def _assert_no_leak(stdout: str):
    for token in SECRET_TOKENS:
        assert token not in stdout, f"secret leaked to stdout: {token!r}"
    assert "alice_at_synth.example.com" not in stdout
    assert "bob_at_synth.example.com" not in stdout


GOOD_ROWS = [
    ("Portal", URL_1, USER_1, PW_1, ""),
    ("Mail", URL_2, USER_2, PW_2, ""),
]


# -- C1/C2: import-csv prints counts only, never secrets --------------------

def test_import_csv_prints_counts_only(cli_vault, tmp_path, capsys):
    csv_path = _write_csv(
        tmp_path,
        [
            *GOOD_ROWS,
            ("Portal dup", URL_1, USER_1, "other-secret-never-stored", ""),  # duplicate
            ("No password", "https://bad.synth.example/", "carol.synth@example.com", "", ""),  # invalid
        ],
    )
    rc = _run("import-csv", csv_path=str(csv_path))
    out = capsys.readouterr().out
    assert rc == 0
    assert out == "imported=2 duplicates=1 invalid=1 services=2\n"
    _assert_no_leak(out)


def test_import_csv_no_secrets_in_stdout(cli_vault, tmp_path, capsys):
    # usernames with '@' get canonicalized; neither raw nor canonical
    # forms may appear in output.
    csv_path = _write_csv(tmp_path, GOOD_ROWS + [("Third", URL_1, "zed.synth@example.com", PW_3, "")])
    rc = _run("import-csv", csv_path=str(csv_path))
    out = capsys.readouterr().out
    assert rc == 0
    _assert_no_leak(out)
    assert "zed.synth@example.com" not in out
    assert "zed_at_synth.example.com" not in out


# -- C5: bad CSV -> return 1, no leak ---------------------------------------

def test_import_csv_bad_csv_returns_1_no_leak(cli_vault, tmp_path, capsys):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("name,url\nx,y\n", encoding="utf-8")
    rc = _run("import-csv", csv_path=str(csv_path))
    out = capsys.readouterr().out
    assert rc == 1
    assert out.startswith("error: import failed:")
    _assert_no_leak(out)


def test_import_csv_missing_file_returns_1_no_leak(cli_vault, tmp_path, capsys):
    rc = _run("import-csv", csv_path=str(tmp_path / "nope.csv"))
    out = capsys.readouterr().out
    assert rc == 1
    assert out.startswith("error: import failed:")
    _assert_no_leak(out)


def test_import_csv_failure_leaves_vault_untouched(cli_vault, tmp_path, capsys):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("name,url\nx,y\n", encoding="utf-8")
    assert _run("import-csv", csv_path=str(csv_path)) == 1
    capsys.readouterr()
    # vault untouched: receipt shows zero services
    assert _run("import-receipt") == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "services=0 entries=0 csv-import-fallbacks=0"


# -- C4: import-receipt is metadata-only -----------------------------------

def test_import_receipt_counts_names_no_secrets(cli_vault, tmp_path, capsys):
    csv_path = _write_csv(
        tmp_path,
        [
            ("Portal", URL_1, USER_1, PW_1, ""),
            ("Portal second user", URL_1, "zed.synth@example.com", PW_3, ""),
            ("Mail", URL_2, USER_2, PW_2, ""),
        ],
    )
    assert _run("import-csv", csv_path=str(csv_path)) == 0
    capsys.readouterr()

    assert _run("import-receipt") == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0] == "services=2 entries=3 csv-import-fallbacks=0"
    assert lines[1:] == ["mail.synth.example", "portal.synth.example"]
    _assert_no_leak(out)
    assert "zed.synth@example.com" not in out


def test_import_receipt_counts_csv_import_fallbacks(cli_vault, tmp_path, capsys):
    csv_path = _write_csv(
        tmp_path,
        [
            ("Good", URL_1, USER_1, PW_1, ""),
            ("Garbage URL", "not a url at all", USER_2, PW_2, ""),
        ],
    )
    assert _run("import-csv", csv_path=str(csv_path)) == 0
    capsys.readouterr()

    assert _run("import-receipt") == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0] == "services=2 entries=2 csv-import-fallbacks=1"
    assert lines[1:] == ["csv-import-1edc88d0873a", "portal.synth.example"]
    _assert_no_leak(out)


def test_import_receipt_fallback_count_is_prefix_based(cli_vault, capsys):
    # Honesty guard for the docstring caveat: the fallback count is purely
    # prefix-based. A hand-stored service reusing the ``csv-import-``
    # prefix is counted too — the receipt reports what the name carries,
    # not how the service got there.
    cli_vault.store("csv-import-manual", "someone", "secret-value-x")
    assert _run("import-receipt") == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "services=1 entries=1 csv-import-fallbacks=1"
    assert "secret-value-x" not in out
    assert "someone" not in out


def test_import_receipt_empty_vault(cli_vault, capsys):
    assert _run("import-receipt") == 0
    out = capsys.readouterr().out
    assert out == "services=0 entries=0 csv-import-fallbacks=0\n"
    _assert_no_leak(out)


# -- C3: secrets never via argv ---------------------------------------------

def test_import_csv_takes_no_secret_argv(capsys):
    """The import-csv parser accepts only csv_path — no password/passphrase flag."""
    with pytest.raises(SystemExit) as exc:
        cli.main(["vault", "import-csv", "--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "csv_path" in help_text
    assert "--password" not in help_text
    assert "--passphrase" not in help_text
    assert "--master" not in help_text
