"""Tests for the syncwatch divergence watchdog (hermetic: tmp dirs only)."""

from __future__ import annotations

import pytest

from levi.daemon.signalbus import SignalBus
from levi.daemon.syncwatch import Syncwatch, SyncwatchError


@pytest.fixture()
def watcher(tmp_path):
    bus = SignalBus(journal_path=tmp_path / "bus.jsonl")
    return Syncwatch(root=tmp_path / "syncwatch", bus=bus)


@pytest.fixture()
def pair(tmp_path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    return left, right


def write_both(left, right, name, text):
    (left / name).write_text(text, encoding="utf-8")
    (right / name).write_text(text, encoding="utf-8")


def test_add_pair_and_list(watcher, pair):
    left, right = pair
    rec = watcher.add_pair("clouds", str(left), str(right))
    assert rec["name"] == "clouds"
    assert [p["name"] for p in watcher.list_pairs()] == ["clouds"]


def test_add_pair_rejects_same_directory(watcher, pair):
    left, _right = pair
    with pytest.raises(SyncwatchError):
        watcher.add_pair("same", str(left), str(left))


def test_add_pair_rejects_missing_directory(watcher, pair, tmp_path):
    left, _right = pair
    with pytest.raises(SyncwatchError):
        watcher.add_pair("ghost", str(left), str(tmp_path / "nope"))


def test_add_pair_rejects_bad_name(watcher, pair):
    left, right = pair
    with pytest.raises(SyncwatchError):
        watcher.add_pair("Bad Name!", str(left), str(right))


def test_add_pair_rejects_nested(watcher, pair):
    left, right = pair
    nested = left / "sub"
    nested.mkdir()
    with pytest.raises(SyncwatchError):
        watcher.add_pair("nested", str(left), str(nested))


def test_tick_converged_pair_no_signals(watcher, pair):
    left, right = pair
    write_both(left, right, "note.txt", "hello")
    watcher.add_pair("clouds", str(left), str(right))
    report = watcher.tick()
    assert report.pairs_checked == 1
    assert report.diverged == []
    assert watcher.bus.history("syncwatch.diverged") == []


def test_tick_diverged_emits_signal_with_reunion(watcher, pair):
    left, right = pair
    write_both(left, right, "note.txt", "hello")
    watcher.add_pair("clouds", str(left), str(right))
    watcher.tick()
    (right / "note.txt").write_text("hello WORLD", encoding="utf-8")
    report = watcher.tick()
    assert len(report.diverged) == 1
    div = report.diverged[0]
    assert div["relpath"] == "note.txt"
    assert div["reunion"] == "single-line"  # two text copies, one differs
    events = watcher.bus.history("syncwatch.diverged")
    assert len(events) == 1
    assert events[0].payload["relpath"] == "note.txt"


def test_tick_no_signal_when_unchanged(watcher, pair):
    left, right = pair
    (left / "note.txt").write_text("a", encoding="utf-8")
    (right / "note.txt").write_text("b", encoding="utf-8")
    watcher.add_pair("clouds", str(left), str(right))
    watcher.tick()
    assert len(watcher.bus.history("syncwatch.diverged")) == 1
    report = watcher.tick()
    assert len(report.diverged) == 1  # still diverged in the report...
    assert len(watcher.bus.history("syncwatch.diverged")) == 1  # ...but no new signal


def test_tick_reunited_when_copies_agree_again(watcher, pair):
    left, right = pair
    (left / "note.txt").write_text("a", encoding="utf-8")
    (right / "note.txt").write_text("b", encoding="utf-8")
    watcher.add_pair("clouds", str(left), str(right))
    watcher.tick()
    (right / "note.txt").write_text("a", encoding="utf-8")
    report = watcher.tick()
    assert len(report.reunited) == 1
    events = watcher.bus.history("syncwatch.reunited")
    assert len(events) == 1
    assert events[0].payload["relpath"] == "note.txt"


def test_tick_never_modifies_watched_trees(watcher, pair):
    left, right = pair
    (left / "note.txt").write_text("a", encoding="utf-8")
    (right / "note.txt").write_text("b", encoding="utf-8")
    watcher.add_pair("clouds", str(left), str(right))
    watcher.tick()
    assert (left / "note.txt").read_text() == "a"
    assert (right / "note.txt").read_text() == "b"


def test_remove_pair_retires_to_ledger(watcher, pair, tmp_path):
    left, right = pair
    watcher.add_pair("clouds", str(left), str(right))
    retired = watcher.remove_pair("clouds", reason="test")
    assert retired["name"] == "clouds"
    assert retired["reason"] == "test"
    assert watcher.list_pairs() == []
    with pytest.raises(SyncwatchError):
        watcher.remove_pair("clouds")


def test_binary_divergence_reported_without_reunion(watcher, pair):
    left, right = pair
    (left / "blob.bin").write_bytes(b"\x00\xff\x00\x01")
    (right / "blob.bin").write_bytes(b"\x00\xff\x00\x02")
    watcher.add_pair("clouds", str(left), str(right))
    report = watcher.tick()
    assert len(report.diverged) == 1
    assert report.diverged[0]["reunion"] is None
