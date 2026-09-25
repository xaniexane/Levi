"""Tests for levi.automation.digest — the run-digest builder."""

from __future__ import annotations

from levi.automation.digest import (
    Digest,
    build_digest,
    format_digest,
    list_digests,
    save_digest,
)


def test_build_groups_and_counts():
    events = [
        {"kind": "watcher", "text": "file changed: notes.md"},
        {"kind": "watcher", "text": "tick fired"},
        {"kind": "flow", "text": "morning brief ran"},
        {"kind": "flow", "text": "backup ran"},
        {"kind": "flow", "text": "cleanup ran"},
        {"nonsense": True},  # skipped, not a crash
        {"kind": "watcher", "text": ""},  # skipped, no text
    ]
    d = build_digest(events, "Nightly")
    assert d.title == "Nightly"
    assert d.counts_by_kind == {"watcher": 2, "flow": 3, "skipped": 2}
    assert d.total_events == 7
    assert len(d.items) == 5


def test_build_respects_limit():
    events = [{"kind": "x", "text": f"event {i}"} for i in range(10)]
    d = build_digest(events, "T", limit=3)
    assert len(d.items) == 3
    assert d.total_events == 10


def test_build_blank_title_gets_default():
    d = build_digest([{"kind": "x", "text": "hi"}], "")
    assert d.title == "Automation digest"


def test_empty_digest_formats_honestly():
    d = build_digest([], "Empty")
    text = format_digest(d)
    assert "No events in this window." in text


def test_format_lists_items_and_hidden_count():
    events = [{"kind": "x", "text": f"event {i}"} for i in range(6)]
    d = build_digest(events, "T", limit=4)
    text = format_digest(d)
    assert "6 events" in text
    assert "[x] event 0" in text
    assert "... and 2 more counted above." in text


def test_save_and_list_roundtrip(tmp_path):
    d1 = build_digest([{"kind": "a", "text": "first"}], "One")
    d2 = build_digest([{"kind": "b", "text": "second"}], "Two")
    save_digest(d1, home=tmp_path)
    save_digest(d2, home=tmp_path)
    back = list_digests(home=tmp_path)
    assert [d.title for d in back] == ["Two", "One"]  # newest first
    assert back[0].counts_by_kind == {"b": 1}


def test_list_empty_store(tmp_path):
    assert list_digests(home=tmp_path) == []


def test_list_limit(tmp_path):
    for i in range(5):
        save_digest(
            build_digest([{"kind": "x", "text": str(i)}], f"D{i}"), home=tmp_path
        )
    back = list_digests(home=tmp_path, limit=2)
    assert [d.title for d in back] == ["D4", "D3"]


def test_corrupt_line_skipped_not_fatal(tmp_path):
    store = tmp_path / ".levi" / "automation"
    store.mkdir(parents=True)
    (store / "digests.jsonl").write_text(
        '{"title": "Good", "created_at": "t", "total_events": 1,'
        ' "counts_by_kind": {"x": 1}, "items": []}\n'
        "this is not json\n",
        encoding="utf-8",
    )
    back = list_digests(home=tmp_path)
    assert len(back) == 1 and back[0].title == "Good"


def test_digest_serializes():
    d = build_digest([{"kind": "x", "text": "hi", "extra": 1}], "T")
    restored = Digest.from_dict(d.to_dict())
    assert restored.title == "T"
    assert restored.items[0]["extra"] == 1
