"""Tests for the ``levi automate`` IFTTT-style workflow creator."""

import argparse
import json
import sys

import pytest

sys.path.insert(0, "core")

from levi.automation import flows
from levi.automation.cli import _cmd_automate_create, register_automate_parser
from levi.automation.creator import (
    FlowBuildError,
    build_workflow,
    describe_trigger,
    render_preview,
    save_workflow,
    slugify,
)
from levi.automation.minions import MINIONS


@pytest.fixture
def home_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _minion_action(label="Do a minion thing", minion_id=None):
    return {
        "kind": "minion",
        "label": label,
        "config": {"minion_id": minion_id or MINIONS[0].id},
    }


def test_slugify():
    assert slugify("Morning Brief!") == "morning-brief"
    with pytest.raises(FlowBuildError):
        slugify("  !!!  ")


def test_describe_trigger():
    assert describe_trigger({"trigger_type": "manual"}) == "manually run"
    assert describe_trigger({"trigger_type": "schedule", "cron": "0 9 * * *"}) == (
        "schedule 0 9 * * *"
    )
    assert describe_trigger({"trigger_type": "webhook-in", "path": "/hook"}) == (
        "webhook /hook"
    )


def test_build_manual_two_actions():
    flow = build_workflow(
        "Evening Shutdown",
        {"trigger_type": "manual"},
        [_minion_action("Digest"), _minion_action("Lock", MINIONS[1].id)],
    )
    flows.build_flow(flow)  # must validate
    assert flow["id"] == "evening-shutdown"
    assert flow["start"] == "trigger"
    assert [n["id"] for n in flow["nodes"]] == ["trigger", "a1", "a2"]
    assert [n["kind"] for n in flow["nodes"]] == ["note", "minion", "minion"]
    assert len(flow["edges"]) == 2


def test_build_schedule_with_condition():
    flow = build_workflow(
        "Morning Brief",
        {"trigger_type": "schedule", "cron": "0 9 * * *"},
        [_minion_action()],
        condition='event.payload.weekday != "sun"',
    )
    flows.build_flow(flow)
    kinds = [n["id"] for n in flow["nodes"]]
    assert kinds == ["trigger", "cond", "a1"]
    assert flow["nodes"][1]["kind"] == "predicate"


def test_build_webhook_google_tasks():
    flow = build_workflow(
        "Task Ping",
        {"trigger_type": "webhook-in", "path": "/tasks"},
        [
            {
                "kind": "google-tasks",
                "label": "Add a task",
                "config": {"list": "today", "title": "Ping"},
            }
        ],
    )
    flows.build_flow(flow)  # emit-carried action must validate
    action_node = flow["nodes"][1]
    assert action_node["kind"] == "emit"
    payload = json.loads(json.loads(action_node["set"]["action_a1"]))
    assert payload["kind"] == "google-tasks"


def test_build_rejects_bad_trigger():
    with pytest.raises(FlowBuildError):
        build_workflow("X", {"trigger_type": "email"}, [_minion_action()])
    with pytest.raises(FlowBuildError):
        build_workflow("X", {"trigger_type": "schedule"}, [_minion_action()])
    with pytest.raises(FlowBuildError):
        build_workflow("X", {"trigger_type": "manual"}, [])


def test_build_rejects_unknown_minion():
    with pytest.raises(FlowBuildError):
        build_workflow(
            "X",
            {"trigger_type": "manual"},
            [{"kind": "minion", "label": "Nope", "config": {"minion_id": "nope"}}],
        )


def test_render_preview():
    flow = build_workflow(
        "Demo",
        {"trigger_type": "manual"},
        [_minion_action("First"), _minion_action("Second")],
    )
    preview = render_preview(flow)
    assert "flowchart TD" in preview
    assert preview.splitlines()[-1] == "WHEN manually run THEN First → Second"


def test_save_load_roundtrip(home_env):
    flow = build_workflow(
        "Round Trip",
        {"trigger_type": "manual"},
        [_minion_action()],
    )
    path = save_workflow(flow)
    assert path.exists()
    loaded = flows.load_flow("round-trip")
    assert loaded["id"] == flow["id"]
    assert loaded["name"] == "Round Trip"
    assert len(loaded["nodes"]) == len(flow["nodes"])


def test_slug_collision_needs_overwrite(home_env):
    flow = build_workflow("Collision", {"trigger_type": "manual"}, [_minion_action()])
    save_workflow(flow)
    with pytest.raises(FlowBuildError):
        save_workflow(flow)  # no overwrite flag
    path = save_workflow(flow, overwrite=True)
    assert path.exists()


def test_run_dry_run(home_env):
    flow = build_workflow(
        "Dry Demo",
        {"trigger_type": "manual"},
        [_minion_action()],
    )
    save_workflow(flow)
    receipt = flows.run_flow(flow, dry_run=True)
    assert receipt.ok
    assert receipt.dry_run


def _create_ns(**overrides):
    ns = argparse.Namespace(
        name=None,
        trigger=None,
        cron=None,
        path=None,
        action=[],
        condition=None,
        yes=False,
    )
    for key, value in overrides.items():
        setattr(ns, key, value)
    return ns


def test_cli_create_noninteractive(home_env):
    ns = _create_ns(
        name="CLI Built",
        trigger="schedule",
        cron="0 8 * * *",
        action=[
            f"minion:Digest;minion_id={MINIONS[0].id}",
            "google-tasks:Queue task;list=today;title=Hello",
        ],
        yes=True,
    )
    rc = _cmd_automate_create(ns)
    assert rc == 0
    flow = flows.load_flow("cli-built")
    assert [n["id"] for n in flow["nodes"]] == ["trigger", "a1", "a2"]
    assert flow["nodes"][1]["kind"] == "minion"
    assert flow["nodes"][2]["kind"] == "emit"


def test_cli_create_needs_flags_when_no_tty(home_env, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    ns = _create_ns()  # no name/trigger/action, non-tty -> error path
    rc = _cmd_automate_create(ns)
    assert rc == 1
    assert "non-interactive create" in capsys.readouterr().out


def test_automate_parser_registers():
    import argparse as ap

    parser = ap.ArgumentParser()
    sub = parser.add_subparsers()
    register_automate_parser(sub)
    ns = parser.parse_args(
        [
            "automate",
            "create",
            "--name",
            "N",
            "--trigger",
            "manual",
            "--action",
            "python:Run;x=1",
            "--yes",
        ]
    )
    assert ns.automate_cmd == "create"
    assert ns.action == ["python:Run;x=1"]
