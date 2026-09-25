"""BLUE-1 batch B: vault-import CLI regression proofs (RED-1 F3).

F3 (MEDIUM): ``levi cybrus vault import-csv`` formatted counts with its
own inline f-string and never called ``vault_import.describe_import`` —
a zero-row import printed a bare ``imported=0 ...`` line with no "no
changes applied" (L9 silent-success look). The CLI now prints exactly
``describe_import(counts)``.

Glyph: 💉 | Agent: cfbc6fb1-6ab7-451d-8c11b83ab41 | 2026-09-23
"""

import argparse
import csv
import io
from contextlib import redirect_stdout
from pathlib import Path

from levi.cybrus.__main__ import _cmd_vault_import_csv
from levi.cybrus.vault import CredentialVault
from levi.cybrus import vault_import as vi

PASS = "test-master-passphrase-1"


def _write_csv(path: Path, rows) -> Path:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["name", "url", "username", "password", "note"])
        writer.writerows(rows)
    return path


def _run(args, vault):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = _cmd_vault_import_csv(args, vault)
    return rc, buf.getvalue()


def test_blue_f3_noop_states_no_changes_applied(tmp_path):
    """Attack closure: the no-op CLI line must name the no-op."""
    vault = CredentialVault(PASS, directory=tmp_path / "vault")
    vault.store("dup.example", "user", "vault-secret")
    csv_path = _write_csv(
        tmp_path / "dup.csv",
        [["A", "https://dup.example/", "user", "csv-secret", ""]],
    )
    rc, out = _run(argparse.Namespace(csv_path=str(csv_path)), vault)
    assert rc == 0
    assert out.strip() == vi.describe_import(
        {"imported": 0, "duplicates": 1, "invalid": 0, "services": 0})
    assert "no changes applied" in out


def test_blue_f3_successful_import_reports_counts(tmp_path):
    """Legitimate behavior: a real import prints the counts line."""
    vault = CredentialVault(PASS, directory=tmp_path / "vault")
    csv_path = _write_csv(
        tmp_path / "new.csv",
        [["A", "https://new.example/", "user", "s3cret-pw", ""]],
    )
    rc, out = _run(argparse.Namespace(csv_path=str(csv_path)), vault)
    assert rc == 0
    assert "imported=1" in out
    assert "no changes applied" not in out
    # The secret really landed, and the CLI never printed it.
    assert vault.get("new.example", "user") == "s3cret-pw"
    assert "s3cret-pw" not in out
