"""Hermetic tests for levi.ux.effects — the terminal UX effects kit.

Two harness modes, both built on pytest's ``capsys`` (fighting pytest's
per-phase stdout swapping proved fragile, so the harnesses patch the gate
instead and read output back through ``capsys``):

- **Degraded (pipe-safe):** the :func:`effects_enabled` gate is forced to
  ``False`` and ``NO_COLOR=1`` is set.  Every public output must contain
  zero ANSI escapes.
- **TTY:** the gate is forced to ``True`` and ``NO_COLOR`` is removed.
  ANSI must appear where expected.

The real gate itself (:func:`effects_enabled`) is tested separately with
genuine stdout doubles.  ``menu``/``confirm``/``pause_for_key`` are driven
with monkeypatched ``input()``.  No subprocesses, no network, no terminal.
"""

from __future__ import annotations

import io
import sys

import pytest

from levi.ux import effects
from levi.ux.effects import (
    ProgressBar,
    Spinner,
    Table,
    banner,
    color,
    confirm,
    effects_enabled,
    menu,
    meter,
    pause_for_key,
    rule,
    sparkline,
    status_line,
    typing_print,
)


# ---------------------------------------------------------------------------
# Harnesses
# ---------------------------------------------------------------------------


class FakeTTY(io.StringIO):
    """A StringIO that claims to be a terminal."""

    def isatty(self) -> bool:  # noqa: D102
        return True


def _out(capsys) -> str:
    return capsys.readouterr().out


@pytest.fixture()
def degraded(monkeypatch, capsys):
    """Pipe-safe mode: gate forced off, NO_COLOR set, width pinned at 80."""
    monkeypatch.setattr(effects, "effects_enabled", lambda: False)
    monkeypatch.setattr(effects, "_terminal_width", lambda: 80)
    monkeypatch.setenv("NO_COLOR", "1")
    effects._status_last = ""
    effects._status_last_len = 0
    return capsys


@pytest.fixture()
def tty(monkeypatch, capsys):
    """Rich mode: gate forced on, NO_COLOR removed, width pinned at 80."""
    monkeypatch.setattr(effects, "effects_enabled", lambda: True)
    monkeypatch.setattr(effects, "_terminal_width", lambda: 80)
    monkeypatch.delenv("NO_COLOR", raising=False)
    effects._status_last = ""
    effects._status_last_len = 0
    return capsys


def assert_no_ansi(text: str) -> None:
    assert "\x1b" not in text, f"ANSI escape found in degraded output: {text!r}"


def assert_ascii_only(text: str) -> None:
    text.encode("ascii")


# ---------------------------------------------------------------------------
# The real gate (tested with genuine stdout doubles, no gate patching)
# ---------------------------------------------------------------------------


def test_effects_enabled_tty(monkeypatch):
    monkeypatch.setattr(sys, "stdout", FakeTTY())
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert effects_enabled() is True


def test_effects_enabled_pipe(monkeypatch):
    monkeypatch.setattr(sys, "stdout", io.StringIO())  # isatty() -> False
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert effects_enabled() is False


def test_effects_enabled_no_color_wins_over_tty(monkeypatch):
    monkeypatch.setattr(sys, "stdout", FakeTTY())
    monkeypatch.setenv("NO_COLOR", "1")
    assert effects_enabled() is False


def test_effects_enabled_broken_stdout(monkeypatch):
    class Broken:
        def isatty(self):
            raise OSError("gone")

    monkeypatch.setattr(sys, "stdout", Broken())
    assert effects_enabled() is False


# ---------------------------------------------------------------------------
# color / rule / banner
# ---------------------------------------------------------------------------


def test_color_degraded_returns_verbatim(degraded):
    assert color("hello", fg="red", bold=True) == "hello"


def test_color_tty_wraps_ansi(tty):
    out = color("hello", fg="red", bold=True)
    assert out.startswith("\x1b[") and out.endswith("\x1b[0m")
    assert "hello" in out
    assert "31" in out and "1" in out


def test_color_unknown_fg_ignored(tty):
    out = color("x", fg="chartreuse")
    assert out == "x"  # no codes at all, no crash


def test_color_no_styles_no_wrap(tty):
    assert color("x") == "x"


@pytest.mark.parametrize(
    "fg", ["red", "green", "yellow", "blue", "magenta", "cyan", "white", "gray"]
)
def test_color_all_fg_names(tty, fg):
    assert "\x1b[" in color("x", fg=fg)


def test_rule_degraded(degraded):
    line = rule()
    assert_no_ansi(line)
    assert_ascii_only(line)
    assert set(line) == {"-"}
    assert len(line) == 80  # pinned width


def test_rule_tty(tty):
    line = rule()
    assert_no_ansi(line)  # rules carry no color codes
    assert set(line) == {"─"}


