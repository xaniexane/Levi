"""Tests for automation run receipts — the append-only evidence ledger."""

import pytest

from levi.automation.receipts import (
    OUTCOMES,
    Receipt,
    ReceiptError,
    ReceiptLedger,
)


def _ledger(tmp_path):
    return ReceiptLedger(tmp_path / "receipts.jsonl")


def test_record_ok(tmp_path):
    ledger = _ledger(tmp_path)
    r = ledger.record("nightly-sweep", "ok", detail="7 files swept")
    assert r.seq == 1
    assert r.automation == "nightly-sweep"
    assert r.outcome == "ok"
    assert r.duration_s == 0.0


def test_deny_closed_outcome(tmp_path):
    ledger = _ledger(tmp_path)
    with pytest.raises(ReceiptError):
        ledger.record("x", "exploded")


def test_deny_closed_negative_duration(tmp_path):
    ledger = _ledger(tmp_path)
    with pytest.raises(ReceiptError):
        ledger.record("x", "ok", duration_s=-1.0)


def test_capture_ok_records_duration(tmp_path):
    ledger = _ledger(tmp_path)
    with ledger.capture("heartbeat"):
        pass
    (r,) = ledger.recent("heartbeat")
    assert r.outcome == "ok"
    assert r.duration_s >= 0.0


def test_capture_failed_propagates_and_records(tmp_path):
    ledger = _ledger(tmp_path)
    with pytest.raises(RuntimeError):
        with ledger.capture("heartbeat"):
            raise RuntimeError("boom")
    (r,) = ledger.recent("heartbeat")
    assert r.outcome == "failed"
    assert "RuntimeError" in r.detail


def test_streaks_and_failing(tmp_path):
    ledger = _ledger(tmp_path)
    for _ in range(3):
        ledger.record("flaky", "failed")
    ledger.record("flaky", "ok")  # streak breaks
    assert ledger.streaks() == {}
    ledger.record("flaky", "failed")
    ledger.record("flaky", "failed")
    assert ledger.streaks() == {"flaky": 2}
    assert ledger.failing(threshold=3) == []
    ledger.record("flaky", "failed")
    assert ledger.failing(threshold=3) == ["flaky"]


def test_recent_limit(tmp_path):
    ledger = _ledger(tmp_path)
    for i in range(5):
        ledger.record("job", "ok", detail=f"run {i}")
    rows = ledger.recent("job", limit=2)
    assert [r.detail for r in rows] == ["run 3", "run 4"]


def test_summarize_names_failing(tmp_path):
    ledger = _ledger(tmp_path)
    for _ in range(3):
        ledger.record("doomed", "failed")
    text = ledger.summarize()
    assert "doomed" in text
    assert "failing streaks" in text


def test_prune_old(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record(
        "old",
        "ok",
        started="2020-01-01T00:00:00+00:00",
        ended="2020-01-01T00:00:01+00:00",
    )
    ledger.record("new", "ok")
    dropped = ledger.prune(older_than_days=30)
    assert dropped == 1
    assert [r.automation for r in ledger.recent(limit=10)] == ["new"]


def test_outcomes_closed_set():
    assert set(OUTCOMES) == {"ok", "failed", "skipped", "held"}


def test_roundtrip(tmp_path):
    ledger = _ledger(tmp_path)
    r = ledger.record("job", "skipped", detail="quiet hours")
    back = Receipt.from_dict(r.to_dict())
    assert back == r
