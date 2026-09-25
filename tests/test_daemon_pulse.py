"""Tests for levi.daemon.pulse — the DemandPulse pulse daemon.

Law → guard → prove for each invariant in pulse.py's header.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from levi.daemon import pulse as pulse_mod
from levi.daemon.herald import HeraldQueue
from levi.demand.alerts import AlertEngine
from levi.demand.pulse import DemandPulse
from levi.demand.scoring import FACTORS, FactorScore, ScoreCard


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def _hot_card() -> ScoreCard:
    """A score card whose composite clears the default 75 bar."""
    factors = [
        FactorScore(name=name, value=95.0, basis="test basis")
        for name in FACTORS
    ]
    weights = {name: 1.0 / len(FACTORS) for name in FACTORS}
    return ScoreCard(
        opportunity_id="opp-1", title="Test opportunity",
        factors=factors, weights=weights,
    )


def _seed_dp(dp_path: Path) -> DemandPulse:
    dp = DemandPulse(path=dp_path)
    dp.score_cards.append(_hot_card())
    dp._persist()
    return dp


def _seed_engine(alerts_path: Path, **kwargs) -> AlertEngine:
    eng = AlertEngine(path=alerts_path)
    eng.create("threshold", "test threshold alert", **kwargs)
    return eng


def _run(tmp_path, **kwargs):
    home = tmp_path / "home"
    dp_path = tmp_path / "demand_pulse.json"
    alerts_path = tmp_path / "demand_alerts.json"
    queue = HeraldQueue(tmp_path / "herald" / "queue.jsonl")
    return pulse_mod.run_pulse(
        home=home,
        dp_path=dp_path,
        alerts_path=alerts_path,
        queue=queue,
        force=True,
        **kwargs,
    ), queue


# ---------------------------------------------------------------------------
# invariant 1: exactly-once firing
# ---------------------------------------------------------------------------


def test_fires_and_barks_exactly_once(tmp_path):
    dp_path = tmp_path / "demand_pulse.json"
    alerts_path = tmp_path / "demand_alerts.json"
    _seed_dp(dp_path)
    _seed_engine(alerts_path)

    r1, queue = _run(tmp_path)
    assert r1.fired == 1
    assert r1.delivered == 1
    assert r1.barked == 1
    assert not r1.silent
    assert len(queue.pending()) == 1
    assert queue.pending()[0].source == "pulse"

    # Second tick: the alert engine's dedup keys stop the re-fire.
    r2, queue2 = _run(tmp_path)
    assert r2.fired == 0
    assert r2.barked == 0
    assert r2.silent
    assert len(queue2.pending()) == 1  # no second bark queued


# ---------------------------------------------------------------------------
# invariant 2: quiet hours hold, then flush
# ---------------------------------------------------------------------------


def test_quiet_hours_hold_then_flush(tmp_path):
    dp_path = tmp_path / "demand_pulse.json"
    alerts_path = tmp_path / "demand_alerts.json"
    _seed_dp(dp_path)
    eng = _seed_engine(
        alerts_path, quiet_start="00:00", quiet_end="23:59"
    )  # always quiet
    alert_id = eng.alerts[0].id

    now = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
    r1, _ = _run(tmp_path, now=now)
    assert r1.fired == 1
    assert r1.held == 1
    assert r1.delivered == 0
    assert r1.barked == 0

    # Reopen the alert outside quiet hours; the held event must flush.
    eng2 = AlertEngine(path=alerts_path)
    for i, a in enumerate(eng2.alerts):
        if a.id == alert_id:
            data = a.to_dict()
            data["quiet_start"] = "03:00"
            data["quiet_end"] = "03:01"
            from levi.demand.alerts import Alert

            eng2.alerts[i] = Alert.from_dict(data)
    eng2._persist()

    r2, queue2 = _run(tmp_path, now=now)
    assert r2.flushed == 1
    assert r2.barked == 1
    assert len(queue2.pending()) == 1


# ---------------------------------------------------------------------------
# invariant 3: never crash on corrupt state
# ---------------------------------------------------------------------------


def test_corrupt_demand_state_is_honest_not_fatal(tmp_path):
    dp_path = tmp_path / "demand_pulse.json"
    dp_path.write_text("{not valid json", encoding="utf-8")
    alerts_path = tmp_path / "demand_alerts.json"

    result, _ = _run(tmp_path)
    assert result.silent
    assert result.reason == "state unreadable"
    assert result.notes, "corrupt state must produce one honest note"


def test_corrupt_alert_store_is_honest_not_fatal(tmp_path):
    dp_path = tmp_path / "demand_pulse.json"
    _seed_dp(dp_path)
    alerts_path = tmp_path / "demand_alerts.json"
    alerts_path.write_text("[broken", encoding="utf-8")

    result, _ = _run(tmp_path)
    # AlertEngine._load swallows corrupt stores and starts empty —
    # the pulse must still complete honestly.
    assert result.silent
    assert result.fired == 0


# ---------------------------------------------------------------------------
# invariant 4: honest channels
# ---------------------------------------------------------------------------


def test_unconfigured_channels_reported_never_faked(tmp_path):
    dp_path = tmp_path / "demand_pulse.json"
    alerts_path = tmp_path / "demand_alerts.json"
    _seed_dp(dp_path)
    _seed_engine(alerts_path, channels=("push",))

    result, _ = _run(tmp_path)
    assert result.delivered == 1  # the tick still counts delivery attempts
    assert any("not configured" in n for n in result.notes), (
        "push must be reported as not_configured, never claimed delivered: "
        + repr(result.notes)
    )


# ---------------------------------------------------------------------------
# invariant 5: silent idle
# ---------------------------------------------------------------------------


def test_silent_when_nothing_fires(tmp_path):
    dp_path = tmp_path / "demand_pulse.json"
    dp_path.write_text(
        json.dumps({"signals": [], "opportunities": [], "score_cards": []}),
        encoding="utf-8",
    )
    result, _ = _run(tmp_path)
    assert result.silent
    assert result.fired == 0
    assert result.reason == "nothing fired"


# ---------------------------------------------------------------------------
# interval discipline
# ---------------------------------------------------------------------------


def test_interval_validation_rejects_bad_values():
    with pytest.raises(ValueError):
        pulse_mod._resolve_interval(0)
    with pytest.raises(ValueError):
        pulse_mod._resolve_interval(-5)
    with pytest.raises(ValueError):
        pulse_mod._resolve_interval(1.5)
    with pytest.raises(ValueError):
        pulse_mod._resolve_interval(True)
    assert pulse_mod._resolve_interval(30) == 30


def test_interval_gate_skips_fresh_tick(tmp_path):
    dp_path = tmp_path / "demand_pulse.json"
    _seed_dp(dp_path)
    alerts_path = tmp_path / "demand_alerts.json"
    _seed_engine(alerts_path)

    home = tmp_path / "home"
    queue = HeraldQueue(tmp_path / "herald" / "queue.jsonl")
    kwargs = dict(
        home=home, dp_path=dp_path, alerts_path=alerts_path,
        queue=queue, force=False,
    )
    r1 = pulse_mod.run_pulse(**kwargs)
    assert r1.reason != "interval not elapsed"
    r2 = pulse_mod.run_pulse(**kwargs)
    assert r2.silent and r2.reason == "interval not elapsed"


# ---------------------------------------------------------------------------
# supervisor registration
# ---------------------------------------------------------------------------


def test_registered_in_supervisor_catalog():
    from levi.daemon.supervisor import Supervisor

    names = [e["name"] for e in Supervisor.SERVICE_CATALOG]
    assert "pulse" in names
    entry = next(e for e in Supervisor.SERVICE_CATALOG if e["name"] == "pulse")
    assert entry["module"] == "levi.daemon.pulse"
    assert callable(entry["_check_fn"])


def test_supervisor_health_check_never_raises(tmp_path):
    from levi.daemon.supervisor import Supervisor

    sup = Supervisor(home=tmp_path / "home")
    st = sup.service_status("pulse")
    assert isinstance(st["ok"], bool) and isinstance(st["detail"], str)
    assert st["ok"] is True


def test_pulse_check_function_reports(tmp_path):
    ok, detail = pulse_mod.check(home=tmp_path / "home")
    assert ok is True
    assert isinstance(detail, str)
