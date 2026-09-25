"""Tests for the diskwatch connector — the ear on local disk health.

Proofs for the laws in ``levi/connectors/diskwatch.py``: observe-only,
honest baseline, edge-only events, and the deny-closed input gates.
"""

from collections import namedtuple

import pytest

from levi.connectors import diskwatch, registry
from levi.connectors.base import ConnectorError

Usage = namedtuple("Usage", "total used free")


def _fake_usage(monkeypatch, total, free):
    monkeypatch.setattr(
        diskwatch.shutil, "disk_usage", lambda _p: Usage(total, total - free, free)
    )


def _poll(**inputs):
    return registry.poll("diskwatch", **inputs)


def test_diskwatch_registers():
    ids = {c.id for c in registry.list()}
    assert "diskwatch" in ids
    desc = registry.get("diskwatch")
    assert desc.risk == "info"


def test_first_poll_emits_honest_baseline(tmp_path):
    events, state = _poll(path=str(tmp_path), state={})
    assert len(events) == 1
    ev = events[0]
    assert ev["kind"] == "baseline"
    assert ev["prev_band"] is None
    assert ev["band"] in ("ok", "warn", "crit")
    assert ev["path"] == str(tmp_path.resolve())
    assert state == {"band": ev["band"]}


def test_steady_band_is_silent(tmp_path, monkeypatch):
    _fake_usage(monkeypatch, total=100, free=50)  # 50% used → ok
    events, state = _poll(path=str(tmp_path), state={})
    assert events[0]["band"] == "ok"
    events2, state2 = _poll(path=str(tmp_path), state=state)
    assert events2 == []
    assert state2 == {"band": "ok"}


def test_band_change_emits_exactly_one_event(tmp_path, monkeypatch):
    _fake_usage(monkeypatch, total=100, free=50)  # ok
    _, state = _poll(path=str(tmp_path), state={})
    _fake_usage(monkeypatch, total=100, free=10)  # 90% → warn
    events, state = _poll(path=str(tmp_path), state=state)
    assert len(events) == 1
    ev = events[0]
    assert ev["kind"] == "band_changed"
    assert ev["prev_band"] == "ok"
    assert ev["band"] == "warn"
    assert ev["used_pct"] == 90.0
    assert state == {"band": "warn"}


def test_recovery_emits_event(tmp_path, monkeypatch):
    _fake_usage(monkeypatch, total=100, free=2)  # 98% → crit
    _, state = _poll(path=str(tmp_path), state={})
    _fake_usage(monkeypatch, total=100, free=60)  # 40% → ok
    events, state = _poll(path=str(tmp_path), state=state)
    assert len(events) == 1
    assert events[0]["kind"] == "band_changed"
    assert events[0]["prev_band"] == "crit"
    assert events[0]["band"] == "ok"
    assert state == {"band": "ok"}


def test_custom_thresholds(tmp_path, monkeypatch):
    _fake_usage(monkeypatch, total=100, free=30)  # 70% used
    events, _ = _poll(path=str(tmp_path), warn_pct=60, crit_pct=90, state={})
    assert events[0]["band"] == "warn"


def test_deny_closed_missing_path(tmp_path):
    with pytest.raises(ConnectorError):
        _poll(path=str(tmp_path / "nope"), state={})
    with pytest.raises(ConnectorError):
        _poll(state={})  # path required


def test_deny_closed_bad_thresholds(tmp_path):
    for warn, crit in ((90, 80), (80, 80), (0, 95), (80, 100), (-1, 50), ("a", 95)):
        with pytest.raises(ConnectorError):
            _poll(path=str(tmp_path), warn_pct=warn, crit_pct=crit, state={})


def test_deny_closed_bad_state_band(tmp_path):
    with pytest.raises(ConnectorError):
        _poll(path=str(tmp_path), state={"band": "meltdown"})


def test_poll_contract_shape(tmp_path):
    result = _poll(path=str(tmp_path), state={})
    assert isinstance(result, tuple) and len(result) == 2
    events, state = result
    assert isinstance(events, list) and isinstance(state, dict)
    for ev in events:
        assert {"kind", "band", "used_pct", "free_bytes", "total_bytes", "path"} <= set(
            ev
        )
