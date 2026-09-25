"""Tests for levi.integrations.phone — the capability-gated hardware bridge.

All tests run WITHOUT Termux present: the subprocess boundary is faked.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from levi.integrations.phone import (
    CAP_ACTUATE,
    CAP_MESSAGE,
    CAP_SENSE,
    CAPABILITIES,
    PHONE_ACTUATE_TOOLS,
    PHONE_MESSAGE_TOOLS,
    PHONE_SENSE_TOOLS,
    PHONE_TOOLS,
    PhoneBridge,
)
from levi.integrations.termux import TERMUX_TOOLS


class Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


RESPONSES = {
    "termux-sensor": json.dumps({"accelerometer": [{"x": 0.1, "y": 0.2}]}),
    "termux-wifi-scaninfo": json.dumps([{"ssid": "home"}]),
    "termux-wifi-connectioninfo": json.dumps({"ssid": "home", "rssi": -60}),
    "termux-telephony-deviceinfo": json.dumps({"device_id": "abc"}),
    "termux-telephony-cellinfo": json.dumps([{"type": "lte"}]),
    "termux-camera-info": json.dumps([{"id": "0", "facing": "back"}]),
    "termux-sms-list": json.dumps([{"body": "hi", "number": "555"}]),
    "termux-call-log": json.dumps([{"name": "ann", "duration": "12"}]),
    "termux-contact-list": json.dumps([{"name": "ann"}]),
    "termux-notification-list": json.dumps([{"id": "n1"}]),
    "termux-battery-status": json.dumps({"percentage": 55}),
}


@pytest.fixture
def no_tools(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    return PhoneBridge.probe()


@pytest.fixture
def full_tools(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: f"/data/data/bin/{name}")

    def fake_run(cmd, **kwargs):
        return Proc(0, RESPONSES.get(cmd[0], ""))

    monkeypatch.setattr("subprocess.run", fake_run)
    return PhoneBridge.probe()


def test_probe_covers_base_and_phone_tools(no_tools):
    assert set(no_tools.available) == set(TERMUX_TOOLS) | set(PHONE_TOOLS)
    assert set(PHONE_TOOLS) == (
        set(PHONE_SENSE_TOOLS) | set(PHONE_ACTUATE_TOOLS) | set(PHONE_MESSAGE_TOOLS)
    )
    assert no_tools.present == []
    assert no_tools.on_termux is False
    assert no_tools.granted == []


def test_capabilities_deny_closed_by_default(no_tools):
    assert set(no_tools.granted) == set()
    for cap in CAPABILITIES:
        assert cap in (CAP_SENSE, CAP_ACTUATE, CAP_MESSAGE)


def test_sensing_refused_without_capability(full_tools):
    reading = full_tools.sensors()
    assert reading.ok is False
    assert "capability 'sense' not granted" in reading.error
    assert full_tools.wifi_scan().ok is False
    assert full_tools.device_info().ok is False
    assert full_tools.sms_list().ok is False


def test_sensing_works_after_grant(full_tools):
    full_tools.grant(CAP_SENSE)
    reading = full_tools.sensors()
    assert reading.ok is True
    assert reading.data["accelerometer"][0]["x"] == 0.1
    assert full_tools.wifi_connection().data["ssid"] == "home"
    assert full_tools.camera_info().data[0]["facing"] == "back"
    assert full_tools.sms_list().data[0]["body"] == "hi"
    assert full_tools.call_log().data[0]["name"] == "ann"
    assert full_tools.contact_list().data[0]["name"] == "ann"
    assert full_tools.notification_list().data[0]["id"] == "n1"
    assert full_tools.wifi_scan().data[0]["ssid"] == "home"
    assert full_tools.cell_info().data[0]["type"] == "lte"


def test_actuation_refused_without_capability(full_tools):
    reading = full_tools.torch(True)
    assert reading.ok is False
    assert "capability 'actuate' not granted" in reading.error
    assert full_tools.camera_photo("/tmp/x.jpg").ok is False


def test_torch_on_off(full_tools, monkeypatch):
    seen = []
    monkeypatch.setattr(
        "subprocess.run",
        lambda cmd, **kw: seen.append(cmd) or Proc(0, ""),
    )
    full_tools.grant(CAP_ACTUATE)
    assert full_tools.torch(True).ok is True
    assert full_tools.torch(False).ok is True
    assert seen[0] == ["termux-torch", "on"]
    assert seen[1] == ["termux-torch", "off"]


def test_camera_photo_default_path(full_tools, monkeypatch, tmp_path):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    seen = []

    def fake_run(cmd, **kwargs):
        seen.append((cmd, kwargs))
        return Proc(0, "")

    monkeypatch.setattr("subprocess.run", fake_run)
    full_tools.grant(CAP_ACTUATE)
    reading = full_tools.camera_photo()
    assert reading.ok is True
    cmd, kwargs = seen[0]
    assert cmd[0] == "termux-camera-photo"
    assert cmd[1:3] == ["-c", "0"]
    assert cmd[3].startswith(str(tmp_path / "phone" / "captures"))
    assert cmd[3].endswith(".jpg")


def test_mic_record_timeout_scales_with_duration(full_tools, monkeypatch):
    seen = []

    def fake_run(cmd, **kwargs):
        seen.append((cmd, kwargs))
        return Proc(0, "")

    monkeypatch.setattr("subprocess.run", fake_run)
    full_tools.grant(CAP_ACTUATE)
    assert full_tools.mic_record("/tmp/rec.m4a", seconds=25).ok is True
    cmd, kwargs = seen[0]
    assert cmd[0] == "termux-microphone-record"
    assert "-f" in cmd and "-l" in cmd and "25" in cmd
    assert kwargs["timeout"] == pytest.approx(45.0)


def test_notification_remove_needs_id(full_tools):
    full_tools.grant(CAP_ACTUATE)
    reading = full_tools.notification_remove("")
    assert reading.ok is False
    assert "id is required" in reading.error


def test_sms_send_requires_confirm_even_with_grant(full_tools):
    full_tools.grant(CAP_MESSAGE)
    refused = full_tools.sms_send("555-0100", "hello")
    assert refused.ok is False
    assert "confirmation required" in refused.error
    assert "confirm=True" in refused.error


def test_sms_send_refuses_without_capability(full_tools):
    refused = full_tools.sms_send("555-0100", "hello", confirm=True)
    assert refused.ok is False
    assert "capability 'message' not granted" in refused.error


def test_sms_send_works_with_grant_and_confirm(full_tools, monkeypatch):
    seen = []
    monkeypatch.setattr(
        "subprocess.run",
        lambda cmd, **kw: seen.append(cmd) or Proc(0, ""),
    )
    full_tools.grant(CAP_MESSAGE)
    reading = full_tools.sms_send("555-0100", "hello", confirm=True)
    assert reading.ok is True
    assert seen[0] == ["termux-sms-send", "-n", "555-0100", "hello"]


def test_sms_send_validates_args(full_tools):
    full_tools.grant(CAP_MESSAGE)
    assert full_tools.sms_send("", "hi", confirm=True).ok is False
    assert full_tools.sms_send("555", "", confirm=True).ok is False


def test_call_requires_confirm(full_tools, monkeypatch):
    full_tools.grant(CAP_MESSAGE)
    refused = full_tools.call("555-0100")
    assert refused.ok is False
    assert "confirmation required" in refused.error

    seen = []
    monkeypatch.setattr(
        "subprocess.run",
        lambda cmd, **kw: seen.append(cmd) or Proc(0, ""),
    )
    assert full_tools.call("555-0100", confirm=True).ok is True
    assert seen[0] == ["termux-telephony-call", "555-0100"]


def test_missing_tool_degrades_gracefully(no_tools):
    full = no_tools.grant(CAP_SENSE, CAP_ACTUATE, CAP_MESSAGE)
    for reading in (
        full.sensors(),
        full.wifi_scan(),
        full.device_info(),
        full.sms_list(),
        full.torch(True),
        full.camera_photo("/tmp/x.jpg"),
        full.mic_record("/tmp/x.m4a", seconds=2),
        full.notification_remove("n1"),
    ):
        assert reading.ok is False
        assert reading.missing_tool is True
    # confirm is checked before the tool check — fail-closed
    refused = full.sms_send("555-0100", "hi")
    assert refused.ok is False
    assert "confirmation required" in refused.error
    missing = full.sms_send("555-0100", "hi", confirm=True)
    assert missing.missing_tool is True


def test_timeout_becomes_reading(full_tools, monkeypatch):
    def slow(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 10)

    monkeypatch.setattr("subprocess.run", slow)
    full_tools.grant(CAP_SENSE)
    reading = full_tools.sensors()
    assert reading.ok is False
    assert "timed out" in reading.error


def test_nonzero_exit_becomes_reading(full_tools, monkeypatch):
    monkeypatch.setattr("subprocess.run", lambda cmd, **kw: Proc(1, "", "denied by os"))
    full_tools.grant(CAP_ACTUATE)
    reading = full_tools.torch(True)
    assert reading.ok is False
    assert reading.error == "denied by os"


def test_every_call_times_out(full_tools, monkeypatch):
    seen = []

    def fake_run(cmd, **kwargs):
        seen.append(kwargs.get("timeout"))
        return Proc(0, "")

    monkeypatch.setattr("subprocess.run", fake_run)
    full_tools.grant(CAP_SENSE, CAP_ACTUATE, CAP_MESSAGE)
    full_tools.sensors()
    full_tools.wifi_scan()
    full_tools.device_info()
    full_tools.torch(True)
    full_tools.sms_send("555", "hi", confirm=True)
    assert seen and all(t is not None and t > 0 for t in seen)


def test_audit_trail_records_everything(full_tools):
    full_tools.sensors()  # refused: no cap
    full_tools.grant(CAP_SENSE)
    full_tools.sensors()  # ok
    full_tools.sms_send("555", "hi")  # refused: no confirm
    tools = [entry["tool"] for entry in full_tools.audit]
    assert tools == ["termux-sensor", "termux-sensor", "termux-sms-send"]
    assert full_tools.audit[0]["refused"] is True
    assert full_tools.audit[1]["ok"] is True
    assert full_tools.audit[2]["refused"] is True


def test_grant_revoke_chaining_and_unknown_cap(full_tools):
    full_tools.grant(CAP_SENSE, CAP_ACTUATE)
    assert full_tools.granted == [CAP_SENSE, CAP_ACTUATE]
    full_tools.revoke(CAP_ACTUATE)
    assert full_tools.granted == [CAP_SENSE]
    with pytest.raises(ValueError, match="unknown capability"):
        full_tools.grant("teleport")


def test_sense_card_is_honest(no_tools):
    card = no_tools.sense_card()
    assert card["granted"] == []
    assert card["on_termux"] is False
    assert card["battery"]["ok"] is False
    assert set(card).issuperset({"present", "missing", "battery"})
