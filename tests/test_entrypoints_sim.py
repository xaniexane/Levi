"""Entrypoint tests: python -m levi.sim (hermetic, zero network)."""

import pytest

from levi.sim.__main__ import main


def test_help_exits_zero():
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0


def test_list(capsys):
    assert main(["--list"]) == 0
    out = capsys.readouterr().out
    assert "bounty-hunt" in out
    assert "soc-shift" in out


def test_bounty_hunt_seeded(capsys):
    assert main(["bounty-hunt", "--seed", "7"]) == 0
    out = capsys.readouterr().out
    assert "SIMULATION" in out
    assert "Nothing in this run was real" in out


def test_unknown_scenario_fails_closed(capsys):
    assert main(["nope-not-real"]) == 2
    assert "unknown simulation" in capsys.readouterr().out


def test_deterministic_same_seed_same_output(capsys):
    assert main(["bounty-hunt", "--seed", "42"]) == 0
    first = capsys.readouterr().out
    assert main(["bounty-hunt", "--seed", "42"]) == 0
    second = capsys.readouterr().out
    assert first == second
    assert "SIMULATION" in first