def test_banner_degraded(degraded):
    out = banner("Title", "sub")
    assert_no_ansi(out)
    assert_ascii_only(out)
    assert "Title" in out and "sub" in out
    assert out.startswith("+") and out.rstrip().endswith("+")


def test_banner_degraded_no_subtitle(degraded):
    out = banner("Only")
    assert "Only" in out
    assert_ascii_only(out)


def test_banner_tty(tty):
    out = banner("Title", "sub")
    assert_no_ansi(out)
    assert "┌" in out and "┘" in out and "│" in out
    assert "Title" in out


# ---------------------------------------------------------------------------
# Spinner
# ---------------------------------------------------------------------------


def test_spinner_degraded_single_static_line(degraded):
    with Spinner("working"):
        pass
    out = _out(degraded)
    assert_no_ansi(out)
    assert_ascii_only(out)
    assert out.strip() == "... working"


def test_spinner_tty_restores_line_cleanly(tty):
    with Spinner("working", interval=0.01):
        import time

        time.sleep(0.05)
    out = _out(tty)
    assert_no_ansi(out)
    # Exit must clear the rewritten line: trailing \r + spaces + \r.
    assert out.endswith("\r" + " " * 80 + "\r")


def test_spinner_tty_animates(tty):
    with Spinner("working", interval=0.01):
        import time

        time.sleep(0.06)
    out = _out(tty)
    assert "\r" in out  # line rewrites happened
    assert "working" in out


# ---------------------------------------------------------------------------
# ProgressBar
# ---------------------------------------------------------------------------


def test_progress_degraded_quarter_lines(degraded):
    bar = ProgressBar(100, "dl")
    for _ in range(100):
        bar.update(1)
    bar.finish()
    out = _out(degraded)
    assert_no_ansi(out)
    assert "25% (25/100)" in out
    assert "50% (50/100)" in out
    assert "75% (75/100)" in out
    assert "100% (100/100)" in out


def test_progress_degraded_no_total_counts(degraded):
    bar = ProgressBar(None, "scan")
    for _ in range(7):
        bar.update()
    bar.finish()
    out = _out(degraded)
    assert_no_ansi(out)
    assert "done (7 items)" in out


def test_progress_tty_rewrites_line(tty):
    bar = ProgressBar(10, "dl")
    bar.update(5)
    out = _out(tty)
    assert "\r" in out
    assert_no_ansi(out)  # the bar itself carries no ANSI styling
    assert "50.0%" in out


def test_progress_tty_unknown_total_counts(tty):
    bar = ProgressBar(0, "scan")
    bar.update(3)
    bar.finish()
    out = _out(tty)
    assert "3 items" in out


def test_progress_finish_idempotent(degraded):
    bar = ProgressBar(4, "x")
    bar.update(4)
    bar.finish()
    bar.finish()
    assert _out(degraded).count("100%") == 1


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------


def test_table_degraded_aligned(degraded):
    t = Table(["name", "score"], [["levi", 98], ["a-much-longer-name", 3]])
    out = t.render()
    assert_no_ansi(out)
    assert_ascii_only(out)
    lines = out.splitlines()
    assert lines[0].startswith("name")
    # Header and separator have identical length => columns aligned.
    assert len(lines[0]) == len(lines[1])


def test_table_truncates_long_cells(degraded):
    t = Table(["c"], [["x" * 200]], max_width=20)
    out = t.render()
    assert_no_ansi(out)
    assert "~" in out  # ASCII ellipsis in degraded mode
    assert all(len(line) <= 20 for line in out.splitlines())


def test_table_truncates_tty_uses_unicode_ellipsis(tty):
    t = Table(["c"], [["x" * 200]], max_width=20)
    out = t.render()
    assert "…" in out


def test_table_handles_non_string_cells(degraded):
    out = Table(["n"], [[1], [None], [3.5]]).render()
    assert "None" in out and "3.5" in out


# ---------------------------------------------------------------------------
# typing_print / status_line
# ---------------------------------------------------------------------------


def test_typing_print_degraded_instant(degraded):
    typing_print("hello world", delay=5.0)  # delay must be ignored
    assert _out(degraded) == "hello world\n"


def test_typing_print_tty_emits_chars(tty, monkeypatch):
    monkeypatch.setattr(effects.time, "sleep", lambda s: None)
    typing_print("hi", delay=0.5)
    assert _out(tty) == "hi\n"


def test_status_line_degraded_prints_only_on_change(degraded):
    status_line("a")
    status_line("a")
    status_line("b")
    assert _out(degraded) == "a\nb\n"


def test_status_line_tty_rewrites(tty):
    status_line("first")
    status_line("second-longer")
    out = _out(tty)
    assert "\r" in out
    assert_no_ansi(out)
    assert "second-longer" in out


