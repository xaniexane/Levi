"""Tests for levi.connectors.memwatch — the /proc/meminfo pressure sensor."""

from __future__ import annotations

import pytest

from levi.connectors import memwatch
from levi.connectors.base import ConnectorError


def _fake_meminfo(root, total_kb, available_kb):
    procdir = root / "proc"
    procdir.mkdir()
    (procdir / "meminfo").write_text(
        f"MemTotal:       {total_kb} kB\nMemAvailable:   {available_kb} kB\n",
        encoding="utf-8",
    )
    return str(procdir)


def test_first_poll_baselines_honestly(tmp_path):
    root = _fake_meminfo(tmp_path, 8_000_000, 4_000_000)  # 50% pressure
    events, state = memwatch.poll_memwatch(proc_root=root)
    assert len(events) == 1
    ev = events[0]
    assert ev["kind"] == "baseline"
    assert ev["band"] == "ok"  # 50 < warn 75
    assert ev["prev_band"] is None
    assert ev["pressure_pct"] == pytest.approx(50.0)
    assert state["band"] == "ok"


def test_band_change_emits_exactly_one_event(tmp_path):
    root = _fake_meminfo(tmp_path, 8_000_000, 4_000_000)
    _, state = memwatch.poll_memwatch(proc_root=root)
    # steady band: silent
    events, _ = memwatch.poll_memwatch(proc_root=root, state=state)
    assert events == []
    # drop available -> 93.75% -> crit
    (tmp_path / "proc" / "meminfo").write_text(
        "MemTotal:       8000000 kB\nMemAvailable:   500000 kB\n",
        encoding="utf-8",
    )
    events, state = memwatch.poll_memwatch(proc_root=root, state=state)
    assert len(events) == 1
    assert events[0]["kind"] == "band_changed"
    assert events[0]["band"] == "crit"
    assert events[0]["prev_band"] == "ok"


def test_recovery_emits_recovered_event(tmp_path):
    root = _fake_meminfo(tmp_path, 8_000_000, 500_000)  # 93.75% crit
    _, state = memwatch.poll_memwatch(proc_root=root)
    assert state["band"] == "crit"
    (tmp_path / "proc" / "meminfo").write_text(
        "MemTotal:       8000000 kB\nMemAvailable:   4000000 kB\n",
        encoding="utf-8",
    )
    events, state = memwatch.poll_memwatch(proc_root=root, state=state)
    assert len(events) == 1
    assert events[0]["kind"] == "recovered"
    assert events[0]["band"] == "ok"
    assert events[0]["prev_band"] == "crit"


def test_deny_closed_thresholds(tmp_path):
    root = _fake_meminfo(tmp_path, 8_000_000, 4_000_000)
    with pytest.raises(ConnectorError):
        memwatch.poll_memwatch(proc_root=root, warn_pct=90, crit_pct=75)
    with pytest.raises(ConnectorError):
        memwatch.poll_memwatch(proc_root=root, warn_pct=0, crit_pct=90)


def test_deny_closed_state_and_files(tmp_path):
    root = _fake_meminfo(tmp_path, 8_000_000, 4_000_000)
    with pytest.raises(ConnectorError):
        memwatch.poll_memwatch(proc_root=root, state={"band": "melted"})
    with pytest.raises(ConnectorError):
        memwatch.poll_memwatch(proc_root="/no/such/dir")
    # missing MemAvailable is refused, never guessed
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "meminfo").write_text("MemTotal: 8000000 kB\n", encoding="utf-8")
    with pytest.raises(ConnectorError):
        memwatch.poll_memwatch(proc_root=str(bad))


def test_registered_in_connector_registry():
    from levi.connectors.base import registry

    conn = registry.get("memwatch")
    assert conn.poll is memwatch.poll_memwatch
    # bad input surfaces as a named refusal through the registry too
    with pytest.raises(ConnectorError):
        conn.poll(proc_root="/no/such/dir")
