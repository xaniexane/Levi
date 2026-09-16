"""The Story Engine — a clean-room parser-interactive-fiction VM.

The dead-genre revival: Infocom's Z-machine (1979) made text adventures
portable by compiling games to versioned story files run by one small
interpreter per machine — write-once-run-anywhere before the phrase
existed. The genre died when graphics won the mainstream; the VM idea
conquered the world elsewhere.

This is the LEVI-native remix, not a replica: a tiny data-driven story
VM in stdlib Python. Adventures are plain-data dicts (rooms, items,
scripted uses); the parser is deliberately constrained — the Z-machine's
hardest lesson is that a weak parser is a frustrating game, so every
verb the engine understands is documented in-game via HELP and nothing
is promised that the parser cannot do. Deterministic, offline,
save/undo via player-owned saves. No licenses, no stores, no accounts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from levi.games.charter import GameManifest

MANIFEST = GameManifest(
    name="story-engine",
    progress_portable=True,
    odds_declared=True,  # no chance at all — stated up front
    hints_free=True,
)

# ---------------------------------------------------------------------------
# Parser vocabulary (the whole language, documented by HELP)
# ---------------------------------------------------------------------------

DIRECTIONS = {
    "north": "north",
    "n": "north",
    "south": "south",
    "s": "south",
    "east": "east",
    "e": "east",
    "west": "west",
    "w": "west",
    "up": "up",
    "u": "up",
    "down": "down",
    "d": "down",
}

VERBS = {
    "go": ["go", "move", "walk", "head"],
    "take": ["take", "get", "grab", "pick"],
    "drop": ["drop", "leave", "discard"],
    "look": ["look", "l", "examine", "x", "inspect"],
    "inventory": ["inventory", "i", "inv"],
    "use": ["use", "apply"],
    "open": ["open", "unlock"],
    "help": ["help", "?", "commands"],
    "quit": ["quit", "exit", "bye"],
}

_ARTICLES = {"the", "a", "an"}

_VERB_OF = {syn: verb for verb, syns in VERBS.items() for syn in syns}


def _normalize_words(text: str) -> List[str]:
    words = [w for w in text.lower().strip().split() if w]
    words = [w for w in words if w not in _ARTICLES]
    if words and words[0] == "pick" and len(words) > 1 and words[1] == "up":
        words = ["take"] + words[2:]
    return words


def parse_command(text: str) -> Tuple[Optional[str], List[str]]:
    """Split input into (verb, args). Bare direction words imply 'go'."""
    words = _normalize_words(text)
    if not words:
        return None, []
    if words[0] in DIRECTIONS and words[0] not in _VERB_OF:
        return "go", [DIRECTIONS[words[0]]]
    verb = _VERB_OF.get(words[0])
    if verb is None:
        return None, words
    args = [DIRECTIONS.get(w, w) for w in words[1:]]
    return verb, args


# ---------------------------------------------------------------------------
# Game state
# ---------------------------------------------------------------------------


@dataclass
class StoryState:
    room: str
    inventory: List[str] = field(default_factory=list)
    room_items: Dict[str, List[str]] = field(default_factory=dict)
    unlocked: List[str] = field(default_factory=list)  # "room:dir" keys
    flags: Dict[str, bool] = field(default_factory=dict)
    moves: int = 0
    won: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "room": self.room,
            "inventory": list(self.inventory),
            "room_items": {k: list(v) for k, v in self.room_items.items()},
            "unlocked": list(self.unlocked),
            "flags": dict(self.flags),
            "moves": self.moves,
            "won": self.won,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoryState":
        return cls(
            room=data["room"],
            inventory=list(data.get("inventory", [])),
            room_items={k: list(v) for k, v in data.get("room_items", {}).items()},
            unlocked=list(data.get("unlocked", [])),
            flags=dict(data.get("flags", {})),
            moves=int(data.get("moves", 0)),
            won=bool(data.get("won", False)),
        )


def new_game(adv: Dict[str, Any]) -> StoryState:
    return StoryState(
        room=adv["start"],
        room_items={rid: list(r.get("items", [])) for rid, r in adv["rooms"].items()},
    )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def _item_name(adv: Dict[str, Any], item_id: str) -> str:
    return adv["items"][item_id].get("name", item_id)


def _find_item(adv: Dict[str, Any], words: List[str], pool: List[str]) -> Optional[str]:
    """Match args against item ids/names in a pool (room or inventory)."""
    query = " ".join(words)
    for iid in pool:
        item = adv["items"][iid]
        if query == iid or query == item.get("name", "").lower():
            return iid
    for iid in pool:  # prefix fallback, still constrained
        item = adv["items"][iid]
        if item.get("name", "").lower().startswith(query) or iid.startswith(query):
            return iid
    return None


def describe_room(adv: Dict[str, Any], state: StoryState) -> str:
    room = adv["rooms"][state.room]
    if _is_dark(adv, state):
        return "It is pitch dark. You are likely to be eaten by a grue. (Something here needs light.)"
    lines = ["== %s ==" % room["name"], room["desc"]]
    items = state.room_items.get(state.room, [])
    if items:
        lines.append("You see: " + ", ".join(_item_name(adv, i) for i in items) + ".")
    exits = list(room.get("exits", {}).keys())
    for key in state.unlocked:
        r, d = key.split(":", 1)
        if r == state.room and d not in exits:
            exits.append(d)
    if exits:
        lines.append("Exits: " + ", ".join(exits) + ".")
    return "\n".join(lines)


def _check_win(adv: Dict[str, Any], state: StoryState) -> Optional[str]:
    win = adv.get("win")
    if not win or state.won:
        return None
    if state.room != win["room"]:
        return None
    have_here = set(state.room_items.get(win["room"], [])) | set(state.inventory)
    if all(req in have_here for req in win.get("requires", [])):
        state.won = True
        return "\n*** %s ***" % win.get("message", "You win!")
    return None


def do_command(adv: Dict[str, Any], state: StoryState, text: str) -> str:
    """Run one command; returns the text to show the player."""
    if state.won:
        return "The story is complete. Start a new game to play again."
    verb, args = parse_command(text)
    if verb is None:
        if args:
            return (
                "I don't know the word %r. Type HELP for the words I do know." % args[0]
            )
        return "Say something. Type HELP for the words I understand."
    handler = _HANDLERS[verb]
    out = handler(adv, state, args)
    state.moves += 1
    win_msg = _check_win(adv, state)
    return out + (win_msg or "")


def _h_go(adv: Dict[str, Any], state: StoryState, args: List[str]) -> str:
    if not args:
        return "Go where? (try: go north)"
    direction = args[0]
    room = adv["rooms"][state.room]
    locked = room.get("locked_exits", {}).get(direction)
    if locked and "%s:%s" % (state.room, direction) not in state.unlocked:
        return locked.get("locked_msg", "Something blocks the way.")
    dest = room.get("exits", {}).get(direction)
    if dest is None and locked:
        dest = locked.get("to")
        key = "%s:%s" % (state.room, direction)
        if key not in state.unlocked:
            state.unlocked.append(key)
    if dest is None:
        return "You can't go %s from here." % direction
    state.room = dest
    return describe_room(adv, state)


def _is_dark(adv: Dict[str, Any], state: StoryState) -> bool:
    room = adv["rooms"][state.room]
    return (
        bool(room.get("dark"))
        and "lantern" not in state.inventory
        and not state.flags.get("lit")
    )


def _h_take(adv: Dict[str, Any], state: StoryState, args: List[str]) -> str:
    if not args:
        return "Take what?"
    if _is_dark(adv, state):
        return "It's too dark to find anything. You need light."
    pool = state.room_items.get(state.room, [])
    iid = _find_item(adv, args, pool)
    if iid is None:
        return "You don't see that here."
    if not adv["items"][iid].get("takeable", True):
        return "You can't take the %s." % _item_name(adv, iid)
    pool.remove(iid)
    state.inventory.append(iid)
    return "Taken: %s." % _item_name(adv, iid)


def _h_drop(adv: Dict[str, Any], state: StoryState, args: List[str]) -> str:
    if not args:
        return "Drop what?"
    iid = _find_item(adv, args, state.inventory)
    if iid is None:
        return "You're not carrying that."
    state.inventory.remove(iid)
    state.room_items.setdefault(state.room, []).append(iid)
    return "Dropped: %s." % _item_name(adv, iid)


def _h_look(adv: Dict[str, Any], state: StoryState, args: List[str]) -> str:
    if not args:
        return describe_room(adv, state)
    pool = state.room_items.get(state.room, []) + state.inventory
    iid = _find_item(adv, args, pool)
    if iid is None:
        return "You see nothing special about that."
    return adv["items"][iid].get("desc", "It's unremarkable.")


def _h_inventory(adv: Dict[str, Any], state: StoryState, args: List[str]) -> str:
    if not state.inventory:
        return "You're carrying nothing."
    return "Carrying: " + ", ".join(_item_name(adv, i) for i in state.inventory) + "."


def _h_use(adv: Dict[str, Any], state: StoryState, args: List[str]) -> str:
    if not args:
        return "Use what?"
    iid = _find_item(adv, args, state.inventory + state.room_items.get(state.room, []))
    if iid is None:
        return "Use what?"
    spec = adv["items"][iid].get("use")
    if not spec:
        return "Nothing interesting happens."
    if spec.get("once") and state.flags.get("used:" + iid):
        return "Nothing more happens."
    if spec.get("once"):
        state.flags["used:" + iid] = True
    room_id = spec.get("room", state.room)
    if room_id != state.room:
        return "That doesn't work here."
    msg = spec.get("message", "Something clicks.")
    if "gives" in spec:
        give = spec["gives"]
        state.room_items.setdefault(state.room, []).append(give)
        msg += " A %s appears." % _item_name(adv, give)
    if "sets_flag" in spec:
        state.flags[spec["sets_flag"]] = True
    return msg


def _h_open(adv: Dict[str, Any], state: StoryState, args: List[str]) -> str:
    # "open east" / "unlock door": try unlocking a locked exit, else use-item path
    if args and args[0] in DIRECTIONS.values():
        key = "%s:%s" % (state.room, args[0])
        locked = adv["rooms"][state.room].get("locked_exits", {}).get(args[0])
        if not locked:
            return "There's nothing locked that way."
        need = locked.get("needs")
        if need and need not in state.inventory:
            return "It's locked. %s" % locked.get("locked_msg", "")
        state.unlocked.append(key)
        return locked.get("open_msg", "Unlocked.")
    return _h_use(adv, state, args)


def _h_help(adv: Dict[str, Any], state: StoryState, args: List[str]) -> str:
    lines = ["I understand these words:"]
    for verb, syns in VERBS.items():
        lines.append(
            "  %s  (also: %s)" % (verb, ", ".join(s for s in syns if s != verb) or verb)
        )
    lines.append("Directions: north/south/east/west/up/down (or n s e w u d).")
    lines.append("Goal: %s" % adv.get("goal", "explore."))
    return "\n".join(lines)


def _h_quit(adv: Dict[str, Any], state: StoryState, args: List[str]) -> str:
    return "QUIT"


_HANDLERS = {
    "go": _h_go,
    "take": _h_take,
    "drop": _h_drop,
    "look": _h_look,
    "inventory": _h_inventory,
    "use": _h_use,
    "open": _h_open,
    "help": _h_help,
    "quit": _h_quit,
}


# ---------------------------------------------------------------------------
# The built-in adventure: THE SUNKEN ARCHIVE
# ---------------------------------------------------------------------------

SUNKEN_ARCHIVE: Dict[str, Any] = {
    "title": "The Sunken Archive",
    "intro": (
        "The old LEVI archive flooded years ago. Three sigils — memory, craft,"
        " and play — lie scattered in the dark. Carry them all into the vault"
        " and the archive remembers itself."
    ),
    "goal": "carry the three sigils (memory, craft, play) into the vault.",
    "start": "foyer",
    "rooms": {
        "foyer": {
            "name": "Flooded Foyer",
            "desc": "Water laps at the marble steps. A brass lantern hangs by the door, still lit.",
            "exits": {"north": "stacks"},
            "items": ["lantern"],
        },
        "stacks": {
            "name": "Drowned Stacks",
            "desc": "Shelves rise out of black water like ribs. Something glints between the shelves.",
            "exits": {"south": "foyer", "east": "scriptorium", "down": "cistern"},
            "items": ["sigil-memory"],
        },
        "scriptorium": {
            "name": "Scriptorium",
            "desc": "Dry, miraculously. A reading desk holds a single drawer. A passage leads east.",
            "exits": {"west": "stacks", "east": "vault-ante"},
            "items": ["desk"],
        },
        "cistern": {
            "name": "The Cistern",
            "desc": "A vast dark tank. Without light you can barely breathe here, let alone search.",
            "dark": True,
            "exits": {"up": "stacks"},
            "items": ["sigil-craft"],
        },
        "vault-ante": {
            "name": "Vault Antechamber",
            "desc": "A bronze door bars the east passage, green with age.",
            "exits": {"west": "scriptorium"},
            "locked_exits": {
                "east": {
                    "to": "vault",
                    "needs": "bronze-key",
                    "locked_msg": "The bronze door is locked. It wants a bronze key.",
                    "open_msg": "The bronze key turns. The vault breathes open.",
                }
            },
            "items": ["sigil-play"],
        },
        "vault": {
            "name": "The Vault",
            "desc": "A round dry room. Three empty niches wait in the wall, shaped like sigils.",
            "exits": {"west": "vault-ante"},
            "items": [],
        },
    },
    "items": {
        "lantern": {
            "name": "brass lantern",
            "desc": "Warm and steady. It pushes back the dark.",
            "takeable": True,
        },
        "sigil-memory": {
            "name": "sigil of memory",
            "desc": "A cold coin etched with an eye.",
            "takeable": True,
        },
        "sigil-craft": {
            "name": "sigil of craft",
            "desc": "A hammer-shaped token, barnacled.",
            "takeable": True,
        },
        "sigil-play": {
            "name": "sigil of play",
            "desc": "A die with no pips — only a smile.",
            "takeable": True,
        },
        "desk": {
            "name": "reading desk",
            "desc": "One drawer. Something rattles inside.",
            "takeable": False,
            "use": {
                "once": True,
                "message": "You open the drawer.",
                "gives": "bronze-key",
            },
        },
        "bronze-key": {
            "name": "bronze key",
            "desc": "Heavy, green with age.",
            "takeable": True,
        },
    },
    "win": {
        "room": "vault",
        "requires": ["sigil-memory", "sigil-craft", "sigil-play"],
        "message": "The three sigils settle into their niches. The archive remembers itself. YOU WIN.",
    },
}

ADVENTURES = {"sunken-archive": SUNKEN_ARCHIVE}


def play(adv: Dict[str, Any], slot: str = "story") -> None:
    """Interactive loop; persists through the player-owned save store."""
    from levi.games.saves import SaveStore

    store = SaveStore()
    state: Optional[StoryState] = None
    if slot in store.list_slots("story-engine"):
        try:
            state = StoryState.from_dict(store.load("story-engine", slot))
            print("(restored your saved story)")
        except Exception:
            state = None
    if state is None:
        state = new_game(adv)
        print(adv["intro"])
        print()
        print(describe_room(adv, state))
    while True:
        try:
            text = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n(saved — the story waits for you)")
            store.save("story-engine", slot, state.to_dict())
            return
        if not text:
            continue
        out = do_command(adv, state, text)
        if out == "QUIT":
            store.save("story-engine", slot, state.to_dict())
            print("Saved. The story waits for you.")
            return
        print(out)
        store.save("story-engine", slot, state.to_dict())
        if state.won:
            return
