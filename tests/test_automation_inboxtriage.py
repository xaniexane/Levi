"""Tests for levi.automation.inboxtriage — the self-filing dropbox.

Proof of the three laws:
1. NOTHING IS EVER DELETED — file count is preserved across a run, every
   move is ledgered with sha256 provenance.
2. DETERMINISTIC — two runs over the same input yield identical moves.
3. BOUNDED — nothing lands outside the inbox root; escapes are refused.

Hermetic: tmp_path only.
"""

from __future__ import annotations

import os
from pathlib import Path

from levi.automation.inboxtriage import (
    classify,
    read_ledger,
    triage,
)


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _inbox_with_samples(tmp_path: Path) -> Path:
    _write(tmp_path / "photo.png", b"\x89PNG\r\n\x1a\n" + b"0" * 100)  # magic, not ext
    _write(tmp_path / "renamed.bin", b"%PDF-1.4 fake")  # magic, wrong ext
    _write(tmp_path / "notes.txt", b"hello world")
    _write(tmp_path / "song.mp3", b"ID3" + b"0" * 50)
    _write(tmp_path / "weird.xyz", b"mystery bytes")
    return tmp_path


def test_classify_magic_before_extension(tmp_path):
    assert classify(_write(tmp_path / "a.bin", b"\x89PNG\r\n\x1a\nxx")) == "images"
    assert classify(_write(tmp_path / "b.txt", b"%PDF-xx")) == "documents"


def test_classify_extension_and_misc(tmp_path):
    assert classify(_write(tmp_path / "a.py", b"print(1)")) == "code"
    assert classify(_write(tmp_path / "a.zip", b"not really zip")) == "archives"
    assert classify(_write(tmp_path / "a.xyz", b"???")) == "misc"


def test_triage_moves_into_drawers_and_ledgers(tmp_path):
    inbox = _inbox_with_samples(tmp_path)
    report = triage(inbox)
    assert report.moved_count == 5
    assert (inbox / "images" / "photo.png").exists()
    assert (inbox / "documents" / "renamed.bin").exists()
    assert (inbox / "documents" / "notes.txt").exists()
    assert (inbox / "audio" / "song.mp3").exists()
    assert (inbox / "misc" / "weird.xyz").exists()

    ledger = read_ledger(inbox)
    assert len(ledger) == 5
    for record in ledger:
        assert record["sha256"] and record["size_bytes"] > 0
        assert record["source"] and record["destination"]


def test_law_nothing_is_deleted(tmp_path):
    inbox = _inbox_with_samples(tmp_path)
    before = sum(1 for p in inbox.rglob("*") if p.is_file())
    report = triage(inbox)
    after = sum(1 for p in inbox.rglob("*") if p.is_file())
    # Files only moved (+1 ledger file); none lost.
    assert after == before + 1
    assert report.moved_count == before


def test_law_deterministic(tmp_path):
    inbox = _inbox_with_samples(tmp_path)
    first = triage(inbox, dry_run=True)
    second = triage(inbox, dry_run=True)
    assert [(m.source, m.destination) for m in first.moved] == [
        (m.source, m.destination) for m in second.moved
    ]


def test_collision_suffix_counts_up(tmp_path):
    inbox = tmp_path
    _write(inbox / "dup.txt", b"one")
    (inbox / "documents").mkdir()
    _write(inbox / "documents" / "dup.txt", b"pre-existing")
    report = triage(inbox)
    assert report.moved_count == 1
    assert report.moved[0].destination == os.path.join("documents", "dup-2.txt")


def test_dry_run_moves_nothing(tmp_path):
    inbox = _inbox_with_samples(tmp_path)
    report = triage(inbox, dry_run=True)
    assert report.moved_count == 5
    assert (inbox / "notes.txt").exists()  # still in place
    assert read_ledger(inbox) == []  # nothing ledgered


def test_directories_are_skipped_not_moved(tmp_path):
    inbox = _inbox_with_samples(tmp_path)
    (inbox / "subdir").mkdir()
    _write(inbox / "subdir" / "inner.txt", b"stays")
    report = triage(inbox)
    assert (inbox / "subdir" / "inner.txt").exists()
    assert "subdir" in report.skipped


def test_symlink_escape_is_refused(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _inbox_with_samples(inbox)
    outside = tmp_path / "outside"
    outside.mkdir()
    _write(outside / "secret.txt", b"do not touch")
    os.symlink(outside / "secret.txt", inbox / "evil-link.txt")
    report = triage(inbox)
    assert "evil-link.txt" in report.refused
    assert (outside / "secret.txt").read_bytes() == b"do not touch"
    assert not (inbox / "documents" / "evil-link.txt").exists()


def test_missing_inbox_is_refused(tmp_path):
    report = triage(tmp_path / "nope")
    assert report.moved_count == 0
    assert report.refused
