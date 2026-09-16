"""Entrypoint tests: python -m levi.memory (hermetic, no network)."""

import pytest

from levi.memory.__main__ import main


def _herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))


def test_help_exits_zero():
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0


def test_add_search_get_delete_roundtrip(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert (
        main(
            ["add", "Chauncey likes oolong", "--type", "preference", "--tags", "drink"]
        )
        == 0
    )
    out = capsys.readouterr().out
    entry_id = out.split()[1]

    assert main(["search", "oolong"]) == 0
    assert "oolong" in capsys.readouterr().out

    assert main(["get", entry_id]) == 0
    assert "preference" in capsys.readouterr().out

    assert main(["delete", entry_id]) == 0
    assert main(["get", entry_id]) == 1  # gone now


def test_stats_json(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["add", "a fact", "--type", "semantic"]) == 0
    capsys.readouterr()  # drain the "added ..." line
    assert main(["stats"]) == 0
    import json

    payload = json.loads(capsys.readouterr().out)
    assert payload["total"] == 1
    assert payload["by_type"]["semantic"] == 1


def test_add_invalid_type_fails_closed(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as e:
        main(["add", "x", "--type", "bogus"])
    assert e.value.code == 2


def test_get_unknown_fails_closed(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["get", "nope"]) == 1


def test_hierarchy_and_explain(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["hierarchy"]) == 0
    assert "Memory Hierarchy" in capsys.readouterr().out
    assert main(["explain", "the sky is blue"]) == 0
