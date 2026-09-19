"""Tiny data-driven parser interactive-fiction VM: the story as data, not code.

Studied from: dead-game-genres-2026-09-16/report.md [Build shortlist -
Z-machine revival] (the revival brief's shape: a constrained verb/noun
parser, rooms/objects/flags as the world model, save plus undo, stdlib-only,
with one built-in micro-adventure).

This is an original, from-scratch implementation for LEVI - no part of it is
derived from any existing IF engine. A ``Story`` is plain data: rooms with
exits and descriptions, objects with portable/fixed placement, flags, and a
rule table. Rules are ``(condition, action)`` pairs evaluated in order after
every command: conditions test flags, inventory, and location; actions print
text, set flags, move objects, open exits, or end the game. The parser
accepts ``verb [noun] [preposition noun]`` and names the exact word it did
not understand. Every understood command pushes a full snapshot first, so
``undo`` restores the exact prior state; ``save``/``load`` serialize to plain
dicts. The built-in micro-adventure, "Lanternlight", is completable and is
wired through the same rule/flag machinery (its special interactions are
registered as extra rules, not engine hacks).

Public surface:
- ``Story(data)``: validated world; ``run(line)`` -> list of output lines.
- ``undo()`` / ``save()`` / ``load(state)``.
- ``LANTERNLIGHT``: the built-in micro-adventure data; ``demo_story()``.

Vocabulary is deliberately constrained (13 verbs) - unknown verbs fail with
the word named, which is the honest-parser contract.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

ORIGIN = "levi-revival/story-vm"

VERBS = (
    "go",
    "take",
    "drop",
    "look",
    "examine",
    "use",
    "open",
    "unlock",
    "talk",
    "give",
    "inventory",
    "undo",
    "help",
)
DIRECTIONS = ("north", "south", "east", "west", "up", "down")
PREPOSITIONS = ("with", "to", "at", "on", "in")


@dataclass
class Story:
    data: Mapping[str, Any]

    def __post_init__(self) -> None:
        d = self.data
        self.rooms: Dict[str, Dict[str, Any]] = {r["id"]: dict(r) for r in d["rooms"]}
        self.objects: Dict[str, Dict[str, Any]] = {
            o["id"]: dict(o) for o in d.get("objects", [])
        }
        self.rules: List[Dict[str, Any]] = [dict(r) for r in d.get("rules", [])]
        self.flags: Dict[str, Any] = dict(d.get("flags", {}))
        self.loc: str = d["start"]
        self.inventory: List[str] = []
        self.over: bool = False
        self.won: bool = False
        self._history: List[Dict[str, Any]] = []
        self._validate()

    # -- validation ------------------------------------------------------------------
    def _validate(self) -> None:
        if self.loc not in self.rooms:
            raise ValueError("start must name a real room")
        for oid, o in self.objects.items():
            where = o.get("at")
            if where is not None and where not in self.rooms:
                raise ValueError(f"object {oid!r} placed in unknown room {where!r}")

    # -- parser ----------------------------------------------------------------------
    def run(self, line: str) -> List[str]:
        """Execute one command line; returns output lines."""
        if self.over:
            return ["The story is over. ('undo' to go back)"]
        words = line.lower().strip().split()
        if not words:
            return ["(type 'help' for verbs)"]
        verb = words[0]
        if verb == "undo":
            return self.undo()
        if verb not in VERBS:
            return [f"I don't know the verb '{verb}'. Try: {', '.join(VERBS)}."]
        rest = [w for w in words[1:] if w not in PREPOSITIONS]
        self._history.append(self.save())
        nouns = self._split_nouns(rest)
        out = getattr(self, f"_v_{verb}")(
            nouns[0] if nouns else None, nouns[1] if len(nouns) > 1 else None
        )
        return list(out) + self._fire_rules()

    def _split_nouns(self, words: List[str]) -> List[str]:
        """Group words into noun phrases, matching the longest object name first.

        Lets players type 'take brass key' instead of forcing single-word names;
        unmatched words pass through as-is so the verbs can report them.
        """
        names = sorted(
            ({o["name"] for o in self.objects.values()} | set(self.objects)),
            key=len,
            reverse=True,
        )
        nouns: List[str] = []
        i = 0
        while i < len(words):
            matched = None
            for name in names:
                parts = name.split()
                if words[i : i + len(parts)] == parts:
                    matched = name
                    i += len(parts)
                    break
            if matched is None:
                nouns.append(words[i])
                i += 1
            else:
                nouns.append(matched)
        return nouns

    # -- verbs -----------------------------------------------------------------------
    def _v_go(self, noun: Optional[str], _n2: Optional[str]) -> List[str]:
        if noun not in DIRECTIONS:
            return [f"Go where? ({', '.join(DIRECTIONS)})"]
        exits = self.rooms[self.loc].get("exits", {})
        if noun not in exits:
            return ["You can't go that way."]
        dest = exits[noun]
        if isinstance(dest, dict):  # locked-exit form
            if dest.get("locked"):
                return [dest.get("locked_msg", "Something blocks the way.")]
            dest = dest["to"]
        self.loc = dest
        return [f"You go {noun}.", self.rooms[self.loc]["description"]]

    def _v_look(self, noun: Optional[str], _n2: Optional[str]) -> List[str]:
        if noun:
            return self._v_examine(noun, None)
        room = self.rooms[self.loc]
        objs = [o["name"] for o in self.objects.values() if o.get("at") == self.loc]
        line = room["description"]
        if objs:
            line += " You see: " + ", ".join(objs) + "."
        return [line]

    def _v_examine(self, noun: Optional[str], _n2: Optional[str]) -> List[str]:
        obj = self._resolve(noun)
        if obj is None:
            return [f"You see no '{noun}' here."]
        extra = obj.get("on_examine")
        lines = [obj.get("description", f"It's {obj['name']}.")]
        if extra:
            lines.extend(self._act(extra))
        return lines

    def _v_take(self, noun: Optional[str], _n2: Optional[str]) -> List[str]:
        obj = self._resolve(noun)
        if obj is None:
            return [f"There's no '{noun}' here to take."]
        if not obj.get("portable", False):
            return [f"You can't take the {obj['name']}."]
        obj["at"] = None
        self.inventory.append(obj["id"])
        return [f"Taken: {obj['name']}."]

    def _v_drop(self, noun: Optional[str], _n2: Optional[str]) -> List[str]:
        if noun is None:
            return ["Drop what?"]
        oid = self._name_to_id(noun)
        if oid not in self.inventory:
            return [f"You're not carrying '{noun}'."]
        self.inventory.remove(oid)
        self.objects[oid]["at"] = self.loc
        return [f"Dropped: {self.objects[oid]['name']}."]

    def _v_inventory(self, _n1: Optional[str], _n2: Optional[str]) -> List[str]:
        if not self.inventory:
            return ["You're carrying nothing."]
        names = [self.objects[i]["name"] for i in self.inventory]
        return ["You're carrying: " + ", ".join(names) + "."]

    def _v_use(self, noun: Optional[str], noun2: Optional[str]) -> List[str]:
        if noun is None:
            return ["Use what?"]
        oid = self._name_to_id(noun)
        if oid is None:
            return [f"You see no '{noun}' to use."]
        obj = self.objects[oid]
        if oid not in self.inventory and obj.get("at") != self.loc:
            return [f"The {obj['name']} isn't here."]
        # object-specific "use X with Y" interactions live in on_use rules
        for spec in obj.get("on_use", []):
            if spec.get("with") in (noun2, None) and self._cond(spec.get("when", {})):
                return self._act(spec.get("then", {}))
        return [f"You use the {obj['name']}. Nothing obvious happens."]

    def _v_open(self, noun: Optional[str], _n2: Optional[str]) -> List[str]:
        obj = self._resolve(noun)
        if obj is None:
            return [f"You see no '{noun}' to open."]
        for spec in obj.get("on_open", []):
            if self._cond(spec.get("when", {})):
                return self._act(spec.get("then", {}))
        return [f"The {obj['name']} won't open."]

    def _v_unlock(self, noun: Optional[str], noun2: Optional[str]) -> List[str]:
        return self._v_open(noun, noun2)

    def _v_talk(self, noun: Optional[str], _n2: Optional[str]) -> List[str]:
        obj = self._resolve(noun)
        if obj is None:
            return [f"There's no '{noun}' here to talk to."]
        return [obj.get("talk", f"The {obj['name']} says nothing.")]

    def _v_give(self, noun: Optional[str], noun2: Optional[str]) -> List[str]:
        if not noun or not noun2:
            return ["Give what to whom? (give <item> to <someone>)"]
        oid = self._name_to_id(noun)
        if oid not in self.inventory:
            return [f"You're not carrying '{noun}'."]
        target = self._resolve(noun2)
        if target is None:
            return [f"There's no '{noun2}' here."]
        for spec in target.get("on_give", []):
            if spec.get("item") == oid and self._cond(spec.get("when", {})):
                self.inventory.remove(oid)
                self.objects[oid]["at"] = None
                return self._act(spec.get("then", {}))
        return [f"The {target['name']} doesn't want your {self.objects[oid]['name']}."]

    def _v_help(self, _n1: Optional[str], _n2: Optional[str]) -> List[str]:
        return [
            "Verbs: " + ", ".join(VERBS) + ".",
            "Directions: " + ", ".join(DIRECTIONS) + ".",
            "Try: go north, take key, examine doormat, use key with door, undo.",
        ]

    # -- rules -----------------------------------------------------------------------
    def _fire_rules(self) -> List[str]:
        out: List[str] = []
        for rule in self.rules:
            if self._cond(rule.get("when", {})):
                out.extend(self._act(rule.get("then", {})))
                if self.over:
                    break
        return out

    def _cond(self, when: Mapping[str, Any]) -> bool:
        for key, val in when.items():
            if key == "flag":
                name, want = val if isinstance(val, (list, tuple)) else (val, True)
                if self.flags.get(name, False) != want:
                    return False
            elif key == "not_flag":
                if self.flags.get(val, False):
                    return False
            elif key == "at":
                if self.loc != val:
                    return False
            elif key == "carries":
                if self._name_to_id(val) not in self.inventory:
                    return False
            elif key == "not_carries":
                if self._name_to_id(val) in self.inventory:
                    return False
            else:
                return False
        return True

    def _act(self, then: Mapping[str, Any]) -> List[str]:
        out: List[str] = []
        for key, val in then.items():
            if key == "say":
                out.append(str(val))
            elif key == "set_flag":
                name, v = val if isinstance(val, (list, tuple)) else (val, True)
                self.flags[name] = v
            elif key == "move_obj":
                oid, dest = val
                self.objects[oid]["at"] = dest
                if dest == "__carried__" and oid not in self.inventory:
                    self.inventory.append(oid)
                elif dest != "__carried__" and oid in self.inventory:
                    self.inventory.remove(oid)
            elif key == "open_exit":
                room_id, direction, to = val
                self.rooms[room_id].setdefault("exits", {})[direction] = to
                out.append("(a way opens)")
            elif key == "teleport":
                self.loc = val
                out.append(self.rooms[self.loc]["description"])
            elif key == "end":
                self.over = True
                self.won = (
                    bool(val.get("won", False)) if isinstance(val, dict) else True
                )
                text = (
                    val.get("text", "The end.") if isinstance(val, dict) else "The end."
                )
                out.append(str(text))
        return out

    # -- helpers -----------------------------------------------------------------------
    def _name_to_id(self, name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        for oid, o in self.objects.items():
            if o["name"] == name or oid == name:
                return oid
        return None

    def _resolve(self, noun: Optional[str]) -> Optional[Dict[str, Any]]:
        oid = self._name_to_id(noun)
        if oid is None:
            return None
        obj = self.objects[oid]
        if obj.get("at") == self.loc or oid in self.inventory:
            return obj
        return None

    # -- save / undo ---------------------------------------------------------------------
    def save(self) -> Dict[str, Any]:
        return {
            "loc": self.loc,
            "inventory": list(self.inventory),
            "flags": copy.deepcopy(self.flags),
            "objects": copy.deepcopy(self.objects),
            "rooms": copy.deepcopy(self.rooms),
            "over": self.over,
            "won": self.won,
        }

    def load(self, state: Mapping[str, Any]) -> None:
        self.loc = str(state["loc"])
        self.inventory = list(state["inventory"])
        self.flags = copy.deepcopy(dict(state["flags"]))
        self.objects = copy.deepcopy(dict(state["objects"]))
        self.rooms = copy.deepcopy(dict(state["rooms"]))
        self.over = bool(state["over"])
        self.won = bool(state["won"])
        # note: history is intentionally left alone so undo keeps working

    def undo(self) -> List[str]:
        if not self._history:
            return ["Nothing to undo."]
        self.load(self._history.pop())
        return ["Undone."]


# ---------------------------------------------------------------------------
# Built-in micro-adventure: "Lanternlight"
# ---------------------------------------------------------------------------

LANTERNLIGHT: Dict[str, Any] = {
    "start": "porch",
    "flags": {},
    "rooms": [
        {
            "id": "porch",
            "description": "A porch at dusk. The house door stands north.",
            "exits": {
                "north": {
                    "to": "hall",
                    "locked": True,
                    "locked_msg": "The house door is locked. It needs a key.",
                }
            },
        },
        {
            "id": "hall",
            "description": "A lamplit hall. Stairs climb up; the porch lies south.",
            "exits": {"south": "porch", "up": "attic"},
        },
        {
            "id": "attic",
            "description": "A dusty attic. Moonlight falls on an old chest.",
            "exits": {"down": "hall"},
        },
    ],
    "objects": [
        {
            "id": "mat",
            "name": "doormat",
            "at": "porch",
            "portable": False,
            "description": "A worn doormat. Something lumpy hides beneath it.",
            "on_examine": {
                "set_flag": "found_key",
                "move_obj": ["key", "porch"],
                "say": "You lift the doormat: a brass key! (take it)",
            },
        },
        {
            "id": "key",
            "name": "brass key",
            "at": None,
            "portable": True,
            "description": "A small brass key.",
            "on_use": [
                {
                    "with": "door",
                    "when": {
                        "at": "porch",
                        "carries": "brass key",
                        "not_flag": "door_open",
                    },
                    "then": {
                        "set_flag": "door_open",
                        "open_exit": ["porch", "north", "hall"],
                        "say": "The brass key turns. The house door swings open.",
                    },
                }
            ],
        },
        {
            "id": "chest",
            "name": "chest",
            "at": "attic",
            "portable": False,
            "description": "An old sea-chest. Inside: a lantern, still warm.",
            "on_open": [
                {
                    "when": {"at": "attic", "not_flag": "lantern_taken"},
                    "then": {
                        "set_flag": "lantern_taken",
                        "move_obj": ["lantern", "__carried__"],
                        "say": "You take the lantern from the chest.",
                    },
                }
            ],
        },
        {
            "id": "lantern",
            "name": "lantern",
            "at": None,
            "portable": True,
            "description": "A lantern, warm as a held hand.",
            "on_use": [
                {
                    "with": None,
                    "when": {"at": "attic", "carries": "lantern"},
                    "then": {
                        "set_flag": "lit",
                        "say": "You lift the lantern. Its light fills the house - "
                        "every shadow becomes a story.",
                        "end": {
                            "won": True,
                            "text": "YOU WIN: the house is yours again.",
                        },
                    },
                }
            ],
        },
    ],
    "rules": [
        {
            "when": {"at": "porch", "not_flag": "found_key"},
            "then": {"say": "(hint: examine the doormat)"},
        },
        {
            "when": {
                "flag": "found_key",
                "not_carries": "brass key",
                "not_flag": "door_open",
            },
            "then": {"say": "(hint: take the brass key)"},
        },
        {
            "when": {"flag": "door_open", "at": "porch", "not_flag": "upstairs"},
            "then": {"say": "(hint: go north, then up)"},
        },
        {
            "when": {"at": "attic", "not_flag": "lit"},
            "then": {
                "set_flag": "upstairs",
                "say": "(hint: open the chest, then use the lantern)",
            },
        },
    ],
}


def demo_story() -> Story:
    """The built-in micro-adventure, wired purely through data rules."""
    return Story(copy.deepcopy(LANTERNLIGHT))
