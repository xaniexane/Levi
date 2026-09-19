"""commons — persistent shared spaces with presence.

Studied from: revival-50-more-20260916-0009/catalog (Section 23).

Load-bearing idea: persistent shared artifacts (boards, notes) plus
*presence* — who's here, what they're viewing — carried on a real-time-ish
in-process event feed, so the space feels inhabited, not filed.

LEVI's take: ``Commons`` holds ``Board``s of ``Note``s (the persistent
artifacts) and a presence table (member -> what they're viewing). Every
join, view, post, edit, and leave appends to an ``EventFeed`` and pings
in-process subscribers — "real-time" means synchronous callbacks, honest
about it. Boards and presence survive in one serializable snapshot via
``to_dict``/``from_dict``.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


ORIGIN = "levi-revival/commons"


@dataclass
class Note:
    id: str
    author: str
    text: str
    created_at: float
    updated_at: float


@dataclass
class Board:
    name: str
    notes: Dict[str, Note] = field(default_factory=dict)


@dataclass
class Presence:
    member: str
    viewing: str  # board name, or "lobby"
    since: float


@dataclass
class Event:
    seq: int
    kind: str  # join | leave | view | post | edit
    actor: str
    detail: str
    ts: float


class Commons:
    """One shared space: persistent boards, live presence, an event feed."""

    def __init__(self, name: str = "commons") -> None:
        self.name = name
        self.boards: Dict[str, Board] = {}
        self.presence: Dict[str, Presence] = {}
        self.feed: List[Event] = []
        self._subscribers: List[Callable[[Event], None]] = []
        self._seq = 0

    # -- artifacts: persistent shared boards --------------------------------

    def board(self, name: str) -> Board:
        """Get-or-create a board. Boards persist for the life of the commons."""
        if name not in self.boards:
            self.boards[name] = Board(name=name)
        return self.boards[name]

    def post_note(
        self, board_name: str, author: str, text: str, now: Optional[float] = None
    ) -> Note:
        board = self.board(board_name)
        ts = now if now is not None else time.time()
        note = Note(
            id=uuid.uuid4().hex[:8],
            author=author,
            text=text,
            created_at=ts,
            updated_at=ts,
        )
        board.notes[note.id] = note
        self._emit("post", author, f"{author} posted on {board_name}: {text[:60]}", ts)
        return note

    def edit_note(
        self,
        board_name: str,
        note_id: str,
        author: str,
        new_text: str,
        now: Optional[float] = None,
    ) -> Note:
        board = self.board(board_name)
        try:
            note = board.notes[note_id]
        except KeyError:
            raise KeyError(f"no note {note_id!r} on {board_name!r}") from None
        if note.author != author:
            raise PermissionError(f"only {note.author!r} may edit this note")
        note.text = new_text
        note.updated_at = now if now is not None else time.time()
        self._emit(
            "edit", author, f"{author} edited a note on {board_name}", note.updated_at
        )
        return note

    # -- presence: who's here, what they're viewing ---------------------------

    def join(self, member: str, now: Optional[float] = None) -> Presence:
        ts = now if now is not None else time.time()
        pres = Presence(member=member, viewing="lobby", since=ts)
        self.presence[member] = pres
        self._emit("join", member, f"{member} entered the commons", ts)
        return pres

    def view(
        self, member: str, board_name: str, now: Optional[float] = None
    ) -> Presence:
        pres = self._present(member)
        self.board(board_name)  # viewing creates the board if needed — the space grows
        pres.viewing = board_name
        pres.since = now if now is not None else time.time()
        self._emit("view", member, f"{member} is viewing {board_name}", pres.since)
        return pres

    def leave(self, member: str, now: Optional[float] = None) -> None:
        self._present(member)
        del self.presence[member]
        self._emit(
            "leave",
            member,
            f"{member} left the commons",
            now if now is not None else time.time(),
        )

    def who_here(self) -> List[Presence]:
        """Presence snapshot: who's here and what each is viewing."""
        return list(self.presence.values())

    def viewers_of(self, board_name: str) -> List[str]:
        return [p.member for p in self.presence.values() if p.viewing == board_name]

    # -- the feed ---------------------------------------------------------------

    def subscribe(self, fn: Callable[[Event], None]) -> None:
        """In-process real-time: subscribers are called synchronously per event."""
        self._subscribers.append(fn)

    def _emit(self, kind: str, actor: str, detail: str, ts: float) -> Event:
        self._seq += 1
        ev = Event(seq=self._seq, kind=kind, actor=actor, detail=detail, ts=ts)
        self.feed.append(ev)
        for fn in self._subscribers:
            fn(ev)
        return ev

    def _present(self, member: str) -> Presence:
        try:
            return self.presence[member]
        except KeyError:
            raise KeyError(f"{member!r} is not in the commons") from None

    # -- snapshot -----------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "boards": {
                name: {
                    n.id: {
                        "author": n.author,
                        "text": n.text,
                        "created_at": n.created_at,
                        "updated_at": n.updated_at,
                    }
                    for n in board.notes.values()
                }
                for name, board in self.boards.items()
            },
            "presence": {
                m: {"viewing": p.viewing, "since": p.since}
                for m, p in self.presence.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Commons":
        c = cls(data.get("name", "commons"))
        for name, notes in data.get("boards", {}).items():
            board = c.board(name)
            for nid, n in notes.items():
                board.notes[nid] = Note(id=nid, **n)
        for m, p in data.get("presence", {}).items():
            c.presence[m] = Presence(member=m, viewing=p["viewing"], since=p["since"])
        return c
