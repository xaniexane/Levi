"""Tests for levi.quickdial — Opera's Speed Dial reborn, LEVI-native."""

import stat

import pytest

from levi.quickdial import (
    check_chord,
    check_name,
    dial,
    find,
    find_by_chord,
    load,
    pin,
    render,
    seed,
    store_dir,
    unpin,
)


@pytest.fixture()
def levi_home(tmp_path, monkeypatch):
    home = tmp_path / "levihome"
    home.mkdir()
    monkeypatch.setenv("LEVI_HOME", str(home))
    return home


def test_pin_and_load(levi_home):
    slot = pin("pulse", "python3 -m levi.perpetual pulse", description="proof of life")
    assert slot.argv == ["python3", "-m", "levi.perpetual", "pulse"]
    slots = load()
    assert [s.name for s in slots] == ["pulse"]
    # argv list form preserves spaces inside arguments
    pin("echo", ["echo", "hello world"])
    assert find("echo").argv == ["echo", "hello world"]


def test_pin_rejects_bad_input(levi_home):
    with pytest.raises(ValueError):
        pin("Bad Name!", "echo hi")
    with pytest.raises(ValueError):
        pin("", "echo hi")
    with pytest.raises(ValueError):
        pin("empty", "")
    with pytest.raises(ValueError):
        pin("empty", [])
    with pytest.raises(ValueError):
        pin("dup", "echo one")
        pin("dup", "echo two")  # without replace


def test_pin_replace_keeps_uses(levi_home):
    pin("a", "echo one")
    dial(find("a"))
    pin("a", "echo two", replace=True)
    s = find("a")
    assert s.argv == ["echo", "two"]
    assert s.uses == 1


def test_chord_binding_and_lookup(levi_home):
    pin("news", "python3 -m levi.news refresh", chord="n")
    assert find_by_chord("n").name == "news"
    with pytest.raises(ValueError):
        pin("other", "echo x", chord="n")  # chord clash
    with pytest.raises(ValueError):
        pin("bad", "echo x", chord="space key")
    check_chord("")  # empty chord is fine
    assert check_name("ok-1_2") == "ok-1_2"


def test_dial_increments_uses_and_renders(levi_home):
    pin("g", ["git", "status", "--short"])
    s = find("g")
    argv = dial(s)
    assert argv == ["git", "status", "--short"]
    assert render(s) == "git status --short"
    assert find("g").uses == 1
    # index lookup is 1-based
    assert find("1").name == "g"
    with pytest.raises(KeyError):
        find("nope")


def test_unpin(levi_home):
    pin("x", "echo x")
    assert unpin("x") is True
    assert unpin("x") is False
    assert load() == []


def test_store_is_owner_only_and_atomic(levi_home):
    pin("s", "echo s")
    d = store_dir()
    assert stat.S_IMODE(d.stat().st_mode) == 0o700
    assert stat.S_IMODE((d / "dials.json").stat().st_mode) == 0o600
    # corrupt file degrades to empty, never crashes
    (d / "dials.json").write_text("not json{{{", encoding="utf-8")
    assert load() == []


def test_seed_is_idempotent(levi_home):
    first = seed()
    assert len(first) == 3
    second = seed()
    assert second == []
    names = {s.name for s in load()}
    assert {"pulse", "growth", "news"} <= names
    assert find_by_chord("p").name == "pulse"


def test_cli_roundtrip(levi_home, capsys):
    from levi.quickdial.__main__ import main

    assert main(["pin", "t", "--", "echo", "hello world"]) == 0
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "t" in out and "echo 'hello world'" in out
    assert main(["dial", "t"]) == 0
    assert main(["unpin", "t"]) == 0
    assert main(["dial", "t"]) == 1  # gone


def test_cli_rejects_bad_slot(levi_home):
    from levi.quickdial.__main__ import main

    assert main(["pin", "UPPER", "--", "echo", "x"]) == 1
