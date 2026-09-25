"""Tests for core/levi/daemon/signalbus.py."""

import json

import pytest

from levi.daemon.signalbus import (
    SignalBus,
    SignalBusError,
    pattern_matches,
    validate_topic,
)


def test_validate_topic_accepts_dotted_lowercase():
    assert validate_topic("heartbeat.pulse") == "heartbeat.pulse"
    assert validate_topic("watchman.file.*") == "watchman.file.*"


@pytest.mark.parametrize(
    "bad",
    ["", "UPPER.case", "has space", ".leading", "trailing.", "double..dot", "wild*"],
)
def test_validate_topic_rejects(bad):
    with pytest.raises(SignalBusError):
        validate_topic(bad)


def test_pattern_matches():
    assert pattern_matches("a.b", "a.b")
    assert not pattern_matches("a.b", "a.c")
    assert pattern_matches("a.*", "a.b")
    assert pattern_matches("a.*", "a.b.c")
    assert pattern_matches("a.*", "a")
    assert not pattern_matches("a.*", "ab")
    assert not pattern_matches("a.*", "b.a")


def test_publish_and_history(tmp_path):
    bus = SignalBus(journal_path=tmp_path / "bus.jsonl")
    bus.subscribe("s1", "heartbeat.*")
    ev = bus.publish("heartbeat.pulse", {"n": 1}, "heartbeat")
    assert ev.payload["_recipients"] == ["s1"]
    hist = bus.history()
    assert len(hist) == 1
    assert hist[0].id == ev.id
    assert hist[0].topic == "heartbeat.pulse"


def test_history_topic_filter_and_limit(tmp_path):
    bus = SignalBus(journal_path=tmp_path / "bus.jsonl")
    for i in range(5):
        bus.publish("a.tick", {"i": i}, "p")
        bus.publish("b.tick", {"i": i}, "p")
    assert len(bus.history(topic="a.tick")) == 5
    recent = bus.history(limit=3)
    assert len(recent) == 3
    # newest first
    assert recent[0].at >= recent[-1].at


def test_replay_missed_events(tmp_path):
    journal = tmp_path / "bus.jsonl"
    bus = SignalBus(journal_path=journal)
    bus.publish("watchman.file.modified", {"f": "a"}, "watchman")
    bus.publish("other.event", {}, "x")
    bus.publish("watchman.file.deleted", {"f": "b"}, "watchman")

    # subscriber joins late; replay everything it would have received
    bus.subscribe("late", "watchman.file.*")
    missed = bus.replay("late")
    assert [e.topic for e in missed] == [
        "watchman.file.modified",
        "watchman.file.deleted",
    ]

    # replay since a known id returns only later events
    later = bus.replay("late", since_id=missed[0].id)
    assert [e.topic for e in later] == ["watchman.file.deleted"]

    # replay on an unknown subscriber is an honest error
    with pytest.raises(SignalBusError):
        bus.replay("ghost")


def test_replay_persists_across_restarts(tmp_path):
    journal = tmp_path / "bus.jsonl"
    bus = SignalBus(journal_path=journal)
    first = bus.publish("heartbeat.pulse", {}, "heartbeat")
    # new process, new bus, same journal
    bus2 = SignalBus(journal_path=journal)
    bus2.subscribe("s", "heartbeat.*")
    assert [e.id for e in bus2.replay("s")] == [first.id]


def test_unsubscribe_stops_matching(tmp_path):
    bus = SignalBus(journal_path=tmp_path / "bus.jsonl")
    bus.subscribe("s", "a.*")
    assert bus.unsubscribe("s") is True
    assert bus.unsubscribe("s") is False
    ev = bus.publish("a.b", {}, "p")
    assert ev.payload["_recipients"] == []


def test_journal_file_is_owner_only(tmp_path):
    import os
    import stat

    journal = tmp_path / "bus.jsonl"
    bus = SignalBus(journal_path=journal)
    bus.publish("a.b", {}, "p")
    mode = stat.S_IMODE(os.stat(journal).st_mode)
    assert mode == 0o600


def test_journal_trim_caps_history(tmp_path):
    journal = tmp_path / "bus.jsonl"
    bus = SignalBus(journal_path=journal, journal_cap=10)
    for i in range(25):
        bus.publish("a.tick", {"i": i}, "p")
    with open(journal, encoding="utf-8") as fh:
        lines = [ln for ln in fh if ln.strip()]
    assert len(lines) == 10
    # newest retained
    assert json.loads(lines[-1])["payload"]["i"] == 24


def test_corrupt_journal_line_skipped(tmp_path):
    journal = tmp_path / "bus.jsonl"
    bus = SignalBus(journal_path=journal)
    bus.publish("a.b", {"ok": True}, "p")
    with open(journal, "a", encoding="utf-8") as fh:
        fh.write("this is not json\n")
    assert len(bus.history()) == 1
