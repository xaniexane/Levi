"""LEVI's shared spaces — persistent artifacts with presence around them.

Studied from: retired-software-revival-research-20260916-0004/report.md
[catalog #23] (PLATO).

The studied capability shape: forums, notes, and games as *shared,
persistent artifacts* with real-time social *presence* around them —
people gathered around things that outlast any single session. This
module is an original, in-process expression of that shape: named
``Space`` objects holding versioned notes, threaded forums, and tiny
rule-checked shared games, plus a presence roster (who is here now, who
went idle), and an append-only event log so a space's history is itself
a persistent artifact.

Honest limits, stated plainly: "real-time" here is *simulated* time.
The clock is an explicit tick counter advanced by ``tick()``; heartbeats
stamp the current tick and presence goes stale after a configurable idle
window. There are no sockets, no network, no actual other people — this
is the *model* of a persistent shared space (artifacts + presence +
history), local-first and stdlib-only, so one owner can study and extend
the shape before any networking exists. Games are tiny rule templates
(``tally`` and ``story``), honestly heuristic, not a game engine.

Original, from-scratch implementation for LEVI. Not artificial. Synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

ORIGIN = "levi-revival/presence-spaces"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SpaceError(Exception):
    """Base class for shared-space failures."""


class UnknownSpace(SpaceError):
    """An operation named a space that doesn't exist."""

    def __init__(self, name: str):
        super().__init__(f"no space named {name!r}")
        self.name = name


class NotPresent(SpaceError):
    """A presence-scoped action came from someone not in the space."""

    def __init__(self, person: str, space: str):
        super().__init__(f"{person!r} is not present in {space!r}")
        self.person = person
        self.space = space


class UnknownArtifact(SpaceError):
    """A note, thread, or game id that isn't in the space."""

    def __init__(self, artifact_id: str):
        super().__init__(f"no artifact {artifact_id!r} in this space")
        self.artifact_id = artifact_id


class IllegalMove(SpaceError):
    """A game move the shared rules rejected."""

    def __init__(self, game_id: str, reason: str):
        super().__init__(f"illegal move in {game_id!r}: {reason}")
        self.game_id = game_id


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


@dataclass
class Revision:
    """One version of a note's text."""

    number: int
    tick: int
    author: str
    text: str


@dataclass
class Note:
    """A persistent shared note with full revision history."""

    note_id: str
    title: str
    revisions: List[Revision] = field(default_factory=list)

    @property
    def current(self) -> str:
        """The latest revision's text."""
        return self.revisions[-1].text if self.revisions else ""


@dataclass
class Post:
    """One forum post."""

    tick: int
    author: str
    text: str


@dataclass
class Thread:
    """A persistent forum thread."""

    thread_id: str
    topic: str
    opened_by: str
    opened_tick: int
    posts: List[Post] = field(default_factory=list)


# Tiny rule templates for shared games. Each kind declares how a move is
# validated and how state evolves. Heuristic by design: the point is the
# *shared, persistent, rule-checked* shape, not a game engine.
_GAME_KINDS = ("tally", "story")


def _validate_move(
    kind: str, state: Dict[str, Any], player: str, move: Any
) -> Dict[str, Any]:
    if kind == "tally":
        # move: {"option": str} — counts votes per option.
        if not isinstance(move, dict) or "option" not in move:
            raise IllegalMove("", "tally moves look like {'option': <name>}")
        option = str(move["option"])
        votes = dict(state.get("votes", {}))
        votes[option] = votes.get(option, 0) + 1
        return {"votes": votes, "last_by": player}
    if kind == "story":
        # move: a line of text; players must strictly alternate.
        if not isinstance(move, str) or not move.strip():
            raise IllegalMove("", "story moves are non-empty lines of text")
        if state.get("last_by") == player:
            raise IllegalMove("", f"{player!r} must wait for another player")
        lines = list(state.get("lines", []))
        lines.append({"by": player, "line": move.strip()})
        return {"lines": lines, "last_by": player}
    raise IllegalMove("", f"unknown game kind {kind!r}")


@dataclass
class Game:
    """A persistent shared game with rule-checked moves."""

    game_id: str
    name: str
    kind: str
    started_by: str
    started_tick: int
    state: Dict[str, Any] = field(default_factory=dict)
    move_count: int = 0


