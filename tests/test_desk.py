"""Tests for levi.desk — the user's own status desk (iGoogle revival)."""

import pytest

from levi.desk.layout import DeskLayout
from levi.desk.registry import Tile, TileError, TileRegistry, register_builtin_tiles
from levi.desk.render import render_desk


def _tile(name="demo"):
    return Tile(name=name, title="Demo", description="a demo tile",
                render=lambda prefs: ["hello %s" % prefs.get("who", "world")])


def test_register_and_deny_closed_duplicates():
    reg = TileRegistry()
    reg.register(_tile())
    assert reg.names() == ["demo"]
    with pytest.raises(TileError):
        reg.register(_tile())  # duplicate refused


def test_bad_tile_names_refused():
    with pytest.raises(TileError):
        Tile(name="has space", title="T", description="d", render=lambda p: [])
    with pytest.raises(TileError):
        Tile(name="x" * 41, title="T", description="d", render=lambda p: [])
    with pytest.raises(TileError):
        Tile(name="ok", title="T", description="d", render="not-callable")


def test_deregister_unknown_refused():
    reg = TileRegistry()
    with pytest.raises(TileError):
        reg.deregister("nope")


def test_layout_add_remove_move_persist(tmp_path):
    lay = DeskLayout(base=tmp_path)
    lay.add("a"); lay.add("b"); lay.add("c")
    assert [e["tile"] for e in lay.entries()] == ["a", "b", "c"]
    lay.move("c", 0)
    assert [e["tile"] for e in lay.entries()] == ["c", "a", "b"]
    lay.set_enabled("a", False)
    lay.remove("b")
    # reload from disk
    lay2 = DeskLayout(base=tmp_path)
    names = [e["tile"] for e in lay2.entries()]
    assert names == ["c", "a"]
    assert lay2.entries()[1]["enabled"] is False


def test_layout_duplicate_add_refused(tmp_path):
    lay = DeskLayout(base=tmp_path)
    lay.add("a")
    with pytest.raises(TileError):
        lay.add("a")


def test_layout_prefs(tmp_path):
    lay = DeskLayout(base=tmp_path)
    lay.add("a")
    lay.set_prefs("a", {"who": "levi"})
    assert lay.entries()[0]["prefs"] == {"who": "levi"}
    with pytest.raises(TileError):
        lay.set_prefs("ghost", {})


def test_render_isolates_tile_failure(tmp_path):
    reg = TileRegistry()
    reg.register(_tile("good"))
    reg.register(Tile(name="bad", title="Bad", description="throws",
                      render=lambda p: 1 / 0))
    lay = DeskLayout(base=tmp_path)
    lay.add("good"); lay.add("bad")
    out = render_desk(reg, base=tmp_path)
    assert "hello world" in out
    assert "tile error" in out  # the bad tile didn't sink the desk


def test_render_unknown_tile_reported_not_crashed(tmp_path):
    reg = TileRegistry()
    lay = DeskLayout(base=tmp_path)
    lay.add("ghost")
    out = render_desk(reg, base=tmp_path)
    assert "not registered" in out


def test_render_empty_desk(tmp_path):
    reg = TileRegistry()
    out = render_desk(reg, base=tmp_path)
    assert "empty desk" in out


def test_render_disabled_tiles_hidden(tmp_path):
    reg = TileRegistry()
    reg.register(_tile("seen"))
    lay = DeskLayout(base=tmp_path)
    lay.add("seen")
    lay.set_enabled("seen", False)
    out = render_desk(reg, base=tmp_path)
    assert "hello world" not in out


def test_builtin_tiles_register_and_render(tmp_path):
    reg = TileRegistry()
    register_builtin_tiles(reg)
    assert {"clock", "archive", "growth"} <= set(reg.names())
    lay = DeskLayout(base=tmp_path)
    lay.add("clock", prefs={"format": "%Y"})
    lay.add("archive")
    lay.add("growth")
    out = render_desk(reg, base=tmp_path)
    assert "[clock]" in out and "[archive]" in out and "[growth]" in out
    # honest degradation: every tile rendered something, no raw traceback
    assert "Traceback" not in out


def test_prefs_override_defaults(tmp_path):
    reg = TileRegistry()
    reg.register(_tile("who"))
    lay = DeskLayout(base=tmp_path)
    lay.add("who", prefs={"who": "chauncey"})
    out = render_desk(reg, base=tmp_path)
    assert "hello chauncey" in out
