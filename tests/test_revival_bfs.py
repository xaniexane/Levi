"""Hermetic tests for revival/bfs.py (BeOS live queries)."""

from __future__ import annotations

import json

import pytest

from levi.revival import bfs
from levi.revival.bfs import (
    LiveQuery,
    LiveStore,
    QuerySpec,
    get_handler,
    query_matches,
    register_handler,
)


class FakeStore:
    """Fake in-memory store with a MemoryStore-like add/get surface."""

    def __init__(self):
        self.entries = {}
        self._seq = 0

    def add(
        self, memory_type, content, importance=0.5, source="test", tags=None, **kwargs
    ):
        self._seq += 1
        entry = {
            "id": "fake-%d" % self._seq,
            "memory_type": memory_type,
            "content": content,
            "importance": importance,
            "source": source,
            "tags": tags or [],
        }
        self.entries[entry["id"]] = entry
        return entry

    def get(self, entry_id):
        return self.entries.get(entry_id)

    def list(self):
        return list(self.entries.values())


@pytest.fixture()
def fake():
    return FakeStore()


@pytest.fixture()
def queries():
    return LiveQuery()


def test_live_query_fires_on_matching_entry_only(queries):
    hits = []
    queries.subscribe(QuerySpec(keywords=["levi"]), hits.append)
    queries.notify({"content": "LEVI is growing", "tags": [], "importance": 0.5})
    queries.notify(
        {"content": "unrelated weather report", "tags": [], "importance": 0.5}
    )
    assert hits == [{"content": "LEVI is growing", "tags": [], "importance": 0.5}]


def test_query_spec_fields_combine_as_and(queries):
    hits = []
    queries.subscribe(
        QuerySpec(keywords=["ship"], tags=["work"], min_importance=0.7), hits.append
    )
    # matches all three
    queries.notify({"content": "ship the release", "tags": ["work"], "importance": 0.9})
    # keyword + tag but too unimportant
    queries.notify({"content": "ship the release", "tags": ["work"], "importance": 0.1})
    # keyword only
    queries.notify({"content": "ship the release", "tags": ["play"], "importance": 0.9})
    assert len(hits) == 1


def test_entry_type_filter(queries):
    hits = []
    queries.subscribe(QuerySpec(entry_type="journal"), hits.append)
    queries.notify({"content": "a", "memory_type": "journal"})
    queries.notify({"content": "b", "memory_type": "fact"})
    assert [h["content"] for h in hits] == ["a"]


def test_unsubscribe_stops_notifications(queries):
    hits = []
    sub_id = queries.subscribe(QuerySpec(keywords=["x"]), hits.append)
    queries.notify({"content": "x marks the spot"})
    assert len(hits) == 1
    queries.unsubscribe(sub_id)
    queries.notify({"content": "x marks the spot"})
    assert len(hits) == 1
    with pytest.raises(ValueError, match="no subscription"):
        queries.unsubscribe(sub_id)


def test_bad_callback_cannot_break_notify(queries):
    good = []

    def bad(entry):
        raise RuntimeError("boom")

    queries.subscribe(QuerySpec(), bad)
    queries.subscribe(QuerySpec(), good.append)
    called = queries.notify({"content": "anything"})
    assert len(called) == 2  # both were attempted
    assert len(good) == 1  # the good one still fired
    assert len(queries.errors()) == 1
    assert "boom" in queries.errors()[0]["error"]


def test_notify_returns_matching_sub_ids(queries):
    q1 = queries.subscribe(QuerySpec(keywords=["a"]), lambda e: None)
    queries.subscribe(QuerySpec(keywords=["zzz"]), lambda e: None)
    assert queries.notify({"content": "a is here"}) == [q1]


def test_live_store_persists_and_notifies(fake, queries):
    store = LiveStore(fake, queries=queries)
    hits = []
    queries.subscribe(QuerySpec(tags=["memory"]), hits.append)
    entry = store.store_entry("fact", "the sky is blue", tags=["memory"])
    assert entry["id"] in fake.entries  # persisted through inner store
    assert hits == [entry]  # subscriber notified
    # non-matching entry: persisted, no notification
    entry2 = store.store_entry("fact", "grass is green", tags=["other"])
    assert entry2["id"] in fake.entries
    assert len(hits) == 1


def test_live_store_rejects_storeless():
    with pytest.raises(TypeError, match="add"):
        LiveStore(None)


def _named_handler(entry):
    _named_handler.seen.append(entry)


def test_durable_subscriptions_rearm_by_handler_name(tmp_path, monkeypatch):
    _named_handler.seen = []
    monkeypatch.setitem(bfs._HANDLER_REGISTRY, "named", _named_handler)
    q = LiveQuery()
    q.subscribe(QuerySpec(keywords=["ping"]), _named_handler, handler_name="named")
    path = q.save(tmp_path / "subs.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["subscriptions"][0]["handler_name"] == "named"

    q2 = LiveQuery()
    rearmed = q2.load(path)
    assert len(rearmed) == 1
    q2.notify({"content": "ping me"})
    assert len(_named_handler.seen) == 1


def test_durable_subscription_with_missing_handler_is_skipped(tmp_path):
    q = LiveQuery()
    q.subscribe(QuerySpec(), lambda e: None, handler_name="ghost-handler")
    path = q.save(tmp_path / "subs.json")
    q2 = LiveQuery()
    assert q2.load(path) == []
    assert any("ghost-handler" in w for w in q2.load_warnings())
    assert q2.subscriptions() == []


def test_handler_registry_validation():
    with pytest.raises(ValueError, match="non-empty string"):
        register_handler("", lambda e: None)
    with pytest.raises(TypeError, match="callable"):
        register_handler("x", "not-callable")
    register_handler("tmp-handler", lambda e: None)
    assert callable(get_handler("tmp-handler"))
    assert get_handler("definitely-missing") is None


def test_query_matches_normalizes_memory_entry_object():
    class Entry:
        def __init__(self):
            self.id = "1"
            self.content = "Levi learns fast"
            self.tags = ["growth"]
            self.importance = 0.9
            self.memory_type = "journal"
            self.source = "test"
            self.metadata = {}

    assert query_matches(QuerySpec(keywords=["learns"], tags=["growth"]), Entry())
    assert not query_matches(QuerySpec(keywords=["nope"]), Entry())
