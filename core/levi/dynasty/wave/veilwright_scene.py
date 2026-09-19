# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Veilwright scene — VR hub first-room prototype, data model only.

Honest limits: this is a pure data model. There is NO hardware here —
no headset, no renderer, no tracking. Rooms are nodes, portals are
bidirectional edges, entities are named points on a 0..100 grid per
room. ``dump``/``load`` round-trip the whole scene as JSON-able data.

Three capabilities:

* **Scene graph** — :meth:`Scene.create_room`, :meth:`Scene.connect_rooms`
  (bidirectional, named portals), :meth:`Scene.place_entity`,
  :meth:`Scene.move_entity`. Movement is allowed only through a
  declared portal between the two rooms — otherwise
  :class:`MovementError`. Coordinates are enforced to 0..100.
* **Overlay layout profiles** — three built-ins (``compact``,
  ``full``, ``minimal``) declare control placements ``{control: (x,
  y)}``; :meth:`Scene.apply_layout` validates every placement is
  within 0..100 and that no two controls share a cell —
  :class:`LayoutError` otherwise. Custom layouts register through the
  same validation.
* **Scene serializer** — :meth:`Scene.dump` returns a JSON-able dict;
  :meth:`Scene.load` rebuilds and validates it, raising
  :class:`SceneError` on unknown room references or corrupt shape.

No network. No I/O unless the caller writes the dumped dict.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from levi.dynasty.dna import scrub_text


class SceneError(Exception):
    """The scene graph operation was refused."""


class MovementError(SceneError):
    """An entity move was refused (no portal between the rooms)."""


class LayoutError(SceneError):
    """An overlay layout was refused (bad placement or unknown profile)."""


def _clean(value: Any, what: str, err: type[Exception] = SceneError) -> str:
    if not isinstance(value, str) or not value.strip():
        raise err(f"{what} must be a non-empty string")
    return scrub_text(value.strip())


def _checked_xy(x: Any, y: Any, what: str) -> Tuple[float, float]:
    for label, coord in (("x", x), ("y", y)):
        if isinstance(coord, bool) or not isinstance(coord, (int, float)):
            raise SceneError(f"{what} {label} must be a number in 0..100")
        if not 0 <= coord <= 100:
            raise SceneError(f"{what} {label}={coord!r} out of bounds 0..100")
    return float(x), float(y)


def _checked_placements(
    placements: Any, layout_name: str
) -> Dict[str, Tuple[float, float]]:
    if not isinstance(placements, dict) or not placements:
        raise LayoutError(f"layout {layout_name!r} must be a non-empty dict")
    clean: Dict[str, Tuple[float, float]] = {}
    for control, pos in placements.items():
        if not isinstance(control, str) or not control.strip():
            raise LayoutError(f"layout {layout_name!r} has a non-string control")
        if not isinstance(pos, (list, tuple)) or len(pos) != 2:
            raise LayoutError(
                f"layout {layout_name!r} control {control!r} must be a (x, y) pair"
            )
        x, y = pos
        for label, coord in (("x", x), ("y", y)):
            if isinstance(coord, bool) or not isinstance(coord, (int, float)):
                raise LayoutError(
                    f"layout {layout_name!r} control {control!r} "
                    f"{label} must be a number in 0..100"
                )
            if not 0 <= coord <= 100:
                raise LayoutError(
                    f"layout {layout_name!r} control {control!r} "
                    f"{label}={coord!r} out of bounds 0..100"
                )
        clean[control.strip()] = (float(x), float(y))
    seen: Dict[Tuple[float, float], str] = {}
    for control, pos in clean.items():
        if pos in seen:
            raise LayoutError(
                f"layout {layout_name!r} controls {seen[pos]!r} and "
                f"{control!r} share cell {pos}"
            )
        seen[pos] = control
    return clean


# Three built-in overlay layout profiles: control -> (x, y) on a
# 0..100 grid. compact: one cluster; full: spread controls; minimal:
# two controls only.
BUILTIN_LAYOUTS: Dict[str, Dict[str, Tuple[float, float]]] = {
    "compact": {
        "launcher": (50.0, 88.0),
        "mic": (35.0, 88.0),
        "dismiss": (65.0, 88.0),
    },
    "full": {
        "launcher": (10.0, 90.0),
        "mic": (25.0, 90.0),
        "chat": (40.0, 90.0),
        "media": (55.0, 90.0),
        "settings": (70.0, 90.0),
        "dismiss": (90.0, 10.0),
    },
    "minimal": {
        "launcher": (50.0, 92.0),
        "dismiss": (90.0, 8.0),
    },
}


