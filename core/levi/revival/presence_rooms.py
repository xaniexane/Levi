"""presence_rooms — drop-in voice rooms, LAN/self-hosted, no accounts.

Studied from: giant-patterns-hunt-20260916-0016 (report.md [Additions 5]).
Load-bearing idea: drop-in voice rooms you host yourself — join with a
room code and a display name, no account, and quality is never paywalled:
every quality tier is available to everyone, chosen by capability.

LEVI's take: ``RoomHost`` runs ``Room``s. Joining needs only a display
name (optionally a join code the room owner set). Members carry presence
(``speaking`` / ``muted`` / ``idle``) on an in-process event feed the
room owner can subscribe to. ``QualityProfile``s (low/balanced/high) are
capability descriptors — free for all, selected by device/network fitness,
never by payment tier. Rooms serialize to dicts for self-hosted handoff.

Honest limits: this is the room *protocol* — roster, presence, and
quality negotiation. It carries no audio; real audio transport is a job
for the host's media layer, not this module.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass
from typing import Callable, Dict, List, Optional


ORIGIN = "levi-revival/presence-rooms"

SPEAKING = "speaking"
MUTED = "muted"
IDLE = "idle"
STATES = (SPEAKING, MUTED, IDLE)


@dataclass
class QualityProfile:
    """Capability descriptor. All tiers are free — pick by fitness, not wallet."""

    name: str  # low | balanced | high
    sample_hz: int
    bitrate_kbps: int
    description: str


PROFILES = {
    "low": QualityProfile("low", 8000, 24, "narrowband; works on weak links"),
    "balanced": QualityProfile("balanced", 24000, 64, "wideband; the everyday default"),
    "high": QualityProfile(
        "high", 48000, 128, "fullband; studio-grade when the link allows"
    ),
}


@dataclass
class Member:
    id: str
    display_name: str
    state: str = IDLE
    profile: str = "balanced"
    joined_at: float = 0.0


@dataclass
class RoomEvent:
    seq: int
    kind: str  # join | leave | state | profile
    member: str
    detail: str
    ts: float


@dataclass
class Room:
    name: str
    join_code: Optional[str] = None
    max_members: int = 50


class RoomHost:
    """Self-hosted presence rooms. No accounts; presence on an event feed."""

    def __init__(self) -> None:
        self.rooms: Dict[str, Room] = {}
        self.members: Dict[str, Dict[str, Member]] = {}
        self.feeds: Dict[str, List[RoomEvent]] = {}
        self._subscribers: Dict[str, List[Callable[[RoomEvent], None]]] = {}
        self._seq: Dict[str, int] = {}

    # -- rooms ----------------------------------------------------------------

    def create_room(
        self, name: str, join_code: Optional[str] = None, max_members: int = 50
    ) -> Room:
        if name in self.rooms:
            raise ValueError(f"room {name!r} already exists")
        room = Room(name=name, join_code=join_code, max_members=max_members)
        self.rooms[name] = room
        self.members[name] = {}
        self.feeds[name] = []
        self._subscribers[name] = []
        self._seq[name] = 0
        return room

    def close_room(self, name: str) -> bool:
        if name not in self.rooms:
            return False
        del self.rooms[name]
        del self.members[name]
        del self.feeds[name]
        del self._subscribers[name]
        del self._seq[name]
        return True

    # -- presence --------------------------------------------------------------

    def _emit(self, room: str, kind: str, member: str, detail: str) -> RoomEvent:
        self._seq[room] += 1
        ev = RoomEvent(
            seq=self._seq[room], kind=kind, member=member, detail=detail, ts=time.time()
        )
        self.feeds[room].append(ev)
        for sub in self._subscribers[room]:
            sub(ev)
        return ev

    def subscribe(self, room: str, callback: Callable[[RoomEvent], None]) -> None:
        self._subscribers[room].append(callback)

    def join(
        self,
        room: str,
        display_name: str,
        join_code: Optional[str] = None,
        profile: str = "balanced",
    ) -> Member:
        r = self.rooms[room]
        if r.join_code and join_code != r.join_code:
            raise PermissionError("wrong join code")
        if len(self.members[room]) >= r.max_members:
            raise OverflowError("room is full")
        if profile not in PROFILES:
            raise ValueError(f"unknown profile {profile!r}")
        m = Member(
            id=f"m-{uuid.uuid4().hex[:8]}",
            display_name=display_name,
            profile=profile,
            joined_at=time.time(),
        )
        self.members[room][m.id] = m
        self._emit(room, "join", m.id, display_name)
        return m

    def leave(self, room: str, member_id: str) -> bool:
        m = self.members[room].pop(member_id, None)
        if m is None:
            return False
        self._emit(room, "leave", member_id, m.display_name)
        return True

    def set_state(self, room: str, member_id: str, state: str) -> Member:
        if state not in STATES:
            raise ValueError(f"state must be one of {STATES}")
        m = self.members[room][member_id]
        m.state = state
        self._emit(room, "state", member_id, state)
        return m

    def set_profile(self, room: str, member_id: str, profile: str) -> Member:
        """Switch quality tier — always free, always allowed."""
        if profile not in PROFILES:
            raise ValueError(f"unknown profile {profile!r}")
        m = self.members[room][member_id]
        m.profile = profile
        self._emit(room, "profile", member_id, profile)
        return m

    # -- roster ---------------------------------------------------------------

    def roster(self, room: str) -> List[Member]:
        return list(self.members[room].values())

    def speakers(self, room: str) -> List[Member]:
        return [m for m in self.members[room].values() if m.state == SPEAKING]

    def recent_events(self, room: str, limit: int = 50) -> List[RoomEvent]:
        return self.feeds[room][-limit:]

    # -- snapshots ------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            name: {
                "room": asdict(r),
                "members": {mid: asdict(m) for mid, m in self.members[name].items()},
            }
            for name, r in self.rooms.items()
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RoomHost":
        host = cls()
        for name, blob in d.items():
            r = blob["room"]
            host.create_room(
                name, join_code=r.get("join_code"), max_members=r.get("max_members", 50)
            )
            for mid, m in blob.get("members", {}).items():
                host.members[name][mid] = Member(**m)
        return host
