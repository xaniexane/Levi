"""Tests for levi.demand.workflows — the 10 original workflows wired into
the alert engine, plus monthly recurrence and day-of-week pinning in alerts."""

from datetime import datetime

import pytest

from levi.demand import workflows as wfmod
from levi.demand.alerts import Alert, AlertEngine
from levi.demand.pulse import DemandPulse


def _local(year=2026, month=9, day=21, hour=12, minute=0):
    return datetime(year, month, day, hour, minute).astimezone()


def _engine(tmp_path):
    return AlertEngine(path=tmp_path / "alerts.json")


# ---- workflow table -----------------------------------------------------------


def test_ten_workflows_with_original_schedules():
    rows = wfmod.list_workflows()
    assert len(rows) == 10
    by_id = {r["id"]: r for r in rows}
    assert by_id[1]["schedule"] == "7:00 AM CDT daily"
    assert by_id[3]["schedule"] == "Monday 8:00 AM CDT"
    assert by_id[4]["schedule"] == "Event-driven (score ≥ threshold)"
    assert by_id[7]["schedule"] == "1st of month 8:00 AM"
    assert by_id[8]["alert_kind"] == "pipeline"  # correlation: not an alert
    assert by_id[10]["schedule"] == "Friday 6:00 PM CDT"


# ---- install_workflows ----------------------------------------------------------


def test_install_workflows_creates_nine_alerts(tmp_path):
    eng = _engine(tmp_path)
    created = wfmod.install_workflows(eng)
    assert len(created) == 9  # workflow 8 is a pipeline step, not an alert
    kinds = [a.type for a in created]
    assert kinds.count("briefing") == 6
    assert kinds.count("watch") == 2
    assert kinds.count("threshold") == 1


def test_install_workflows_idempotent(tmp_path):
    eng = _engine(tmp_path)
    assert len(wfmod.install_workflows(eng)) == 9
    assert wfmod.install_workflows(eng) == []  # second install: no-op
    assert len(eng.alerts) == 9


def test_workflow_alert_specs(tmp_path):
    eng = _engine(tmp_path)
    wfmod.install_workflows(eng)
    by_name = {a.name: a for a in eng.alerts}
    digest = by_name["DP Workflow 3: Weekly Opportunity Digest"]
    assert digest.recurrence == "weekly" and digest.dow == 0 and digest.time == "08:00"
    monthly = by_name["DP Workflow 7: Monthly Industry Landscape Report"]
    assert monthly.recurrence == "monthly"
    miner = by_name["DP Workflow 2: Community Pain Point Miner"]
    assert miner.type == "watch" and miner.segment == "pain_point"
    detector = by_name["DP Workflow 9: Breakout Detector"]
    assert detector.type == "watch" and detector.segment == "breakout"
    high = by_name["DP Workflow 4: High-Score Alert"]
    assert high.type == "threshold" and high.threshold == 75.0


def test_workflow_status(tmp_path):
    eng = _engine(tmp_path)
    rows = wfmod.workflow_status(eng)
    assert all(r["installed"] is False for r in rows if r["id"] != 8)
    wfmod.install_workflows(eng)
    rows = wfmod.workflow_status(eng)
    assert all(r["installed"] and r["enabled"] for r in rows if r["id"] != 8)
    assert next(r for r in rows if r["id"] == 8)["installed"] is None


# ---- monthly recurrence ----------------------------------------------------------


def test_monthly_briefing_fires_on_first_of_month(tmp_path):
    eng = _engine(tmp_path)
    eng.create("briefing", "monthly test", time="08:00", recurrence="monthly")
    dp = DemandPulse(path=tmp_path / "dp.json")
    # before the 1st 08:00: nothing due
    assert eng.evaluate(dp, _local(day=1, hour=7)) == []
    # after the 1st 08:00: fires once
    assert len(eng.evaluate(dp, _local(day=1, hour=9))) == 1
    # later in the month: deduped, no second fire
    assert eng.evaluate(dp, _local(day=15, hour=9)) == []


def test_monthly_recurrence_rejected_without_support(tmp_path):
    with pytest.raises(ValueError):
        Alert(id="x", type="briefing", name="bad", recurrence="fortnightly")


# ---- weekly day-of-week pinning -----------------------------------------------------


def test_weekly_dow_pins_monday(tmp_path):
    eng = _engine(tmp_path)
    eng.create("briefing", "monday digest", time="08:00", recurrence="weekly", dow=0)
    dp = DemandPulse(path=tmp_path / "dp.json")
    # 2026-09-21 is a Monday
    assert len(eng.evaluate(dp, _local(day=21, hour=9))) == 1
    # Tuesday: not the pinned day
    assert eng.evaluate(dp, _local(day=22, hour=9)) == []


def test_weekly_dow_any_day_default(tmp_path):
    eng = _engine(tmp_path)
    eng.create("briefing", "any-day", time="08:00", recurrence="weekly")
    dp = DemandPulse(path=tmp_path / "dp.json")
    eng2_now = _local(day=22, hour=9)  # Tuesday
    assert len(eng.evaluate(dp, eng2_now)) == 1


