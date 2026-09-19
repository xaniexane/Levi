"""LEVI's parser loop: the shared-imagination engine of text adventures.

Studied from: games-hunt-20260916-0022/report.md [Find 1 — Interactive fiction].

The shape being studied: the parser text adventure. The game describes a
scene; the player types *anything*; a parser resolves intent into the
world's small verb set. Near-zero production cost, no asset pipeline — the
whole game is a data structure plus a sentence resolver, and the player's
imagination renders the graphics.

``parser_if`` rebuilds that shape from scratch, LEVI-native:

- ``World`` — rooms, exits, items, all built from a plain dict spec
  (``World.from_spec``): authoring is data entry, not programming.
- ``Engine`` — the loop: ``step(text)`` tokenizes, maps the player's
  words through a synonym table onto a small verb set (go/take/drop/look/
  inventory/use), resolves nouns against what's visible, and mutates the
  world. Unknown words get an honest "I don't know that word" rather than
  a hallucinated guess.
- Items can carry ``on_use`` hooks so a world spec can wire simple cause
  and effect without a scripting language.

Honest limits: the parser is a verb-first keyword matcher with a synonym
table, not natural-language understanding. It handles one clause per
command ("take lamp", "go north", "use key on door"); it does not parse
conjunctions, pronouns, or complex sentences, and it says so when it
fails. Worlds are fully deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


ORIGIN = "levi-revival/parser-if"


class IFError(Exception):
    """Base class for parser-IF failures."""


# ---------------------------------------------------------------------------
# World model
# ---------------------------------------------------------------------------


@dataclass
class Room:
    id: str
    name: str
    desc: str
    exits: Dict[str, str] = field(default_factory=dict)  # direction -> room id
    items: List[str] = field(default_factory=list)  # item ids lying here


@dataclass
class Item:
    id: str
    name: str
    desc: str
    aliases: List[str] = field(default_factory=list)
    portable: bool = True
    # Optional cause-and-effect: on_use(engine, target_id) -> response text.
    on_use: Optional[Callable[["Engine", Optional[str]], str]] = None

    def matches(self, word: str) -> bool:
        w = word.lower()
        return (
            w == self.id.lower()
            or w == self.name.lower()
            or any(w == a.lower() for a in self.aliases)
        )


@dataclass
class World:
    rooms: Dict[str, Room]
    items: Dict[str, Item]
    start: str

    @classmethod
    def from_spec(cls, spec: Dict[str, Any]) -> "World":
        """Build a world from plain data — the no-asset-pipeline authoring path."""
        rooms = {
            rid: Room(
                id=rid,
                name=r.get("name", rid),
                desc=r.get("desc", ""),
                exits=dict(r.get("exits", {})),
                items=list(r.get("items", [])),
            )
            for rid, r in spec.get("rooms", {}).items()
        }
        items = {
            iid: Item(
                id=iid,
                name=i.get("name", iid),
                desc=i.get("desc", ""),
                aliases=list(i.get("aliases", [])),
                portable=i.get("portable", True),
            )
            for iid, i in spec.get("items", {}).items()
        }
        start = spec.get("start", next(iter(rooms)))
        if start not in rooms:
            raise IFError(f"start room {start!r} not in rooms")
        # Validate exits point somewhere real — fail at build time, not play time.
        for rid, room in rooms.items():
            for direction, target in room.exits.items():
                if target not in rooms:
                    raise IFError(
                        f"room {rid!r} exit {direction!r} -> unknown {target!r}"
                    )
            for iid in room.items:
                if iid not in items:
                    raise IFError(f"room {rid!r} holds unknown item {iid!r}")
        return cls(rooms=rooms, items=items, start=start)


# ---------------------------------------------------------------------------
# Parser + engine
# ---------------------------------------------------------------------------


DIRECTIONS = {
    "n": "north",
    "s": "south",
    "e": "east",
    "w": "west",
    "north": "north",
    "south": "south",
    "east": "east",
    "west": "west",
    "up": "up",
    "down": "down",
    "in": "in",
    "out": "out",
}

VERBS: Dict[str, List[str]] = {
    "go": ["go", "move", "walk", "run", "head", "travel"],
    "take": ["take", "grab", "get", "pick", "carry"],
    "drop": ["drop", "leave", "discard", "put"],
    "look": ["look", "examine", "inspect", "view", "describe", "l", "x"],
    "inventory": ["inventory", "inv", "i", "belongings"],
    "use": ["use", "apply", "operate", "unlock", "open"],
    "help": ["help", "?", "commands"],
}

_WORD_TO_VERB = {w: v for v, words in VERBS.items() for w in words}
_FILLER = {"the", "a", "an", "to", "at", "on", "with", "my"}


class Engine:
    """The shared-imagination loop: describe, read, resolve, mutate."""

    def __init__(self, world: World):
        self.world = world
        self.location = world.start
        self.inventory: List[str] = []
        self.turns = 0

    # -- sensing ---------------------------------------------------------

    def room(self) -> Room:
        return self.world.rooms[self.location]

    def visible_items(self) -> List[Item]:
        return [self.world.items[i] for i in self.room().items]

    def carried_items(self) -> List[Item]:
        return [self.world.items[i] for i in self.inventory]

    def describe(self) -> str:
        r = self.room()
        lines = [r.name, r.desc]
        if r.items:
            names = ", ".join(self.world.items[i].name for i in r.items)
            lines.append(f"You see: {names}.")
        exits = ", ".join(sorted(r.exits))
        lines.append(f"Exits: {exits}." if exits else "There are no exits.")
        return "\n".join(lines)

    # -- parsing ----------------------------------------------------------

    def _resolve_item(self, word: str) -> Optional[Item]:
        for item in self.visible_items() + self.carried_items():
            if item.matches(word):
                return item
        return None

    def step(self, text: str) -> str:
        """Take one line of player input; return the game's response."""
        self.turns += 1
        words = [w for w in text.lower().split() if w]
        if not words:
            return "Say something."
        verb = _WORD_TO_VERB.get(words[0])
        args = [w for w in words[1:] if w not in _FILLER]
        if verb is None:
            # Maybe they typed a bare direction: "north".
            if words[0] in DIRECTIONS:
                return self._do_go(DIRECTIONS[words[0]])
            return f"I don't know the word {words[0]!r}. Try 'help'."
        handler = getattr(self, f"_do_{verb}")
        return handler(args)

    # -- verbs ------------------------------------------------------------

    def _do_go(self, args: List[str]) -> str:
        if not args:
            return "Go where?"
        direction = DIRECTIONS.get(args[0])
        if direction is None:
            return f"I don't know the direction {args[0]!r}."
        room = self.room()
        if direction not in room.exits:
            return "You can't go that way."
        self.location = room.exits[direction]
        return self.describe()

    def _do_take(self, args: List[str]) -> str:
        if not args:
            return "Take what?"
        noun = " ".join(args)
        item = self._resolve_item(noun)
        if item is None or item.id not in self.room().items:
            return f"You don't see {noun!r} here."
        if not item.portable:
            return f"You can't take the {item.name}."
        self.room().items.remove(item.id)
        self.inventory.append(item.id)
        return f"Taken: {item.name}."

    def _do_drop(self, args: List[str]) -> str:
        if not args:
            return "Drop what?"
        noun = " ".join(args)
        item = self._resolve_item(noun)
        if item is None or item.id not in self.inventory:
            return f"You're not carrying {noun!r}."
        self.inventory.remove(item.id)
        self.room().items.append(item.id)
        return f"Dropped: {item.name}."

    def _do_look(self, args: List[str]) -> str:
        if not args:
            return self.describe()
        noun = " ".join(args)
        item = self._resolve_item(noun)
        if item is None:
            return f"You don't see {noun!r} here."
        return item.desc

    def _do_inventory(self, args: List[str]) -> str:
        if not self.inventory:
            return "You're carrying nothing."
        names = ", ".join(self.world.items[i].name for i in self.inventory)
        return f"Carrying: {names}."

    def _do_use(self, args: List[str]) -> str:
        if not args:
            return "Use what?"
        # "use key on door" -> item=key, target=door
        if "on" in args:
            cut = args.index("on")
            noun, target_words = " ".join(args[:cut]), args[cut + 1 :]
        else:
            noun, target_words = " ".join(args), []
        item = self._resolve_item(noun)
        if item is None or (
            item.id not in self.inventory and item.id not in self.room().items
        ):
            return f"You don't have {noun!r} to use."
        target = self._resolve_item(" ".join(target_words)) if target_words else None
        if item.on_use is not None:
            return item.on_use(self, target.id if target else None)
        if target:
            return f"Nothing happens when you use the {item.name} on the {target.name}."
        return f"Nothing happens when you use the {item.name}."

    def _do_help(self, args: List[str]) -> str:
        return (
            "Commands: go <direction>, take <thing>, drop <thing>, "
            "look [at <thing>], inventory, use <thing> [on <thing>]. "
            "Directions: north/south/east/west (n/s/e/w), up, down, in, out."
        )


def demo_world() -> World:
    """A tiny two-room world used by tests and as an authoring example."""
    return World.from_spec(
        {
            "start": "hall",
            "rooms": {
                "hall": {
                    "name": "Stone Hall",
                    "desc": "A cold hall. A brass lamp flickers on a table.",
                    "exits": {"north": "vault"},
                    "items": ["lamp"],
                },
                "vault": {
                    "name": "Vault",
                    "desc": "A round vault. Something glints in the dark.",
                    "exits": {"south": "hall"},
                    "items": ["coin"],
                },
            },
            "items": {
                "lamp": {
                    "name": "brass lamp",
                    "desc": "A heavy brass lamp, warm to the touch.",
                    "aliases": ["lantern", "light"],
                },
                "coin": {
                    "name": "gold coin",
                    "desc": "A gold coin stamped with a leviathan.",
                    "aliases": ["gold"],
                    "portable": True,
                },
            },
        }
    )
