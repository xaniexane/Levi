"""Live-builder MUD: veteran players earn ranks and build the world from inside it.

Studied from: games-deadmechanics-20260916 / findings.jsonl
[arch-games-mud-builders] (veteran players earn ranks and create
rooms/objects/quests from inside the game; the world is its own editor,
players are the content pipeline).

This is an original, from-scratch implementation for LEVI. The world ships
with a rank ladder — player, builder, wizard — and the build verbs are gated
by rank: builders can dig rooms and make objects, wizards can also script
quests, promote, and demote. There is no separate editor or admin console;
every build action is a command issued from inside the game, and every action
lands in an append-only audit log so the community can see who built what.

Public surface:
- ``BuilderWorld``: ``join(name)``, ``earn(name, points)``,
  ``promote(name, by)``, ``demote(name, by)``, ``dig(...)``, ``make(...)``,
  ``script(...)``, ``rooms()``, ``objects()``, ``quests()``, ``audit()``,
  ``rank_of(name)``.
- ``BuildRecord``: frozen audit entry — who, their rank, what, when (seq).
- ``BuilderError`` for violations (unknown player, rank too low, ...).

Ranks: ``player`` < ``builder`` < ``wizard``. Points are earned by play
(``earn``); ``promote`` additionally requires the promoter to be a wizard and
the promotee to hold enough points — rank is granted, never bought. The
first wizard is seeded at world creation.

Honest limits: points are a trust token, not an anti-griefing system — a
malicious wizard is outside this module's threat model. The audit log is
append-only in memory only; durable moderation tooling is out of scope.

stdlib-only. No network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


ORIGIN = "levi-revival/live_builder"


class BuilderError(ValueError):
    """Raised when builder-world rules are violated."""


RANKS = ("player", "builder", "wizard")

# Points needed before a wizard may promote a player to each rank.
_PROMOTE_POINTS = {"builder": 100, "wizard": 500}


def _rank_level(rank: str) -> int:
    return RANKS.index(rank)


@dataclass(frozen=True)
class BuildRecord:
    """One immutable audit entry: who built what, at which rank."""

    seq: int
    author: str
    author_rank: str
    action: str
    detail: str


@dataclass
class _Player:
    name: str
    rank: str = "player"
    points: int = 0


class BuilderWorld:
    """A world whose players are also its content pipeline."""

    def __init__(self, founder: str = "founder") -> None:
        self._players: Dict[str, _Player] = {}
        self._rooms: Dict[str, Dict[str, Any]] = {}
        self._objects: Dict[str, Dict[str, Any]] = {}
        self._quests: Dict[str, Dict[str, Any]] = {}
        self._audit: List[BuildRecord] = []
        self._seq = 0
        self._players[founder] = _Player(name=founder, rank="wizard")
        self._log(founder, "wizard", "seed", f"world founded by {founder}")

    # -- player lifecycle -------------------------------------------------
    def join(self, name: str) -> str:
        """A new player enters the world at the bottom of the ladder."""
        if not name:
            raise BuilderError("name must be non-empty")
        if name in self._players:
            raise BuilderError(f"already joined: {name!r}")
        self._players[name] = _Player(name=name)
        return f"{name} joins as a player."

    def earn(self, name: str, points: int) -> int:
        """Award play points toward future promotion. Returns the new total."""
        player = self._require(name)
        if points < 0:
            raise BuilderError("points must be non-negative")
        player.points += points
        return player.points

    def rank_of(self, name: str) -> str:
        return self._require(name).rank

    def points_of(self, name: str) -> int:
        return self._require(name).points

    def promote(self, name: str, by: str) -> str:
        """A wizard promotes a player one rung, if they have earned it."""
        promoter = self._require(by)
        if promoter.rank != "wizard":
            raise BuilderError(f"only wizards can promote ({by} is {promoter.rank})")
        player = self._require(name)
        level = _rank_level(player.rank)
        if level >= len(RANKS) - 1:
            raise BuilderError(f"{name} is already at the top rank")
        new_rank = RANKS[level + 1]
        if player.points < _PROMOTE_POINTS[new_rank]:
            raise BuilderError(
                f"{name} needs {_PROMOTE_POINTS[new_rank]} points for {new_rank} "
                f"(has {player.points})"
            )
        player.rank = new_rank
        self._log(by, promoter.rank, "promote", f"{name} -> {new_rank}")
        return f"{name} is now a {new_rank}."

    def demote(self, name: str, by: str) -> str:
        """A wizard demotes a player one rung."""
        promoter = self._require(by)
        if promoter.rank != "wizard":
            raise BuilderError(f"only wizards can demote ({by} is {promoter.rank})")
        player = self._require(name)
        level = _rank_level(player.rank)
        if level == 0:
            raise BuilderError(f"{name} is already at the bottom rank")
        player.rank = RANKS[level - 1]
        self._log(by, promoter.rank, "demote", f"{name} -> {player.rank}")
        return f"{name} is now a {player.rank}."

    # -- build verbs (the world as its own editor) -------------------------
    def dig(self, name: str, room_id: str, description: str = "") -> str:
        """Create a room. Requires builder rank or higher."""
        player = self._require_rank(name, "builder")
        if not room_id:
            raise BuilderError("room_id must be non-empty")
        if room_id in self._rooms:
            raise BuilderError(f"room already exists: {room_id!r}")
        self._rooms[room_id] = {"description": description, "built_by": name}
        self._log(name, player.rank, "dig", f"room {room_id!r}: {description}")
        return f"Room {room_id!r} dug."

    def make(
        self, name: str, object_id: str, room_id: str, description: str = ""
    ) -> str:
        """Create an object inside a room. Requires builder rank or higher."""
        player = self._require_rank(name, "builder")
        if not object_id:
            raise BuilderError("object_id must be non-empty")
        if object_id in self._objects:
            raise BuilderError(f"object already exists: {object_id!r}")
        if room_id not in self._rooms:
            raise BuilderError(f"unknown room: {room_id!r}")
        self._objects[object_id] = {
            "room": room_id,
            "description": description,
            "built_by": name,
        }
        self._log(name, player.rank, "make", f"object {object_id!r} in {room_id!r}")
        return f"Object {object_id!r} placed in {room_id!r}."

    def script(self, name: str, quest_id: str, steps: List[str]) -> str:
        """Create a quest (ordered steps). Wizards only."""
        player = self._require_rank(name, "wizard")
        if not quest_id:
            raise BuilderError("quest_id must be non-empty")
        if quest_id in self._quests:
            raise BuilderError(f"quest already exists: {quest_id!r}")
        if not steps:
            raise BuilderError("a quest needs at least one step")
        self._quests[quest_id] = {"steps": list(steps), "built_by": name}
        self._log(
            name, player.rank, "script", f"quest {quest_id!r}: {len(steps)} steps"
        )
        return f"Quest {quest_id!r} scripted with {len(steps)} steps."

    # -- inspection --------------------------------------------------------
    def rooms(self) -> List[str]:
        return sorted(self._rooms)

    def objects(self) -> List[str]:
        return sorted(self._objects)

    def quests(self) -> List[str]:
        return sorted(self._quests)

    def room_info(self, room_id: str) -> Dict[str, Any]:
        try:
            return dict(self._rooms[room_id])
        except KeyError:
            raise BuilderError(f"unknown room: {room_id!r}") from None

    def audit(self) -> List[BuildRecord]:
        """The append-only build log. Returns a copy."""
        return list(self._audit)

    # -- internals ---------------------------------------------------------
    def _require(self, name: str) -> _Player:
        try:
            return self._players[name]
        except KeyError:
            raise BuilderError(f"unknown player: {name!r}") from None

    def _require_rank(self, name: str, minimum: str) -> _Player:
        player = self._require(name)
        if _rank_level(player.rank) < _rank_level(minimum):
            raise BuilderError(f"{name} is {player.rank}; {minimum} rank required")
        return player

    def _log(self, author: str, author_rank: str, action: str, detail: str) -> None:
        self._seq += 1
        self._audit.append(
            BuildRecord(
                seq=self._seq,
                author=author,
                author_rank=author_rank,
                action=action,
                detail=detail,
            )
        )