def test_dow_validation():
    with pytest.raises(ValueError):
        Alert(id="x", type="briefing", name="bad dow", dow=7)
    with pytest.raises(ValueError):
        Alert(id="x", type="briefing", name="bad dow", dow=-2)
    Alert(id="x", type="briefing", name="ok", dow=-1)  # any day: fine
    Alert(id="x", type="briefing", name="ok", dow=6)  # Sunday: fine


# ---- feed_scan_into_demandpulse ------------------------------------------------------


def _cluster(cid, stype, n_signals, n_sources, theme):
    return {
        "cluster_id": cid,
        "theme": theme,
        "industry": "Technology / SaaS",
        "signal_type": stype,
        "signal_count": n_signals,
        "multi_source_validated": n_sources >= 2,
        "confidence": "high" if n_sources >= 2 else "medium",
        "signals": [
            {"source": f"src{i % n_sources}", "summary": theme}
            for i in range(n_signals)
        ],
    }


def _scan():
    return {
        "scanned_at": "2026-09-21T00:00:00+00:00",
        "clusters": [
            _cluster("c1", "pain_point", 5, 2, "i wish dispatch was simpler"),
            _cluster("c2", "trend", 1, 1, "offline tools trending"),
        ],
    }


def test_feed_scan_bridges_clusters_to_observed_signals(tmp_path):
    dp = DemandPulse(path=tmp_path / "dp.json")
    produced = wfmod.feed_scan_into_demandpulse(dp, _scan())
    segments = [s.segment for s in produced]
    # one per cluster in its signal-type segment, plus a breakout signal
    # for the multi-source 5-signal cluster
    assert segments == ["pain_point", "breakout", "trend"]
    for sig in produced:
        assert sig.kind == "OBSERVED"  # real fetched text, never invented
        assert "OBSERVED" in sig.evidence


def test_breakout_needs_multi_source_and_four_signals(tmp_path):
    dp = DemandPulse(path=tmp_path / "dp.json")
    scan = {
        "scanned_at": "x",
        "clusters": [
            _cluster("c1", "pain_point", 3, 2, "small cluster"),  # multi but < 4
            _cluster("c2", "pain_point", 5, 1, "one-source"),  # 5 but 1 source
        ],
    }
    produced = wfmod.feed_scan_into_demandpulse(dp, scan)
    assert [s.segment for s in produced] == ["pain_point", "pain_point"]


def test_watch_alert_fires_on_fed_pain_point(tmp_path):
    dp = DemandPulse(path=tmp_path / "dp.json")
    eng = _engine(tmp_path)
    eng.create("watch", "pain miner", segment="pain_point")
    wfmod.feed_scan_into_demandpulse(dp, _scan())
    events = eng.evaluate(dp, _local(hour=12))
    assert any(e.kind == "watch" and "pain_point" in e.title for e in events)


# ---- run_workflow --------------------------------------------------------------------


def test_run_workflow_rejects_unknown():
    with pytest.raises(ValueError):
        wfmod.run_workflow(11)


def test_run_workflow_8_without_scan(monkeypatch):
    monkeypatch.setattr(wfmod, "load_last_scan", lambda: None)
    result = wfmod.run_workflow(8)
    assert result["correlated"] == 0
    assert "no stored scan" in result["note"]


def test_run_workflow_8_recorrelates_stored_scan(monkeypatch):
    monkeypatch.setattr(
        wfmod,
        "load_last_scan",
        lambda: {
            "scanned_at": "x",
            "signals": [
                {
                    "industry": "Technology / SaaS",
                    "signal_type": "pain_point",
                    "keywords": ["dispatch"],
                    "source": "social",
                    "confidence": "high",
                    "summary": "i wish dispatch was simpler",
                },
                {
                    "industry": "Technology / SaaS",
                    "signal_type": "pain_point",
                    "keywords": ["dispatch"],
                    "source": "reddit",
                    "confidence": "high",
                    "summary": "i wish dispatch was simpler",
                },
            ],
        },
    )
    result = wfmod.run_workflow(8)
    assert result["correlated"] == 1


def test_run_workflow_scan_feeds_and_evaluates(monkeypatch, tmp_path):
    from levi.demand import alerts as alertmod

    scan = _scan()
    monkeypatch.setattr(wfmod, "run_scan", lambda query: scan)
    monkeypatch.setattr(alertmod, "DEFAULT_OUTBOX_PATH", tmp_path / "outbox.jsonl")
    dp = DemandPulse(path=tmp_path / "dp.json")
    eng = _engine(tmp_path)
    eng.create("watch", "pain miner", segment="pain_point")
    result = wfmod.run_workflow(2, query="dispatch", dp=dp, engine=eng)
    assert result["workflow"] == 2
    assert result["fed_into_demandpulse"] == 3
    assert result["alert_receipt"]["fired"] >= 1
