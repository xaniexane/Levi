"""Entrypoint tests: python -m levi.king (hermetic, no network)."""

import pytest

from levi.king.__main__ import main


def _herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))


def test_help_exits_zero():
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0


def test_status(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["status"]) == 0
    assert "King Control Plane" in capsys.readouterr().out


def test_default_action_is_status(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main([]) == 0
    assert "King Control Plane" in capsys.readouterr().out


def test_invalid_action_fails_closed(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as e:
        main(["nope-not-real"])
    assert e.value.code == 2


def test_social_post_unknown_id_sends_nothing(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as e:
        main(["social-post", "--id", "nope"])
    assert e.value.code == 1
    assert "nothing was sent" in capsys.readouterr().err
