"""Tests for levi.automation.watchers — polling trigger sources."""

from __future__ import annotations

import json
import os

import pytest

from levi.automation.watchers import (
    CommandWatcher,
    FileWatcher,
    JournalWatcher,
    TickWatcher,
    WatcherError,
    WatcherHub,
)


class FakeClock:
    def __init__(self, start: float = 1_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_file_watcher_created_modified_deleted(tmp_path):
    clock = FakeClock()
    target = tmp_path / "note.txt"
    w = FileWatcher("files", [str(tmp_path)], clock=clock)

    assert w.poll() == []  # baseline snapshot, no events

    target.write_text("hello")
    events = w.poll()
    assert len(events) == 1
    assert events[0].kind == "file"
    assert events[0].payload["change"] == "created"
    assert events[0].payload["watcher"] == "files"

    assert w.poll() == []  # quiet — nothing changed

    os.utime(target, ns=(target.stat().st_mtime_ns + 5_000_000_000,) * 2)
    target.write_text("hello world!!")
    events = w.poll()
    assert len(events) == 1
    assert events[0].payload["change"] == "modified"

    target.unlink()
    events = w.poll()
    assert len(events) == 1
    assert events[0].payload["change"] == "deleted"


def test_file_watcher_missing_root_is_quiet(tmp_path):
    w = FileWatcher("ghost", [str(tmp_path / "nope")])
    assert w.poll() == []


def test_journal_watcher_tails_new_lines(tmp_path):
    journal = tmp_path / "events.jsonl"
    w = JournalWatcher("j", str(journal), event_kind="file")

    journal.write_text(
        json.dumps({"kind": "created", "summary": "a"}) + "\n"
        "not json at all\n" + json.dumps({"kind": "modified", "summary": "b"}) + "\n"
    )
    events = w.poll()
    assert [e.summary for e in events] == ["a", "b"]
    assert events[0].kind == "file"
    assert events[0].payload["skipped_lines"] == 1
    assert events[0].payload["journal"] == str(journal)

    assert w.poll() == []  # offset advanced; nothing new

    journal.write_text(json.dumps({"kind": "deleted", "summary": "c"}) + "\n")
    events = w.poll()  # truncated journal → offset resets, starts over
    assert [e.summary for e in events] == ["c"]


def test_journal_watcher_missing_journal_is_quiet(tmp_path):
    w = JournalWatcher("j", str(tmp_path / "missing.jsonl"))
    assert w.poll() == []


def test_command_watcher_fires_on_output_change():
    outputs = iter([b"one", b"one", b"two"])

    def runner(argv):
        return 0, next(outputs)

    w = CommandWatcher("cmd", ["uptime"], runner=runner)
    assert w.poll() == []  # baseline
    assert w.poll() == []  # same output — quiet
    events = w.poll()
    assert len(events) == 1
    assert events[0].kind == "command"
    assert "uptime" in events[0].summary
    assert events[0].payload["argv"] == ["uptime"]


def test_command_watcher_rejects_empty_argv():
    with pytest.raises(WatcherError):
        CommandWatcher("bad", [])


def test_tick_watcher_arms_then_ticks():
    clock = FakeClock()
    w = TickWatcher("beat", interval_sec=60.0, clock=clock)
    assert w.poll() == []  # first poll arms, emits nothing
    clock.advance(30.0)
    assert w.poll() == []
    clock.advance(31.0)
    events = w.poll()
    assert len(events) == 1
    assert events[0].kind == "time"
    assert events[0].payload["interval_sec"] == 60.0
    assert w.poll() == []  # timer reset


def test_tick_watcher_rejects_nonpositive_interval():
    with pytest.raises(WatcherError):
        TickWatcher("bad", interval_sec=0)


def test_hub_polls_all_and_rejects_duplicate_names(tmp_path):
    clock = FakeClock()
    hub = WatcherHub()
    hub.add(TickWatcher("beat", interval_sec=10.0, clock=clock))
    with pytest.raises(WatcherError):
        hub.add(TickWatcher("beat", interval_sec=10.0, clock=clock))

    hub.poll_all()  # arm
    clock.advance(11.0)
    events = hub.poll_all()
    assert len(events) == 1
    assert events[0].payload["watcher"] == "beat"

    assert hub.remove("beat") is True
    assert hub.remove("beat") is False
    assert hub.poll_all() == []

    described = hub.describe()
    assert described == []