class Scene:
    """The hub's first room — rooms, portals, entities, overlay layout."""

    def __init__(self) -> None:
        self._rooms: Dict[str, Dict[str, str]] = {}  # room -> {portal: target}
        self._entities: Dict[str, Dict[str, Any]] = {}  # entity -> {room,x,y}
        self._layouts: Dict[str, Dict[str, Tuple[float, float]]] = {
            name: dict(placements) for name, placements in BUILTIN_LAYOUTS.items()
        }
        self._active_layout: Optional[str] = None

    # -- scene graph --------------------------------------------------
    def create_room(self, name: Any) -> str:
        """Create a room; duplicates raise :class:`SceneError`."""
        clean = _clean(name, "room name")
        if clean in self._rooms:
            raise SceneError(f"room {clean!r} already exists")
        self._rooms[clean] = {}
        return clean

    def connect_rooms(self, a: Any, b: Any, portal_name: Any) -> str:
        """Connect two rooms with a bidirectional named portal."""
        ra = _clean(a, "room a")
        rb = _clean(b, "room b")
        portal = _clean(portal_name, "portal name")
        for room in (ra, rb):
            if room not in self._rooms:
                raise SceneError(f"unknown room: {room!r}")
        if ra == rb:
            raise SceneError("cannot connect a room to itself")
        if portal in self._rooms[ra] or portal in self._rooms[rb]:
            raise SceneError(f"portal {portal!r} already declared on this route")
        self._rooms[ra][portal] = rb
        self._rooms[rb][portal] = ra
        return portal

    def portals(self, room: Any) -> Dict[str, str]:
        """Portal name -> target room for one room."""
        clean = _clean(room, "room name")
        if clean not in self._rooms:
            raise SceneError(f"unknown room: {clean!r}")
        return dict(self._rooms[clean])

    def place_entity(self, room: Any, entity: Any, x: Any, y: Any) -> Dict[str, Any]:
        """Place (or re-place) an entity at (x, y) in a room."""
        clean_room = _clean(room, "room name")
        if clean_room not in self._rooms:
            raise SceneError(f"unknown room: {clean_room!r}")
        clean_entity = _clean(entity, "entity name")
        px, py = _checked_xy(x, y, f"entity {clean_entity!r}")
        record = {"room": clean_room, "x": px, "y": py}
        self._entities[clean_entity] = record
        return dict(record)

    def move_entity(self, entity: Any, to_room: Any, x: Any, y: Any) -> Dict[str, Any]:
        """Move an entity — only through a declared portal.

        The entity's current room and ``to_room`` must share a portal
        edge; otherwise :class:`MovementError`. Bounds 0..100 enforced.
        """
        clean_entity = _clean(entity, "entity name")
        record = self._entities.get(clean_entity)
        if record is None:
            raise SceneError(f"unknown entity: {clean_entity!r}")
        dest = _clean(to_room, "destination room")
        if dest not in self._rooms:
            raise SceneError(f"unknown room: {dest!r}")
        px, py = _checked_xy(x, y, f"entity {clean_entity!r}")
        current = record["room"]
        if dest != current and dest not in self._rooms[current].values():
            raise MovementError(
                f"no portal from {current!r} to {dest!r}; "
                "declare one with connect_rooms first"
            )
        record["room"] = dest
        record["x"] = px
        record["y"] = py
        return dict(record)

    def where(self, entity: Any) -> Dict[str, Any]:
        """Current room + coordinates of an entity."""
        clean = _clean(entity, "entity name")
        record = self._entities.get(clean)
        if record is None:
            raise SceneError(f"unknown entity: {clean!r}")
        return dict(record)

    # -- overlay layouts ----------------------------------------------
    def register_layout(self, name: Any, placements: Any) -> str:
        """Register a custom layout through the same validation."""
        clean = _clean(name, "layout name", LayoutError)
        self._layouts[clean] = _checked_placements(placements, clean)
        return clean

    def apply_layout(self, name: Any) -> Dict[str, Tuple[float, float]]:
        """Activate a layout after validating its placements."""
        clean = _clean(name, "layout name", LayoutError)
        placements = self._layouts.get(clean)
        if placements is None:
            raise LayoutError(f"unknown layout: {clean!r}")
        validated = _checked_placements(
            {c: list(p) for c, p in placements.items()}, clean
        )
        self._layouts[clean] = validated
        self._active_layout = clean
        return dict(validated)

    @property
    def active_layout(self) -> Optional[str]:
        return self._active_layout

    @property
    def layout_names(self) -> List[str]:
        return sorted(self._layouts)

    # -- serializer ---------------------------------------------------
    def dump(self) -> Dict[str, Any]:
        """JSON-able snapshot of rooms, portals, entities, layout."""
        return {
            "rooms": {
                room: {"portals": dict(portals)}
                for room, portals in self._rooms.items()
            },
            "entities": {
                entity: dict(record) for entity, record in self._entities.items()
            },
            "layout": self._active_layout,
        }

    @classmethod
    def load(cls, data: Any) -> "Scene":
        """Rebuild a scene from :meth:`dump` output; validates strictly."""
        if not isinstance(data, dict):
            raise SceneError("scene data must be a dict")
        rooms = data.get("rooms")
        entities = data.get("entities")
        if not isinstance(rooms, dict):
            raise SceneError("scene data needs a 'rooms' object")
        if not isinstance(entities, dict):
            raise SceneError("scene data needs an 'entities' object")

        scene = cls()
        for name in rooms:
            scene.create_room(name)
        for name, spec in rooms.items():
            if not isinstance(spec, dict) or not isinstance(spec.get("portals"), dict):
                raise SceneError(f"room {name!r} has a corrupt portal map")
            for portal, target in spec["portals"].items():
                clean_target = _clean(target, "portal target")
                if clean_target not in scene._rooms:
                    raise SceneError(
                        f"portal {portal!r} of room {name!r} "
                        f"points at unknown room {clean_target!r}"
                    )
        # Wire portals exactly as dumped (dump is bidirectional).
        wired: set[Tuple[str, str]] = set()
        for name, spec in rooms.items():
            for portal, target in spec["portals"].items():
                key = tuple(sorted((name, target)))
                if key in wired:
                    continue
                wired.add(key)
                scene.connect_rooms(name, target, portal)
        for entity, record in entities.items():
            if not isinstance(record, dict):
                raise SceneError(f"entity {entity!r} has a corrupt record")
            room = record.get("room")
            clean_room = _clean(room, "entity room")
            if clean_room not in scene._rooms:
                raise SceneError(f"entity {entity!r} is in unknown room {clean_room!r}")
            scene.place_entity(clean_room, entity, record.get("x"), record.get("y"))

        layout = data.get("layout")
        if layout is not None:
            scene.apply_layout(layout)
        return scene
