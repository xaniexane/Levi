"""Real-time multi-user chat rooms on a dialup exchange.

Studied from: dead-networks-20260916/report.md (The Major BBS / Worldgroup).

The old mechanism: callers dropped into named teleconference rooms where
everything typed was broadcast to everyone present, with whispers for
private asides and a moderator's kick for rowdy lines. LEVI's
reimplementation is that shape in local memory: rooms, membership,
sequence-ordered broadcast, whisper inboxes, and a flood heuristic
(flag, don't silence — the old sysops warned first too).

Honest limits: there is no network here. "Real-time" means
sequence-ordered within one process; wall-clock time is deliberately
not modeled. The flood check is a documented heuristic (N messages per
K sequence ticks), not abuse detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/teleconference"

FLOOD_WINDOW = 20  # sequence ticks
FLOOD_LIMIT = 8  # messages inside the window earns a warning


@dataclass
class ChatMessage:
    seq: int
    room: str
    sender: str
    text: str
    kind: str = "say"  # say | action | whisper | system


@dataclass
class Room:
    name: str
    topic: str = ""
    members: List[str] = field(default_factory=list)
    history: List[ChatMessage] = field(default_factory=list)
    moderators: List[str] = field(default_factory=list)


class Teleconference:
    """The exchange's chat floor."""

    def __init__(self) -> None:
        self.rooms: Dict[str, Room] = {}
        self.inboxes: Dict[str, List[ChatMessage]] = {}
        self._seq = 0
        self._spoken_at: Dict[Tuple[str, str], List[int]] = {}
        self.warnings: Dict[str, int] = {}

    # -- rooms -----------------------------------------------------------
    def create_room(self, name: str, topic: str = "") -> Room:
        if not name or not name.strip():
            raise ValueError("room name required")
        if name in self.rooms:
            raise ValueError(f"room {name!r} already exists")
        room = Room(name=name, topic=topic)
        self.rooms[name] = room
        return room

    def join(self, room_name: str, handle: str, *, moderator: bool = False) -> None:
        room = self._room(room_name)
        self._check_handle(handle)
        if handle in room.members:
            raise ValueError(f"{handle} already in {room_name}")
        room.members.append(handle)
        if moderator and handle not in room.moderators:
            room.moderators.append(handle)
        self.inboxes.setdefault(handle, [])
        self._announce(room, f"{handle} joins the room.")

    def leave(self, room_name: str, handle: str) -> None:
        room = self._room(room_name)
        if handle not in room.members:
            raise ValueError(f"{handle} is not in {room_name}")
        room.members.remove(handle)
        self._announce(room, f"{handle} leaves the room.")

    def kick(
        self, room_name: str, moderator: str, target: str, reason: str = ""
    ) -> None:
        room = self._room(room_name)
        if moderator not in room.moderators:
            raise ValueError(f"{moderator} is not a moderator of {room_name}")
        if target not in room.members:
            raise ValueError(f"{target} is not in {room_name}")
        room.members.remove(target)
        note = f"{target} kicked by {moderator}."
        if reason:
            note += f" ({reason})"
        self._announce(room, note, kind="system")

    # -- talking ---------------------------------------------------------
    def say(self, room_name: str, handle: str, text: str) -> ChatMessage:
        room = self._room(room_name)
        self._require_member(room, handle)
        self._check_text(text)
        return self._broadcast(room, handle, text, kind="say")

    def emote(self, room_name: str, handle: str, text: str) -> ChatMessage:
        """An /me-style action line ('* handle does text')."""
        room = self._room(room_name)
        self._require_member(room, handle)
        self._check_text(text)
        return self._broadcast(room, handle, text, kind="action")

    def whisper(self, sender: str, target: str, text: str) -> ChatMessage:
        """A private aside: delivered to the target's inbox, never to a
        room. Both parties must exist on the exchange."""
        self._check_handle(sender)
        self._check_handle(target)
        if sender not in self.inboxes:
            raise ValueError(f"{sender} has never joined a room")
        if target not in self.inboxes:
            raise ValueError(f"no such caller {target!r}")
        self._check_text(text)
        msg = ChatMessage(
            seq=self._next(), room="", sender=sender, text=text, kind="whisper"
        )
        self.inboxes[target].append(msg)
        self.inboxes[sender].append(msg)
        return msg

    def inbox(self, handle: str) -> List[ChatMessage]:
        return list(self.inboxes.get(handle, []))

    def history(self, room_name: str, last: int = 50) -> List[ChatMessage]:
        room = self._room(room_name)
        return list(room.history[-last:])

    def who(self, room_name: str) -> List[str]:
        return list(self._room(room_name).members)

    def flooded(self, handle: str) -> bool:
        """Has this caller tripped the flood heuristic (warning issued)?
        Heuristic: more than FLOOD_LIMIT messages inside FLOOD_WINDOW
        sequence ticks."""
        return self.warnings.get(handle, 0) > 0

    # -- internals -------------------------------------------------------
    def _next(self) -> int:
        self._seq += 1
        return self._seq

    def _room(self, name: str) -> Room:
        try:
            return self.rooms[name]
        except KeyError:
            raise ValueError(f"no room {name!r}") from None

    @staticmethod
    def _check_handle(handle: str) -> None:
        if not handle or not handle.strip() or len(handle) > 24:
            raise ValueError("handle must be 1..24 characters")

    @staticmethod
    def _check_text(text: str) -> None:
        if not text or not text.strip():
            raise ValueError("message text required")
        if len(text) > 240:
            raise ValueError("message too long (240 chars max)")

    @staticmethod
    def _require_member(room: Room, handle: str) -> None:
        if handle not in room.members:
            raise ValueError(f"{handle} is not in room {room.name!r}")

    def _announce(self, room: Room, text: str, kind: str = "system") -> None:
        room.history.append(
            ChatMessage(
                seq=self._next(), room=room.name, sender="*", text=text, kind=kind
            )
        )

    def _broadcast(self, room: Room, handle: str, text: str, kind: str) -> ChatMessage:
        msg = ChatMessage(
            seq=self._next(),
            room=room.name,
            sender=handle,
            text=text,
            kind=kind,
        )
        room.history.append(msg)
        key = (room.name, handle)
        recent = self._spoken_at.setdefault(key, [])
        recent.append(msg.seq)
        recent[:] = [s for s in recent if msg.seq - s <= FLOOD_WINDOW]
        if len(recent) > FLOOD_LIMIT:
            self.warnings[handle] = self.warnings.get(handle, 0) + 1
        return msg

    def floor_status(self) -> Dict[str, object]:
        return {
            "rooms": len(self.rooms),
            "callers": len(self.inboxes),
            "messages": self._seq,
            "warned": dict(self.warnings),
        }
