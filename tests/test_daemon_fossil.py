"""Tests for levi.daemon.fossil — the journal-compaction daemon."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from levi.daemon.fossil import (
    FossilConfig,
    compact_journal,
    digest_records,
    run_once,
)


def _journal(tmp_path, name="journal.jsonl", records=()) -> str:
    path = tmp_path / name
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return str(path)


def _rec(day_offset, kind="note"):
    return {
        "at": (datetime.now(timezone.utc) - timedelta(days=day_offset)).isoformat(),
        "kind": kind,
        "id": f"rec-{day_offset}-{kind}",
    }


def test_digest_groups_by_day_and_kind():
    records = [_rec(40, "note"), _rec(41, "note"), _rec(42, "crash")]
    digest = digest_records(records)
    assert digest["total"] == 3
    total_kinds = sum(sum(day.values()) for day in digest["per_day"].values())
    assert total_kinds == 3
    assert digest["first_ts"] < digest["last_ts"]
    assert digest["samples"]["note"] == ["rec-40-note", "rec-41-note"]


def test_dry_run_changes_nothing(tmp_path):
    path = _journal(tmp_path, records=[_rec(60), _rec(1)])
    before = open(path, encoding="utf-8").read()
    receipt = compact_journal(path, older_than_days=30, dry_run=True)
    assert receipt.dry_run is True
    assert receipt.kept == 1
    assert receipt.compacted == 1
    assert receipt.digest["total"] == 1
    assert open(path, encoding="utf-8").read() == before


def test_apply_compacts_and_keeps_recent(tmp_path):
    path = _journal(tmp_path, records=[_rec(60, "crash"), _rec(90, "crash"), _rec(1)])
    receipt = compact_journal(path, older_than_days=30, dry_run=False)
    assert receipt.kept == 1
    assert receipt.compacted == 2
    lines = [json.loads(ln) for ln in open(path, encoding="utf-8")]
    assert len(lines) == 1
    # digest landed on disk before the journal was rewritten
    import os

    digest_file = receipt.digest_path
    assert os.path.exists(digest_file)
    entry = json.loads(
        open(digest_file, encoding="utf-8").read().strip().splitlines()[-1]
    )
    assert entry["digest"]["total"] == 2


def test_undated_records_are_never_compacted(tmp_path):
    path = _journal(
        tmp_path, records=[{"kind": "note", "text": "no timestamp at all"}, _rec(99)]
    )
    receipt = compact_journal(path, older_than_days=30, dry_run=False)
    assert receipt.kept == 1
    assert receipt.compacted == 1


def test_corrupt_line_aborts_run(tmp_path):
    path = tmp_path / "journal.jsonl"
    path.write_text(
        '{"at": "2020-01-01T00:00:00+00:00"}\n{not json}\n', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="corrupt"):
        compact_journal(str(path), older_than_days=30, dry_run=False)
    # journal untouched
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_missing_file_and_non_jsonl_refused(tmp_path):
    with pytest.raises(FileNotFoundError):
        compact_journal(str(tmp_path / "nope.jsonl"))
    txt = tmp_path / "notes.txt"
    txt.write_text("hello\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not a JSONL"):
        compact_journal(str(txt))


def test_run_once_writes_receipts_when_applied(tmp_path):
    path = _journal(tmp_path, records=[_rec(60), _rec(1)])
    receipts_path = tmp_path / "receipts.jsonl"
    config = FossilConfig(
        targets=[path],
        older_than_days=30,
        dry_run=False,
        receipts_path=str(receipts_path),
    )
    receipts = run_once(config)
    assert len(receipts) == 1
    assert receipts[0].compacted == 1
    lines = receipts_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["target"] == path
