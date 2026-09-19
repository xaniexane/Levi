"""Tests for revival wave 33 — interface-metaphors."""

import pytest

from levi.revival.town_metaphor import Town
from levi.revival.service_directory import ServiceDirectory
from levi.revival.speed_dial import SpeedDial
from levi.revival.tab_stacking import TabBar
from levi.revival.transpointing import PointingSpace
from levi.revival.transvisibility import Transvisibility
from levi.revival.tiled_viewers import TileSpace


def _town() -> Town:
    town = Town("Testville")
    town.add_street("a", "b")
    town.add_street("b", "c")
    town.add_street("a", "d")
    town.add_building("post", "Post Office", "messaging", "Civic", "a")
    town.add_building("ledger", "Ledger Hall", "finance", "Civic", "b")
    town.add_building("archive", "Archive", "memory", "Scholar", "c")
    town.add_building("docks", "Docks", "transport", "Harbor", "d")
    return town


def test_town_route_and_directions():
    town = _town()
    assert town.route("docks", "archive") == ["d", "a", "b", "c"]
    steps = town.directions("docks", "archive")
    assert any("Archive" in s for s in steps)
    assert any("docks" in s.lower() or "Docks" in s for s in steps)
    assert town.route("post", "post") == ["a"]


def test_town_search_and_kinds():
    town = _town()
    assert [b.id for b in town.find_by_kind("memory")] == ["archive"]
    assert len(town.find_by_district("Civic")) == 2
    hits = town.search("ledger")
    assert [b.id for b in hits] == ["ledger"]
    with pytest.raises(ValueError):
        town.add_building("post", "Dupe", "x", "Civic", "a")


def test_town_nearby():
    town = _town()
    near = {b.id for b in town.nearby("post", blocks=1)}
    assert near == {"ledger", "docks"}
    far = {b.id for b in town.nearby("post", blocks=2)}
    assert "archive" in far


def _directory() -> ServiceDirectory:
    d = ServiceDirectory()
    d.register("inkjet", "printer", "home", "addr://p/inkjet")
    d.register("laser", "printer", "home", "addr://p/laser")
    d.register("vault", "fileserver", "home", "addr://f/vault")
    d.register("plotter", "printer", "shop", "addr://p/plotter")
    return d


def test_directory_browse_and_zones():
    d = _directory()
    assert d.zones() == ["home", "shop"]
    assert d.types("home") == ["fileserver", "printer"]
    assert [s.name for s in d.browse(type="printer", zone="home")] == [
        "inkjet",
        "laser",
    ]
    assert len(d.browse()) == 4


def test_directory_lookup_and_resolve():
    d = _directory()
    assert [s.address for s in d.lookup("vault")] == ["addr://f/vault"]
    assert d.resolve("plotter", "printer", "shop") == "addr://p/plotter"
    with pytest.raises(KeyError):
        d.resolve("nope", "printer", "home")
    assert d.unregister("inkjet", "printer", "home") is True
    assert d.unregister("inkjet", "printer", "home") is False


def test_directory_rejects_bad_registration():
    d = ServiceDirectory()
    with pytest.raises(ValueError):
        d.register("", "printer", "home", "addr://x")
    d.register("inkjet", "printer", "home", "addr://x")
    with pytest.raises(ValueError):
        d.register("inkjet", "printer", "home", "addr://y")


def test_speed_dial_slots_and_move():
    pad = SpeedDial(columns=2)
    a = pad.add("news", "levi://news")
    b = pad.add("build", "levi://build")
    assert (a.slot, b.slot) == (0, 1)
    pad.move(a.id, 1)  # swap
    assert pad.by_slot()[0].id == b.id
    assert pad.by_slot()[1].id == a.id
    pad.remove(b.id)
    c = pad.add("notes", "levi://notes")
    assert c.slot == 0  # reuses freed slot


def test_speed_dial_launch_records_habit():
    pad = SpeedDial()
    a = pad.add("news", "levi://news")
    b = pad.add("build", "levi://build")
    pad.launch(a.id)
    pad.launch(a.id)
    pad.launch(b.id)
    assert pad.launch(a.id) == "levi://news"
    assert [d.id for d in pad.by_habit()] == [a.id, b.id]
    assert pad.find("NEWS")[0].id == a.id
    with pytest.raises(KeyError):
        pad.launch(999)


def test_speed_dial_render_and_roundtrip():
    pad = SpeedDial(columns=3)
    pad.add("one", "t1")
    pad.add("two", "t2")
    grid = pad.render()
    assert "[0] one" in grid and "[1] two" in grid
    pad2 = SpeedDial.from_dict(pad.to_dict())
    assert [d.title for d in pad2.by_slot()] == ["one", "two"]
    assert pad2.columns == 3
    with pytest.raises(ValueError):
        pad.add("  ", "t3")
    pad.rename(pad.by_slot()[0].id, "uno")
    assert pad.by_slot()[0].title == "uno"


def _tabbar() -> TabBar:
    bar = TabBar()
    bar.open("inbox", "t1")
    bar.open("drafts", "t2")
    bar.open("build", "t3")
    return bar


def test_tab_stacking_collapse_render():
    bar = _tabbar()
    ids = [t.id for t in bar.tabs()][:2]
    stack = bar.stack("mail", ids)
    assert "[mail x2]" in bar.render()
    bar.expand(stack.id)
    assert "inbox" in bar.render() and "drafts" in bar.render()
    bar.rename_stack(stack.id, "post")
    assert "[post:" in bar.render()


