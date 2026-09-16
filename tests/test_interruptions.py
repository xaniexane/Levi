"""Hermetic tests for levi.interruptions — tmp HOME, injectable now."""

from datetime import datetime, timedelta, timezone

import pytest

from levi.interruptions import InterruptionError, InterruptionLedger, check, noise_roi


def _t(days_ago=0):
    return datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc) - timedelta(days=days_ago)


@pytest.fixture()
def ledger(tmp_path):
    return InterruptionLedger(home=tmp_path)


def test_log_and_values(ledger):
    e = ledger.log("heartbeat", "pulse check", "useful")
    assert e["value"] == "useful"
    assert e["source"] == "heartbeat"
    ledger.log("nudge-engine", "random tip", "noise")
    ledger.log("nudge-engine", "another tip", "mixed")
    assert len(ledger.entries()) == 3


def test_log_validation(ledger):
    with pytest.raises(InterruptionError):
        ledger.log("", "summary", "noise")
    with pytest.raises(InterruptionError):
        ledger.log("src", "", "noise")
    with pytest.raises(InterruptionError):
        ledger.log("src", "summary", "vibes")


def test_noise_roi_mixed_data(ledger):
    ledger.log("nudge-engine", "tip 1", "noise", at=_t(1))
    ledger.log("nudge-engine", "tip 2", "noise", at=_t(2))
    ledger.log("heartbeat", "pulse", "useful", at=_t(1))
    ledger.log("heartbeat", "digest", "mixed", at=_t(3))
    ledger.log("old-source", "stale", "noise", at=_t(30))  # outside window

    r = ledger.noise_roi(days=7, now=_t(0))
    assert r["counts"] == {"useful": 1, "noise": 2, "mixed": 1}
    assert r["total"] == 4
    assert r["noise_ratio"] == pytest.approx(0.5)
    assert r["top_noisy_sources"][0] == {
        "source": "nudge-engine",
        "noise": 2,
        "total": 2,
    }
    assert "nudge-engine" in r["verdict"]


def test_noise_roi_quiet_week(ledger):
    ledger.log("heartbeat", "pulse", "useful", at=_t(1))
    ledger.log("heartbeat", "digest", "useful", at=_t(2))
    r = ledger.noise_roi(days=7, now=_t(0))
    assert r["noise_ratio"] == 0.0
    assert "quiet" in r["verdict"]


def test_noise_roi_empty_state_honesty(ledger):
    r = ledger.noise_roi(days=7, now=_t(0))
    assert r["total"] == 0
    assert r["noise_ratio"] is None
    assert r["top_noisy_sources"] == []
    assert "nothing logged" in r["verdict"]


def test_check_weekly_nudge_card(ledger):
    ledger.log("nudge-engine", "tip", "noise", at=_t(1))
    ledger.log("heartbeat", "pulse", "useful", at=_t(2))
    cards = ledger.check(now=_t(0))
    assert len(cards) == 1
    card = cards[0]
    assert card["grade"] == "NUDGE"
    assert card["tag"] == "interruptions:weekly-noise"
    assert set(card) == {"grade", "tag", "title", "body"}
    assert "nudge-engine" in card["body"]


def test_check_empty_is_honest_nudge(ledger):
    cards = ledger.check(now=_t(0))
    assert len(cards) == 1
    assert cards[0]["grade"] == "NUDGE"
    assert "empty" in cards[0]["body"]


def test_module_level_surfaces(tmp_path):
    lg = InterruptionLedger(home=tmp_path)
    lg.log("heartbeat", "pulse", "useful", at=_t(1))
    r = noise_roi(home=tmp_path, days=7, now=_t(0))
    assert r["total"] == 1
    cards = check(home=tmp_path, now=_t(0))
    assert cards and cards[0]["grade"] == "NUDGE"


def test_window_boundaries(ledger):
    ledger.log("s", "inside", "noise", at=_t(6))
    ledger.log("s", "outside", "noise", at=_t(8))
    r = ledger.noise_roi(days=7, now=_t(0))
    assert r["total"] == 1


def test_days_validation(ledger):
    with pytest.raises(InterruptionError):
        ledger.noise_roi(days=0)


def test_home_resolution_call_time(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "alt"))
    lg = InterruptionLedger()
    lg.log("src", "summary", "useful")
    assert (
        tmp_path / "alt" / ".levi" / "interruptions" / "interruptions.jsonl"
    ).exists()
