"""Tests for levi.intelligence.field_journal — the keeper's encounter log.

The journal is append-only JSONL. One corrupt line must never brick the
whole journal: reads skip it, appends still land, and a status rewrite
keeps it byte-identical (nothing is ever thrown away).
"""

import json

import pytest

from levi.intelligence import field_journal as fj


@pytest.fixture(autouse=True)
def isolated_journal(tmp_path, monkeypatch):
    monkeypatch.setattr(fj, "JOURNAL_DIR", str(tmp_path))
    monkeypatch.setattr(fj, "ENTRIES_PATH", str(tmp_path / "entries.jsonl"))


def _log(**kw):
    base = {"title": "T", "where": "lab", "pattern": "x+y=z", "language": "probe"}
    base.update(kw)
    return fj.log(**base)


def test_log_assigns_sequential_ids():
    e1 = _log(title="first")
    e2 = _log(title="second")
    assert e1["id"] == "enc-0001"
    assert e2["id"] == "enc-0002"


def test_log_trims_fields_and_applies_defaults():
    e = _log(
        title="  spaced  ",
        where=" w ",
        pattern=" p ",
        language=" l ",
        class_code="  ",
        notes=" n ",
    )
    assert e["title"] == "spaced"
    assert e["class"] == "?"
    assert e["status"] == "encounter"
    assert e["notes"] == "n"
    assert e["date"]  # defaults to today


def test_log_rejects_blank_required_field():
    for field in ("title", "where", "pattern", "language"):
        kw = {"title": "T", "where": "w", "pattern": "p", "language": "l"}
        kw[field] = "   "
        with pytest.raises(ValueError):
            fj.log(**kw)


def test_log_rejects_bad_status():
    with pytest.raises(ValueError):
        _log(status="declared-by-nobody")


def test_list_entries_filters():
    _log(title="a", status="encounter", class_code="?")
    _log(title="b", status="studied", class_code="AI")
    _log(title="c", status="encounter", class_code="AI")
    assert [e["title"] for e in fj.list_entries(status="encounter")] == ["a", "c"]
    assert [e["title"] for e in fj.list_entries(class_code="AI")] == ["b", "c"]
    assert len(fj.list_entries()) == 3


def test_unknowns_returns_unclassified_only():
    _log(title="mystery", class_code="?")
    _log(title="known", class_code="AI")
    assert [e["title"] for e in fj.unknowns()] == ["mystery"]


def test_mark_studied_moves_status_and_persists():
    e = _log(title="odd")
    out = fj.mark_studied(e["id"])
    assert out["status"] == "studied"
    assert fj.list_entries(status="studied")[0]["id"] == e["id"]


def test_mark_studied_unknown_id_raises_keyerror():
    with pytest.raises(KeyError):
        fj.mark_studied("enc-9999")


def test_corrupt_line_does_not_break_reads_or_appends():
    e1 = _log(title="good-one")
    corrupt = "THIS IS NOT JSON {{{{\n"
    with open(fj.ENTRIES_PATH, "a", encoding="utf-8") as fh:
        fh.write(corrupt)
        fh.write("[1, 2, 3]\n")  # valid JSON, not an entry object
    e2 = _log(title="good-two")  # append must still land
    assert e2["id"] == "enc-0002"
    assert [e["id"] for e in fj.list_entries()] == [e1["id"], e2["id"]]
    assert fj.unknowns()[0]["id"] == e1["id"]
    assert fj.mark_studied(e1["id"])["status"] == "studied"


def test_mark_studied_preserves_corrupt_line_byte_identical():
    e = _log(title="good")
    corrupt = "broken line \u00e9\u00e8"
    with open(fj.ENTRIES_PATH, "a", encoding="utf-8") as fh:
        fh.write(corrupt + "\n")
    fj.mark_studied(e["id"])
    with open(fj.ENTRIES_PATH, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    assert len(lines) == 2
    assert lines[1] == corrupt  # kept byte-identical, not dropped
    assert json.loads(lines[0])["status"] == "studied"


def test_ids_sequence_past_existing_max():
    with open(fj.ENTRIES_PATH, "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "id": "enc-0041",
                    "title": "t",
                    "where": "w",
                    "pattern": "p",
                    "language": "l",
                    "class": "?",
                    "status": "encounter",
                }
            )
            + "\n"
        )
    assert _log(title="next")["id"] == "enc-0042"
