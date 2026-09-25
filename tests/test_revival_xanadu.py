"""Hermetic tests for revival/xanadu.py (transclusion + trails)."""

from __future__ import annotations

import json

import pytest

from levi.revival.xanadu import (
    DocStore,
    Quote,
    Trail,
    TrailStore,
    Transclusion,
    ask_and_trail,
    demo,
    trail_from_citations,
)


@pytest.fixture()
def docs():
    store = DocStore()
    store.add("d1", "The quick brown fox jumps over the lazy dog.", title="Fox")
    store.add("d2", "Pack my box with five dozen liquor jugs.", title="Box")
    return store


@pytest.fixture()
def trails(docs, tmp_path):
    return TrailStore(docs, trail_dir=tmp_path / "trails")


def test_quote_returns_text_with_provenance(docs):
    trans = Transclusion(docs)
    q = trans.quote("d1", 4, 9)
    assert isinstance(q, Quote)
    assert q.text == "quick"
    assert q.doc_id == "d1"
    assert q.span == (4, 9)
    assert q.title == "Fox"
    # citation carries attribution: text is never handed out bare
    assert "d1" in q.citation() and "Fox" in q.citation() and "quick" in q.citation()


def test_quote_unknown_doc_raises(docs):
    trans = Transclusion(docs)
    with pytest.raises(KeyError):
        trans.quote("missing", 0, 1)


def test_span_out_of_range_raises(docs):
    with pytest.raises(ValueError, match="out of range"):
        Transclusion(docs).quote("d1", 0, 10_000)


def test_transclusion_tracks_who_quotes_whom(docs):
    trans = Transclusion(docs)
    q = trans.transclude("d2", "d1", 0, 3)
    assert q.text == "The"
    assert trans.quotes("d2") == ["d1"]  # d2 quotes d1
    assert trans.quoted_by("d1") == ["d2"]  # d1 is quoted by d2
    assert trans.quoted_by("d2") == []


def test_transclusion_serializes(docs):
    trans = Transclusion(docs)
    trans.transclude("d2", "d1", 0, 3)
    data = trans.to_dict()
    assert data["quoted_by"]["d1"] == ["d2"]
    trans2 = Transclusion.from_dict(docs, json.loads(json.dumps(data)))
    assert trans2.quoted_by("d1") == ["d2"]


def test_trail_following_order(docs, trails):
    trail = trails.create("t1", "My trail")
    trail.add_stop("d1", "first: the fox")
    trail.add_stop("d2", "second: the box")
    walked = list(trails.follow_trail("t1"))
    assert [doc.doc_id for doc, _ in walked] == ["d1", "d2"]
    assert [ann for _, ann in walked] == ["first: the fox", "second: the box"]
    assert walked[0][0].title == "Fox"


def test_trail_persists_and_reloads(docs, tmp_path):
    trails = TrailStore(docs, trail_dir=tmp_path / "trails")
    trail = trails.create("t9", "Persisted")
    trail.add_stop("d2", "only stop")
    path = trails.save("t9")
    assert path.exists()
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["stops"][0]["doc_id"] == "d2"

    trails2 = TrailStore(docs, trail_dir=tmp_path / "trails")
    walked = list(trails2.follow_trail("t9"))
    assert [d.doc_id for d, _ in walked] == ["d2"]


def test_follow_missing_trail_or_doc_raises(docs, trails):
    with pytest.raises(KeyError):
        list(trails.follow_trail("nope"))
    trail = trails.create("broken", "Broken")
    trail.add_stop("ghost-doc", "points nowhere")
    with pytest.raises(KeyError):
        list(trails.follow_trail("broken"))  # never silently skips


def test_trail_duplicate_id_rejected(trails):
    trails.create("dup", "A")
    with pytest.raises(ValueError, match="already exists"):
        trails.create("dup", "B")


def test_trail_delete(trails):
    trails.create("gone", "Gone")
    trails.save("gone")
    trails.delete("gone")
    with pytest.raises(KeyError):
        trails.get("gone")


def test_trail_from_citations(docs, trails):
    trail = trail_from_citations(
        trails,
        "rag-trail",
        "From RAG",
        ["d1", "d2"],
        annotations={"d1": "top hit"},
    )
    assert isinstance(trail, Trail)
    walked = list(trails.follow_trail("rag-trail"))
    assert [d.doc_id for d, _ in walked] == ["d1", "d2"]
    assert walked[0][1] == "top hit"


def test_ask_and_trail_degrades_honestly_without_rag(docs, trails, monkeypatch):
    """If levi.rag cannot be imported, ask_and_trail says so (no fake citations)."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("levi.rag"):
            raise ImportError("no module named levi.rag")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError, match="levi.rag is unavailable"):
        ask_and_trail("anything", object(), trails, "t", "T")


def test_docstore_validation():
    store = DocStore()
    with pytest.raises(ValueError, match="doc_id"):
        store.add("", "text")
    with pytest.raises(ValueError, match="text"):
        store.add("x", "")
    with pytest.raises(KeyError):
        store.get("missing")


def test_docstore_persistence(tmp_path, docs):
    path = tmp_path / "docs.json"
    docs.save(path)
    loaded = DocStore.load(path)
    assert loaded.get("d1").title == "Fox"
    assert "brown fox" in loaded.get("d1").text


def test_demo_runs(capsys):
    demo()
    out = capsys.readouterr().out
    assert "transclusion:" in out
    assert "following trail" in out
    assert "memex-1945" in out and "xanadu-1965" in out
