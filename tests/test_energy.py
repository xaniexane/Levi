"""Hermetic tests for levi.energy — peak learning with honest small samples.

No network, no real ~/.levi: every test redirects $LEVI_HOME to a tmp dir
(or injects an explicit home), and "now" is always injectable.
"""

import pytest

from levi.energy.tracker import EnergyLog, MIN_PEAK_SESSIONS


@pytest.fixture
def log(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return EnergyLog()


def _day(base, hour, minute=0, span=90):
    from datetime import datetime, timedelta

    s = datetime(2026, 9, 7 + base, hour, minute)  # a Mon..Sun week
    return s, s + timedelta(minutes=span)


def test_log_session_roundtrip(log):
    s, e = _day(0, 9, 0, 90)
    sess = log.log_session(s, e, "deep", True)
    assert sess.duration_min == 90
    assert sess.kind == "deep"
    assert sess.shipped is True
    rows = log.sessions()
    assert len(rows) == 1
    assert rows[0].id == sess.id


def test_log_session_validation(log):
    s, e = _day(0, 9)
    with pytest.raises(ValueError):
        log.log_session(e, s, "deep", True)  # end before start
    with pytest.raises(ValueError):
        log.log_session(s, e, "   ", True)  # blank kind
    with pytest.raises(ValueError):
        log.log_session("not-a-date", e, "deep", True)


def test_log_session_accepts_iso_strings(log):
    sess = log.log_session("2026-09-15T09:00:00", "2026-09-15T10:30:00", "admin", False)
    assert sess.duration_min == 90
    assert sess.shipped is False


def test_small_sample_honesty(log):
    for i in range(3):
        s, e = _day(i, 9, 0, 60)
        log.log_session(s, e, "deep", True)
    peaks = log.peak_hours()
    assert peaks["enough_data"] is False
    assert peaks["n_deep_shipped"] == 3
    assert peaks["need"] == MIN_PEAK_SESSIONS - 3
    assert peaks["windows"] == []
    assert "not enough data" in peaks["note"]


def test_only_shipped_deep_counts(log):
    # 8 sessions but half unshipped, half admin — still not enough deep/shipped
    for i in range(4):
        s, e = _day(i, 9, 0, 60)
        log.log_session(s, e, "deep", False)
    for i in range(4):
        s, e = _day(i, 14, 0, 60)
        log.log_session(s, e, "admin", True)
    peaks = log.peak_hours()
    assert peaks["enough_data"] is False
    assert peaks["n_deep_shipped"] == 0


def _seed_morning_peaks(log):
    # 10 shipped deep sessions, 9:00-10:30 — a clear morning peak.
    for i in range(10):
        s, e = _day(i % 7, 9, 0, 90)
        log.log_session(s, e, "deep", True)
    # 2 shipped deep sessions in the evening — noise, not the peak.
    for i in range(2):
        s, e = _day(i, 20, 0, 60)
        log.log_session(s, e, "deep", True)


def test_peak_learning_finds_morning(log):
    _seed_morning_peaks(log)
    peaks = log.peak_hours()
    assert peaks["enough_data"] is True
    assert peaks["n_deep_shipped"] == 12
    top = peaks["windows"][0]
    assert top["start_hour"] == 9
    assert top["share"] > 0.5


def test_suggest_slot_learned_basis(log):
    from datetime import datetime

    _seed_morning_peaks(log)
    slot = log.suggest_slot("hard", now=datetime(2026, 9, 15, 7, 0))
    assert slot["basis"] == "learned"
    when = datetime.fromisoformat(slot["when"])
    assert when.hour == 9
    assert "shipped deep sessions" in slot["rationale"]


def test_suggest_slot_heuristic_when_no_data(log):
    from datetime import datetime

    slot = log.suggest_slot("deep", now=datetime(2026, 9, 15, 7, 0))
    assert slot["basis"] == "heuristic"
    assert "log" in slot["rationale"]  # honest about needing data
    when = datetime.fromisoformat(slot["when"])
    assert when.hour == 8  # morning fallback


def test_suggest_slot_light_needs_no_peak(log):
    from datetime import datetime

    now = datetime(2026, 9, 15, 15, 30)
    slot = log.suggest_slot("admin", now=now)
    assert slot["basis"] == "heuristic"
    assert datetime.fromisoformat(slot["when"]) == now.replace(second=0, microsecond=0)


def test_suggest_slot_rejects_bad_weight(log):
    with pytest.raises(ValueError):
        log.suggest_slot("extreme")


def test_explicit_home_injection(tmp_path):
    log = EnergyLog(home=tmp_path / "custom")
    s, e = _day(0, 9, 0, 30)
    log.log_session(s, e, "deep", True)
    assert (tmp_path / "custom" / "energy" / "sessions.json").exists()


def test_cli_smoke(tmp_path, monkeypatch, capsys):
    from levi.energy.__main__ import main

    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    assert (
        main(
            [
                "log",
                "--start",
                "2026-09-15T09:00",
                "--end",
                "2026-09-15T10:00",
                "--kind",
                "deep",
                "--shipped",
                "yes",
            ]
        )
        == 0
    )
    assert main(["peaks"]) == 0
    out = capsys.readouterr().out
    assert "not enough data" in out
    assert main(["suggest", "--weight", "hard", "--at", "2026-09-15T07:00"]) == 0
    out = capsys.readouterr().out
    assert "heuristic" in out
    assert (
        main(["log", "--start", "2026-09-15T10:00", "--end", "2026-09-15T09:00"]) == 1
    )  # rejected cleanly
