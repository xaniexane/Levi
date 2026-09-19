"""E2 engine/executor hardening: structured cron + event triggers,
hyphenated KV keys, extended device-tool recognition."""

import json
from pathlib import Path

import pytest

import sys

sys.path.insert(0, "core")

from levi.automation.engine import (
    TriggerEvent,
    _cron_matches,
    evaluate_condition,
    trigger_matches,
)
from levi.automation.executor import DeviceArtifactAdapter, route
from levi.automation.minions import Minion


def _minion(**kw):
    base = dict(
        id="e2-probe-01",
        category="Probe",
        subcategory="Probe",
        trigger="Always",
        condition="Always",
        android_tool="",
        windows_tool="",
        mac_tool="",
        chrome_extension="",
        bridge="",
        usb_auto_launch="",
        hitl_type="Notification",
        example_rite="Probe the thing",
        notes="",
        origin="levi-original",
        incomplete=False,
        signature_id="ipsig-test",
    )
    base.update(kw)
    return Minion(**base)


def _event(kind, summary="", payload=None, ts=""):
    return TriggerEvent(kind=kind, summary=summary, payload=payload or {}, ts=ts)


# ---------------------------------------------------------------------------
# Cron triggers
# ---------------------------------------------------------------------------


def test_cron_exact_match():
    ev = _event("time", ts="2026-09-17T09:30:00+00:00")
    assert _cron_matches("30 9 * * *", ev) is True
    assert _cron_matches("31 9 * * *", ev) is False
    assert _cron_matches("30 10 * * *", ev) is False


def test_cron_step_range_list():
    ev = _event("time", ts="2026-09-17T09:30:00+00:00")
    assert _cron_matches("*/15 9 * * *", ev) is True
    assert _cron_matches("*/20 9 * * *", ev) is False
    assert _cron_matches("25-35 9 * * *", ev) is True
    assert _cron_matches("0,30 9 * * *", ev) is True
    assert _cron_matches("0,15 9 * * *", ev) is False


def test_cron_dow():
    # 2026-09-17 is a Thursday. Cron dow: 4 = Thursday.
    ev = _event("time", ts="2026-09-17T09:30:00+00:00")
    assert _cron_matches("30 9 * * 4", ev) is True
    assert _cron_matches("30 9 * * 5", ev) is False
    assert _cron_matches("30 9 * * 0", ev) is False  # Sunday


def test_cron_dom_dow_or_semantics():
    # Both restricted: POSIX OR.
    ev = _event("time", ts="2026-09-17T09:30:00+00:00")  # 17th, Thursday
    assert _cron_matches("30 9 17 * 5", ev) is True  # dom hits
    assert _cron_matches("30 9 18 * 4", ev) is True  # dow hits
    assert _cron_matches("30 9 18 * 5", ev) is False  # neither


def test_cron_malformed_never_matches_never_raises():
    ev = _event("time", ts="2026-09-17T09:30:00+00:00")
    assert _cron_matches("not a cron", ev) is False
    assert _cron_matches("30 9 * *", ev) is False
    assert _cron_matches("*/0 9 * * *", ev) is False
    bad_ts = _event("time", ts="not-a-time")
    assert _cron_matches("30 9 * * *", bad_ts) is False


def test_trigger_matches_cron_family():
    ev = _event("cron", ts="2026-09-17T09:00:00+00:00")
    assert trigger_matches("Cron 0 9 * * *", ev) is True
    assert trigger_matches("Cron 0 10 * * *", ev) is False


# ---------------------------------------------------------------------------
# Event triggers
# ---------------------------------------------------------------------------


def test_event_trigger_kind_and_detail():
    ev = _event("finance", summary="price swing on BTC", payload={"symbol": "BTC"})
    assert trigger_matches("Event finance: price_swing", ev) is True
    assert trigger_matches("Event finance: dividend", ev) is False
    assert trigger_matches("Event travel: price_swing", ev) is False


def test_event_trigger_detail_in_payload():
    ev = _event("solar", summary="sun moved", payload={"phase": "sunset"})
    assert trigger_matches("Event solar: sunset", ev) is True


# ---------------------------------------------------------------------------
# Hyphenated KV keys
# ---------------------------------------------------------------------------


def test_kv_hyphenated_key_colon():
    ev = _event("note", payload={"round_up_enabled": "true"})
    v = evaluate_condition("Round-up enabled: true", ev)
    assert v.holds is True


def test_kv_hyphenated_key_equals():
    ev = _event("note", payload={"quote_worthy_line": "detected"})
    v = evaluate_condition("Quote-worthy line = detected", ev)
    assert v.holds is True


def test_kv_plain_keys_still_work():
    ev = _event("email", payload={"priority": "high"})
    assert evaluate_condition("Priority: high", ev).holds is True
    assert evaluate_condition("Priority = high", ev).holds is True
    assert evaluate_condition("Priority: low", ev).holds is False


# ---------------------------------------------------------------------------
# Extended device tools
# ---------------------------------------------------------------------------

NEW_TOOLS = [
    ("Tasker", "tasker-task.txt"),
    ("Automate", "automate-flow.json"),
    ("Shortcuts", "shortcuts-setup.txt"),
    ("PowerShell", "automation.ps1"),
    ("Python", "automation.py"),
    ("Hammerspoon", "hammerspoon.lua"),
    ("Distill", "distill-monitor.json"),
    ("Web Clipper", "web-clipper.txt"),
]


@pytest.mark.parametrize("tool,filename", NEW_TOOLS)
def test_new_device_tools_recognized(tmp_path, tool, filename):
    m = _minion(android_tool=tool)
    adapter = DeviceArtifactAdapter()
    assert adapter.can_handle(m) is True
    assert route(m).__class__ is DeviceArtifactAdapter
    ev = _event("time", summary="probe")
    result = adapter.execute(m, ev, gate_receipt=None, run_id="r1", home=tmp_path)
    assert result.ok is True
    assert (tmp_path / "automation" / "artifacts" / "e2-probe-01" / filename).exists()


def test_new_tools_beat_refusal(tmp_path):
    m = _minion(android_tool="Tasker")  # previously unrecognized -> refusal
    routed = route(m, home=tmp_path)
    assert routed.name == "device-artifacts"


def test_generated_python_scaffold_is_valid_python(tmp_path):
    import ast

    m = _minion(windows_tool="Python")
    adapter = DeviceArtifactAdapter()
    ev = _event("time", summary="probe")
    adapter.execute(m, ev, gate_receipt=None, run_id="r1", home=tmp_path)
    path = tmp_path / "automation" / "artifacts" / "e2-probe-01" / "automation.py"
    ast.parse(path.read_text(encoding="utf-8"))


def test_generated_json_artifacts_parse(tmp_path):
    m = _minion(android_tool="Automate", mac_tool="Distill")
    adapter = DeviceArtifactAdapter()
    ev = _event("time", summary="probe")
    adapter.execute(m, ev, gate_receipt=None, run_id="r1", home=tmp_path)
    dest = tmp_path / "automation" / "artifacts" / "e2-probe-01"
    for name in ("automate-flow.json", "distill-monitor.json"):
        json.loads((dest / name).read_text(encoding="utf-8"))
