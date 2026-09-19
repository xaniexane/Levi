"""BBS add-on game hosting: a multiplayer RPG world bolted onto a BBS host.

Studied from: dead-networks-20260916 / report.md [The Major BBS / Worldgroup]
(multiplayer RPG bolted onto a BBS as a DLL add-on module).

This is an original, from-scratch implementation for LEVI. ``DoorHost`` is the
BBS-side loader: game authors write an ``AddOn`` subclass exposing a command
table and per-session lifecycle hooks, register it with the host, and the host
routes each player's input lines to the active add-on, keeps per-player
persistent state across sessions, and keeps the BBS session and the game world
on one login — the historical "game as a BBS door" shape, minus the DLL.

Public surface:
- ``AddOn``: base class — ``name``, ``commands`` (verb -> handler), and
  ``on_enter(player)`` / ``on_leave(player)`` hooks.
- ``DoorHost``: ``register(addon)``, ``launch(name, player)``,
  ``handle(player, line)``, ``quit(player)``, ``save_player(player)``,
  ``load_player(name)``.
- ``PlayerState``: name, active add-on, and a JSON-safe state bag persisted
  by the host.
- ``SimpleTavern``: a minimal worked-example add-on used by the tests.
- ``HostError`` for rule violations (unknown add-on, double launch, ...).

Honest limits: the host handles loading, input routing, and persistence. It
does NOT implement RPG rules — combat, quests, and economies live in the
add-on's command handlers. State bags must be JSON-safe; the host refuses to
persist anything else.

stdlib-only. No network. All sessions are in-process.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


ORIGIN = "levi-revival/major_mud"


class HostError(ValueError):
    """Raised when add-on hosting rules are violated."""


Handler = Callable[["PlayerState", List[str]], str]


class AddOn:
    """Base class for a game add-on that plugs into the BBS host.

    Subclasses set ``name`` and fill ``commands`` with verb -> handler
    functions. Each handler takes the player's state and the tokenized
    arguments and returns the text the player should see.
    """

    name: str = "addon"

    def __init__(self) -> None:
        self.commands: Dict[str, Handler] = {}

    def on_enter(self, player: "PlayerState") -> str:
        """Called once when a player launches this add-on."""
        return f"Welcome to {self.name}, {player.name}."

    def on_leave(self, player: "PlayerState") -> str:
        """Called once when a player quits back to the BBS."""
        return f"You leave {self.name}."


@dataclass
class PlayerState:
    """One player's persistent state, shared between BBS and game add-ons."""

    name: str
    active_addon: Optional[str] = None
    bag: Dict[str, Any] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        json.dumps({key: value})  # fail fast on non-JSON-safe values
        self.bag[key] = value


