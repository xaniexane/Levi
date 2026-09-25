"""Point-and-click adventure scripting engine; content arrives as data.

Studied from: dead-game-genres-2026-09-16/report.md [Entries - Point-and-Click Adventures]
(the genre's engine-side shape: rooms as state machines, a fixed verb list,
inventory logic, dialogue trees, cutscene scripting; engine reusable across
games while the content ships as data).

This is an original, from-scratch implementation for LEVI. A ``Game`` is built
from plain dicts: rooms (exits, objects, background state), objects (verbs
mapped to scripted effects), items, dialogue trees, and cutscenes. The engine
executes player commands of the form ``(verb, target, indirect)`` against the
current room, mutating world state, and can run cutscenes (ordered command
lists with timed waits) that temporarily lock player input. The built-in demo
game ("The Rusty Lantern") is a three-room micro-adventure proving the engine.

Public surface:
- ``build_game(data)`` -> ``Game``: validate and load content dicts.
- ``Game.command(verb, target, indirect=None)`` -> list of ``Event`` lines.
- ``Game.start_cutscene(name)`` / ``Game.advance_cutscene()``: scripted
  sequences; player commands are rejected while a cutscene is playing.
- ``Game.save()`` / ``Game.load(state)``: JSON-serializable snapshots.
- ``demo_game()``: the built-in micro-adventure as data.

Verb list is deliberately small (walk, look, take, use, talk, give, push,
open, close) and enforced: unknown verbs are rejected, which keeps every
game's parser behavior predictable.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

ORIGIN = "levi-revival/scumm"

VERBS = ("walk", "look", "take", "use", "talk", "give", "push", "open", "close")

# ---------------------------------------------------------------------------
# Data model (content as data)
# ---------------------------------------------------------------------------


@dataclass
class GameObject:
    name: str
    room: str
    description: str
    takeable: bool = False
    # verb -> script: list of effect dicts
    scripts: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    state: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DialogueNode:
    text: str
    # choice label -> next node id
    choices: Dict[str, str] = field(default_factory=dict)
    # effect dicts applied when the node is shown
    effects: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Game:
    rooms: Dict[str, Dict[str, Any]]
    objects: Dict[str, GameObject]
    dialogues: Dict[str, DialogueNode]
    cutscenes: Dict[str, List[Dict[str, Any]]]
    start_room: str
    # -- runtime state ------------------------------------------------------
    current_room: str = ""
    inventory: List[str] = field(default_factory=list)
    flags: Dict[str, Any] = field(default_factory=dict)
    log: List[str] = field(default_factory=list)
    active_cutscene: Optional[str] = None
    cutscene_step: int = 0

    def __post_init__(self) -> None:
        if not self.current_room:
            self.current_room = self.start_room

    # -- queries ------------------------------------------------------------
    def room_objects(self) -> List[GameObject]:
        return [o for o in self.objects.values() if o.room == self.current_room]

    def exits(self) -> Dict[str, str]:
        return dict(self.rooms[self.current_room].get("exits", {}))

    # -- commands -------------------------------------------------------------
    def command(
        self, verb: str, target: str, indirect: Optional[str] = None
    ) -> List[str]:
        """Run one player command; returns the event lines it produced."""
        verb = verb.lower().strip()
        target = target.lower().strip()
        if self.active_cutscene:
            return ["(a cutscene is playing - wait for it to finish)"]
        if verb not in VERBS:
            return [f"'{verb}' is not a verb I understand."]
        handler = getattr(self, f"_do_{verb}")
        return handler(target, indirect.lower().strip() if indirect else None)

    def _do_walk(self, target: Optional[str], _ind: Optional[str]) -> List[str]:
        exits = self.exits()
        if target in exits:
            dest = exits[target]
            room = self.rooms[dest]
            if room.get("locked"):
                need = room.get("locked_by", "something")
                return [f"The way to {target} is locked ({need})."]
            self.current_room = dest
            events = [f"You go to {target}."]
            events.extend(self._run_script(self.rooms[dest].get("on_enter", [])))
            return events
        return [f"You can't get to '{target}' from here."]

    def _do_look(self, target: Optional[str], _ind: Optional[str]) -> List[str]:
        if not target:
            room = self.rooms[self.current_room]
            objs = ", ".join(o.name for o in self.room_objects()) or "nothing of note"
            return [room["description"], f"You see: {objs}."]
        obj = self._find(target)
        if obj is None:
            return [f"You don't see any '{target}' here."]
        return [obj.description] + self._run_script(obj.scripts.get("look", []))

    def _do_take(self, target: str, _ind: Optional[str]) -> List[str]:
        obj = self._find(target)
        if obj is None:
            return [f"There's no '{target}' here to take."]
        if not obj.takeable:
            return [f"You can't take the {obj.name}."]
        obj.room = "__inventory__"
        self.inventory.append(obj.name)
        return [f"You take the {obj.name}."] + self._run_script(
            obj.scripts.get("take", [])
        )

    def _do_use(self, target: str, indirect: Optional[str]) -> List[str]:
        obj = self._find_anywhere(target)
        if obj is None:
            return [f"You don't have '{target}'."]
        if indirect:
            tgt2 = self._find(indirect)
            key = f"use:{indirect}"
            if tgt2 is None and key not in obj.scripts:
                return [f"You don't see any '{indirect}' here."]
        else:
            key = "use"
        script = obj.scripts.get(key, obj.scripts.get("use", []))
        if not script:
            return [f"Using the {obj.name} accomplishes nothing."]
        return [
            f"You use the {obj.name}" + (f" on the {indirect}." if indirect else ".")
        ] + self._run_script(script)

    def _do_talk(self, target: str, _ind: Optional[str]) -> List[str]:
        obj = self._find(target)
        if obj is None:
            return [f"There's no one called '{target}' here."]
        if obj.state.get("dialogue"):
            self.flags["__dialogue_node__"] = obj.state["dialogue"]
            return self._show_dialogue(obj.state["dialogue"])
        return [f"The {obj.name} has nothing to say."] + self._run_script(
            obj.scripts.get("talk", [])
        )

    def _do_give(self, target: str, indirect: Optional[str]) -> List[str]:
        if target not in self.inventory:
            return [f"You don't have a {target}."]
        npc = self._find(indirect or "")
        if npc is None:
            return ["Give it to whom?"]
        key = f"give:{target}"
        script = npc.scripts.get(key, [])
        if not script:
            return [f"The {npc.name} doesn't want your {target}."]
        self.inventory.remove(target)
        self.objects[target].room = "__gone__"
        return [f"You give the {target} to the {npc.name}."] + self._run_script(script)

    def _do_push(self, target: str, _ind: Optional[str]) -> List[str]:
        obj = self._find(target)
        if obj is None:
            return [f"There's no '{target}' here to push."]
        return [f"You push the {obj.name}."] + self._run_script(
            obj.scripts.get("push", [])
        )

    def _do_open(self, target: str, _ind: Optional[str]) -> List[str]:
        obj = self._find(target)
        if obj is None:
            return [f"There's no '{target}' here to open."]
        return [f"You open the {obj.name}."] + self._run_script(
            obj.scripts.get("open", [])
        )

    def _do_close(self, target: str, _ind: Optional[str]) -> List[str]:
        obj = self._find(target)
        if obj is None:
            return [f"There's no '{target}' here to close."]
        return [f"You close the {obj.name}."] + self._run_script(
            obj.scripts.get("close", [])
        )

    # -- dialogue ---------------------------------------------------------------
    def _show_dialogue(self, node_id: str) -> List[str]:
        node = self.dialogues[node_id]
        self.flags["__dialogue_node__"] = node_id
        events = self._run_script(node.effects)
        lines = [f">> {node.text}"] + events
        if node.choices:
            lines.append("Choices: " + " / ".join(node.choices))
        else:
            lines.append("(the conversation ends)")
        return lines

    def choose(self, label: str) -> List[str]:
        """Pick a dialogue choice from the most recently shown node."""
        # find the last shown node with choices by scanning the log-free trail:
        # we track the current node on the object instead - simpler:
        node_id = self.flags.get("__dialogue_node__")
        if not node_id:
            return ["You're not in a conversation."]
        node = self.dialogues[node_id]
        nxt = node.choices.get(label)
        if nxt is None:
            return [f"'{label}' is not one of the choices."]
        return self._show_dialogue(nxt)

    # -- cutscenes ----------------------------------------------------------------
    def start_cutscene(self, name: str) -> List[str]:
        if name not in self.cutscenes:
            return [f"No cutscene named '{name}'."]
        self.active_cutscene = name
        self.cutscene_step = 0
        return self.advance_cutscene()

    def advance_cutscene(self) -> List[str]:
        if not self.active_cutscene:
            return ["No cutscene is playing."]
        script = self.cutscenes[self.active_cutscene]
        if self.cutscene_step >= len(script):
            self.active_cutscene = None
            self.cutscene_step = 0
            return ["(cutscene ends)"]
        step = script[self.cutscene_step]
        self.cutscene_step += 1
        return self._run_script([step])

    # -- script effects ---------------------------------------------------------------
    def _run_script(self, script: Sequence[Mapping[str, Any]]) -> List[str]:
        events: List[str] = []
        for fx in script:
            kind = fx.get("do")
            if kind == "say":
                events.append(str(fx.get("text", "")))
            elif kind == "set_flag":
                self.flags[fx["flag"]] = fx.get("value", True)
            elif kind == "unlock_exit":
                room = self.rooms[fx["room"]]
                room["locked"] = False
                events.append(f"(the way {fx.get('label', 'onward')} is now open)")
            elif kind == "move_object":
                self.objects[fx["object"]].room = fx["room"]
            elif kind == "start_dialogue":
                self.flags["__dialogue_node__"] = fx["node"]
                events.extend(self._show_dialogue(fx["node"]))
            elif kind == "start_cutscene":
                events.extend(self.start_cutscene(fx["name"]))
            elif kind == "give_item":
                name = fx["item"]
                self.objects[name].room = "__inventory__"
                self.inventory.append(name)
                events.append(f"(you receive: {name})")
            elif kind == "end_game":
                self.flags["__won__"] = True
                events.append(str(fx.get("text", "You win!")))
        for line in events:
            self.log.append(line)
        return events

    # -- helpers ----------------------------------------------------------------------
    def _find(self, name: str) -> Optional[GameObject]:
        for obj in self.objects.values():
            if obj.name == name and obj.room == self.current_room:
                return obj
        return None

    def _find_anywhere(self, name: str) -> Optional[GameObject]:
        obj = self._find(name)
        if obj is not None:
            return obj
        if name in self.inventory:
            return self.objects[name]
        return None

    # -- save / load --------------------------------------------------------------------
    def save(self) -> Dict[str, Any]:
        return {
            "current_room": self.current_room,
            "inventory": list(self.inventory),
            "flags": copy.deepcopy(self.flags),
            "objects": {
                n: {"room": o.room, "state": copy.deepcopy(o.state)}
                for n, o in self.objects.items()
            },
            "rooms": copy.deepcopy(self.rooms),
            "log": list(self.log),
        }

    def load(self, state: Mapping[str, Any]) -> None:
        self.current_room = str(state["current_room"])
        self.inventory = list(state["inventory"])
        self.flags = copy.deepcopy(dict(state["flags"]))
        for name, snap in state["objects"].items():
            self.objects[name].room = snap["room"]
            self.objects[name].state = copy.deepcopy(snap["state"])
        self.rooms = copy.deepcopy(dict(state["rooms"]))
        self.log = list(state.get("log", []))
        self.active_cutscene = None
        self.cutscene_step = 0


def build_game(data: Mapping[str, Any]) -> Game:
    """Validate content dicts and build a Game. Raises ValueError on bad data."""
    rooms = {r["id"]: dict(r) for r in data["rooms"]}
    for rid, room in rooms.items():
        if "description" not in room:
            raise ValueError(f"room '{rid}' needs a description")
        room.setdefault("exits", {})
    objects: Dict[str, GameObject] = {}
    for o in data.get("objects", []):
        if o["room"] != "__inventory__" and o["room"] not in rooms:
            raise ValueError(f"object '{o['name']}' is in unknown room '{o['room']}'")
        objects[o["name"]] = GameObject(
            name=o["name"],
            room=o["room"],
            description=o.get("description", ""),
            takeable=bool(o.get("takeable", False)),
            scripts={k: list(v) for k, v in o.get("scripts", {}).items()},
            state=dict(o.get("state", {})),
        )
    dialogues = {
        d["id"]: DialogueNode(
            text=d["text"],
            choices=dict(d.get("choices", {})),
            effects=list(d.get("effects", [])),
        )
        for d in data.get("dialogues", [])
    }
    cutscenes = {c["id"]: list(c["steps"]) for c in data.get("cutscenes", [])}
    if data["start_room"] not in rooms:
        raise ValueError("start_room must name a real room")
    return Game(
        rooms=rooms,
        objects=objects,
        dialogues=dialogues,
        cutscenes=cutscenes,
        start_room=data["start_room"],
    )


def demo_game() -> Game:
    """Built-in three-room micro-adventure proving the engine."""
    return build_game(
        {
            "start_room": "porch",
            "rooms": [
                {
                    "id": "porch",
                    "description": "A creaking porch. A lantern hangs by the door.",
                    "exits": {"north": "hall"},
                },
                {
                    "id": "hall",
                    "description": "A dusty hall. A cellar door yawns in the floor.",
                    "exits": {"south": "porch", "down": "cellar"},
                    "on_enter": [
                        {"do": "say", "text": "The floorboards groan under your feet."}
                    ],
                },
                {
                    "id": "cellar",
                    "description": "A dark cellar. Something glints in the corner.",
                    "exits": {"up": "hall"},
                    "locked": True,
                    "locked_by": "darkness",
                },
            ],
            "objects": [
                {
                    "name": "lantern",
                    "room": "porch",
                    "description": "A rusty lantern, still oily.",
                    "takeable": True,
                    "scripts": {
                        "use:cellar door": [
                            {
                                "do": "say",
                                "text": "The lantern flares. The cellar is safe to enter.",
                            },
                            {"do": "unlock_exit", "room": "cellar", "label": "down"},
                            {"do": "set_flag", "flag": "lit_cellar", "value": True},
                        ]
                    },
                },
                {
                    "name": "cellar door",
                    "room": "hall",
                    "description": "A heavy trapdoor. It is pitch black below.",
                    "scripts": {
                        "open": [
                            {
                                "do": "say",
                                "text": "You heave the trapdoor open. Darkness stares back.",
                            }
                        ]
                    },
                },
                {
                    "name": "keeper",
                    "room": "hall",
                    "description": "An old keeper dozing in a chair.",
                    "state": {"dialogue": "keeper_hello"},
                },
                {
                    "name": "brass key",
                    "room": "cellar",
                    "description": "A small brass key, warm to the touch.",
                    "takeable": True,
                    "scripts": {
                        "take": [
                            {
                                "do": "say",
                                "text": "As you lift it, a bell tolls far away.",
                            },
                            {"do": "start_cutscene", "name": "bell"},
                        ]
                    },
                },
            ],
            "dialogues": [
                {
                    "id": "keeper_hello",
                    "text": "KEEPER: Mind the cellar, traveler. None go down without light.",
                    "choices": {"thanks": "keeper_bye", "who are you?": "keeper_who"},
                },
                {
                    "id": "keeper_who",
                    "text": "KEEPER: Only the last soul who remembers this house.",
                    "choices": {"thanks": "keeper_bye"},
                },
                {
                    "id": "keeper_bye",
                    "text": "KEEPER: Light first. Always light first.",
                    "effects": [{"do": "set_flag", "flag": "warned", "value": True}],
                },
            ],
            "cutscenes": [
                {
                    "id": "bell",
                    "steps": [
                        {
                            "do": "say",
                            "text": "[cutscene] The bell tolls once... twice...",
                        },
                        {
                            "do": "say",
                            "text": "[cutscene] Dust falls like snow in the lantern light.",
                        },
                        {
                            "do": "end_game",
                            "text": "You found the brass key. The house lets you leave. THE END.",
                        },
                    ],
                }
            ],
        }
    )
