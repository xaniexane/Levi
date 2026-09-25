"""Tests for the wordbook customization (his words, kept verbatim)."""

import json

import pytest

from levi.customizations import wordbook
from levi.customizations.wordbook import WordbookError


@pytest.fixture()
def root(tmp_path):
    return tmp_path / "customizations"


def test_add_and_get_roundtrip(root):
    entry = wordbook.add_term(
        "The Plumb Line",
        "hang the law, read the evidence",
        note="verification pattern",
        root=root,
    )
    assert entry["term"] == "The Plumb Line"
    got = wordbook.get("the plumb line", root=root)
    assert got is not None
    assert got["phrasing"] == "hang the law, read the evidence"
    assert "added" in got


def test_case_insensitive_no_silent_duplicates(root):
    wordbook.add_term("Echo", "the original name", root=root)
    with pytest.raises(WordbookError, match="already worded"):
        wordbook.add_term("ECHO", "something else", root=root)


def test_deny_closed_inputs(root):
    with pytest.raises(WordbookError, match="non-empty string"):
        wordbook.add_term("   ", "phrasing", root=root)
    with pytest.raises(WordbookError, match="non-empty"):
        wordbook.add_term("term", "   ", root=root)
    with pytest.raises(WordbookError, match="exceeds 64 chars"):
        wordbook.add_term("t" * 65, "phrasing", root=root)
    with pytest.raises(WordbookError, match="exceeds 500 chars"):
        wordbook.add_term("term", "p" * 501, root=root)
    with pytest.raises(WordbookError, match="non-empty string"):
        wordbook.get("", root=root)


def test_get_missing_returns_none(root):
    assert wordbook.get("never-worded", root=root) is None


def test_retire_keeps_provenance(root):
    wordbook.add_term("doom engine", "old framing", note="struck", root=root)
    record = wordbook.retire("DOOM ENGINE", reason="his word: struck", root=root)
    assert record["reason"] == "his word: struck"
    assert "retired_at" in record
    assert wordbook.get("doom engine", root=root) is None
    # The ledger holds it — nothing deleted.
    data = json.loads((root / "wordbook.json").read_text(encoding="utf-8"))
    assert len(data["retired"]) == 1
    assert data["retired"][0]["term"] == "doom engine"
    assert data["retired"][0]["phrasing"] == "old framing"


def test_retire_missing_refused(root):
    with pytest.raises(WordbookError, match="not in the wordbook"):
        wordbook.retire("ghost", root=root)


def test_restore_brings_back_latest(root):
    wordbook.add_term("kfx", "absorb reverse improve return", root=root)
    wordbook.retire("kfx", reason="v1", root=root)
    entry = wordbook.restore("KFX", root=root)
    assert entry["phrasing"] == "absorb reverse improve return"
    assert "restored" in entry
    with pytest.raises(WordbookError, match="already active"):
        wordbook.restore("kfx", root=root)
    with pytest.raises(WordbookError, match="no retired record"):
        wordbook.restore("never", root=root)


def test_list_sorted_deterministic(root):
    wordbook.add_term("zulu", "z", root=root)
    wordbook.add_term("Alpha", "a", root=root)
    wordbook.add_term("mike", "m", root=root)
    names = [e["term"] for e in wordbook.list_terms(root=root)]
    assert names == ["Alpha", "mike", "zulu"]


def test_find_searches_terms_and_phrasings(root):
    wordbook.add_term("plumb line", "hang the law", root=root)
    wordbook.add_term("demand", "scan score surface", root=root)
    assert [e["term"] for e in wordbook.find("LAW", root=root)] == ["plumb line"]
    assert [e["term"] for e in wordbook.find("demand", root=root)] == ["demand"]
    assert wordbook.find("zzz-nope", root=root) == []
    with pytest.raises(WordbookError, match="non-empty string"):
        wordbook.find("  ", root=root)


def test_corrupt_store_is_an_error_not_silence(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / "wordbook.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(WordbookError, match="not valid JSON"):
        wordbook.list_terms(root=root)


def test_cli_add_get_list(root, monkeypatch, capsys):
    monkeypatch.setattr(wordbook, "DEFAULT_ROOT", root)
    assert wordbook._cli(["add", "omega", "powered by alpha"]) == 0
    assert wordbook._cli(["get", "OMEGA"]) == 0
    out = capsys.readouterr().out
    assert "powered by alpha" in out
    assert wordbook._cli(["list"]) == 0
    assert "omega" in capsys.readouterr().out


def test_interop_self_declaration():
    from levi.interop import registry as ireg

    decl = ireg.check("customizations-wordbook")
    assert "customizations.wordbook.term" in decl["provides"]
