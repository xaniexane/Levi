"""Text virtual world as a shared database players edit together.

Studied from: dead-game-genres-2026-09-16 / report.md [Entries — MUD1]
(persistent shared text world via shared writable memory IPC; user-extensible
content via MUDDL; the world as a database players edit together).

This is an original, from-scratch implementation for LEVI. ``WorldDB`` is the
shared writable store: rooms with named exits, objects with attribute bags,
and players with locations and inventories. Players extend the world with a
tiny content-definition language — ``ContentScript`` parses lines like::

    room hall "The Grand Hall"
    exit hall north to courtyard
    object lamp in hall name "Brass Lamp" desc "It glows faintly."
    attr lamp fuel = 7

``apply(script)`` runs a script and reports per-line results, so builders see
exactly which lines landed and which failed. The whole database serializes to
JSON for persistence (``save``/``load``): the world survives restarts because
it is a database, not a program.

Public surface:
- ``WorldDB``: ``add_room``, ``add_exit``, ``add_object``, ``set_attr``,
  ``move_player``, ``take``, ``drop``, ``look(room_id)``, ``rooms()``,
  ``objects_in(room_id)``, ``apply(script)``, ``save(path)``, ``load(path)``.
- ``ContentScript``: ``parse(text)`` -> list of ``Directive``; the
  ``directives`` are plain data — the DB executes them.
- ``Directive``: frozen ``(verb, args)`` record.
- ``ScriptResult``: per-line ``(line_no, ok, message)`` records.
- ``WorldDbError`` for violations.

Honest limits: content is data, not code — there is no scripting or verb
execution engine here, only declarative world-building. Attribute values are
JSON-safe scalars. Concurrency is single-process; "shared writable memory" is
modeled as one in-process store.

stdlib-only. No network.
"""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


ORIGIN = "levi-revival/text_world_db"


class WorldDbError(ValueError):
    """Raised when world-database rules are violated."""


@dataclass(frozen=True)
class Directive:
    """One parsed content-language line: a verb and its string arguments."""

    verb: str
    args: Tuple[str, ...]
    line_no: int


@dataclass(frozen=True)
class ScriptResult:
    """Outcome of executing one script line."""

    line_no: int
    ok: bool
    message: str


