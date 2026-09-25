"""Tests for levi.daemon.ledger: the local-first resource logbook."""

import json
import time

import pytest

from levi.daemon.ledger import (
    DISK_FLAG_PCT,
    LedgerError,
    Sample,
    read_samples,
    sample,
    summarize,
)


@pytest.fixture()
def ledger(tmp_path):
    return tmp_path / "ledger.jsonl"


def test_sample_appends_and_reads_back(ledger):
    first = sample(ledger=ledger)
    second = sample(ledger=ledger)
    assert second.ts >= first.ts
    records = read_samples(ledger)
    assert len(records) == 2
    assert records[0].to_dict()["disk_pct"] == records[0].disk_pct
    assert 0.0 <= records[0].disk_pct <= 100.0
    assert records[0].disk_total_gb >= records[0].disk_used_gb


def test_sample_refuses_missing_disk_path(ledger, tmp_path):
    with pytest.raises(LedgerError):
        sample(ledger=ledger, path=tmp_path / "nope")


def test_read_samples_skips_malformed_lines(ledger):
    ledger.write_text(
        '{"ts": 1}\nnot json\n{"ts": 2, "load1": null}\n', encoding="utf-8"
    )
    # {"ts": 1} is missing required keys -> LedgerError -> skipped
    records = read_samples(ledger)
    assert records == []


def _write(ledger, rows):
    with ledger.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _record(ts, load1=0.1, pct=10.0, cpu=8):
    return {
        "ts": ts,
        "load1": load1,
        "load5": 0.1,
        "load15": 0.1,
        "cpu_count": cpu,
        "disk_used_gb": 1.0,
        "disk_total_gb": 10.0,
        "disk_pct": pct,
    }


def test_summarize_window_averages(ledger):
    now = time.time()
    _write(
        ledger,
        [
            _record(now - 3600, load1=0.2, pct=20.0),
            _record(now - 1800, load1=0.4, pct=30.0),
            _record(now - 30 * 86400, load1=99.0, pct=99.0),  # outside window
        ],
    )
    report = summarize(hours=24, ledger=ledger, now=now)
    assert report.samples == 2
    assert report.load1_avg == pytest.approx(0.3)
    assert report.disk_pct_avg == pytest.approx(25.0)
    assert not report.flagged()


def test_summarize_flags_high_disk(ledger):
    now = time.time()
    _write(ledger, [_record(now - 60, pct=DISK_FLAG_PCT + 5)])
    report = summarize(hours=1, ledger=ledger, now=now)
    assert report.disk_flagged
    assert report.flagged()


def test_summarize_flags_high_load(ledger):
    now = time.time()
    _write(ledger, [_record(now - 60, load1=7.5, cpu=8)])  # > 0.9 * 8
    report = summarize(hours=1, ledger=ledger, now=now)
    assert report.load_flagged
    assert report.flagged()
    assert "exceeds" in report.load_note


def test_summarize_empty_window(ledger):
    report = summarize(hours=1, ledger=ledger)
    assert report.samples == 0
    assert not report.flagged()
    assert report.load_note  # says why


def test_summarize_deny_closed_bad_hours(ledger):
    with pytest.raises(LedgerError):
        summarize(hours=0, ledger=ledger)
    with pytest.raises(LedgerError):
        summarize(hours=-3, ledger=ledger)
    with pytest.raises(LedgerError):
        summarize(hours="day", ledger=ledger)


def test_sample_record_round_trip():
    s = Sample(
        ts=1700000000.0,
        load1=0.5,
        load5=0.4,
        load15=0.3,
        cpu_count=4,
        disk_used_gb=12.5,
        disk_total_gb=100.0,
        disk_pct=12.5,
    )
    back = Sample.from_dict(json.loads(json.dumps(s.to_dict())))
    assert back == s


def test_sample_record_deny_closed_bad_dict():
    with pytest.raises(LedgerError):
        Sample.from_dict({"ts": "yesterday"})
