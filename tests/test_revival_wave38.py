"""Wave 38 tests: input methods + thin-client graphics revival modules."""

from __future__ import annotations

import json

import pytest

from core.levi.revival import actionable_text, marking_menus, mouse_gestures
from core.levi.revival import pie_menus, spatial_nav, thin_vector_pages
from core.levi.revival import local_asset_graphics, web_clipping


# ---- mouse_gestures ----


def test_gesture_quantize_simple_strokes():
    assert mouse_gestures.quantize([(0, 0), (0, -100)]) == "U"
    assert mouse_gestures.quantize([(0, 0), (-100, 0)]) == "L"
    assert mouse_gestures.quantize([(0, 0), (0, -60), (60, -60)]) == "UR"
    assert mouse_gestures.quantize([(0, 0)]) == ""


def test_gesture_jitter_is_dropped():
    # Sub-8px wobble must not register as a stroke.
    assert mouse_gestures.quantize([(0, 0), (3, 2), (1, 4)]) == ""


def test_gesture_default_vocabulary_and_rocker():
    v = mouse_gestures.GestureVocabulary()
    assert v.recognize([(0, 0), (0, -120)]) == "new-tab"
    assert v.recognize([(0, 0), (0, 120)]) == "close-tab"
    assert v.recognize([(0, 0), (-120, 0)]) == "back"
    assert v.rocker("L", "R") == "back"
    assert v.rocker("R", "L") == "forward"
    assert v.rocker("L", "L") is None


def test_gesture_custom_binding_and_confusables():
    v = mouse_gestures.GestureVocabulary()
    v.bind("UDL", "my-command")
    assert v.match("UDL") == "my-command"
    assert "UD" in v.confusable("UDL")
    assert v.unbind("UDL") == "my-command"
    assert v.match("UDL") is None


# ---- spatial_nav ----


def _nav() -> spatial_nav.SpatialMap:
    m = spatial_nav.SpatialMap()
    m.add("a", "Alpha link", 0, 0, 40, 20)
    m.add("b", "Beta link", 100, 0, 40, 20)
    m.add("c", "Gamma link", 0, 60, 40, 20)
    return m


def test_spatial_move_cardinal():
    m = _nav()
    assert m.move("a", "right") == "b"
    assert m.move("a", "down") == "c"
    assert m.move("b", "left") == "a"
    assert m.move("a", "up") is None


def test_spatial_bad_direction_rejected():
    m = _nav()
    with pytest.raises(ValueError):
        m.move("a", "northwest")


def test_spatial_jump_and_nearest():
    m = _nav()
    assert m.jump("bet") == "b"
    assert m.jump("zzz") is None
    assert m.nearest(5, 5) == "a"
    assert m.nearest(500, 500) == "b"


def test_spatial_wrap_option():
    m = spatial_nav.SpatialMap(wrap=True)
    m.add("a", "A", 0, 0, 10, 10)
    m.add("b", "B", 100, 0, 10, 10)
    assert m.move("b", "right") == "a"  # wraps to farthest-left
    m2 = spatial_nav.SpatialMap(wrap=False)
    m2.add("b", "B", 100, 0, 10, 10)
    assert m2.move("b", "right") is None


# ---- actionable_text ----


def _registry() -> actionable_text.ToolRegistry:
    r = actionable_text.ToolRegistry()
    r.register("Edit.Cut", lambda sel, *a: f"cut:{sel}")
    r.register("File.Open", lambda sel, *a: f"open:{a[0] if a else ''}:{sel}")
    return r


def test_actionable_scan_finds_tokens():
    cmds = actionable_text.scan("Please Edit.Cut this and File.Open('a.txt') now.")
    assert [str(c) for c in cmds] == ["Edit.Cut", "File.Open(a.txt)"]
    assert cmds[0].span[0] < cmds[1].span[0]


def test_actionable_activate_at_position():
    r = _registry()
    text = "Please Edit.Cut this word."
    pos = text.index("Edit.Cut") + 2
    assert actionable_text.activate(text, pos, r, selection="hello") == "cut:hello"


def test_actionable_unknown_tool_is_inert():
    r = _registry()
    text = "Try Bogus.Nope here."
    pos = text.index("Bogus.Nope") + 2
    assert actionable_text.activate(text, pos, r) is None
    assert actionable_text.activate("no commands at all", 3, r) is None


def test_actionable_args_parsing():
    r = _registry()
    text = 'Open File.Open("report.txt", extra) please.'
    pos = text.index("File.Open") + 5
    assert actionable_text.activate(text, pos, r, selection="s") == "open:report.txt:s"


