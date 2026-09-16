"""Entrypoint tests: python -m levi.growth (hermetic, no network)."""

import pytest

from levi.growth.__main__ import main


def _herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))


def test_help_exits_zero():
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0


def test_status(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert "stage:" in out
    assert "cycles completed" in out


def test_cycle_dry_run_writes_nothing(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["cycle", "--dry-run", "--no-model"]) == 0
    out = capsys.readouterr().out
    assert "dry_run=True" in out
    # dry run must not journal a cycle
    assert main(["journal"]) == 0
    assert "journal is empty" in capsys.readouterr().out


def test_journal_empty(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["journal"]) == 0
    assert "journal is empty" in capsys.readouterr().out


def test_forget_documents_policy(capsys):
    # fail-closed with a non-zero exit: growth journal is append-only
    assert main(["forget"]) == 2
    assert "append-only" in capsys.readouterr().err
