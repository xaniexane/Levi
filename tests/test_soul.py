"""Hermetic tests for LEVI's customizable soul (levi.agent.soul)."""

import os
import stat
import sys

import pytest

sys.path.insert(0, "core")

from levi.agent.loop import _build_system_prompt, _default_system_prompt
from levi.agent.soul import SOUL_MARKER, apply_soul, cmd_soul, load_soul


def _write_soul(home, text: str):
    d = home / ".levi"
    d.mkdir(parents=True, exist_ok=True)
    (d / "soul.md").write_text(text, encoding="utf-8")


# -- load_soul ------------------------------------------------------------


def test_load_soul_missing_file(tmp_path):
    assert load_soul(home=tmp_path) == ""


def test_load_soul_empty_and_whitespace_only(tmp_path):
    _write_soul(tmp_path, "")
    assert load_soul(home=tmp_path) == ""
    _write_soul(tmp_path, "   \n\t\n ")
    assert load_soul(home=tmp_path) == ""


def test_load_soul_strips_surrounding_whitespace(tmp_path):
    _write_soul(tmp_path, "\n  You are warm and brief.\n\n")
    assert load_soul(home=tmp_path) == "You are warm and brief."


def test_load_soul_never_raises_on_directory_at_path(tmp_path):
    d = tmp_path / ".levi"
    d.mkdir(parents=True, exist_ok=True)
    (d / "soul.md").mkdir()  # a directory, not a file
    assert load_soul(home=tmp_path) == ""


def test_load_soul_never_raises_on_unreadable(tmp_path):
    _write_soul(tmp_path, "secret soul")
    p = tmp_path / ".levi" / "soul.md"
    p.chmod(0)
    try:
        if os.geteuid() == 0:
            pytest.skip("running as root: unreadable files are still readable")
        assert load_soul(home=tmp_path) == ""
    finally:
        p.chmod(stat.S_IRUSR | stat.S_IWUSR)


def test_load_soul_never_raises_on_invalid_utf8(tmp_path):
    d = tmp_path / ".levi"
    d.mkdir(parents=True, exist_ok=True)
    (d / "soul.md").write_bytes(b"\xff\xfe not utf8 \x80")
    assert load_soul(home=tmp_path) == ""


# -- apply_soul ------------------------------------------------------------


def test_apply_soul_no_file_returns_prompt_unchanged(tmp_path):
    prompt = "the base prompt"
    result = apply_soul(prompt, home=tmp_path)
    assert result == prompt
    assert result is prompt or result == prompt  # exact equality at least


def test_apply_soul_prepends_marker_and_content(tmp_path):
    _write_soul(tmp_path, "Speak like a pirate, but stay honest.")
    out = apply_soul("base prompt", home=tmp_path)
    assert out == (
        SOUL_MARKER + "\n"
        "Speak like a pirate, but stay honest.\n\n"
        "base prompt"
    )
    assert out.startswith(SOUL_MARKER)


def test_apply_soul_does_not_mutate_original(tmp_path):
    _write_soul(tmp_path, "override")
    prompt = "base"
    apply_soul(prompt, home=tmp_path)
    assert prompt == "base"


# -- _build_system_prompt (the real helper run_subtask uses) --------------


def test_build_system_prompt_without_soul_matches_old_behavior(tmp_path):
    schemas = [{"name": "echo", "description": "echoes", "parameters": {}}]
    # run with HOME pointed at an empty dir so no soul is found
    old_home = os.environ.get("HOME")
    os.environ["HOME"] = str(tmp_path)
    try:
        assert _build_system_prompt(schemas) == _default_system_prompt(schemas)
        assert _build_system_prompt(schemas, "custom") == "custom"
    finally:
        if old_home is None:
            del os.environ["HOME"]
        else:
            os.environ["HOME"] = old_home


def test_build_system_prompt_with_soul_prepends_override(tmp_path):
    _write_soul(tmp_path, "You adore haiku answers.")
    schemas = [{"name": "echo", "description": "echoes", "parameters": {}}]
    old_home = os.environ.get("HOME")
    os.environ["HOME"] = str(tmp_path)
    try:
        got = _build_system_prompt(schemas)
        assert got.startswith(SOUL_MARKER + "\nYou adore haiku answers.\n\n")
        assert got.endswith(_default_system_prompt(schemas))
        got_custom = _build_system_prompt(schemas, "custom base")
        assert got_custom == (
            SOUL_MARKER + "\nYou adore haiku answers.\n\ncustom base"
        )
    finally:
        if old_home is None:
            del os.environ["HOME"]
        else:
            os.environ["HOME"] = old_home


# -- cmd_soul --------------------------------------------------------------


def _args(action=None):
    from argparse import Namespace

    return Namespace(action=action)


def test_cmd_soul_show_no_file(capsys):
    old_home = os.environ.get("HOME")
    os.environ["HOME"] = "/tmp/levi-soul-test-nonexistent-home-xyz"
    try:
        assert cmd_soul(_args()) == 0
        out = capsys.readouterr().out
        assert "no soul override set" in out
        assert "~/.levi/soul.md" in out
    finally:
        if old_home is None:
            del os.environ["HOME"]
        else:
            os.environ["HOME"] = old_home


def test_cmd_soul_edit_note_prints_instructions(capsys):
    assert cmd_soul(_args("edit-note")) == 0
    out = capsys.readouterr().out
    assert "soul.md" in out
    assert "editor" in out.lower()


def test_cmd_soul_unknown_action_returns_2(capsys):
    assert cmd_soul(_args("frobnicate")) == 2
    assert "unknown soul action" in capsys.readouterr().out
