"""Presence, message, and status as one primitive.

Studied from: dead-networks-20260916 report.md [AIM].

The mechanism under study: a single frame primitive carries
*presence* (who is online), *message* (the text), and *status*
(away, idle notes) together — the server tracks buddy sessions and
fans status changes out to watchers, so "is she there?" and "what did
she say?" travel the same pipe.

Original, from-scratch implementation for LEVI. In-process server, no
sockets, no wall clock (away/idle are set explicitly). stdlib-only.
No network.

Public surface:
- ``Frame`` — channel + sequence + kind + fields; ``encode()`` /
  ``decode()`` binary frames.
- ``PresenceServer`` — ``logon(name)`` / ``logoff(name)``,
  ``set_status(name, status, note)``, ``watch(watcher, buddy)``,
  ``send_message(frm, to, text)``, ``inbox(name)``.
- Status values: ``online``, ``away``, ``offline`` (offline is the
  absence of a session, never stored).

Honest limits: messages to offline buddies are refused (no offline
storage — the study's primitive assumes a live session); there is no
real authentication, names are first-come.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/oscar_presence"

_MAGIC = b"OSC1"

# channels: one primitive, three concerns
CH_CONTROL = 0x01  # logon/logoff/status
CH_MESSAGE = 0x02  # instant messages
CH_NOTIFY = 0x03  # presence fan-out to watchers

# frame kinds
K_LOGON = 0x01
K_LOGOFF = 0x02
K_STATUS = 0x03
K_MSG = 0x04
K_PRESENCE = 0x05  # server -> watcher: buddy changed state
K_ERROR = 0x7F

STATUS_ONLINE = "online"
STATUS_AWAY = "away"


@dataclass
class Frame:
    """One wire primitive: channel, sequence, kind, string fields."""

    channel: int
    seq: int
    kind: int
    fields: List[str] = field(default_factory=list)

    def encode(self) -> bytes:
        body = b""
        for f in self.fields:
            raw = f.encode("utf-8")
            body += struct.pack(">H", len(raw)) + raw
        head = struct.pack(
            ">4sBBBH", _MAGIC, self.channel, self.seq, self.kind, len(self.fields)
        )
        return head + body

    @classmethod
    def decode(cls, raw: bytes) -> "Frame":
        try:
            magic, channel, seq, kind, nfields = struct.unpack_from(">4sBBBH", raw)
        except struct.error as exc:
            raise ValueError(f"bad frame: {exc}") from None
        if magic != _MAGIC:
            raise ValueError("bad frame magic")
        off = 9
        fields = []
        try:
            for _ in range(nfields):
                (length,) = struct.unpack_from(">H", raw, off)
                off += 2
                fields.append(raw[off : off + length].decode("utf-8"))
                off += length
        except struct.error as exc:
            raise ValueError(f"bad frame: {exc}") from None
        if off != len(raw):
            raise ValueError("trailing bytes in frame")
        return cls(channel, seq, kind, fields)


@dataclass
class Session:
    name: str
    status: str = STATUS_ONLINE
    note: str = ""  # away message / status note
    inbox: List[Frame] = field(default_factory=list)


class PresenceServer:
    """Tracks buddy sessions; fans presence out to watchers.

    Watchers subscribe to buddies; every logon/logoff/status change is
    delivered to watchers as a presence frame, and messages route only
    between live sessions.
    """

    def __init__(self) -> None:
        self.sessions: Dict[str, Session] = {}
        self.watchers: Dict[str, List[str]] = {}  # buddy -> [watchers]
        self._seq = 0

    # -- sessions ---------------------------------------------------------
    def logon(self, name: str) -> Session:
        session = self.sessions.get(name)
        if session is None:
            session = Session(name)
            self.sessions[name] = session
        session.status = STATUS_ONLINE
        self._broadcast(name, STATUS_ONLINE, "")
        return session

    def logoff(self, name: str) -> None:
        if name in self.sessions:
            del self.sessions[name]
            self._broadcast(name, "offline", "")

    def set_status(self, name: str, status: str, note: str = "") -> None:
        session = self._require(name)
        if status not in (STATUS_ONLINE, STATUS_AWAY):
            raise ValueError(f"bad status: {status}")
        session.status = status
        session.note = note
        self._broadcast(name, status, note)

    def _require(self, name: str) -> Session:
        try:
            return self.sessions[name]
        except KeyError:
            raise KeyError(f"not logged on: {name}") from None

    # -- watching -----------------------------------------------------------
    def watch(self, watcher: str, buddy: str) -> None:
        """`watcher` gets presence frames whenever `buddy` changes state."""
        self.watchers.setdefault(buddy, [])
        if watcher not in self.watchers[buddy]:
            self.watchers[buddy].append(watcher)
        # immediate snapshot of current presence
        session = self.sessions.get(buddy)
        state = session.status if session else "offline"
        note = session.note if session else ""
        self._notify(watcher, buddy, state, note)

    def _broadcast(self, buddy: str, state: str, note: str) -> None:
        for watcher in self.watchers.get(buddy, []):
            self._notify(watcher, buddy, state, note)

    def _notify(self, watcher: str, buddy: str, state: str, note: str) -> None:
        session = self.sessions.get(watcher)
        if session is None:
            return  # watchers must be logged on to receive
        self._seq += 1
        session.inbox.append(
            Frame(CH_NOTIFY, self._seq, K_PRESENCE, [buddy, state, note])
        )

    # -- messaging ------------------------------------------------------------
    def send_message(self, frm: str, to: str, text: str) -> None:
        """Route a message; away buddies get their note appended honestly."""
        self._require(frm)
        target = self.sessions.get(to)
        if target is None:
            raise KeyError(f"{to} is offline; messages need a live session")
        self._seq += 1
        fields = [frm, text]
        if target.status == STATUS_AWAY and target.note:
            fields.append(f"(away: {target.note})")
        target.inbox.append(Frame(CH_MESSAGE, self._seq, K_MSG, fields))

    def inbox(self, name: str) -> List[Frame]:
        """Take all frames waiting for a session."""
        session = self._require(name)
        got = session.inbox
        session.inbox = []
        return got

    def roster(self) -> Dict[str, Tuple[str, str]]:
        """Current presence snapshot: name -> (status, note)."""
        return {n: (s.status, s.note) for n, s in self.sessions.items()}


def demo() -> Dict[str, object]:
    srv = PresenceServer()
    srv.logon("alice")
    srv.logon("bob")
    srv.watch("alice", "bob")
    srv.set_status("bob", STATUS_AWAY, "out for lunch")
    srv.send_message("alice", "bob", "ping when back")
    bob_frames = [(f.kind, f.fields) for f in srv.inbox("bob")]
    alice_frames = [(f.kind, f.fields) for f in srv.inbox("alice")]
    return {"bob": bob_frames, "alice": alice_frames, "roster": srv.roster()}
