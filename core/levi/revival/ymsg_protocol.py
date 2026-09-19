"""Lightweight key/value protocol with honest degraded mode.

Studied from: dead-networks-20260916 report.md [Yahoo! Messenger].

The mechanism under study: a *lightweight key/value binary protocol*
— every packet is a service id plus a flat list of key/value pairs,
so presence, messages, and login all share one tiny frame shape. And
the honest part: clients that cannot hold a live connection (behind
firewalls) fall back to *HTTP-style polling* — the client asks "any
news?" on a timer, and presence becomes an approximation ("last seen
N polls ago") instead of a lie.

Original, from-scratch implementation for LEVI. In-process server; the
"polling" is a method call on a timer the caller drives — no sockets,
no wall clock. stdlib-only. No network.

Public surface:
- ``Packet`` — service, status, session_id, kv pairs; ``encode()`` /
  ``decode()`` binary frames.
- ``YMsgServer`` — ``login(name) -> session_id``, ``set_presence``,
  ``send_message``, ``poll(session_id)`` (the degraded-mode read),
  ``logout``.
- ``PollingClient`` — drives ``poll()`` on a tick schedule and keeps
  an *approximate* presence table with staleness counts.

Service ids: 0x01 login, 0x02 presence, 0x04 message, 0x06 poll reply.

Honest limits: polling presence is explicitly approximate — the
client reports `stale_after` polls and marks buddies `suspect` past
it; message order across polls is server order, which is FIFO here.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/ymsg_protocol"

_MAGIC = b"YMSG"

SVC_LOGIN = 0x01
SVC_PRESENCE = 0x02
SVC_MESSAGE = 0x04
SVC_POLL = 0x06

STATUS_OK = 0
STATUS_ERR = 1


@dataclass
class Packet:
    """One key/value frame: service + status + session + flat kv pairs."""

    service: int
    status: int
    session_id: int
    pairs: List[Tuple[str, str]] = field(default_factory=list)

    def encode(self) -> bytes:
        body = b""
        for key, val in self.pairs:
            kb = key.encode("utf-8")
            vb = val.encode("utf-8")
            body += struct.pack(">HH", len(kb), len(vb)) + kb + vb
        head = struct.pack(
            ">4sHHIIH",
            _MAGIC,
            1,
            self.service,
            self.status,
            self.session_id,
            len(self.pairs),
        )
        return head + body

    @classmethod
    def decode(cls, raw: bytes) -> "Packet":
        try:
            magic, _ver, service, status, session_id, npairs = struct.unpack_from(
                ">4sHHIIH", raw
            )
        except struct.error as exc:
            raise ValueError(f"bad packet: {exc}") from None
        if magic != _MAGIC:
            raise ValueError("bad packet magic")
        off = 18
        pairs = []
        try:
            for _ in range(npairs):
                klen, vlen = struct.unpack_from(">HH", raw, off)
                off += 4
                key = raw[off : off + klen].decode("utf-8")
                off += klen
                val = raw[off : off + vlen].decode("utf-8")
                off += vlen
                pairs.append((key, val))
        except struct.error as exc:
            raise ValueError(f"bad packet: {exc}") from None
        if off != len(raw):
            raise ValueError("trailing bytes in packet")
        return cls(service, status, session_id, pairs)

    def get(self, key: str, default: str = "") -> str:
        for k, v in self.pairs:
            if k == key:
                return v
        return default


@dataclass
class _Session:
    name: str
    session_id: int
    presence: str = "online"
    queue: List[Packet] = field(default_factory=list)  # waiting datagrams


class YMsgServer:
    """The server side: sessions, presence, message queues, poll reads."""

    def __init__(self) -> None:
        self._sessions: Dict[int, _Session] = {}
        self._by_name: Dict[str, int] = {}
        self._next_id = 1000

    def login(self, name: str) -> Packet:
        """Fresh login always mints a new session id."""
        sid = self._next_id
        self._next_id += 1
        self._sessions[sid] = _Session(name, sid)
        self._by_name[name] = sid
        return Packet(SVC_LOGIN, STATUS_OK, sid, [("user", name)])

    def logout(self, session_id: int) -> None:
        sess = self._sessions.pop(session_id, None)
        if sess is not None:
            self._by_name.pop(sess.name, None)

    def _require(self, session_id: int) -> _Session:
        try:
            return self._sessions[session_id]
        except KeyError:
            raise KeyError(f"bad session: {session_id}") from None

    def set_presence(self, session_id: int, presence: str) -> Packet:
        sess = self._require(session_id)
        sess.presence = presence
        # fan the presence out as queued packets to every other session
        note = Packet(
            SVC_PRESENCE, STATUS_OK, 0, [("user", sess.name), ("presence", presence)]
        )
        for other in self._sessions.values():
            if other.session_id != session_id:
                other.queue.append(note)
        return Packet(SVC_PRESENCE, STATUS_OK, session_id, [("presence", presence)])

    def send_message(self, session_id: int, to: str, text: str) -> Packet:
        frm = self._require(session_id)
        target_id = self._by_name.get(to)
        if target_id is None:
            return Packet(
                SVC_MESSAGE, STATUS_ERR, session_id, [("error", f"{to} is offline")]
            )
        pkt = Packet(
            SVC_MESSAGE,
            STATUS_OK,
            session_id,
            [("from", frm.name), ("to", to), ("text", text)],
        )
        self._sessions[target_id].queue.append(pkt)
        return Packet(SVC_MESSAGE, STATUS_OK, session_id, [("sent", to)])

    def poll(self, session_id: int) -> List[Packet]:
        """Degraded-mode read: take everything queued since the last poll."""
        sess = self._require(session_id)
        got = sess.queue
        sess.queue = []
        return got

    def roster(self) -> Dict[str, str]:
        return {s.name: s.presence for s in self._sessions.values()}


class PollingClient:
    """A client behind a firewall: no live pipe, just timed polls.

    Presence here is *approximate by design*: each buddy carries a
    `last_seen` poll count, and buddies unseen for more than
    `stale_after` polls are reported `suspect` instead of online.
    """

    def __init__(self, server: YMsgServer, stale_after: int = 3) -> None:
        self.server = server
        self.stale_after = stale_after
        self.session_id: int = 0
        self.name: str = ""
        self.polls = 0
        self.messages: List[Tuple[str, str]] = []  # (from, text)
        self._seen: Dict[str, int] = {}  # buddy -> last poll with news

    def login(self, name: str) -> None:
        pkt = self.server.login(name)
        self.session_id = pkt.session_id
        self.name = name

    def tick(self) -> List[Packet]:
        """One poll cycle: fetch news, update the approximate roster."""
        packets = self.server.poll(self.session_id)
        self.polls += 1
        for pkt in packets:
            if pkt.service == SVC_MESSAGE:
                self.messages.append((pkt.get("from"), pkt.get("text")))
                self._seen[pkt.get("from")] = self.polls
            elif pkt.service == SVC_PRESENCE:
                self._seen[pkt.get("user")] = self.polls
        return packets

    def presence(self) -> Dict[str, str]:
        """Approximate roster: 'online' or 'suspect' (stale). Never certain."""
        out = {}
        for buddy, last in self._seen.items():
            age = self.polls - last
            out[buddy] = "online" if age <= self.stale_after else "suspect"
        return out

    def send(self, to: str, text: str) -> Packet:
        return self.server.send_message(self.session_id, to, text)


def demo() -> Dict[str, object]:
    srv = YMsgServer()
    alice = PollingClient(srv)
    bob = PollingClient(srv)
    alice.login("alice")
    bob.login("bob")
    srv.set_presence(bob.session_id, "online")
    alice.send("bob", "hello over polling")
    alice.tick()
    bob.tick()
    return {
        "bob_messages": bob.messages,
        "alice_presence_view": alice.presence(),
        "roster": srv.roster(),
    }
