"""Proof tests for BeOS live queries (revival/live_query.py).

Laws: predicates deterministic, ids stable and never reused,
unsubscribe total, every mutation emits a change receipt and updates
all live result sets.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from levi.revival.live_query import LiveIndex, QueryError  # noqa: E402


def _idx():
    ix = LiveIndex()
    ix.insert({"kind": "note", "tag": "levi"}, id="a")
    ix.insert({"kind": "note", "tag": "other"}, id="b")
    ix.insert({"kind": "task", "tag": "levi"}, id="c")
    return ix


def test_subscribe_computes_initial_results():
    ix = _idx()
    q = ix.subscribe(lambda r: r["kind"] == "note", name="notes")
    assert [r["id"] for r in q.results()] == ["a", "b"]


def test_insert_updates_live_results():
    ix = _idx()
    q = ix.subscribe(lambda r: r.get("tag") == "levi", name="tagged")
    ix.insert({"kind": "note", "tag": "levi"}, id="d")
    assert [r["id"] for r in q.results()] == ["a", "c", "d"]


def test_update_moves_record_out_of_results():
    ix = _idx()
    q = ix.subscribe(lambda r: r.get("tag") == "levi", name="tagged")
    ix.update("a", {"tag": "archived"})
    assert [r["id"] for r in q.results()] == ["c"]


def test_remove_updates_live_results():
    ix = _idx()
    q = ix.subscribe(lambda r: r["kind"] == "note", name="notes")
    ix.remove("a")
    assert [r["id"] for r in q.results()] == ["b"]


def test_change_receipts_in_order():
    ix = LiveIndex()
    ix.insert({"x": 1}, id="a")
    ix.update("a", {"x": 2})
    ix.remove("a")
    assert ix.log == [(1, "insert", "a"), (2, "update", "a"), (3, "remove", "a")]
    # ids are never reused
    with pytest.raises(QueryError):
        ix.insert({"x": 9}, id="a")


def test_unsubscribe_is_total():
    ix = _idx()
    q = ix.subscribe(lambda r: True, name="all")
    q.unsubscribe()
    assert not q.active
    ix.insert({"kind": "note"}, id="z")
    with pytest.raises(QueryError):
        q.results()
    assert "all" not in [qq.name for qq in ix._queries.values()]


def test_raising_predicate_is_non_matching_not_fatal():
    ix = _idx()

    def bad(r):
        if r["id"] == "a":
            raise RuntimeError("boom")
        return True

    q = ix.subscribe(bad, name="fragile")
    assert [r["id"] for r in q.results()] == ["b", "c"]
    assert q.predicate_errors  # reported, honestly


def test_duplicate_and_unknown_ids_refused():
    ix = _idx()
    with pytest.raises(QueryError):
        ix.insert({"x": 1}, id="a")
    with pytest.raises(QueryError):
        ix.update("nope", {"x": 1})
    with pytest.raises(QueryError):
        ix.remove("nope")


def test_multiple_queries_stay_independent():
    ix = _idx()
    notes = ix.subscribe(lambda r: r["kind"] == "note", name="notes")
    tasks = ix.subscribe(lambda r: r["kind"] == "task", name="tasks")
    ix.insert({"kind": "task"}, id="t2")
    assert [r["id"] for r in tasks.results()] == ["c", "t2"]
    assert [r["id"] for r in notes.results()] == ["a", "b"]
