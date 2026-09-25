"""Entrypoint tests: python -m levi.backup (hermetic, no network)."""

import pytest

from levi.backup.__main__ import main


def _herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))


def test_help_exits_zero():
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0


def test_status_empty(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["status"]) == 0
    assert "local snapshots: 0" in capsys.readouterr().out


def test_now_then_status_then_verify(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["now", "--label", "test"]) == 0
    assert "created" in capsys.readouterr().out
    assert main(["status"]) == 0
    assert "local snapshots: 1" in capsys.readouterr().out

    from levi.backup.snapshot import list_snapshots

    sid = list_snapshots()[0]["snapshot_id"]
    assert main(["verify", sid]) == 0
    assert "OK" in capsys.readouterr().out


def test_verify_missing_fails_closed(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["verify", "no-such-snapshot"]) == 1
    assert "FAILED" in capsys.readouterr().out


def test_restore_apply_without_yes_refused(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["now", "--label", "test"]) == 0
    from levi.backup.snapshot import list_snapshots

    sid = list_snapshots()[0]["snapshot_id"]
    # --apply without --yes must fail closed: live state is never touched
    assert main(["restore", sid, "--apply"]) == 2
