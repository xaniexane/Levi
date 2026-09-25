"""Tests for the battery connector — the ear on device power.

Proofs for the laws in ``levi/connectors/battery.py``: observe-only
(sysfs reads, never writes), honest baseline (battery / no-battery /
mains-only), edge-only events (status, band, mains, presence), and the
deny-closed input gates. The sysfs tree is injected via ``tmp_path`` —
no test touches the real ``/sys``.
"""

from __future__ import annotations

import os

import pytest

from levi.connectors import battery
from levi.connectors.base import ConnectorError, registry


def _tree(tmp_path, supplies):
    """Write a fake /sys/class/power_supply tree. supplies: name -> fields."""
    root = tmp_path / "power_supply"
    root.mkdir(exist_ok=True)
    for name, fields in supplies.items():
        d = root / name
        d.mkdir(exist_ok=True)
        for field, value in fields.items():
            (d / field).write_text(value)
    return str(root)


_BAT = {"type": "Battery", "capacity": "82", "status": "Charging"}
_AC = {"type": "Mains", "online": "1"}


def test_baseline_names_everything(tmp_path):
    root = _tree(tmp_path, {"BAT0": _BAT, "AC": _AC})
    events, state = battery.poll(sysfs_root=root)
    assert len(events) == 1
    base = events[0]
    assert base["kind"] == "baseline"
    assert base["present"] is True
    assert base["capacity"] == 82
    assert base["status"] == "charging"
    assert base["mains"] is True
    assert base["name"] == "BAT0"
    assert state["band"] == "ok"
    assert state["status"] == "charging"
    assert state["mains"] is True


def test_steady_state_emits_nothing(tmp_path):
    root = _tree(tmp_path, {"BAT0": _BAT, "AC": _AC})
    _, state = battery.poll(sysfs_root=root)
    events, _ = battery.poll(state=state, sysfs_root=root)
    assert events == []


def test_status_change_emits_one_event(tmp_path):
    root = _tree(tmp_path, {"BAT0": _BAT, "AC": _AC})
    _, state = battery.poll(sysfs_root=root)
    _tree(tmp_path, {"BAT0": {**_BAT, "status": "Discharging"}, "AC": _AC})
    events, new_state = battery.poll(state=state, sysfs_root=root)
    assert len(events) == 1
    ev = events[0]
    assert ev["kind"] == "status_changed"
    assert ev["status"] == "discharging"
    assert ev["prev_status"] == "charging"
    assert new_state["status"] == "discharging"


def test_band_change_including_recovery(tmp_path):
    root = _tree(tmp_path, {"BAT0": {**_BAT, "capacity": "82"}, "AC": _AC})
    _, state = battery.poll(sysfs_root=root)
    assert state["band"] == "ok"
    _tree(tmp_path, {"BAT0": {**_BAT, "capacity": "10"}, "AC": _AC})
    events, state = battery.poll(state=state, sysfs_root=root)
    assert [e["kind"] for e in events] == ["band_changed"]
    assert events[0]["band"] == "crit"
    assert events[0]["prev_band"] == "ok"
    _tree(tmp_path, {"BAT0": {**_BAT, "capacity": "95"}, "AC": _AC})
    events, state = battery.poll(state=state, sysfs_root=root)
    assert [e["kind"] for e in events] == ["band_changed"]
    assert events[0]["band"] == "ok"
    assert events[0]["prev_band"] == "crit"


def test_mains_change(tmp_path):
    root = _tree(tmp_path, {"BAT0": _BAT, "AC": _AC})
    _, state = battery.poll(sysfs_root=root)
    _tree(tmp_path, {"BAT0": _BAT, "AC": {"type": "Mains", "online": "0"}})
    events, _ = battery.poll(state=state, sysfs_root=root)
    assert [e["kind"] for e in events] == ["mains_changed"]
    assert events[0]["mains"] is False
    assert events[0]["prev_mains"] is True


def test_no_battery_is_honest_and_quiet(tmp_path):
    root = _tree(tmp_path, {"AC": _AC})
    events, state = battery.poll(sysfs_root=root)
    assert len(events) == 1
    assert events[0]["kind"] == "baseline"
    assert events[0]["present"] is False
    assert events[0]["capacity"] is None
    events, _ = battery.poll(state=state, sysfs_root=root)
    assert events == []


def test_battery_disappears_is_an_event(tmp_path):
    import shutil

    root = _tree(tmp_path, {"BAT0": _BAT, "AC": _AC})
    _, state = battery.poll(sysfs_root=root)
    shutil.rmtree(os.path.join(root, "BAT0"))  # hot-unplug the battery
    events, new_state = battery.poll(state=state, sysfs_root=root)
    assert [e["kind"] for e in events] == ["present_changed"]
    assert events[0]["present"] is False
    assert new_state["present"] is False


def test_deny_closed_inputs(tmp_path):
    root = _tree(tmp_path, {"BAT0": _BAT})
    with pytest.raises(ConnectorError):
        battery.poll(sysfs_root="/no/such/tree")
    with pytest.raises(ConnectorError):
        battery.poll(sysfs_root=root, warn_pct=10, crit_pct=30)
    with pytest.raises(ConnectorError):
        battery.poll(sysfs_root=root, warn_pct=30, crit_pct=30)
    with pytest.raises(ConnectorError):
        battery.poll(sysfs_root=root, state={"band": "nonsense"})
    with pytest.raises(ConnectorError):
        battery.poll(sysfs_root=root, state={"status": "exploding"})
    with pytest.raises(ConnectorError):
        battery.poll(sysfs_root=root, state="not-a-dict")


def test_unreadable_capacity_is_unknown_not_zero(tmp_path):
    root = _tree(tmp_path, {"BAT0": {"type": "Battery", "status": "Unknown"}})
    events, state = battery.poll(sysfs_root=root)
    assert events[0]["capacity"] is None
    assert state["band"] is None


def test_registered_in_connector_registry(tmp_path):
    root = _tree(tmp_path, {"BAT0": _BAT})
    events, _ = registry.poll("battery", sysfs_root=root)
    assert events[0]["kind"] == "baseline"
