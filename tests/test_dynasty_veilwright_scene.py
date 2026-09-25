# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Veilwright scene — VR scene graph, overlay layouts, serializer.

Hermetic: pure in-memory data model, no hardware, no network, no I/O.
"""

from __future__ import annotations

import pytest

from levi.dynasty.wave.veilwright_scene import (
    BUILTIN_LAYOUTS,
    LayoutError,
    MovementError,
    Scene,
    SceneError,
)


@pytest.fixture
def scene():
    return Scene()


def _two_room(scene):
    scene.create_room("hub")
    scene.create_room("den")
    scene.connect_rooms("hub", "den", "archway")
    return scene


# -- scene graph: happy path ------------------------------------------


def test_create_room_and_portals(scene):
    assert scene.create_room("hub") == "hub"
    assert scene.create_room("den") == "den"
    scene.connect_rooms("hub", "den", "archway")
    assert scene.portals("hub") == {"archway": "den"}
    assert scene.portals("den") == {"archway": "hub"}  # bidirectional


def test_place_and_move_through_portal(scene):
    _two_room(scene)
    record = scene.place_entity("hub", "orb", 10, 20)
    assert record == {"room": "hub", "x": 10.0, "y": 20.0}
    moved = scene.move_entity("orb", "den", 30, 40)
    assert moved["room"] == "den"
    assert (moved["x"], moved["y"]) == (30.0, 40.0)
    assert scene.where("orb")["room"] == "den"


def test_move_within_same_room_needs_no_portal(scene):
    scene.create_room("hub")
    scene.place_entity("hub", "orb", 10, 20)
    moved = scene.move_entity("orb", "hub", 50, 60)
    assert moved["room"] == "hub"


def test_bounds_edges_allowed(scene):
    scene.create_room("hub")
    scene.place_entity("hub", "corner", 0, 100)
    scene.place_entity("hub", "other", 100, 0)
    assert scene.where("corner") == {"room": "hub", "x": 0.0, "y": 100.0}


# -- scene graph: adversarial -----------------------------------------


def test_move_without_portal_refused(scene):
    scene.create_room("hub")
    scene.create_room("vault")
    scene.place_entity("hub", "orb", 10, 20)
    with pytest.raises(MovementError):
        scene.move_entity("orb", "vault", 30, 40)
    # the entity did not move
    assert scene.where("orb")["room"] == "hub"


def test_movement_error_is_a_scene_error(scene):
    _two_room(scene)
    scene.create_room("vault")
    scene.place_entity("hub", "orb", 1, 2)
    with pytest.raises(SceneError):
        scene.move_entity("orb", "vault", 1, 2)


def test_out_of_bounds_refused(scene):
    scene.create_room("hub")
    for bad in ((-1, 50), (50, 101), (100.5, 50), (50, -0.1)):
        with pytest.raises(SceneError):
            scene.place_entity("hub", "orb", *bad)
    with pytest.raises(SceneError):
        scene.place_entity("hub", "orb", "left", 50)
    with pytest.raises(SceneError):
        scene.place_entity("hub", "orb", True, 50)


def test_duplicate_room_and_bad_connects_refused(scene):
    scene.create_room("hub")
    with pytest.raises(SceneError):
        scene.create_room("hub")
    with pytest.raises(SceneError):
        scene.create_room("")
    with pytest.raises(SceneError):
        scene.connect_rooms("hub", "missing", "door")
    with pytest.raises(SceneError):
        scene.connect_rooms("missing", "hub", "door")
    with pytest.raises(SceneError):
        scene.connect_rooms("hub", "hub", "mirror")
    scene.create_room("den")
    scene.connect_rooms("hub", "den", "archway")
    with pytest.raises(SceneError):
        scene.connect_rooms("hub", "den", "archway")  # duplicate portal


def test_unknown_entity_and_room_refused(scene):
    scene.create_room("hub")
    with pytest.raises(SceneError):
        scene.place_entity("missing", "orb", 1, 2)
    with pytest.raises(SceneError):
        scene.move_entity("ghost", "hub", 1, 2)
    with pytest.raises(SceneError):
        scene.place_entity("hub", "orb", 1, 2)
        scene.move_entity("orb", "missing", 1, 2)
    with pytest.raises(SceneError):
        scene.where("ghost")
    with pytest.raises(SceneError):
        scene.portals("missing")


def test_move_enforces_bounds(scene):
    _two_room(scene)
    scene.place_entity("hub", "orb", 10, 20)
    with pytest.raises(SceneError):
        scene.move_entity("orb", "den", 200, 20)
    assert scene.where("orb")["room"] == "hub"


# -- overlay layouts ---------------------------------------------------


def test_builtin_layouts_all_apply_clean(scene):
    assert set(BUILTIN_LAYOUTS) == {"compact", "full", "minimal"}
    for name in ("compact", "full", "minimal"):
        applied = scene.apply_layout(name)
        assert scene.active_layout == name
        for control, (x, y) in applied.items():
            assert isinstance(control, str)
            assert 0 <= x <= 100
            assert 0 <= y <= 100


def test_builtin_layouts_have_no_shared_cells():
    for name, placements in BUILTIN_LAYOUTS.items():
        cells = list(placements.values())
        assert len(cells) == len(set(cells)), name


def test_custom_layout_registers_and_applies(scene):
    scene.register_layout("wide", {"launcher": (5, 95), "dismiss": (95, 5)})
    assert "wide" in scene.layout_names
    applied = scene.apply_layout("wide")
    assert applied == {"launcher": (5.0, 95.0), "dismiss": (95.0, 5.0)}
    assert scene.active_layout == "wide"


def test_overlapping_controls_refused(scene):
    with pytest.raises(LayoutError):
        scene.register_layout("clash", {"a": (10, 10), "b": (10, 10)})
    # built-in rejected if tampered into a clash: re-validate path
    scene.apply_layout("compact")  # sanity: still fine before tampering
    scene._layouts["compact"]["launcher"] = (35.0, 88.0)  # collide w/ mic
    with pytest.raises(LayoutError):
        scene.apply_layout("compact")


def test_out_of_bounds_placement_refused(scene):
    with pytest.raises(LayoutError):
        scene.register_layout("off", {"launcher": (101, 50)})
    with pytest.raises(LayoutError):
        scene.register_layout("off", {"launcher": (-1, 50)})
    with pytest.raises(LayoutError):
        scene.register_layout("off", {"launcher": ("x", 50)})


def test_unknown_layout_refused(scene):
    with pytest.raises(LayoutError):
        scene.apply_layout("nope")


def test_malformed_layout_refused(scene):
    with pytest.raises(LayoutError):
        scene.register_layout("bad", {})
    with pytest.raises(LayoutError):
        scene.register_layout("bad", {"launcher": (1, 2, 3)})
    with pytest.raises(LayoutError):
        scene.register_layout("bad", {123: (1, 2)})
    with pytest.raises(LayoutError):
        scene.register_layout("", {"launcher": (1, 2)})


# -- serializer --------------------------------------------------------


def test_dump_load_round_trip(scene):
    _two_room(scene)
    scene.place_entity("hub", "orb", 10, 20)
    scene.place_entity("den", "lamp", 70, 80)
    scene.apply_layout("full")

    data = scene.dump()
    import json

    json.dumps(data)  # must be JSON-able

    rebuilt = Scene.load(data)
    assert rebuilt.where("orb") == {"room": "hub", "x": 10.0, "y": 20.0}
    assert rebuilt.where("lamp") == {"room": "den", "x": 70.0, "y": 80.0}
    assert rebuilt.portals("hub") == {"archway": "den"}
    assert rebuilt.portals("den") == {"archway": "hub"}
    assert rebuilt.active_layout == "full"
    # rebuilt scene moves work through the restored portal
    rebuilt.move_entity("orb", "den", 1, 1)
    assert rebuilt.where("orb")["room"] == "den"


def test_load_without_layout_ok(scene):
    scene.create_room("hub")
    rebuilt = Scene.load(scene.dump())
    assert rebuilt.active_layout is None
    assert rebuilt.portals("hub") == {}


def test_load_unknown_room_refs_refused():
    with pytest.raises(SceneError):
        Scene.load(
            {
                "rooms": {"hub": {"portals": {"door": "nowhere"}}},
                "entities": {},
                "layout": None,
            }
        )
    with pytest.raises(SceneError):
        Scene.load(
            {
                "rooms": {"hub": {"portals": {}}},
                "entities": {"ghost": {"room": "nowhere", "x": 1, "y": 2}},
                "layout": None,
            }
        )


def test_load_malformed_data_refused():
    with pytest.raises(SceneError):
        Scene.load("not a dict")
    with pytest.raises(SceneError):
        Scene.load({"entities": {}})
    with pytest.raises(SceneError):
        Scene.load({"rooms": {}})
    with pytest.raises(SceneError):
        Scene.load(
            {
                "rooms": {"hub": {"portals": "nope"}},
                "entities": {},
                "layout": None,
            }
        )
    with pytest.raises(SceneError):
        Scene.load(
            {
                "rooms": {"hub": {"portals": {}}},
                "entities": {},
                "layout": "nope",
            }
        )


def test_load_rejects_out_of_bounds_entity():
    with pytest.raises(SceneError):
        Scene.load(
            {
                "rooms": {"hub": {"portals": {}}},
                "entities": {"orb": {"room": "hub", "x": 999, "y": 1}},
                "layout": None,
            }
        )