def test_tab_stacking_unstack_dissolves():
    bar = _tabbar()
    ids = [t.id for t in bar.tabs()]
    bar.stack("all", ids[:2])
    bar.unstack(ids[0])
    assert bar.stack_of(ids[0]) is None
    assert bar.stack_of(ids[1]) is not None
    bar.unstack(ids[1])  # last tab out dissolves the stack
    assert bar.stacks() == []
    with pytest.raises(ValueError):
        bar.stack("tiny", [ids[2]])


def test_tab_stacking_close_and_activate():
    bar = _tabbar()
    ids = [t.id for t in bar.tabs()]
    stack = bar.stack("mail", ids[:2])
    assert bar.active_tab == ids[2]
    bar.add_to_stack(stack.id, ids[2])
    assert bar.stack_of(ids[2]) is not None
    bar.close(ids[2])
    assert bar.active_tab in (ids[0], ids[1])
    bar.activate(ids[0])
    assert bar.active_tab == ids[0]
    with pytest.raises(KeyError):
        bar.activate(999)


def _space() -> PointingSpace:
    space = PointingSpace()
    space.add_window("notes", 0, 0, 40, 20, "Notes")
    space.add_window("plan", 45, 5, 40, 20, "Plan")
    return space


def test_transpointing_point_and_translate():
    space = _space()
    win, local = space.point(50, 7)
    assert win.id == "plan"
    assert local == (5, 2)
    assert space.to_global("notes", 5, 5) == (5, 5)
    assert space.to_local("plan", 50, 7) == (5, 2)
    with pytest.raises(ValueError):
        space.point(1000, 1000)


def test_transpointing_follow():
    space = _space()
    tp = space.transpoint("notes", (5, 5), "plan", (10, 2), label="see-also")
    target_win, local, glob = space.follow(tp.id)
    assert (target_win, local, glob) == ("plan", (10, 2), (55, 7))
    assert [p.label for p in space.from_window("notes")] == ["see-also"]
    assert [p.label for p in space.into_window("plan")] == ["see-also"]


def test_transpointing_window_removal_kills_links():
    space = _space()
    tp = space.transpoint("notes", (1, 1), "plan", (1, 1))
    assert space.remove_window("plan") is True
    assert space.remove_transpoint(tp.id) is False
    assert space.into_window("plan") == []
    with pytest.raises(ValueError):
        space.transpoint("notes", (99, 99), "notes", (1, 1))


def _tv() -> Transvisibility:
    tv = Transvisibility()
    tv.register("m:12", "essay", (40, 120), "We hold that ", " is law.")
    tv.register("m:12", "pamphlet", (5, 85), "Printed: ", " — take it.", "abridged")
    tv.register("o:3", "essay", (200, 260), "Meanwhile, ", "")
    return tv


def test_transvisibility_siblings():
    tv = _tv()
    first = tv.instances_of("m:12")[0]
    sibs = tv.siblings(first.id)
    assert len(sibs) == 1
    assert sibs[0].doc_id in ("essay", "pamphlet")
    assert sibs[0].id != first.id
    lone = tv.instances_of("o:3")[0]
    assert tv.siblings(lone.id) == []


def test_transvisibility_view_marks_current():
    tv = _tv()
    first = tv.instances_of("m:12")[0]
    view = tv.visibility(first.id)
    assert view["sibling_count"] == 1
    assert view["instance"]["current"] is True
    assert all(s["current"] is False for s in view["siblings"])
    assert "[…]" in view["siblings"][0]["context"]
    assert tv.sources() == ["m:12", "o:3"]


def test_transvisibility_rejects_bad_spans():
    tv = Transvisibility()
    with pytest.raises(ValueError):
        tv.register("s", "d", (10, 5))
    with pytest.raises(ValueError):
        tv.register("", "d", (0, 5))
    inst = tv.register("s", "d", (0, 5))
    assert tv.remove(inst.id) is True
    assert tv.remove(inst.id) is False


def test_tiled_viewers_split_and_tiles():
    space = TileSpace(width=60, height=16)
    left, right = space.split(space.root.id, "v", ratio=0.5, name="tasks")
    assert len(space.tiles()) == 2
    widths = sorted(t["w"] for t in space.tiles())
    assert sum(widths) + 1 == 60  # divider column between tiles
    assert space.root.find(left) is not None
    with pytest.raises(ValueError):
        space.split(space.root.id, "v")  # root is no longer a leaf


def test_tiled_viewers_edit_and_close():
    space = TileSpace(width=60, height=16)
    space.type("hello")
    left, right = space.split(space.root.id, "v", name="right")
    space.type("world", tile_id=right)
    assert space.buffer(right).text() == "world"
    space.buffer(left).insert(0, "first")
    assert space.buffer(left).lines[0] == "first"
    assert space.close(right) is True
    assert len(space.tiles()) == 1
    assert space.close(space.root.id) is False  # cannot close last tile


def test_tiled_viewers_focus_and_render():
    space = TileSpace(width=60, height=16)
    left, right = space.split(space.root.id, "v", name="b")
    space.focus(right)
    assert space.focused == right
    assert space.focus_dir("left") is True
    assert space.focused == left
    rendered = space.render()
    assert "*" in rendered  # focus marker on the label line
    assert "scratch" in rendered and " b*" not in rendered
    with pytest.raises(ValueError):
        space.focus(9999)
