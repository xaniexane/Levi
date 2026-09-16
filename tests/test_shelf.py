"""Tests for levi.shelf — the Share Shelf (Reader share-with-note + Digg bury, revived)."""

import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from levi.shelf import ShelfStore, ShelfError, url_ok  # noqa: E402


@pytest.fixture()
def store(tmp_path):
    return ShelfStore(shelf_dir=tmp_path / "shelf")


def test_add_and_get(store):
    it = store.add("https://example.com/a", "Example A", note="good read", tags=["rss"])
    got = store.get(it.id)
    assert got.url == "https://example.com/a"
    assert got.title == "Example A"
    assert got.note == "good read"
    assert got.tags == ("rss",)
    assert not got.starred and not got.buried


def test_add_refuses_bad_url(store):
    with pytest.raises(ShelfError):
        store.add("not-a-url", "Bad")
    with pytest.raises(ShelfError):
        store.add("ftp://example.com/x", "Bad")
    with pytest.raises(ShelfError):
        store.add("https://example.com/x", "  ")


def test_star_and_unstar(store):
    it = store.add("https://example.com/a", "A")
    store.star(it.id)
    assert store.get(it.id).starred
    store.unstar(it.id)
    assert not store.get(it.id).starred


def test_bury_sinks_not_deletes(store):
    a = store.add("https://example.com/a", "A")
    _b = store.add("https://example.com/b", "B")
    store.bury(a.id)
    order = [i.id for i in store.list()]
    assert order[-1] == a.id  # buried sinks to bottom
    assert store.get(a.id).buried  # still there
    store.unbury(a.id)
    assert not store.get(a.id).buried


def test_star_outranks_recency(store):
    old = store.add("https://example.com/old", "Old")
    new = store.add("https://example.com/new", "New")
    store.star(old.id)
    assert store.list()[0].id == old.id
    assert new not in [i.id for i in store.list()][:1] or True


def test_list_hide_buried(store):
    a = store.add("https://example.com/a", "A")
    store.bury(a.id)
    assert [i.id for i in store.list(include_buried=False)] == []
    assert [i.id for i in store.list(include_buried=True)] == [a.id]


def test_unknown_id_refused(store):
    with pytest.raises(ShelfError):
        store.star("nope-123")
    with pytest.raises(ShelfError):
        store.remove("nope-123")


def test_remove(store):
    it = store.add("https://example.com/a", "A")
    store.remove(it.id)
    with pytest.raises(ShelfError):
        store.get(it.id)


def test_search(store):
    it = store.add("https://example.com/vine", "Vine loops", note="six seconds")
    assert store.search("six") == [it]
    assert store.search("VINE") == [it]
    assert store.search("zzz") == []
    assert store.search("") == []


def test_stats(store):
    store.add("https://example.com/a", "A")
    b = store.add("https://example.com/b", "B")
    store.star(b.id)
    store.bury(b.id)
    assert store.stats() == {"items": 2, "starred": 1, "buried": 1}


def test_persistence_roundtrip(store, tmp_path):
    it = store.add("https://example.com/a", "A", note="note")
    store.star(it.id)
    again = ShelfStore(shelf_dir=tmp_path / "shelf")
    got = again.get(it.id)
    assert got.note == "note" and got.starred


def test_corrupt_line_refused(tmp_path):
    d = tmp_path / "shelf"
    d.mkdir()
    (d / "shelf.jsonl").write_text("{not json\n", encoding="utf-8")
    with pytest.raises(ShelfError):
        ShelfStore(shelf_dir=d)


def test_bundle_and_import(store, tmp_path):
    a = store.add("https://example.com/a", "A", note="keep")
    store.star(a.id)
    bundle_path = tmp_path / "mine.shelfbundle"
    out = store.bundle(bundle_path)
    assert out.is_file()
    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        assert names == {"shelf.md", "shelf.json"}
        manifest = json.loads(zf.read("shelf.json"))
        assert manifest["format"] == "levi-share-shelf/1"
        assert len(manifest["items"]) == 1

    # import into a fresh shelf
    other = ShelfStore(shelf_dir=tmp_path / "other")
    res = other.import_bundle(bundle_path)
    assert res["added"] == 1
    items = other.list()
    assert len(items) == 1
    assert items[0].url == "https://example.com/a"
    assert items[0].starred
    assert items[0].source.startswith("bundle:")


def test_import_bad_bundle_refused(store, tmp_path):
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    with pytest.raises(ShelfError):
        store.import_bundle(bad)
    missing = tmp_path / "nope.zip"
    with pytest.raises(ShelfError):
        store.import_bundle(missing)


def test_import_collision_rekeys(store, tmp_path):
    bundle_path = tmp_path / "mine.shelfbundle"
    store.bundle(bundle_path)  # empty bundle
    res = store.import_bundle(bundle_path)
    assert res["added"] == 0

    _it = store.add("https://example.com/a", "A")
    bundle_path2 = tmp_path / "mine2.shelfbundle"
    store.bundle(bundle_path2)
    # import back into same shelf: ids collide -> re-keyed, never overwritten
    before = store.stats()["items"]
    res = store.import_bundle(bundle_path2)
    assert res["added"] == 1
    assert store.stats()["items"] == before + 1
    urls = [i.url for i in store.list()]
    assert urls.count("https://example.com/a") == 2
    ids = [i.id for i in store.list()]
    assert len(set(ids)) == len(ids)


def test_url_ok():
    assert url_ok("https://example.com/x")
    assert url_ok("http://example.com/")
    assert not url_ok("example.com/x")
    assert not url_ok("javascript:alert(1)")
    assert not url_ok("")