@dataclass
class Event:
    """One entry in a space's append-only history."""

    tick: int
    kind: str
    detail: str


@dataclass
class Space:
    """A persistent shared place: artifacts + presence + history."""

    name: str
    description: str = ""
    notes: Dict[str, Note] = field(default_factory=dict)
    threads: Dict[str, Thread] = field(default_factory=dict)
    games: Dict[str, Game] = field(default_factory=dict)
    roster: Dict[str, int] = field(
        default_factory=dict
    )  # person -> last heartbeat tick
    log: List[Event] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Spaces
# ---------------------------------------------------------------------------


class Spaces:
    """A host of shared spaces running on simulated time.

    ``tick()`` advances the clock; heartbeats stamp presence against it.
    Everything — artifacts, roster, event log — lives in memory, local
    and inspectable.
    """

    def __init__(self, idle_after: int = 5) -> None:
        self._spaces: Dict[str, Space] = {}
        self._tick = 0
        self.idle_after = idle_after
        self._next_id = 1

    # -- time ------------------------------------------------------------

    @property
    def tick_now(self) -> int:
        """The current simulated tick."""
        return self._tick

    def tick(self, n: int = 1) -> int:
        """Advance simulated time by n ticks."""
        if n < 0:
            raise SpaceError("time does not run backwards here")
        self._tick += n
        return self._tick

    # -- spaces ----------------------------------------------------------

    def create_space(self, name: str, description: str = "") -> Space:
        """Open a new persistent shared space."""
        if name in self._spaces:
            raise SpaceError(f"space {name!r} already exists")
        space = Space(name, description)
        self._spaces[name] = space
        space.log.append(Event(self._tick, "space", f"space {name!r} created"))
        return space

    def spaces(self) -> List[str]:
        """Names of every space."""
        return list(self._spaces.keys())

    def _get(self, name: str) -> Space:
        space = self._spaces.get(name)
        if space is None:
            raise UnknownSpace(name)
        return space

    # -- presence --------------------------------------------------------

    def join(self, space_name: str, person: str) -> None:
        """Enter a space; presence starts now."""
        space = self._get(space_name)
        space.roster[person] = self._tick
        space.log.append(Event(self._tick, "join", f"{person} joined"))

    def leave(self, space_name: str, person: str) -> None:
        """Leave a space; presence ends now."""
        space = self._get(space_name)
        if person not in space.roster:
            raise NotPresent(person, space_name)
        del space.roster[person]
        space.log.append(Event(self._tick, "leave", f"{person} left"))

    def heartbeat(self, space_name: str, person: str) -> None:
        """Refresh presence; staleness is measured from the last beat."""
        space = self._get(space_name)
        if person not in space.roster:
            raise NotPresent(person, space_name)
        space.roster[person] = self._tick

    def roster(self, space_name: str) -> List[Dict[str, Any]]:
        """Who is present, each with a status: here / idle.

        Anyone silent for more than ``idle_after`` ticks counts as idle.
        """
        space = self._get(space_name)
        result = []
        for person, last in sorted(space.roster.items()):
            silent = self._tick - last
            result.append(
                {
                    "person": person,
                    "status": "here" if silent <= self.idle_after else "idle",
                    "silent_ticks": silent,
                }
            )
        return result

    def _require_present(self, space: Space, person: str) -> None:
        if person not in space.roster:
            raise NotPresent(person, space.name)

    # -- notes -----------------------------------------------------------

    def post_note(self, space_name: str, person: str, title: str, text: str) -> str:
        """Pin a persistent shared note; returns its id."""
        space = self._get(space_name)
        self._require_present(space, person)
        note_id = f"note-{self._next_id}"
        self._next_id += 1
        space.notes[note_id] = Note(
            note_id, title, [Revision(1, self._tick, person, text)]
        )
        space.log.append(Event(self._tick, "note", f"{person} posted {title!r}"))
        return note_id

    def revise_note(self, space_name: str, note_id: str, person: str, text: str) -> int:
        """Append a revision; returns the new revision number."""
        space = self._get(space_name)
        self._require_present(space, person)
        note = space.notes.get(note_id)
        if note is None:
            raise UnknownArtifact(note_id)
        number = len(note.revisions) + 1
        note.revisions.append(Revision(number, self._tick, person, text))
        space.log.append(
            Event(
                self._tick, "revision", f"{person} revised {note.title!r} to r{number}"
            )
        )
        return number

    def note_history(self, space_name: str, note_id: str) -> List[Revision]:
        """Every revision of a note, oldest first."""
        space = self._get(space_name)
        note = space.notes.get(note_id)
        if note is None:
            raise UnknownArtifact(note_id)
        return list(note.revisions)

    # -- forums ----------------------------------------------------------

    def open_thread(self, space_name: str, person: str, topic: str) -> str:
        """Open a persistent forum thread; returns its id."""
        space = self._get(space_name)
        self._require_present(space, person)
        thread_id = f"thread-{self._next_id}"
        self._next_id += 1
        space.threads[thread_id] = Thread(thread_id, topic, person, self._tick)
        space.log.append(Event(self._tick, "thread", f"{person} opened {topic!r}"))
        return thread_id

    def reply(self, space_name: str, thread_id: str, person: str, text: str) -> int:
        """Post to a thread; returns the post count."""
        space = self._get(space_name)
        self._require_present(space, person)
        thread = space.threads.get(thread_id)
        if thread is None:
            raise UnknownArtifact(thread_id)
        thread.posts.append(Post(self._tick, person, text))
        space.log.append(
            Event(self._tick, "reply", f"{person} replied in {thread.topic!r}")
        )
        return len(thread.posts)

    def thread(self, space_name: str, thread_id: str) -> Thread:
        """Read a whole thread back."""
        space = self._get(space_name)
        thread = space.threads.get(thread_id)
        if thread is None:
            raise UnknownArtifact(thread_id)
        return thread

    # -- games -----------------------------------------------------------

    def start_game(self, space_name: str, person: str, kind: str, name: str) -> str:
        """Start a shared, rule-checked game; returns its id."""
        if kind not in _GAME_KINDS:
            raise SpaceError(f"unknown game kind {kind!r}; kinds: {_GAME_KINDS}")
        space = self._get(space_name)
        self._require_present(space, person)
        game_id = f"game-{self._next_id}"
        self._next_id += 1
        space.games[game_id] = Game(game_id, name, kind, person, self._tick)
        space.log.append(
            Event(self._tick, "game", f"{person} started {name!r} ({kind})")
        )
        return game_id

    def move(
        self, space_name: str, game_id: str, person: str, move: Any
    ) -> Dict[str, Any]:
        """Make a rule-checked move; illegal moves raise, legal ones persist."""
        space = self._get(space_name)
        self._require_present(space, person)
        game = space.games.get(game_id)
        if game is None:
            raise UnknownArtifact(game_id)
        try:
            game.state = _validate_move(game.kind, game.state, person, move)
        except IllegalMove as exc:
            raise IllegalMove(game_id, str(exc)) from exc
        game.move_count += 1
        space.log.append(
            Event(
                self._tick,
                "move",
                f"{person} moved in {game.name!r} (#{game.move_count})",
            )
        )
        return dict(game.state)

    def game_state(self, space_name: str, game_id: str) -> Dict[str, Any]:
        """The current persistent state of a game."""
        space = self._get(space_name)
        game = space.games.get(game_id)
        if game is None:
            raise UnknownArtifact(game_id)
        return dict(game.state)

    # -- history ---------------------------------------------------------

    def events(self, space_name: str, since: int = 0) -> List[Event]:
        """The space's append-only history from a tick onward."""
        space = self._get(space_name)
        return [e for e in space.log if e.tick >= since]

    def describe(self, space_name: str) -> Dict[str, Any]:
        """One-glance census: artifacts, presence, history length."""
        space = self._get(space_name)
        return {
            "name": space.name,
            "description": space.description,
            "tick": self._tick,
            "notes": len(space.notes),
            "threads": len(space.threads),
            "games": len(space.games),
            "present": len(space.roster),
            "events": len(space.log),
        }


__all__ = [
    "ORIGIN",
    "SpaceError",
    "UnknownSpace",
    "NotPresent",
    "UnknownArtifact",
    "IllegalMove",
    "Revision",
    "Note",
    "Post",
    "Thread",
    "Game",
    "Event",
    "Space",
    "Spaces",
]
