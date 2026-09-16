"""Entrypoint tests: python -m levi.academy (hermetic, no network)."""

import pytest

from levi.academy.__main__ import main


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
    assert "Boot Camp" in out
    assert "sessions completed" in out


def test_corpus(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["corpus"]) == 0
    assert "corpus:" in capsys.readouterr().out


def test_research_bad_track_fails_closed(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    assert main(["research", "phishing", "--track", "Z", "--budget", "1"]) == 2


def test_unknown_subcommand_fails_closed():
    with pytest.raises(SystemExit) as e:
        main(["nope"])
    assert e.value.code != 0