def test_status_line_tty_pads_shorter_text(tty):
    status_line("longer-text-here")
    status_line("short")
    out = _out(tty)
    # The shorter rewrite must erase leftovers: total visible length kept.
    last = out.split("\r")[-1]
    assert len(last) == len("longer-text-here")


# ---------------------------------------------------------------------------
# sparkline / meter
# ---------------------------------------------------------------------------


def test_sparkline_empty(degraded):
    assert sparkline([]) == ""


def test_sparkline_single_value(degraded):
    assert len(sparkline([42.0])) == 1


def test_sparkline_constant_degraded(degraded):
    out = sparkline([5.0, 5.0, 5.0])
    assert len(out) == 3
    assert_ascii_only(out)
    assert len(set(out)) == 1  # one repeated mid-level mark


def test_sparkline_constant_tty(tty):
    out = sparkline([5.0, 5.0, 5.0])
    assert out == "▅▅▅"  # middle block for every value


def test_sparkline_monotonic_increases(tty):
    out = sparkline([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    assert out == "▁▂▃▄▅▆▇█"


def test_sparkline_handles_negatives(tty):
    out = sparkline([-3.0, 0.0, 3.0])
    assert len(out) == 3
    assert out[0] == "▁" and out[-1] == "█"


def test_sparkline_degraded_ascii_only(degraded):
    out = sparkline([1.0, 5.0, 3.0, 9.0])
    assert_no_ansi(out)
    assert_ascii_only(out)
    assert len(out) == 4


def test_meter_degraded(degraded):
    out = meter(6, 10, width=10)
    assert_no_ansi(out)
    assert_ascii_only(out)
    assert out == "[######----]  60%"


def test_meter_tty_uses_blocks(tty):
    out = meter(6, 10, width=10)
    assert "█" in out and "░" in out


def test_meter_clamps(degraded):
    assert meter(99, 10, width=10) == "[##########] 100%"
    assert meter(-5, 10, width=10) == "[----------]   0%"


def test_meter_zero_max(degraded):
    assert meter(5, 0, width=10) == "[----------]   0%"


# ---------------------------------------------------------------------------
# menu / confirm / pause_for_key
# ---------------------------------------------------------------------------


def test_menu_pick_number(monkeypatch, degraded):
    monkeypatch.setattr("builtins.input", lambda prompt="": "2")
    assert menu(["a", "b", "c"]) == 1


def test_menu_pick_letter(monkeypatch, degraded):
    monkeypatch.setattr("builtins.input", lambda prompt="": "c")
    assert menu(["a", "b", "c"]) == 2


def test_menu_quit(monkeypatch, degraded):
    monkeypatch.setattr("builtins.input", lambda prompt="": "q")
    assert menu(["a", "b"]) is None


def test_menu_eof(monkeypatch, degraded):
    def boom(prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", boom)
    assert menu(["a"]) is None


def test_menu_reprompts_then_accepts(monkeypatch, degraded):
    answers = iter(["nope", "99", "1"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert menu(["a", "b"]) == 0


def test_menu_empty_options(degraded):
    assert menu([]) is None


def test_confirm_yes(monkeypatch, degraded):
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    assert confirm("Sure?") is True


def test_confirm_default_no(monkeypatch, degraded):
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert confirm("Sure?") is False
    assert confirm("Sure?", default=True) is True


def test_confirm_eof_is_default(monkeypatch, degraded):
    def boom(prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", boom)
    assert confirm("Sure?") is False


def test_pause_for_key(monkeypatch, degraded):
    def fake_input(prompt=""):
        print(prompt, end="")  # echo the prompt like real input() does
        return ""

    monkeypatch.setattr("builtins.input", fake_input)
    pause_for_key("wait")  # must not raise
    assert "wait" in _out(degraded)


def test_pause_for_key_eof(monkeypatch, degraded):
    def boom(prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", boom)
    pause_for_key("wait")  # must not raise


# ---------------------------------------------------------------------------
# No-ANSI sweep: degraded output of every visual must be escape-free
# ---------------------------------------------------------------------------


def test_no_ansi_sweep(degraded, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "q")
    pieces = [
        color("c", fg="cyan", bold=True),
        rule(),
        banner("T", "S"),
        sparkline([1, 2, 3]),
        meter(1, 2),
        Table(["h"], [["r"]]).render(),
    ]
    typing_print("typed")
    status_line("st")
    with Spinner("spin"):
        pass
    bar = ProgressBar(4, "p")
    bar.update(4)
    bar.finish()
    confirm("ok?")
    menu(["only"])
    pause_for_key("k")
    combined = "\n".join(pieces) + "\n" + _out(degraded)
    assert_no_ansi(combined)
