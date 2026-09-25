"""Hermetic tests for revival/soups.py (Newton object stores)."""

from __future__ import annotations

import os

import pytest

from levi.revival.soups import (
    Soup,
    SoupCorruptError,
    SoupError,
    list_soups,
)


@pytest.fixture()
def base(tmp_path):
    return tmp_path / "soups"


def test_soup_round_trip(base):
    soup = Soup("notes", base_dir=base)
    obj_id = soup.put({"title": "hello", "n": 1}, schema="note", schema_version=1)
    rec = soup.get(obj_id)
    assert rec["id"] == obj_id
    assert rec["schema"] == "note"
    assert rec["schema_version"] == 1
    assert rec["data"] == {"title": "hello", "n": 1}
    # persisted: a fresh Soup over the same dir sees it
    soup2 = Soup("notes", base_dir=base)
    assert soup2.get(obj_id)["data"] == {"title": "hello", "n": 1}


def test_owner_only_permissions(base):
    soup = Soup("notes", base_dir=base)
    soup.put({"a": 1}, schema="note", schema_version=1)
    mode = os.stat(soup.path()).st_mode & 0o777
    assert mode == 0o600


def test_query_predicate_and_schema(base):
    soup = Soup("mix", base_dir=base)
    soup.put({"v": 1}, schema="a", schema_version=1)
    soup.put({"v": 2}, schema="a", schema_version=2)
    soup.put({"v": 3}, schema="b", schema_version=1)
    assert len(soup.query(lambda r: True)) == 3
    v2 = soup.query_schema("a", min_version=2)
    assert [r["data"]["v"] for r in v2] == [2]
    assert len(soup.query_schema("b")) == 1


def test_no_silent_coercion(base):
    """Versioned objects keep their original shape; readers opt into versions."""
    soup = Soup("cfg", base_dir=base)
    oid = soup.put({"fields": ["x"]}, schema="cfg", schema_version=1)
    # compatible() is explicit; query_schema filters explicitly
    assert soup.compatible(oid, "cfg", min_version=1)
    assert not soup.compatible(oid, "cfg", min_version=2)
    assert not soup.compatible(oid, "other", min_version=1)
    assert soup.query_schema("cfg", min_version=2) == []


def test_delete(base):
    soup = Soup("d", base_dir=base)
    oid = soup.put({"a": 1}, schema="s", schema_version=1)
    removed = soup.delete(oid)
    assert removed["id"] == oid
    assert soup.count() == 0
    with pytest.raises(SoupError, match="no object"):
        soup.delete(oid)
    with pytest.raises(SoupError, match="no object"):
        soup.get(oid)


def test_corrupt_file_quarantined_fail_closed(base):
    soup = Soup("fragile", base_dir=base)
    soup.put({"a": 1}, schema="s", schema_version=1)
    path = soup.path()
    path.write_text("{ this is not json", encoding="utf-8")
    with pytest.raises(SoupCorruptError) as excinfo:
        Soup("fragile", base_dir=base)
    err = excinfo.value
    assert "corrupt" in str(err)
    assert err.quarantined_to is not None
    assert err.quarantined_to.exists()
    assert not path.exists()  # moved away, not silently dropped
    assert err.quarantined_to.read_text(encoding="utf-8") == "{ this is not json"


def test_non_object_json_is_corrupt(base):
    path = base / "weird.json"
    base.mkdir(parents=True, exist_ok=True)
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(SoupCorruptError):
        Soup("weird", base_dir=base)


def test_registry_lists_schemas_and_counts(base):
    Soup("one", base_dir=base).put({"a": 1}, schema="note", schema_version=1)
    s2 = Soup("two", base_dir=base)
    s2.put({"a": 1}, schema="note", schema_version=1)
    s2.put({"b": 2}, schema="note", schema_version=3)
    registry = list_soups(base)
    by_name = {r["name"]: r for r in registry}
    assert by_name["one"]["objects"] == 1
    assert by_name["one"]["schemas"] == {"note": [1]}
    assert by_name["two"]["schemas"] == {"note": [1, 3]}
    assert by_name["two"]["corrupt"] is False


def test_registry_marks_corrupt_instead_of_raising(base):
    bad = Soup("bad", base_dir=base)
    bad.put({"a": 1}, schema="s", schema_version=1)
    bad.path().write_text("nope", encoding="utf-8")
    registry = list_soups(base)
    by_name = {r["name"]: r for r in registry}
    assert by_name["bad"]["corrupt"] is True
    assert "error" in by_name["bad"]


def test_registry_empty_for_missing_dir(tmp_path):
    assert list_soups(tmp_path / "nope") == []


def test_invalid_inputs_rejected(base):
    with pytest.raises(ValueError, match="non-empty string"):
        Soup("", base_dir=base)
    with pytest.raises(ValueError, match="invalid soup name"):
        Soup("../escape", base_dir=base)
    soup = Soup("ok", base_dir=base)
    with pytest.raises(TypeError, match="must be a dict"):
        soup.put([1, 2], schema="s", schema_version=1)
    with pytest.raises(ValueError, match="schema name"):
        soup.put({"a": 1}, schema="", schema_version=1)
    with pytest.raises(ValueError, match=">= 1"):
        soup.put({"a": 1}, schema="s", schema_version=0)
    with pytest.raises(ValueError, match="JSON-serializable"):
        soup.put({"a": object()}, schema="s", schema_version=1)
    with pytest.raises(TypeError, match="callable"):
        soup.query("nope")


def test_data_outlives_modules(base):
    """The Newton's promise: the soup survives whoever wrote it."""
    writer = Soup("shared", base_dir=base)
    oid = writer.put({"memo": "data outlives apps"}, schema="memo", schema_version=2)
    del writer
    reader = Soup("shared", base_dir=base)  # a different "module"
    rec = reader.get(oid)
    assert rec["data"]["memo"] == "data outlives apps"
    assert rec["schema_version"] == 2
