"""Automation registry hardening tests (hermetic, stdlib-only)."""

from __future__ import annotations

import json

import pytest

from levi.daemon.automation import (
    AutomationAction,
    AutomationError,
    AutomationRegistry,
    TriggerKind,
)


@pytest.fixture()
def reg(tmp_path):
    return AutomationRegistry(data_dir=tmp_path / "autos")


def _action():
    return AutomationAction(skill_id="status", args={}, risk_level=0)


def test_create_validates_inputs(reg):
    with pytest.raises(AutomationError, match="non-empty string"):
        reg.create("", "desc", [_action()])
    with pytest.raises(AutomationError, match="must be a list"):
        reg.create("name", "desc", "not-a-list")
    with pytest.raises(AutomationError, match="AutomationAction"):
        reg.create("name", "desc", ["not-an-action"])
    with pytest.raises(AutomationError, match="TriggerKind"):
        reg.create("name", "desc", [_action()], trigger="manual")
    with pytest.raises(AutomationError, match="risk_ceiling"):
        reg.create("name", "desc", [_action()], risk_ceiling=-1)
    with pytest.raises(AutomationError, match="risk_level"):
        reg.create(
            "name",
            "desc",
            [AutomationAction(skill_id="s", args={}, risk_level="high")],
        )


def test_create_roundtrip_and_ceiling(reg):
    auto = reg.create(
        "nightly",
        "does the thing",
        [AutomationAction(skill_id="s", args={}, risk_level=2)],
        trigger=TriggerKind.SCHEDULE,
    )
    assert auto.risk_ceiling == 2  # raised to max action risk
    assert reg.get(auto.id).name == "nightly"


def test_unknown_ids_are_actionable(reg):
    with pytest.raises(AutomationError, match="unknown automation"):
        reg.activate("auto.nope")
    with pytest.raises(AutomationError, match="unknown automation"):
        reg.run_manual("auto.nope")
    assert reg.remove("auto.nope") is False
    assert reg.get("auto.nope") is None
    assert reg.get(None) is None


def test_activate_and_run_manual(reg):
    auto = reg.create("m", "d", [_action()])
    reg.activate(auto.id)
    assert reg.get(auto.id).status.value == "active"
    out = reg.run_manual(auto.id, skill_registry=None)
    assert isinstance(out, str)


def test_corrupt_record_is_skipped_and_valid_kept(reg, tmp_path):
    data_dir = tmp_path / "autos"
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "automations": [
            {
                "id": "auto.good",
                "name": "good",
                "trigger": "manual",
                "status": "draft",
                "actions": [{"skill_id": "status", "args": {}, "risk_level": 0}],
            },
            {"id": "auto.bad", "name": "", "trigger": "manual"},  # bad name
            {"id": "auto.bad2", "name": "bad2", "trigger": "nope"},  # bad trigger
            "not-a-dict",
        ]
    }
    (data_dir / "automations.json").write_text(json.dumps(payload))
    reg2 = AutomationRegistry(data_dir=data_dir)
    assert set(reg2._autos) == {"auto.good"}


def test_garbage_store_degrades_to_empty(tmp_path, capsys):
    data_dir = tmp_path / "autos"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "automations.json").write_text("{not json")
    reg = AutomationRegistry(data_dir=data_dir)
    assert reg.list() == []
    assert "cannot read" in capsys.readouterr().err


def test_persist_failure_is_domain_error(reg, tmp_path, monkeypatch):
    auto = reg.create("m", "d", [_action()])
    # Make the data dir unwritable by replacing _persist's target with a dir.
    path = reg.data_dir / "automations.json"
    path.unlink()
    path.mkdir()
    with pytest.raises(AutomationError, match="cannot persist"):
        reg.activate(auto.id)
