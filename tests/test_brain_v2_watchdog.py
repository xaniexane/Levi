"""Hermetic tests for levi.brain.train.v2.watchdog.

Only the decision logic, state handling, and launch-command construction
are tested — actual process launching is never exercised here. stdlib only.
"""

import json
import os

import pytest

from levi.brain.train.v2 import watchdog as wd


def test_decide_alive_is_ok():
    state = {"pid": 1234, "restarts": 3, "events": []}
    assert wd.decide(state, 5, alive=True) == wd.OK


def test_decide_dead_restarts_under_cap():
    state = {"pid": 1234, "restarts": 0, "events": []}
    assert wd.decide(state, 5, alive=False) == wd.RESTART
    state = {"pid": None, "restarts": 4, "events": []}
    assert wd.decide(state, 5, alive=False) == wd.RESTART


def test_decide_dead_at_cap_is_cap_reached():
    state = {"pid": 1234, "restarts": 5, "events": []}
    assert wd.decide(state, 5, alive=False) == wd.CAP_REACHED
    state = {"pid": None, "restarts": 9, "events": []}
    assert wd.decide(state, 5, alive=False) == wd.CAP_REACHED


def test_decide_zero_cap_never_restarts():
    state = {"pid": None, "restarts": 0, "events": []}
    assert wd.decide(state, 0, alive=False) == wd.CAP_REACHED


def test_process_alive_current_and_bogus():
    assert wd.process_alive(os.getpid()) is True
    assert wd.process_alive(None) is False
    assert wd.process_alive(2**30) is False  # no such pid


def test_load_state_missing_is_fresh(tmp_path):
    state = wd.load_state(tmp_path / "nope.json")
    assert state == {"pid": None, "restarts": 0, "events": []}


def test_load_state_corrupt_is_fresh_but_usable(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    state = wd.load_state(p)
    assert state["restarts"] == 0 and state["events"] == []


def test_save_and_reload_state_roundtrip(tmp_path):
    p = tmp_path / "state.json"
    state = wd.new_state()
    wd.record_event(state, "check", "alive")
    wd.save_state(p, state)
    again = wd.load_state(p)
    assert again["events"][0]["kind"] == "check"
    assert again["events"][0]["at"]  # timestamped


def test_check_refuses_restart_without_config(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    decision, msg = wd.check(
        run_dir=run_dir,
        repo_root=tmp_path,
        config=tmp_path / "missing.yaml",
        python="python3",
        log_path=run_dir / "train.log",
        state_path=run_dir / "watchdog.json",
        max_restarts=5,
    )
    assert decision == wd.CAP_REACHED
    assert "refusing restart" in msg
    state = wd.load_state(run_dir / "watchdog.json")
    assert state["restarts"] == 0  # refused launches do not consume budget
    kinds = [e["kind"] for e in state["events"]]
    assert "refused" in kinds


def test_check_cap_reached_does_not_launch(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state_path = run_dir / "watchdog.json"
    state = wd.new_state()
    state["restarts"] = 5
    wd.save_state(state_path, state)
    decision, msg = wd.check(
        run_dir=run_dir,
        repo_root=tmp_path,
        config=tmp_path / "train.yaml",
        python="python3",
        log_path=run_dir / "train.log",
        state_path=state_path,
        max_restarts=5,
    )
    assert decision == wd.CAP_REACHED
    assert "manual intervention" in msg
    state = wd.load_state(state_path)
    assert state["restarts"] == 5
    assert state["events"][-1]["kind"] == "cap_reached"


def test_build_launch_cmd_matches_launch_doc(tmp_path):
    argv = wd.build_launch_cmd(
        "python3", tmp_path, tmp_path / "train.yaml", tmp_path / "run"
    )
    assert argv == [
        "python3",
        "-m",
        "levi.brain.train.v2.trainer",
        "--config",
        str(tmp_path / "train.yaml"),
        "--run-dir",
        str(tmp_path / "run"),
    ]


def test_parse_args_defaults():
    args = wd.parse_args(
        ["--run-dir", "runs/x", "--config", "core/levi/brain/train/v2/train.yaml"]
    )
    assert args.max_restarts == wd.DEFAULT_MAX_RESTARTS
    assert args.log == ""
    assert args.state == ""


def test_main_rejects_negative_cap():
    assert wd.main(["--run-dir", "x", "--config", "y", "--max-restarts", "-1"]) == 2
