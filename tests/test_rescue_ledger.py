"""The Rescue Stone: append-only, oldest-first, no delete path.

Hermetic: tmp rescue home only.
"""

import pytest

from levi.rescue import ledger


def test_record_and_read_oldest_first(tmp_path):
    ledger.record(tmp_path, "intake.invited", "ep-1", {"owner": "A"})
    ledger.record(tmp_path, "audit.completed", "ep-1", {"score": 77})
    ledger.record(tmp_path, "intake.invited", "ep-2", {"owner": "B"})
    entries = ledger.ledger(tmp_path)
    assert [e["event"] for e in entries] == [
        "intake.invited",
        "audit.completed",
        "intake.invited",
    ]
    assert all(e["ts"] for e in entries)
    assert entries[0]["detail"] == {"owner": "A"}


def test_episodes_in_first_seen_order(tmp_path):
    ledger.record(tmp_path, "intake.invited", "ep-2", {})
    ledger.record(tmp_path, "intake.invited", "ep-1", {})
    ledger.record(tmp_path, "audit.completed", "ep-2", {})
    assert ledger.episodes(tmp_path) == ["ep-2", "ep-1"]


def test_empty_stone_reads_empty(tmp_path):
    assert ledger.ledger(tmp_path) == []
    assert ledger.episodes(tmp_path) == []


def test_record_requires_event_name(tmp_path):
    with pytest.raises(ValueError):
        ledger.record(tmp_path, "  ", "ep-1", {})


def test_no_delete_path_exists():
    public = [n for n in dir(ledger) if not n.startswith("_")]
    for n in public:
        assert "delete" not in n and "remove" not in n and "clear" not in n, n
    assert not hasattr(ledger, "delete")
    assert not hasattr(ledger, "wipe")