# ---- pie_menus ----


def test_pie_select_by_angle():
    p = pie_menus.PieMenu(["copy", "paste", "cut", "undo"])
    assert p.select(0, -100) == "copy"  # north
    assert p.select(100, 0) == "paste"  # east
    assert p.select(0, 100) == "cut"  # south
    assert p.select(-100, 0) == "undo"  # west


def test_pie_dead_zone():
    p = pie_menus.PieMenu(["a", "b", "c"], dead_radius=24.0)
    assert p.select(0, 0) is None
    assert p.select(10, 10) is None
    assert p.select(0, -100) == "a"


def test_pie_sectors_and_neighbors():
    p = pie_menus.PieMenu(["a", "b", "c", "d"])
    assert p.angle_of("a") == pytest.approx(0.0)
    assert p.angle_of("c") == pytest.approx(180.0)
    start, end = p.sector_of("a")
    assert (end - start) % 360.0 == pytest.approx(90.0)
    assert p.neighbor("d") == "a"
    assert p.neighbor("a", -1) == "d"
    with pytest.raises(ValueError):
        pie_menus.PieMenu([])


# ---- marking_menus ----


def _mm() -> marking_menus.MarkingMenu:
    return marking_menus.MarkingMenu(
        [
            marking_menus.MenuItem("copy", ["E"], "clipboard.copy"),
            marking_menus.MenuItem("paste", ["E", "S"], "clipboard.paste"),
            marking_menus.MenuItem("cut", ["E", "N"], "clipboard.cut"),
            marking_menus.MenuItem("undo", ["W"], "edit.undo"),
        ]
    )


def test_marking_recognize_states():
    m = _mm()
    assert m.recognize(["E"]) == "exact"
    assert m.recognize([]) == "prefix"
    assert m.recognize(["N"]) == "none"


def test_marking_novice_and_expert_share_matcher():
    m = _mm()
    # Expert: mouse-ahead, no popup.
    assert m.expert_select(["E", "S"]).name == "paste"
    assert m.expert_select(["E"]) is not None  # exact match still works
    assert m.expert_select(["N"]) is None
    # Novice: popup appears on prefix.
    sel, submenu = m.novice_select([])
    assert sel is None
    assert {i.name for i in submenu} == {"copy", "undo"}
    sel2, _ = m.novice_select(["E", "S"])
    assert sel2.name == "paste"


def test_marking_quantize_and_learn():
    m = _mm()
    assert marking_menus.quantize([(0, 0), (100, 5), (200, -5)]) == ["E"]
    assert m.learn_path("paste") == ["E", "S"]
    assert m.learn_path("missing") is None
    with pytest.raises(ValueError):
        marking_menus.MarkingMenu(
            [marking_menus.MenuItem("x", ["E"]), marking_menus.MenuItem("y", ["E"])]
        )


# ---- thin_vector_pages ----


def test_vector_page_encode_decode_roundtrip():
    cache = thin_vector_pages.AssetCache()
    page = thin_vector_pages.Page(title="home")
    page.add_rect(0, 0, 80, 24, "blue").add_text(4, 4, "Hello", 14)
    icon = b"\x89PNG" + b"x" * 100
    page.add_blit(icon, 70, 2, 8, 8, cache)
    payload = page.encode()
    assert thin_vector_pages.wire_bytes(payload) > 0
    page2, missing = thin_vector_pages.Page.decode(payload, cache)
    assert missing == []
    assert page2.title == "home"
    assert len(page2.commands) == 3
    assert cache.stats()["hits"] >= 1


def test_vector_page_missing_asset_listed():
    cache = thin_vector_pages.AssetCache()
    page = thin_vector_pages.Page()
    page.add_blit(b"blob-bytes", 0, 0, 8, 8, cache)
    payload = page.encode()
    fresh = thin_vector_pages.AssetCache()  # empty client cache
    _, missing = thin_vector_pages.Page.decode(payload, fresh)
    assert len(missing) == 1
    assert fresh.stats()["misses"] >= 1


def test_vector_page_cached_asset_skips_wire():
    cache = thin_vector_pages.AssetCache()
    big = b"A" * 5000
    page = thin_vector_pages.Page()
    page.add_blit(big, 0, 0, 32, 32, cache).add_blit(big, 40, 0, 32, 32, cache)
    payload = page.encode()
    # Two 5KB blits, but the wire carries only hashes (~16 chars each).
    assert thin_vector_pages.wire_bytes(payload) < 1000
    assert cache.stats()["assets"] == 1  # dedup by content hash


