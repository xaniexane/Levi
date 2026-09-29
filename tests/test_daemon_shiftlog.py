"""Proof for the shift-log daemon: the five declared laws, machine-checked."""

import json
import os
import stat

import pytest

from levi.daemon import shiftlog
from levi.daemon.shiftlog import ShiftLogError


@pytest.fixture()
def journal(tmp_path):
    return tmp_path / "shiftlog.ndjson"


def test_append_roundtrip(journal):
    entry = shiftlog.append(
        {
            "actor": "pack-to-the-brim",
            "note": "packed staleness",
            "surfaces": ["engines/staleness"],
        },
        journal,
    )
    entries, quarantined = shiftlog.read(journal)
    assert quarantined == []
    assert len(entries) == 1
    assert entries[0]["actor"] == "pack-to-the-brim"
    assert entries[0]["note"] == "packed staleness"
    assert entries[0]["surfaces"] == ["engines/staleness"]
    assert "ts" in entries[0]
    assert entry["ts"] == entries[0]["ts"]


def test_append_only_never_rewrites(journal):
    shiftlog.append({"actor": "a", "note": "first"}, journal)
    raw_before = journal.read_bytes()
    shiftlog.append({"actor": "b", "note": "second"}, journal)
    raw_after = journal.read_bytes()
    assert raw_after.startswith(raw_before)  # earlier line untouched
    assert len(raw_after.splitlines()) == 2
    entries, _ = shiftlog.read(journal)
    assert entries[0]["note"] == "first"
    assert entries[1]["note"] == "second"


def test_missing_actor_refused(journal):
    with pytest.raises(ShiftLogError):
        shiftlog.append({"note": "no actor"}, journal)
    assert not journal.exists() or journal.read_bytes() == b""


def test_missing_note_refused(journal):
    with pytest.raises(ShiftLogError):
        shiftlog.append({"actor": "a"}, journal)


def test_non_dict_entry_refused(journal):
    with pytest.raises(ShiftLogError):
        shiftlog.append(["not", "a", "dict"], journal)


def test_bad_surfaces_shape_refused(journal):
    with pytest.raises(ShiftLogError):
        shiftlog.append({"actor": "a", "note": "n", "surfaces": ["ok", 42]}, journal)


def test_failed_append_leaves_file_untouched(journal):
    shiftlog.append({"actor": "a", "note": "good"}, journal)
    raw = journal.read_bytes()
    with pytest.raises(ShiftLogError):
        shiftlog.append({"actor": ""}, journal)
    assert journal.read_bytes() == raw  # byte-identical: atomic


def test_quarantine_counts_corrupt_lines(journal):
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_bytes(
        b'{"actor":"a","note":"good","ts":"2026-09-27T10:00:00+00:00"}\n'
        b"this is not json\n"
        b'{"actor":"b","ts":"2026-09-27T11:00:00+00:00"}\n'
        b"\n"
    )
    entries, quarantined = shiftlog.read(journal)
    assert len(entries) == 1
    assert entries[0]["actor"] == "a"
    assert len(quarantined) == 2
    assert quarantined[0][0] == 2  # line number
    assert quarantined[1][0] == 3


def test_journal_is_owner_only(journal):
    shiftlog.append({"actor": "a", "note": "perms"}, journal)
    mode = stat.S_IMODE(os.stat(journal).st_mode)
    assert mode == 0o600


def test_missing_journal_reads_empty(tmp_path):
    entries, quarantined = shiftlog.read(tmp_path / "nope.ndjson")
    assert entries == [] and quarantined == []


def test_summarize_one_day(journal):
    shiftlog.append(
        {
            "actor": "a",
            "note": "morning shift",
            "surfaces": ["engines/x"],
            "ts": "2026-09-27T08:00:00+00:00",
        },
        journal,
    )
    shiftlog.append(
        {
            "actor": "b",
            "note": "night shift",
            "surfaces": ["daemons/y", "engines/x"],
            "ts": "2026-09-27T20:00:00+00:00",
        },
        journal,
    )
    shiftlog.append(
        {"actor": "a", "note": "old", "ts": "2026-09-20T08:00:00+00:00"},
        journal,
    )
    report = shiftlog.summarize(journal, day="2026-09-27")
    assert report["shifts"] == 2
    assert report["actors"] == ["a", "b"]
    assert report["surfaces"] == ["engines/x", "daemons/y"]
    assert report["notes"] == ["morning shift", "night shift"]
    assert report["total_entries"] == 3
    assert report["quarantined_lines"] == 0


def test_summarize_includes_quarantine_count(journal):
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_bytes(b"broken{\n")
    report = shiftlog.summarize(journal, day="2026-09-27")
    assert report["quarantined_lines"] == 1


def test_cli_note_subcommand(journal, capsys):
    assert (
        shiftlog.main(
            [
                "--journal",
                str(journal),
                "note",
                "packed three surfaces",
                "--actor",
                "pack-to-the-brim",
                "--surface",
                "engines/staleness",
                "--head",
                "abc1234",
            ]
        )
        == 0
    )
    entries, _ = shiftlog.read(journal)
    assert len(entries) == 1
    assert entries[0]["head"] == "abc1234"


def test_cli_summary_subcommand(journal, capsys):
    shiftlog.append(
        {"actor": "a", "note": "x", "ts": "2026-09-27T10:00:00+00:00"}, journal
    )
    assert shiftlog.main(["--journal", str(journal)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["shifts"] >= 1


def test_run_once_returns_report(journal):
    report = shiftlog.run_once(journal)
    assert report["day"] and report["total_entries"] == 0
