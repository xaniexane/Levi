"""Tests for levi.integrations.termux — the Termux device bridge."""

from __future__ import annotations

import json

import pytest

from levi.integrations.termux import TERMUX_TOOLS, TermuxBridge


@pytest.fixture
def no_tools(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    return TermuxBridge.probe()


@pytest.fixture
def full_tools(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: f"/data/data/bin/{name}")

    def fake_run(cmd, **kwargs):
        tool = cmd[0]

        class Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        proc = Proc()
        if tool == "termux-battery-status":
            proc.stdout = json.dumps(
                {"percentage": 82, "plugged": "PLUGGED_AC", "health": "GOOD"}
            )
        elif tool == "termux-clipboard-get":
            proc.stdout = "hello from device"
        return proc

    monkeypatch.setattr("subprocess.run", fake_run)
    return TermuxBridge.probe()


def test_probe_reports_honest_availability(no_tools):
    assert no_tools.available == {t: False for t in TERMUX_TOOLS}
    assert no_tools.on_termux is False
    assert no_tools.missing == list(TERMUX_TOOLS)
    assert no_tools.present == []


def test_missing_tool_degrades_gracefully(no_tools):
    reading = no_tools.battery()
    assert reading.ok is False
    assert reading.missing_tool is True
    assert "termux-battery-status" in reading.error
    # actions never raise on a tool-less machine
    assert no_tools.notify("hi").missing_tool is True
    assert no_tools.toast("hi").missing_tool is True
    assert no_tools.clipboard_get().missing_tool is True


def test_validation_runs_before_tool_check(full_tools):
    reading = full_tools.notify("", "content")
    assert reading.ok is False
    assert "title is required" in reading.error
    assert full_tools.toast("").ok is False


def test_battery_parses_json(full_tools):
    reading = full_tools.battery()
    assert reading.ok is True
    assert reading.data["percentage"] == 82
    assert reading.data["health"] == "GOOD"


def test_clipboard_get_plain_text(full_tools):
    reading = full_tools.clipboard_get()
    assert reading.ok is True
    assert reading.data == "hello from device"


def test_status_card_is_honest(no_tools):
    card = no_tools.status_card()
    assert card["on_termux"] is False
    assert card["missing"] == list(TERMUX_TOOLS)
    assert card["battery"]["ok"] is False


def test_subprocess_timeout_becomes_reading(full_tools, monkeypatch):
    import subprocess

    def slow(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 1)

    monkeypatch.setattr("subprocess.run", slow)
    reading = full_tools.location()
    assert reading.ok is False
    assert "timed out" in reading.error


def test_nonzero_exit_becomes_reading(full_tools, monkeypatch):
    def failing(cmd, **kwargs):
        class Proc:
            returncode = 1
            stdout = ""
            stderr = "boom"

        return Proc()

    monkeypatch.setattr("subprocess.run", failing)
    reading = full_tools.vibrate()
    assert reading.ok is False
    assert reading.error == "boom"
