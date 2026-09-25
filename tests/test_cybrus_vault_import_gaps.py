"""Proof gate for the vault_import gap fixes: SAF folder picker (L7),
overwrite guard (L8), honest no-op reporting (L9).

All CSVs here are synthetic, written to tmp_path. The real export at
``~/workspace/user/files/Google_Passwords.csv`` is NEVER opened, read,
logged, or copied by these tests.
"""

import csv
import os
from pathlib import Path

import pytest

from levi.cybrus.vault import CredentialVault
from levi.cybrus import vault_import
from levi.cybrus.vault_import import (
    OverwriteRefusedError,
    SafNotAvailableError,
    describe_import,
    import_google_csv,
    main,
    pick_saf_folder,
    register_saf_picker,
    write_import_report,
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


def _getpass(monkeypatch):
    monkeypatch.setattr(
        "levi.cybrus.vault_import.getpass.getpass", lambda prompt="": PASS
    )


@pytest.fixture
def clean_saf(monkeypatch):
    """Isolate the module-level SAF bridge + env override per test."""
    monkeypatch.delenv(vault_import.SAF_ENV_DIR, raising=False)
    register_saf_picker(None)
    yield
    register_saf_picker(None)
    monkeypatch.delenv(vault_import.SAF_ENV_DIR, raising=False)


# -- L7: SAF folder picker never fabricates a path --------------------------

def test_saf_no_bridge_no_env_refuses_loudly(clean_saf):
    with pytest.raises(SafNotAvailableError) as excinfo:
        pick_saf_folder()
    msg = str(excinfo.value)
    # Honest guidance: names the two real integration paths.
    assert "register_saf_picker" in msg
    assert vault_import.SAF_ENV_DIR in msg


def test_saf_registered_bridge_is_used(clean_saf, tmp_path):
    register_saf_picker(lambda purpose: str(tmp_path))
    assert pick_saf_folder(purpose="csv-import") == tmp_path


def test_saf_bridge_receives_purpose(clean_saf, tmp_path):
    seen = []
    register_saf_picker(lambda purpose: seen.append(purpose) or str(tmp_path))
    pick_saf_folder(purpose="csv-import")
    assert seen == ["csv-import"]


def test_saf_bridge_cancelled_refuses(clean_saf):
    register_saf_picker(lambda purpose: None)
    with pytest.raises(SafNotAvailableError, match="cancelled"):
        pick_saf_folder()


def test_saf_bridge_nonexistent_dir_refuses(clean_saf, tmp_path):
    register_saf_picker(lambda purpose: str(tmp_path / "nope"))
    with pytest.raises(SafNotAvailableError, match="not a directory"):
        pick_saf_folder()


def test_saf_bridge_file_not_dir_refuses(clean_saf, tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("x")
    register_saf_picker(lambda purpose: str(f))
    with pytest.raises(SafNotAvailableError, match="not a directory"):
        pick_saf_folder()


def test_saf_bridge_exception_becomes_saf_error(clean_saf):
    def boom(purpose):
        raise RuntimeError("host blew up")
    register_saf_picker(boom)
    with pytest.raises(SafNotAvailableError, match="bridge failed"):
        pick_saf_folder()


def test_saf_env_dir_used_when_set(clean_saf, tmp_path, monkeypatch):
    monkeypatch.setenv(vault_import.SAF_ENV_DIR, str(tmp_path))
    assert pick_saf_folder() == tmp_path


def test_saf_env_dir_missing_refuses(clean_saf, tmp_path, monkeypatch):
    monkeypatch.setenv(vault_import.SAF_ENV_DIR, str(tmp_path / "missing"))
    with pytest.raises(SafNotAvailableError, match=vault_import.SAF_ENV_DIR):
        pick_saf_folder()


def test_saf_env_dir_wins_over_bridge(clean_saf, tmp_path, monkeypatch):
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setenv(vault_import.SAF_ENV_DIR, str(other))
    register_saf_picker(lambda purpose: str(tmp_path))
    assert pick_saf_folder() == other


def test_saf_unregister_restores_refusal(clean_saf, tmp_path):
    register_saf_picker(lambda purpose: str(tmp_path))
    assert pick_saf_folder() == tmp_path
    register_saf_picker(None)
    with pytest.raises(SafNotAvailableError):
        pick_saf_folder()


# -- L9: honest no-op reporting ----------------------------------------------

def test_noop_report_states_no_changes_applied(tmp_path):
    vault = _vault(tmp_path)
    # Every row a duplicate of a pre-existing vault entry: nothing changes.
    vault.store("dup.example", "user", "vault-secret")
    path = _write_csv(
        tmp_path, [["A", "https://dup.example/", "user", "csv-secret", ""]]
    )
    counts = import_google_csv(path, vault)
    assert counts["imported"] == 0
    report = describe_import(counts)
    assert "no changes applied" in report
    assert "imported=0" in report


def test_noop_all_invalid_states_no_changes_applied(tmp_path):
    vault = _vault(tmp_path)
    path = _write_csv(tmp_path, [["A", "https://a.example/", "u", "", ""]])
    counts = import_google_csv(path, vault)
    assert counts == {"imported": 0, "duplicates": 0, "invalid": 1, "services": 0}
    assert "no changes applied" in describe_import(counts)


def test_successful_import_does_not_claim_no_changes(tmp_path):
    vault = _vault(tmp_path)
    path = _write_csv(tmp_path, [["A", "https://a.example/", "u", "pw", ""]])
    counts = import_google_csv(path, vault)
    assert counts["imported"] == 1
    report = describe_import(counts)
    assert "no changes applied" not in report
    assert report.startswith("imported=1 duplicates=0 invalid=0 services=1")


def test_cli_noop_prints_no_changes_applied(tmp_path, capsys, monkeypatch):
    secret = "NoopSecret-111"
    _getpass(monkeypatch)
    vault = _vault(tmp_path)
    vault.store("dup.example", "user", "vault-secret")
    path = _write_csv(
        tmp_path, [["A", "https://dup.example/", "user", secret, ""]]
    )
    rc = main([str(path), "--vault-dir", str(tmp_path / "vault")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "no changes applied" in out
    assert "imported=0" in out
    # L1 still holds on the no-op path: no credential material printed.
    for leak in (secret, "dup.example", PASS):
        assert leak not in out


# -- L8: overwrite guard -----------------------------------------------------

def test_write_report_creates_new_file(tmp_path):
    counts = {"imported": 2, "duplicates": 1, "invalid": 0, "services": 2}
    target = tmp_path / "reports" / "import.txt"
    result = write_import_report(target, counts)
    assert result == target
    body = target.read_text(encoding="utf-8")
    assert "imported=2 duplicates=1 invalid=0 services=2" in body
    assert "no changes applied" not in body


def test_write_report_refuses_existing_without_opt_in(tmp_path):
    target = tmp_path / "report.txt"
    target.write_text("original\n", encoding="utf-8")
    counts = {"imported": 1, "duplicates": 0, "invalid": 0, "services": 1}
    with pytest.raises(OverwriteRefusedError) as excinfo:
        write_import_report(target, counts)
    # It is a FileExistsError, and the message names the path.
    assert isinstance(excinfo.value, FileExistsError)
    assert str(target) in str(excinfo.value)
    # The original file is untouched.
    assert target.read_text(encoding="utf-8") == "original\n"


def test_write_report_explicit_overwrite_opt_in(tmp_path):
    target = tmp_path / "report.txt"
    target.write_text("original\n", encoding="utf-8")
    counts = {"imported": 0, "duplicates": 3, "invalid": 0, "services": 0}
    write_import_report(target, counts, overwrite=True)
    body = target.read_text(encoding="utf-8")
    assert "original" not in body
    assert "no changes applied" in body


def test_write_report_never_contains_secrets(tmp_path):
    secret = "ReportSecret-999"
    counts = {"imported": 1, "duplicates": 0, "invalid": 0, "services": 1}
    target = tmp_path / "report.txt"
    write_import_report(target, counts)
    body = target.read_text(encoding="utf-8")
    assert secret not in body  # counts-only by construction


def test_cli_report_flag_writes_file(tmp_path, capsys, monkeypatch):
    _getpass(monkeypatch)
    path = _write_csv(tmp_path, [["A", "https://a.example/", "u", "pw", ""]])
    report = tmp_path / "import-report.txt"
    rc = main(
        [str(path), "--vault-dir", str(tmp_path / "vault"),
         "--report-path", str(report)]
    )
    assert rc == 0
    assert report.is_file()
    assert "imported=1" in report.read_text(encoding="utf-8")


def test_cli_report_refuses_overwrite_without_flag(tmp_path, capsys, monkeypatch):
    _getpass(monkeypatch)
    path = _write_csv(tmp_path, [["A", "https://a.example/", "u", "pw", ""]])
    report = tmp_path / "import-report.txt"
    report.write_text("original\n", encoding="utf-8")
    rc = main(
        [str(path), "--vault-dir", str(tmp_path / "vault"),
         "--report-path", str(report)]
    )
    assert rc == 1
    out = capsys.readouterr().out
    assert "refusing to overwrite" in out
    assert report.read_text(encoding="utf-8") == "original\n"


def test_cli_report_overwrite_flag_opts_in(tmp_path, capsys, monkeypatch):
    _getpass(monkeypatch)
    path = _write_csv(tmp_path, [["A", "https://a.example/", "u", "pw", ""]])
    report = tmp_path / "import-report.txt"
    report.write_text("original\n", encoding="utf-8")
    rc = main(
        [str(path), "--vault-dir", str(tmp_path / "vault"),
         "--report-path", str(report), "--overwrite-report"]
    )
    assert rc == 0
    assert "original" not in report.read_text(encoding="utf-8")


# -- CLI --saf wiring --------------------------------------------------------

def test_cli_saf_without_picker_fails_loudly(tmp_path, capsys, monkeypatch, clean_saf):
    _getpass(monkeypatch)
    path = _write_csv(tmp_path, [["A", "https://a.example/", "u", "pw", ""]])
    rc = main(["--saf", str(path), "--vault-dir", str(tmp_path / "vault")])
    assert rc == 1
    out = capsys.readouterr().out
    assert "SAF folder picker unavailable" in out


def test_cli_saf_relative_csv_resolves_in_picked_folder(
    tmp_path, capsys, monkeypatch, clean_saf
):
    _getpass(monkeypatch)
    folder = tmp_path / "picked"
    folder.mkdir()
    _write_csv(folder, [["A", "https://a.example/", "u", "pw", ""]], name="exp.csv")
    monkeypatch.setenv(vault_import.SAF_ENV_DIR, str(folder))
    monkeypatch.chdir(tmp_path)  # bare filename must NOT resolve from cwd
    rc = main(["--saf", "exp.csv", "--vault-dir", str(tmp_path / "vault")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "imported=1" in out


def test_cli_saf_absolute_csv_outside_picked_folder_refused(
    tmp_path, capsys, monkeypatch, clean_saf
):
    _getpass(monkeypatch)
    folder = tmp_path / "picked"
    folder.mkdir()
    monkeypatch.setenv(vault_import.SAF_ENV_DIR, str(folder))
    elsewhere = _write_csv(tmp_path, [["A", "https://a.example/", "u", "pw", ""]])
    rc = main(["--saf", str(elsewhere), "--vault-dir", str(tmp_path / "vault")])
    assert rc == 1
    out = capsys.readouterr().out
    assert "outside the picked folder" in out


# -- R2G-1 / R2G-2: SAF jail covers relative paths and symlinks ------------

def _saf_pair(tmp_path, monkeypatch, clean_saf):
    """A picked SAF folder plus an outside dir holding a valid secret CSV."""
    saf = tmp_path / "saf"
    saf.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _write_csv(
        outside,
        [["X", "https://outside.example/", "evil", "evilpw", ""]],
        name="secret.csv",
    )
    monkeypatch.setenv(vault_import.SAF_ENV_DIR, str(saf))
    return saf, outside


def test_saf_relative_dotdot_is_jailed(tmp_path, monkeypatch, clean_saf):
    """R2G-1: --saf ../outside/secret.csv is refused; vault untouched."""
    _saf_pair(tmp_path, monkeypatch, clean_saf)
    _getpass(monkeypatch)
    rc = main(
        ["--saf", "../outside/secret.csv", "--vault-dir", str(tmp_path / "vault")]
    )
    assert rc == 1
    assert _vault(tmp_path).list_services() == []


def test_saf_symlink_inside_folder_is_jailed(tmp_path, monkeypatch, clean_saf):
    """R2G-2: --saf link.csv where link.csv -> outside file is refused."""
    saf, outside = _saf_pair(tmp_path, monkeypatch, clean_saf)
    (saf / "link.csv").symlink_to(outside / "secret.csv")
    _getpass(monkeypatch)
    rc = main(["--saf", "link.csv", "--vault-dir", str(tmp_path / "vault")])
    assert rc == 1
    assert _vault(tmp_path).list_services() == []


def test_saf_symlinked_subdir_escape_is_jailed(tmp_path, monkeypatch, clean_saf):
    """R2G-2 variant: a symlinked subdirectory inside the picked folder
    must not smuggle an outside CSV in either."""
    saf, outside = _saf_pair(tmp_path, monkeypatch, clean_saf)
    (saf / "sub").symlink_to(outside)
    _getpass(monkeypatch)
    rc = main(
        ["--saf", "sub/secret.csv", "--vault-dir", str(tmp_path / "vault")]
    )
    assert rc == 1
    assert _vault(tmp_path).list_services() == []


# -- R2G-3: report tmp file is symlink-safe ---------------------------------

def test_write_report_ignores_planted_tmp_symlink(tmp_path):
    """R2G-3: a pre-planted <report>.tmp symlink neither diverts the body
    into a victim file nor leaves the report path as a symlink."""
    victim = tmp_path / "victim.txt"
    victim.write_text("VICTIM-ORIGINAL", encoding="utf-8")
    target = tmp_path / "report.txt"
    (tmp_path / "report.txt.tmp").symlink_to(victim)
    counts = {"imported": 1, "duplicates": 0, "invalid": 0, "services": 1}
    write_import_report(target, counts)
    assert victim.read_text(encoding="utf-8") == "VICTIM-ORIGINAL"
    assert not target.is_symlink()
    assert "imported=1" in target.read_text(encoding="utf-8")
    # No stray tmp files left behind.
    assert list(tmp_path.glob("report.txt.*.tmp")) == []


def test_write_report_overwrite_true_replaces_symlink_target(tmp_path):
    """os.replace swaps the symlink itself: with overwrite=True on a
    symlinked report path, the victim behind it is never touched."""
    victim = tmp_path / "victim.txt"
    victim.write_text("VICTIM-ORIGINAL", encoding="utf-8")
    target = tmp_path / "report.txt"
    target.symlink_to(victim)
    counts = {"imported": 0, "duplicates": 1, "invalid": 0, "services": 0}
    write_import_report(target, counts, overwrite=True)
    assert victim.read_text(encoding="utf-8") == "VICTIM-ORIGINAL"
    assert not target.is_symlink()
    assert "no changes applied" in target.read_text(encoding="utf-8")


def test_saf_bridge_non_string_truthy_is_loud_saf_error(clean_saf):
    """RED-3: a bridge returning a non-string truthy value raises
    SafNotAvailableError (L7's loud refusal), not a raw TypeError."""
    register_saf_picker(lambda purpose: 12345)
    with pytest.raises(SafNotAvailableError, match="non-path"):
        pick_saf_folder(purpose="csv-import")


def test_saf_bridge_pathlike_result_accepted(clean_saf, tmp_path):
    """os.PathLike results are legitimate paths, not type confusion."""
    register_saf_picker(lambda purpose: tmp_path)
    assert pick_saf_folder() == tmp_path
