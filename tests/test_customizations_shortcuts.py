"""Tests for the shortcuts customization (hermetic: tmp root)."""

from __future__ import annotations

import pytest

from levi.customizations import shortcuts
from levi.customizations.shortcuts import ShortcutError


@pytest.fixture()
def root(tmp_path):
    return tmp_path / "customizations"


def test_add_and_get_roundtrip(root):
    rec = shortcuts.add_shortcut("hb", "daemon heartbeat --force", root=root)
    assert rec["name"] == "hb"
    assert (
        shortcuts.get_shortcut("hb", root=root)["expansion"]
        == "daemon heartbeat --force"
    )


def test_add_rejects_bad_names(root):
    for bad in ["", "UPPER", "has space", "9lives", "-dash", "a" * 41]:
        with pytest.raises(ShortcutError):
            shortcuts.add_shortcut(bad, "daemon heartbeat", root=root)


def test_add_rejects_shell_metacharacters(root):
    for bad in [
        "echo hi; rm -rf /",
        "a | b",
        "x && y",
        "$(evil)",
        "`evil`",
        "a > b",
        "a\nb",
    ]:
        with pytest.raises(ShortcutError):
            shortcuts.add_shortcut("ok", bad, root=root)


def test_add_rejects_duplicates(root):
    shortcuts.add_shortcut("hb", "daemon heartbeat", root=root)
    with pytest.raises(ShortcutError):
        shortcuts.add_shortcut("hb", "daemon other", root=root)


def test_expand_simple_with_args(root):
    shortcuts.add_shortcut("hb", "daemon heartbeat --force", root=root)
    assert shortcuts.expand("hb --json", root=root) == "daemon heartbeat --force --json"
    assert shortcuts.expand("hb", root=root) == "daemon heartbeat --force"


def test_expand_passthrough_for_unknown(root):
    shortcuts.add_shortcut("hb", "daemon heartbeat", root=root)
    assert shortcuts.expand("daemon status", root=root) == "daemon status"


def test_expand_follows_chains(root):
    shortcuts.add_shortcut("hb", "daemon heartbeat", root=root)
    shortcuts.add_shortcut("hbf", "hb --force", root=root)
    assert shortcuts.expand("hbf", root=root) == "daemon heartbeat --force"


def test_expand_refuses_cycles(root):
    shortcuts.add_shortcut("aa", "bb", root=root)
    shortcuts.add_shortcut("bb", "aa", root=root)
    with pytest.raises(ShortcutError):
        shortcuts.expand("aa", root=root)


def test_remove_retires_nothing_deleted(root):
    shortcuts.add_shortcut("hb", "daemon heartbeat", root=root)
    retired = shortcuts.remove_shortcut("hb", reason="renamed", root=root)
    assert retired["reason"] == "renamed"
    assert shortcuts.list_shortcuts(root=root) == []
    with pytest.raises(ShortcutError):
        shortcuts.get_shortcut("hb", root=root)


def test_restore_brings_back(root):
    shortcuts.add_shortcut("hb", "daemon heartbeat", root=root)
    shortcuts.remove_shortcut("hb", root=root)
    rec = shortcuts.restore_shortcut("hb", root=root)
    assert rec["expansion"] == "daemon heartbeat"
    assert shortcuts.get_shortcut("hb", root=root)["expansion"] == "daemon heartbeat"


def test_find_searches_names_and_expansions(root):
    shortcuts.add_shortcut("hb", "daemon heartbeat --force", root=root)
    shortcuts.add_shortcut("st", "daemon status", root=root)
    assert [s["name"] for s in shortcuts.find("h", root=root)] == ["hb"]
    assert {s["name"] for s in shortcuts.find("daemon", root=root)} == {"hb", "st"}


def test_list_sorted(root):
    shortcuts.add_shortcut("zz", "b", root=root)
    shortcuts.add_shortcut("aa", "a", root=root)
    assert [s["name"] for s in shortcuts.list_shortcuts(root=root)] == ["aa", "zz"]
