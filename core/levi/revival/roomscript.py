"""roomscript — user-hosted programmable spaces: the Palace.

Studied from: revival-50-more-20260916-0009/report-part1.md (Section 21).

Load-bearing idea: spatial rooms on a 2-D grid with avatars and props;
rooms run small scripts in a tiny original scripting dialect
(on-enter / on-say triggers, do-actions); a room is data + script, fully
serializable, so anyone can host one.

LEVI's take: ``Room`` holds a grid, ``Avatar``s, ``Prop``s, and a list
of ``Rule``s parsed from the roomscript dialect::

    on enter: say "Welcome, {name}!"
    on say hello: say "Hey there, {name}."
    on say /dance/: emote "does a little jig"
    on enter: move 2 1

Triggers: ``enter``, ``say <literal>``, ``say /<regex>/``. Actions:
``say <text>``, ``emote <text>``, ``move <dx> <dy>``. ``{name}`` and
``{said}`` template into text. ``to_dict``/``from_dict`` round-trip the
whole room — script included — so rooms travel as plain data.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List


ORIGIN = "levi-revival/roomscript"


class RoomScriptError(Exception):
    """A roomscript line wouldn't parse, or a rule misfired."""


# ---------------------------------------------------------------------------
# Pieces
# ---------------------------------------------------------------------------


@dataclass
class Avatar:
    name: str
    x: int
    y: int


@dataclass
class Prop:
    name: str
    x: int
    y: int
    description: str = ""


@dataclass
class Rule:
    trigger_kind: str  # "enter" | "say"
    trigger_arg: str  # "" | literal | "/regex/"
    action: str  # "say" | "emote" | "move"
    action_arg: str

    def fires_on_enter(self) -> bool:
        return self.trigger_kind == "enter"

    def fires_on_say(self, text: str) -> bool:
        if self.trigger_kind != "say":
            return False
        arg = self.trigger_arg
        if arg.startswith("/") and arg.endswith("/") and len(arg) >= 2:
            return re.search(arg[1:-1], text, re.IGNORECASE) is not None
        return arg.lower() in text.lower()


# ---------------------------------------------------------------------------
# The dialect
# ---------------------------------------------------------------------------

_RULE_RE = re.compile(
    r"^\s*on\s+(enter|say(?:\s+(.*))?)\s*:\s*(say|emote|move)\s*(.*)$", re.IGNORECASE
)


def parse_script(source: str) -> List[Rule]:
    """Parse roomscript source into rules. Blank lines and # comments skipped."""
    rules: List[Rule] = []
    for lineno, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _RULE_RE.match(line)
        if not m:
            raise RoomScriptError(f"line {lineno}: cannot parse {raw!r}")
        trigger, arg, action, action_arg = (
            m.group(1).lower(),
            (m.group(2) or "").strip(),
            m.group(3).lower(),
            m.group(4).strip(),
        )
        trigger_kind = "enter" if trigger == "enter" else "say"
        if action == "move":
            parts = action_arg.split()
            if len(parts) != 2:
                raise RoomScriptError(
                    f"line {lineno}: move needs dx dy, got {action_arg!r}"
                )
            try:
                int(parts[0]), int(parts[1])
            except ValueError:
                raise RoomScriptError(
                    f"line {lineno}: move args must be ints"
                ) from None
        rules.append(Rule(trigger_kind, arg, action, action_arg))
    return rules


# ---------------------------------------------------------------------------
# Room
# ---------------------------------------------------------------------------


@dataclass
class RoomEvent:
    kind: str  # "say" | "emote" | "move" | "enter" | "leave"
    actor: str
    text: str


