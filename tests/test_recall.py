"""Tests for core/levi/memory/recall.py — FTS5 + BM25 recall index."""

from __future__ import annotations

import json


from levi.memory.recall import (
    BAD_QUERY,
    EMPTY_QUERY,
    NOT_INDEXED,
    NO_DOCS,
    RecallIndex,
)


def _idx(tmp_path, **kw):
    db = tmp_path / "recall.db"
    return RecallIndex(db_path=db, **kw)


def test_add_and_ranked_search_orders_by_bm25(tmp_path):
    idx = _idx(tmp_path)
    n = idx.add_documents(
        [
            {
                "doc_id": "a",
                "title": "one",
                "body": "whisper whisper whisper whisper engine",
                "tags": [],
            },
            {"doc_id": "b", "title": "two", "body": "whisper engine", "tags": []},
            {
                "doc_id": "c",
                "title": "three",
                "body": "nothing relevant here at all",
                "tags": [],
            },
        ]
    )
    assert n == 3
    results, reason = idx.search("whisper")
    assert reason is None
    assert [r.doc_id for r in results] == ["a", "b"]
    assert results[0].score < results[1].score  # bm25: lower is better


def test_snippet_output_contains_markers(tmp_path):
    idx = _idx(tmp_path)
    idx.add_documents(
        [
            {
                "doc_id": "s",
                "title": "t",
                "body": "the quick brown fox jumps over the lazy dog",
                "tags": [],
            }
        ]
    )
    results, reason = idx.search("fox")
    assert reason is None
    assert len(results) == 1
    assert "<<" in results[0].snippet and ">>" in results[0].snippet
    assert "fox" in results[0].snippet.lower()


def test_search_unbuilt_index_is_honest(tmp_path):
    idx = _idx(tmp_path)
    results, reason = idx.search("anything")
    assert results == []
    assert reason == NOT_INDEXED


def test_search_empty_index_is_honest(tmp_path):
    import sqlite3

    db = tmp_path / "recall2.db"
    idx = RecallIndex(db_path=db)
    idx.add_documents([{"doc_id": "z", "body": "temp doc"}])
    with sqlite3.connect(str(db)) as c:
        c.execute("DELETE FROM docs")
        c.commit()
    results, reason = idx.search("temp")
    assert results == []
    assert reason == NO_DOCS
    assert _idx(tmp_path / "unbuilt").search("x")[1] == NOT_INDEXED


def test_bad_query_degrades(tmp_path):
    idx = _idx(tmp_path)
    idx.add_documents([{"doc_id": "q", "body": "some body text"}])
    results, reason = idx.search('((("unbalanced')
    assert results == []
    assert reason == BAD_QUERY


def test_empty_query(tmp_path):
    idx = _idx(tmp_path)
    assert idx.search("")[1] == EMPTY_QUERY
    assert idx.search("   ")[1] == EMPTY_QUERY
    assert idx.search(None)[1] == EMPTY_QUERY


def test_source_filter(tmp_path):
    idx = _idx(tmp_path)
    idx.add_documents([{"doc_id": "m1", "body": "shared token alpha"}])
    idx2docs = [{"doc_id": "j1", "body": "shared token alpha"}]
    idx.add_documents(idx2docs, source="journal")
    results, _ = idx.search("shared token alpha", source="journal")
    assert [r.doc_id for r in results] == ["j1"]


def test_malformed_docs_skipped(tmp_path):
    idx = _idx(tmp_path)
    n = idx.add_documents(
        [
            {"doc_id": "", "body": "blank id"},
            {"doc_id": "ok", "body": "  "},
            {"doc_id": "good", "body": "real content here"},
            "not a dict",
        ]
    )
    assert n == 1
    results, _ = idx.search("real content")
    assert len(results) == 1 and results[0].doc_id == "good"


def test_index_memory_store_missing_dir(tmp_path):
    idx = _idx(tmp_path, memory_dir=tmp_path / "no-such-dir")
    report = idx.index_memory_store()
    assert report["indexed"] == 0
    # MemoryStore creates the dir on init, so it degrades to empty, not crash.
    assert isinstance(report, dict)


def test_index_memory_store_roundtrip(tmp_path):
    from levi.memory.store import MemoryStore
    from levi.memory.types import MemoryType

    mem_dir = tmp_path / "mem"
    store = MemoryStore(data_dir=mem_dir)
    store.add(MemoryType.SEMANTIC, "Wax is the coordination comb", tags=["wax", "hive"])
    idx = _idx(tmp_path, memory_dir=mem_dir)
    report = idx.index_memory_store()
    assert report["indexed"] == 1
    results, reason = idx.search("coordination comb")
    assert reason is None
    assert len(results) == 1
    assert results[0].source == "memory"
    assert results[0].doc_id.startswith("memory:")


def test_index_growth_journal_roundtrip(tmp_path):
    jdir = tmp_path / "growth"
    jdir.mkdir()
    jpath = jdir / "journal.jsonl"
    jpath.write_text(
        json.dumps(
            {"id": "cyc-1", "cycle": 1, "learned": ["levi likes the basement quietly"]}
        )
        + "\n"
        + "this is not json\n",
        encoding="utf-8",
    )
    idx = _idx(tmp_path, journal_path=jpath)
    report = idx.index_growth_journal()
    assert report["indexed"] == 1
    assert report["skipped"] == 1
    results, reason = idx.search("basement quietly")
    assert reason is None
    assert len(results) == 1
    assert results[0].source == "journal"


def test_index_growth_journal_missing(tmp_path):
    idx = _idx(tmp_path, journal_path=tmp_path / "nope.jsonl")
    report = idx.index_growth_journal()
    assert report["indexed"] == 0
    assert "reason" in report


def test_rebuild_and_stats(tmp_path):
    idx = _idx(tmp_path)
    idx.add_documents([{"doc_id": "r1", "body": "hello there"}])
    stats = idx.stats()
    assert stats["indexed"] is True
    assert stats["documents"] == 1
    assert stats["by_source"] == {"adhoc": 1}
    # rebuild on empty sources clears the index honestly (journal path isolated)
    fresh = _idx(
        tmp_path / "fresh",
        memory_dir=tmp_path / "empty-mem",
        journal_path=tmp_path / "no-journal.jsonl",
    )
    fresh.rebuild()
    assert fresh.stats()["documents"] == 0


def test_fts5_phrase_query(tmp_path):
    idx = _idx(tmp_path)
    idx.add_documents(
        [
            {"doc_id": "p1", "body": "the quick brown fox"},
            {"doc_id": "p2", "body": "quick brown things are fast"},
        ]
    )
    results, _ = idx.search('"quick brown fox"')
    assert [r.doc_id for r in results] == ["p1"]
