"""Tests for the cross-device bridge.

Hermetic: LEVI_HOME pinned to tmp, no network, no real devices — the
outbox dir is the asserted handoff point.
"""

import json

import pytest

from levi.automation.bridges.devices import (
    dispatch_to_device,
    get_device,
    handle,
    list_devices,
    outbox_dir,
    register_device,
    register_device_action,
)
from levi.automation.flows import FlowError


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def test_registry_round_trip(home):
    rec = register_device(
        "my-phone",
        "phone",
        "Chauncey Phone",
        capabilities=["sms", "shell"],
        termux=True,
    )
    assert rec["device_id"] == "my-phone"
    assert rec["kind"] == "phone"
    assert rec["termux"] is True
    assert list_devices() == [rec]
    assert get_device("my-phone") == rec
    assert get_device("nope") is None


def test_register_updates_existing(home):
    register_device("box", "workstation", "Old Label")
    rec = register_device("box", "workstation", "New Label")
    assert rec["label"] == "New Label"
    assert len(list_devices()) == 1


def test_registry_bad_inputs(home):
    with pytest.raises(ValueError):
        register_device("../evil", "phone", "x")
    with pytest.raises(ValueError):
        register_device("d1", "watch", "x")
    with pytest.raises(ValueError):
        register_device("d1", "phone", "   ")
    with pytest.raises(TypeError):
        register_device("d1", "phone", "x", capabilities=["ok", 3])


def test_dispatch_termux_phone(home):
    register_device("my-phone", "phone", "Phone", termux=True)
    receipt = dispatch_to_device(
        "my-phone", {"action": "send-sms", "args": {"to": "+1555", "text": "hi"}}
    )
    assert receipt["ok"] is True
    box = outbox_dir("my-phone")
    files = receipt["files"]
    assert len(files) == 2
    manifest_path = box / files[0]
    script_path = box / files[1]
    assert manifest_path.suffix == ".json"
    assert script_path.suffix == ".sh"

    manifest = json.loads(manifest_path.read_text())
    assert manifest["device_id"] == "my-phone"
    assert manifest["action"] == "send-sms"
    assert manifest["args"] == {"to": "+1555", "text": "hi"}

    script = script_path.read_text()
    assert script.startswith("#!/data/data/com.termux/files/usr/bin/bash")
    assert "send-sms" in script
    assert '"+1555"' in script


def test_dispatch_workstation(home):
    register_device("desk", "workstation", "Desk")
    receipt = dispatch_to_device(
        "desk", {"action": "open-url", "args": {"url": "https://x"}}
    )
    assert receipt["ok"] is True
    box = outbox_dir("desk")
    script_path = box / receipt["files"][1]
    assert script_path.suffix == ".py"
    script = script_path.read_text()
    assert "open-url" in script


def test_dispatch_unknown_device(home):
    with pytest.raises(FlowError, match="unknown device"):
        dispatch_to_device("ghost", {"action": "x"})


def test_dispatch_bad_command(home):
    register_device("d", "phone", "D", termux=True)
    with pytest.raises(ValueError):
        dispatch_to_device("d", {"args": {}})
    with pytest.raises(TypeError):
        dispatch_to_device("d", {"action": "x", "args": "nope"})


def test_handle_node(home):
    register_device("my-phone", "phone", "Phone", termux=True)
    node = {"config": {"device_id": "my-phone", "action": "ping", "args": {"n": 1}}}
    result = handle(node, {}, {})
    assert result["ok"] is True
    assert "my-phone" in result["output"]
    assert result["evidence"]["ok"] is True


def test_handle_node_missing_config(home):
    with pytest.raises(FlowError):
        handle({"config": {"action": "x"}}, {}, {})


def test_register_device_action_returns_bool():
    assert isinstance(register_device_action(), bool)