class DoorHost:
    """The BBS side: registers add-ons and routes player input to them."""

    def __init__(self) -> None:
        self._addons: Dict[str, AddOn] = {}
        self._players: Dict[str, PlayerState] = {}

    def register(self, addon: AddOn) -> None:
        """Register an add-on module. Names must be unique."""
        if not addon.name:
            raise HostError("add-on must have a non-empty name")
        if addon.name in self._addons:
            raise HostError(f"add-on already registered: {addon.name!r}")
        self._addons[addon.name] = addon

    def addons(self) -> List[str]:
        """Names of registered add-ons, in registration order."""
        return list(self._addons)

    def login(self, name: str) -> PlayerState:
        """Start (or resume) a BBS session for ``name``."""
        if name not in self._players:
            self._players[name] = PlayerState(name=name)
        return self._players[name]

    def launch(self, addon_name: str, player: PlayerState) -> str:
        """Launch an add-on for a player already logged in."""
        if player.name not in self._players:
            raise HostError(f"player not logged in: {player.name!r}")
        if addon_name not in self._addons:
            raise HostError(f"unknown add-on: {addon_name!r}")
        if player.active_addon is not None:
            raise HostError(f"{player.name} is already inside {player.active_addon!r}")
        addon = self._addons[addon_name]
        player.active_addon = addon_name
        return addon.on_enter(player)

    def handle(self, player: PlayerState, line: str) -> str:
        """Route one input line from a player to their active add-on."""
        if player.active_addon is None:
            return "You are at the BBS menu. Type the name of a game to launch."
        addon = self._addons[player.active_addon]
        tokens = line.strip().split()
        if not tokens:
            return ""
        verb, args = tokens[0].lower(), tokens[1:]
        handler = addon.commands.get(verb)
        if handler is None:
            return f"Unknown command: {verb!r}. Try 'help'."
        return handler(player, args)

    def quit(self, player: PlayerState) -> str:
        """Quit the active add-on back to the BBS menu."""
        if player.active_addon is None:
            raise HostError(f"{player.name} is not inside any add-on")
        addon = self._addons[player.active_addon]
        player.active_addon = None
        return addon.on_leave(player)

    def save_player(self, player: PlayerState) -> str:
        """Serialize a player's state bag to JSON for persistence."""
        json.dumps(player.bag)  # fail fast on non-JSON-safe values
        return json.dumps(
            {
                "name": player.name,
                "active_addon": player.active_addon,
                "bag": player.bag,
            }
        )

    def load_player(self, data: str) -> PlayerState:
        """Restore a player from ``save_player`` output; replaces the session."""
        raw = json.loads(data)
        player = PlayerState(
            name=raw["name"],
            active_addon=raw.get("active_addon"),
            bag=raw.get("bag", {}),
        )
        self._players[player.name] = player
        return player


class SimpleTavern(AddOn):
    """Worked example: a tiny multiplayer tavern RPG add-on.

    Demonstrates the contract real add-ons follow: commands read and write
    ``player.bag`` and return display text. Shared world state (who is in the
    tavern, the notice board) lives on the add-on instance, the BBS-era
    equivalent of the DLL's shared segment.
    """

    name = "tavern"

    def __init__(self) -> None:
        super().__init__()
        self.patrons: List[str] = []
        self.board: List[str] = []
        self.commands = {
            "help": self._help,
            "look": self._look,
            "sit": self._sit,
            "shout": self._shout,
            "note": self._note,
            "read": self._read,
        }

    def on_enter(self, player: PlayerState) -> str:
        if player.name not in self.patrons:
            self.patrons.append(player.name)
        player.set("gold", player.bag.get("gold", 10))
        return (
            f"The tavern door creaks open for {player.name}. "
            f"Patrons here: {', '.join(self.patrons)}. Type 'help'."
        )

    def on_leave(self, player: PlayerState) -> str:
        if player.name in self.patrons:
            self.patrons.remove(player.name)
        return f"{player.name} slips out of the tavern."

    def _help(self, player: PlayerState, args: List[str]) -> str:
        return "commands: look, sit, shout <words>, note <text>, read"

    def _look(self, player: PlayerState, args: List[str]) -> str:
        return (
            f"A smoky tavern. Patrons: {', '.join(self.patrons) or 'none'}. "
            f"Your purse: {player.bag.get('gold', 0)} gold."
        )

    def _sit(self, player: PlayerState, args: List[str]) -> str:
        return f"{player.name} takes a stool by the fire."

    def _shout(self, player: PlayerState, args: List[str]) -> str:
        if not args:
            return "Shout what?"
        return f"{player.name} shouts: {' '.join(args)}"

    def _note(self, player: PlayerState, args: List[str]) -> str:
        if not args:
            return "Pin what to the board?"
        self.board.append(f"{player.name}: {' '.join(args)}")
        return "Your note is pinned to the board."

    def _read(self, player: PlayerState, args: List[str]) -> str:
        if not self.board:
            return "The board is bare."
        return "\n".join(f"{i + 1}. {note}" for i, note in enumerate(self.board))
