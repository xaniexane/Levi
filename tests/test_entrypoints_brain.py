"""Entrypoint tests: python -m levi.brain (hermetic, no network)."""

import pytest

from levi.brain.__main__ import main


def test_help_exits_zero():
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0


def test_table_upsert_and_search(tmp_path, capsys):
    bd = str(tmp_path / "brain")
    assert (
        main(["--brain-dir", bd, "table-upsert", "facts", "sky", "the sky is blue"])
        == 0
    )
    assert main(["--brain-dir", bd, "table-search", "sky"]) == 0
    assert "the sky is blue" in capsys.readouterr().out


def test_table_upsert_empty_value_refused(tmp_path):
    bd = str(tmp_path / "brain")
    assert main(["--brain-dir", bd, "table-upsert", "facts", "sky", ""]) == 1


def test_corpus_add_and_search(tmp_path, capsys):
    bd = str(tmp_path / "brain")
    assert (
        main(
            [
                "--brain-dir",
                bd,
                "corpus-add",
                "observed daylight",
                "--kind",
                "OBSERVED",
                "--source",
                "test",
            ]
        )
        == 0
    )
    assert main(["--brain-dir", bd, "corpus-search", "daylight"]) == 0
    assert "daylight" in capsys.readouterr().out


def test_corpus_add_empty_refused(tmp_path):
    bd = str(tmp_path / "brain")
    assert main(["--brain-dir", bd, "corpus-add", "   "]) == 1


def test_corpus_stats(tmp_path, capsys):
    bd = str(tmp_path / "brain")
    assert main(["--brain-dir", bd, "corpus-stats"]) == 0
    assert "corpus units:" in capsys.readouterr().out


def test_export(tmp_path, capsys):
    bd = str(tmp_path / "brain")
    out = str(tmp_path / "export.md")
    assert main(["--brain-dir", bd, "table-upsert", "facts", "k", "v"]) == 0
    assert main(["--brain-dir", bd, "export", "--out", out]) == 0
    assert "exported brain" in capsys.readouterr().out