class Room:
    """A hostable 2-D room: grid, avatars, props, and a running script."""

    def __init__(
        self,
        name: str,
        width: int = 10,
        height: int = 10,
        script: str = "",
    ) -> None:
        self.name = name
        self.width = width
        self.height = height
        self.script_source = script
        self.rules: List[Rule] = parse_script(script)
        self.avatars: Dict[str, Avatar] = {}
        self.props: Dict[str, Prop] = {}
        self.log: List[RoomEvent] = []

    # -- hosting ----------------------------------------------------------

    def enter(self, name: str, x: int = 0, y: int = 0) -> List[RoomEvent]:
        """An avatar walks in. on-enter rules fire."""
        if name in self.avatars:
            raise RoomScriptError(f"{name!r} is already in the room")
        self.avatars[name] = Avatar(
            name, self._clamp(x, self.width), self._clamp(y, self.height)
        )
        self.log.append(RoomEvent("enter", name, f"{name} enters {self.name}"))
        return self._fire_enter(name)

    def leave(self, name: str) -> None:
        self._avatar(name)
        del self.avatars[name]
        self.log.append(RoomEvent("leave", name, f"{name} leaves"))

    def say(self, name: str, text: str) -> List[RoomEvent]:
        """An avatar speaks. on-say rules fire; the speech itself is logged."""
        avatar = self._avatar(name)
        self.log.append(RoomEvent("say", name, text))
        fired: List[RoomEvent] = []
        for rule in self.rules:
            if rule.fires_on_say(text):
                fired.extend(self._run(rule, avatar, said=text))
        return fired

    def move(self, name: str, dx: int, dy: int) -> RoomEvent:
        avatar = self._avatar(name)
        avatar.x = self._clamp(avatar.x + dx, self.width)
        avatar.y = self._clamp(avatar.y + dy, self.height)
        ev = RoomEvent("move", name, f"{name} moves to ({avatar.x}, {avatar.y})")
        self.log.append(ev)
        return ev

    def place_prop(self, prop: Prop) -> None:
        self.props[prop.name] = prop

    # -- the engine ----------------------------------------------------------

    def _fire_enter(self, name: str) -> List[RoomEvent]:
        avatar = self.avatars[name]
        fired: List[RoomEvent] = []
        for rule in self.rules:
            if rule.fires_on_enter():
                fired.extend(self._run(rule, avatar, said=""))
        return fired

    def _run(self, rule: Rule, avatar: Avatar, said: str) -> List[RoomEvent]:
        text = rule.action_arg.replace("{name}", avatar.name).replace("{said}", said)
        if rule.action == "say":
            ev = RoomEvent("say", "room", text)
        elif rule.action == "emote":
            ev = RoomEvent("emote", avatar.name, f"{avatar.name} {text}")
        elif rule.action == "move":
            dx, dy = (int(p) for p in rule.action_arg.split())
            avatar.x = self._clamp(avatar.x + dx, self.width)
            avatar.y = self._clamp(avatar.y + dy, self.height)
            ev = RoomEvent(
                "move", avatar.name, f"{avatar.name} moves to ({avatar.x}, {avatar.y})"
            )
        else:  # pragma: no cover — parser only emits the three actions
            raise RoomScriptError(f"unknown action {rule.action!r}")
        self.log.append(ev)
        return [ev]

    # -- serialization: room = data + script ---------------------------------

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "script": self.script_source,
            "avatars": {n: {"x": a.x, "y": a.y} for n, a in self.avatars.items()},
            "props": {
                n: {"x": p.x, "y": p.y, "description": p.description}
                for n, p in self.props.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Room":
        room = cls(
            name=data["name"],
            width=data.get("width", 10),
            height=data.get("height", 10),
            script=data.get("script", ""),
        )
        for n, a in data.get("avatars", {}).items():
            room.avatars[n] = Avatar(n, a["x"], a["y"])
        for n, p in data.get("props", {}).items():
            room.props[n] = Prop(n, p["x"], p["y"], p.get("description", ""))
        return room

    # -- internals ------------------------------------------------------------

    def _avatar(self, name: str) -> Avatar:
        try:
            return self.avatars[name]
        except KeyError:
            raise RoomScriptError(f"{name!r} is not in the room") from None

    @staticmethod
    def _clamp(v: int, hi: int) -> int:
        return max(0, min(hi - 1, v))