# ---- local_asset_graphics ----


def _vault_and_template(tmp) -> tuple:
    vault = local_asset_graphics.AssetVault()
    hero = vault.add_bytes(b"hero-sprite-bytes")
    tree = vault.add_bytes(b"tree-sprite-bytes")
    tpl = {
        "name": "meadow",
        "sprites": {"hero": hero, "tree": tree},
        "layers": [
            {"sprite": "hero", "at": [10, 20]},
            {"sprite": "tree", "at": [0, 0], "when": "daytime"},
        ],
    }
    d = tmp / "tpl"
    d.mkdir()
    (d / "meadow.json").write_text(json.dumps(tpl), encoding="utf-8")
    return vault, str(d)


def test_local_graphics_compose_from_disk(tmp_path):
    vault, d = _vault_and_template(tmp_path)
    store = local_asset_graphics.TemplateStore()
    assert store.load_dir(d) == ["meadow"]
    tpl = store.get("meadow")
    placements, missing = local_asset_graphics.compose(tpl, {"daytime": True}, vault)
    assert missing == []
    assert {p["sprite"] for p in placements} == {"hero", "tree"}
    placements2, _ = local_asset_graphics.compose(tpl, {"daytime": False}, vault)
    assert {p["sprite"] for p in placements2} == {"hero"}  # conditional layer skipped


def test_local_graphics_missing_asset_flagged(tmp_path):
    vault, d = _vault_and_template(tmp_path)
    store = local_asset_graphics.TemplateStore()
    store.load_dir(d)
    tpl = dict(store.get("meadow"))
    tpl["sprites"] = dict(tpl["sprites"], ghost="deadbeefdeadbeef")
    tpl["layers"] = list(tpl["layers"]) + [{"sprite": "ghost", "at": [5, 5]}]
    empty_vault = local_asset_graphics.AssetVault()
    _, missing = local_asset_graphics.compose(tpl, {}, empty_vault)
    assert "deadbeefdeadbeef" in missing


def test_local_graphics_diff_apply_and_protocol():
    old = {"turn": 1, "x": 3, "dead": True}
    new = {"turn": 2, "x": 3, "alive": False}
    ops = local_asset_graphics.diff(old, new)
    assert ("set", "turn", "2") in ops
    assert ("del", "dead") in ops
    assert all(k != "x" for _, k, *_ in ops)  # unchanged keys produce no ops
    assert local_asset_graphics.apply(old, ops) == new
    p = local_asset_graphics.TurnProtocol
    msg = p.pack(7, "move", json.dumps({"x": 4}))
    assert p.unpack(msg) == (7, "move", json.dumps({"x": 4}))
    with pytest.raises(ValueError):
        p.unpack(b"garbage")
    with pytest.raises(ValueError):
        p.unpack(b"1|move|999|short")


# ---- web_clipping ----

_PAGE = """<html><head><title>Weather Report</title></head><body>
<h1>Today's Weather</h1>
<p>Sunny skies are expected across the region today with a gentle breeze from the west.</p>
<p>High: 72F, Low: 55F. Humidity: 40%.</p>
<nav><a href="/x">home</a><a href="/y">archive</a></nav>
</body></html>"""


def test_web_clip_extracts_title_summary():
    c = web_clipping.clip(_PAGE)
    assert c.title == "Weather Report"
    assert "Sunny skies" in c.summary
    assert c.bytes_out < c.bytes_in
    assert 0.0 < c.ratio < 1.0


def test_web_clip_facts_heuristic():
    c = web_clipping.clip(_PAGE)
    assert any("72F" in f for f in c.facts)
    # Title fallback when no <title>: first h1.
    c2 = web_clipping.clip(
        "<h1>Just A Heading</h1><p>Body text here is long enough.</p>"
    )
    assert c2.title == "Just A Heading"


def test_web_clip_empty_page():
    c = web_clipping.clip("")
    assert c.title == ""
    assert c.summary == ""
    assert c.facts == []
    assert c.ratio == 0.0


def test_web_clip_microapp_card():
    app = (
        web_clipping.MicroApp("weather")
        .add_field("high", r"High:\s*([0-9]+F)")
        .add_field("low", r"Low:\s*([0-9]+F)")
        .add_field("missing", r"Nope:\s*(.*)")
    )
    card = app.build(_PAGE)
    assert card["app"] == "weather"
    assert card["data"]["high"] == "72F"
    assert card["data"]["low"] == "55F"
    assert card["data"]["missing"] == ""
    assert card["bytes"] < len(_PAGE.encode("utf-8"))