class ContentScript:
    """Parser for the tiny content-definition language.

    Grammar (one directive per line, ``#`` starts a comment):
      room <id> "<description>"
      exit <room> <direction> to <room>
      object <id> in <room> name "<name>" desc "<description>"
      attr <object> <key> = <value>
      spawn <player> in <room>
    Quoting follows shell rules via ``shlex``. Parsing never touches the
    database — it only produces ``Directive`` records.
    """

    @staticmethod
    def parse(text: str) -> List[Directive]:
        directives: List[Directive] = []
        for line_no, raw in enumerate(text.splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                tokens = shlex.split(line)
            except ValueError as exc:
                raise WorldDbError(f"line {line_no}: cannot tokenize: {exc}") from None
            if not tokens:
                continue
            directives.append(
                Directive(
                    verb=tokens[0].lower(), args=tuple(tokens[1:]), line_no=line_no
                )
            )
        return directives


class WorldDB:
    """The shared writable world: rooms, objects, players."""

    def __init__(self) -> None:
        self._rooms: Dict[str, Dict[str, Any]] = {}
        self._objects: Dict[str, Dict[str, Any]] = {}
        self._players: Dict[str, Dict[str, Any]] = {}

    # -- rooms ------------------------------------------------------------
    def add_room(self, room_id: str, description: str = "") -> None:
        if not room_id:
            raise WorldDbError("room_id must be non-empty")
        if room_id in self._rooms:
            raise WorldDbError(f"room already exists: {room_id!r}")
        self._rooms[room_id] = {"description": description, "exits": {}}

    def add_exit(self, room_id: str, direction: str, target: str) -> None:
        room = self._room(room_id)
        if target not in self._rooms:
            raise WorldDbError(f"exit target unknown: {target!r}")
        room["exits"][direction] = target

    def rooms(self) -> List[str]:
        return sorted(self._rooms)

    def look(self, room_id: str) -> str:
        """Human-readable description of a room: text, exits, contents."""
        room = self._room(room_id)
        lines = [room["description"] or room_id]
        exits = room["exits"]
        lines.append("Exits: " + (", ".join(sorted(exits)) if exits else "none"))
        contents = self.objects_in(room_id)
        lines.append("Here: " + (", ".join(contents) if contents else "nothing"))
        return "\n".join(lines)

    # -- objects ----------------------------------------------------------
    def add_object(
        self, object_id: str, room_id: str, name: str = "", description: str = ""
    ) -> None:
        if not object_id:
            raise WorldDbError("object_id must be non-empty")
        if object_id in self._objects:
            raise WorldDbError(f"object already exists: {object_id!r}")
        self._room(room_id)  # validate
        self._objects[object_id] = {
            "room": room_id,
            "name": name or object_id,
            "description": description,
            "attrs": {},
            "holder": None,
        }

    def set_attr(self, object_id: str, key: str, value: Any) -> None:
        obj = self._object(object_id)
        json.dumps(value)  # attrs must stay JSON-safe for persistence
        obj["attrs"][key] = value

    def get_attr(self, object_id: str, key: str, default: Any = None) -> Any:
        return self._object(object_id)["attrs"].get(key, default)

    def objects_in(self, room_id: str) -> List[str]:
        self._room(room_id)
        return sorted(
            oid
            for oid, obj in self._objects.items()
            if obj["room"] == room_id and obj["holder"] is None
        )

    # -- players ----------------------------------------------------------
    def spawn_player(self, name: str, room_id: str) -> None:
        if not name:
            raise WorldDbError("player name must be non-empty")
        if name in self._players:
            raise WorldDbError(f"player already exists: {name!r}")
        self._room(room_id)
        self._players[name] = {"room": room_id, "inventory": []}

    def move_player(self, name: str, direction: str) -> str:
        """Walk through an exit. Returns the new room id."""
        player = self._player(name)
        room = self._room(player["room"])
        if direction not in room["exits"]:
            raise WorldDbError(f"no exit {direction!r} from {player['room']!r}")
        player["room"] = room["exits"][direction]
        return player["room"]

    def take(self, name: str, object_id: str) -> None:
        player = self._player(name)
        obj = self._object(object_id)
        if obj["holder"] is not None or obj["room"] != player["room"]:
            raise WorldDbError(f"{object_id!r} is not here")
        obj["holder"] = name
        player["inventory"].append(object_id)

    def drop(self, name: str, object_id: str) -> None:
        player = self._player(name)
        obj = self._object(object_id)
        if obj["holder"] != name:
            raise WorldDbError(f"{name} is not holding {object_id!r}")
        obj["holder"] = None
        obj["room"] = player["room"]
        player["inventory"].remove(object_id)

    def inventory(self, name: str) -> List[str]:
        return list(self._player(name)["inventory"])

    def where(self, name: str) -> str:
        return self._player(name)["room"]

    # -- content language --------------------------------------------------
    def apply(self, text: str) -> List[ScriptResult]:
        """Parse and execute a content script; report per-line outcomes.

        Lines are executed in order; a failing line is reported and skipped,
        and later lines still run.
        """
        results: List[ScriptResult] = []
        for directive in ContentScript.parse(text):
            try:
                message = self._execute(directive)
                results.append(ScriptResult(directive.line_no, True, message))
            except WorldDbError as exc:
                results.append(ScriptResult(directive.line_no, False, str(exc)))
        return results

    def _execute(self, directive: Directive) -> str:
        verb, args = directive.verb, directive.args
        if verb == "room":
            if len(args) < 1:
                raise WorldDbError("room needs an id")
            self.add_room(args[0], args[1] if len(args) > 1 else "")
            return f"room {args[0]!r} created"
        if verb == "exit":
            if len(args) != 4 or args[2] != "to":
                raise WorldDbError("usage: exit <room> <direction> to <room>")
            self.add_exit(args[0], args[1], args[3])
            return f"exit {args[1]!r} from {args[0]!r} to {args[3]!r}"
        if verb == "object":
            # object <id> in <room> name "<name>" desc "<description>"
            if len(args) < 3 or args[1] != "in":
                raise WorldDbError("usage: object <id> in <room> [name ..] [desc ..]")
            name, desc = "", ""
            rest = list(args[3:])
            while rest:
                key = rest.pop(0)
                if key == "name" and rest:
                    name = rest.pop(0)
                elif key == "desc" and rest:
                    desc = rest.pop(0)
                else:
                    raise WorldDbError(f"unknown object option: {key!r}")
            self.add_object(args[0], args[2], name, desc)
            return f"object {args[0]!r} placed in {args[2]!r}"
        if verb == "attr":
            if len(args) != 4 or args[2] != "=":
                raise WorldDbError("usage: attr <object> <key> = <value>")
            self.set_attr(args[0], args[1], _coerce(args[3]))
            return f"{args[0]}.{args[1]} = {args[3]}"
        if verb == "spawn":
            if len(args) != 3 or args[1] != "in":
                raise WorldDbError("usage: spawn <player> in <room>")
            self.spawn_player(args[0], args[2])
            return f"player {args[0]!r} spawned in {args[2]!r}"
        raise WorldDbError(f"unknown directive: {verb!r}")

    # -- persistence -------------------------------------------------------
    def save(self, path: str) -> None:
        """Persist the whole world database to a JSON file."""
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "rooms": self._rooms,
                    "objects": self._objects,
                    "players": self._players,
                },
                fh,
                indent=2,
                sort_keys=True,
            )

    @classmethod
    def load(cls, path: str) -> "WorldDB":
        """Restore a world database saved with ``save``."""
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        db = cls()
        db._rooms = raw.get("rooms", {})
        db._objects = raw.get("objects", {})
        db._players = raw.get("players", {})
        return db

    # -- internals ---------------------------------------------------------
    def _room(self, room_id: str) -> Dict[str, Any]:
        try:
            return self._rooms[room_id]
        except KeyError:
            raise WorldDbError(f"unknown room: {room_id!r}") from None

    def _object(self, object_id: str) -> Dict[str, Any]:
        try:
            return self._objects[object_id]
        except KeyError:
            raise WorldDbError(f"unknown object: {object_id!r}") from None

    def _player(self, name: str) -> Dict[str, Any]:
        try:
            return self._players[name]
        except KeyError:
            raise WorldDbError(f"unknown player: {name!r}") from None


def _coerce(text: str) -> Any:
    """Best-effort scalar coercion for ``attr`` values: int, float, else str."""
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    return text
