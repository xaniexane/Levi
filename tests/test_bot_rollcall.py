"""Tests for levi.bot.rollcall: who answers, and who went silent."""

import pytest

from levi.bot.rollcall import RollcallError, probe_status, take_rollcall


def _roster(**probes):
    return dict(probes)


def test_rollcall_counts_up_down_silent():
    result = take_rollcall(
        "Roster",
        _roster(
            up_one=lambda: True,
            up_two=lambda: 1,
            down_one=lambda: False,
            down_two=lambda: 0,
            quiet_one=lambda: 1 / 0,
        ),
    )
    assert result.up == 2
    assert result.down == 2
    assert result.silent == 1
    assert "quiet_one: SILENT (ZeroDivisionError" in result.text
    assert "Answering (2)" in result.text
    assert "Down (2)" in result.text
    assert "Silent (1)" in result.text


def test_rollcall_silent_note_is_short_not_a_traceback():
    def bad():
        raise RuntimeError("x" * 300)

    state, note = probe_status(bad)
    assert state == "SILENT"
    assert len(note) <= len("RuntimeError: ") + 80
    assert "\n" not in note
    assert "Traceback" not in note


def test_rollcall_deny_closed_empty_title():
    with pytest.raises(RollcallError):
        take_rollcall("  ", _roster(a=lambda: True))


def test_rollcall_deny_closed_empty_roster():
    with pytest.raises(RollcallError):
        take_rollcall("T", {})


def test_rollcall_deny_closed_bad_roster():
    with pytest.raises(RollcallError):
        take_rollcall("T", {"a": 42})
    with pytest.raises(RollcallError):
        take_rollcall("T", {"": lambda: True})
    with pytest.raises(RollcallError):
        take_rollcall("T", ["not-a-mapping"])


def test_rollcall_deny_closed_small_budget():
    with pytest.raises(RollcallError):
        take_rollcall("T", _roster(a=lambda: True), max_lines=4)


def test_rollcall_deterministic():
    roster = _roster(a=lambda: True, b=lambda: False, c=lambda: 1 / 0)
    first = take_rollcall("T", roster)
    second = take_rollcall("T", roster)
    assert first == second


def test_rollcall_respects_the_budget():
    roster = {f"svc-{i}": (lambda: True) for i in range(10)}
    result = take_rollcall("T", roster, max_lines=10)
    assert result.lines <= 10
    assert result.dropped > 0  # body held back, disclosed by the card


def test_rollcall_down_bots_exit_code_cli():
    # the CLI returns 1 when anything is down or silent
    from levi.bot.rollcall import _cli

    # probe_status takes one arg, called with zero -> TypeError -> silent
    code = _cli(["T", "up=levi.bot.rollcall:probe_status"])
    assert code == 1
    code = _cli(["T", "ok=builtins:bool"])
    assert code == 1  # bool() is callable; bool() is falsy -> DOWN -> 1
