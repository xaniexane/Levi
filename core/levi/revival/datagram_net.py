"""Pure datagrams: the network promises nothing.

Studied from: dead-networks-20260916 report.md [CYCLADES].

The mechanism under study: the *end-to-end principle*. The network
offers only unreliable best-effort datagram delivery — switches are
trivially simple: look up the destination prefix, forward, and drop
whatever does not fit (no buffers held for anyone). ALL reliability
lives at the hosts: a host-level reliable channel adds end-to-end
sequence numbers, cumulative ACKs, sliding windows, and retransmission
on timeout. The network never retransmits, never reorders on purpose,
never promises.

Original, from-scratch implementation for LEVI. In-process delivery on
an explicit virtual clock (no wall clock). stdlib-only. No network.

Public surface:
- ``Datagram`` — src, dst, ident, payload; ``encode()`` / ``decode()``.
- ``DatagramSwitch`` — ``add_route(prefix, host)``; ``forward()``
  drops on congestion instead of queueing; counters ``forwarded`` /
  ``dropped``.
- ``DatagramNet`` — ``attach(name)``, ``send(dgram)``, ``pump()``.
- ``ReliableEndpoint`` — host-side sliding window: ``send(bytes)``,
  ``receive() -> bytes``, ``pump()`` for timeouts; reassembles in
  order, suppresses duplicates.

Honest limits: one switch per net; congestion is a per-tick capacity
per port; the reliable channel is stop-and-wait per window with a
fixed RTO — no congestion control, just the drop-driven kind the
study describes.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/datagram_net"

# reliable-channel constants
WINDOW = 4
RTO = 6
CHUNK = 32  # bytes per datagram payload in the reliable channel


@dataclass
class Datagram:
    """One best-effort packet: source, destination, id, payload."""

    src: str
    dst: str
    ident: int
    payload: bytes = b""

    def encode(self) -> bytes:
        s = self.src.encode("utf-8")
        d = self.dst.encode("utf-8")
        head = struct.pack(">BBHI", len(s), len(d), self.ident, len(self.payload))
        return head + s + d + self.payload

    @classmethod
    def decode(cls, raw: bytes) -> "Datagram":
        try:
            slen, dlen, ident, plen = struct.unpack_from(">BBHI", raw)
        except struct.error as exc:
            raise ValueError(f"bad datagram: {exc}") from None
        off = 8
        src = raw[off : off + slen].decode("utf-8")
        off += slen
        dst = raw[off : off + dlen].decode("utf-8")
        off += dlen
        payload = raw[off : off + plen]
        return cls(src, dst, ident, payload)


class DatagramSwitch:
    """A trivially simple switch: route by prefix, drop when congested.

    There are no per-flow buffers and no retransmission here — that is
    the whole point. ``capacity`` is datagrams per port per tick; the
    excess is dropped and counted.
    """

    def __init__(self, capacity: int = 8) -> None:
        self.capacity = capacity
        self.routes: Dict[str, str] = {}  # dst prefix -> host name
        self.forwarded = 0
        self.dropped = 0
        self._used: Dict[str, int] = {}

    def add_route(self, prefix: str, host: str) -> None:
        self.routes[prefix] = host

    def _port(self, dst: str) -> Optional[str]:
        for prefix in sorted(self.routes, key=len, reverse=True):
            if dst.startswith(prefix):
                return self.routes[prefix]
        return None

    def forward(self, dgram: Datagram, net: "DatagramNet") -> None:
        port = self._port(dgram.dst)
        if port is None:
            self.dropped += 1  # unroutable: dropped, not bounced
            return
        used = self._used.get(port, 0)
        if used >= self.capacity:
            self.dropped += 1  # congestion: drop, never queue
            return
        self._used[port] = used + 1
        self.forwarded += 1
        net._deliver(port, dgram)

    def end_tick(self) -> None:
        self._used.clear()


class DatagramNet:
    """The unreliable network: hosts, one switch, a virtual clock."""

    def __init__(self, capacity: int = 8) -> None:
        self.switch = DatagramSwitch(capacity=capacity)
        self._hosts: Dict[str, List[Datagram]] = {}
        self.now = 0

    def attach(self, name: str) -> None:
        self._hosts[name] = []
        self.switch.add_route(name, name)

    def send(self, dgram: Datagram) -> None:
        """Best effort: may arrive, may not. No promises made."""
        self.switch.forward(dgram, self)

    def _deliver(self, host: str, dgram: Datagram) -> None:
        self._hosts[host].append(dgram)

    def inbox(self, host: str) -> List[Datagram]:
        """Take everything that happened to arrive for a host."""
        got = self._hosts[host]
        self._hosts[host] = []
        return got

    def pump(self, steps: int = 1) -> None:
        for _ in range(steps):
            self.now += 1
            self.switch.end_tick()


class ReliableEndpoint:
    """Host-side reliability: sliding window over raw datagrams.

    Splits a byte stream into chunked datagrams with end-to-end
    sequence numbers; the receiver ACKs cumulatively and reassembles
    in order; the sender retransmits whatever the RTO catches. The
    network underneath may drop anything — this layer recovers.
    """

    def __init__(self, net: DatagramNet, name: str, peer: str) -> None:
        self.net = net
        self.name = name
        self.peer = peer
        self._send_seq = 0
        self._recv_seq = 0
        self._unacked: Dict[int, Tuple[bytes, int]] = {}
        self._held: Dict[int, bytes] = {}
        self._ready: List[bytes] = []
        self._ident = 0
        self.retransmits = 0

    # -- sending ----------------------------------------------------------
    def send(self, data: bytes) -> None:
        """Queue a byte stream for reliable delivery to the peer."""
        for off in range(0, len(data) or 1, CHUNK):
            chunk = data[off : off + CHUNK]
            seq = self._send_seq
            self._send_seq += 1
            self._unacked[seq] = (chunk, self.net.now)
            self._emit(seq, chunk)

    def _emit(self, seq: int, chunk: bytes) -> None:
        self._ident += 1
        body = struct.pack(">I", seq) + chunk
        self.net.send(Datagram(self.name, self.peer, self._ident, body))

    def _emit_ack(self) -> None:
        self._ident += 1
        body = b"A" + struct.pack(">I", self._recv_seq)
        self.net.send(Datagram(self.name, self.peer, self._ident, body))

    # -- receiving ---------------------------------------------------------
    def _ingest(self) -> None:
        for dgram in self.net.inbox(self.name):
            body = dgram.payload
            if body.startswith(b"A") and len(body) == 5:
                ack = struct.unpack_from(">I", body, 1)[0]
                for seq in [s for s in self._unacked if s < ack]:
                    del self._unacked[seq]
            elif len(body) >= 4:
                seq = struct.unpack_from(">I", body)[0]
                chunk = body[4:]
                if seq == self._recv_seq:
                    self._ready.append(chunk)
                    self._recv_seq += 1
                    while self._recv_seq in self._held:
                        self._ready.append(self._held.pop(self._recv_seq))
                        self._recv_seq += 1
                elif seq > self._recv_seq:
                    self._held.setdefault(seq, chunk)
                # else: duplicate — ignored, but still ACKed below
                self._emit_ack()

    def receive(self) -> bytes:
        """Return all in-order bytes available so far."""
        self._ingest()
        out = b"".join(self._ready)
        self._ready = []
        return out

    def pump(self, steps: int = 1) -> None:
        """Advance time: retransmit whatever the RTO catches; ingest."""
        for _ in range(steps):
            self.net.pump(1)
            self._ingest()
            for seq in sorted(self._unacked):
                chunk, sent_at = self._unacked[seq]
                if self.net.now - sent_at >= RTO:
                    self.retransmits += 1
                    self._unacked[seq] = (chunk, self.net.now)
                    self._emit(seq, chunk)
            self._ingest()

    @property
    def pending(self) -> int:
        return len(self._unacked)


def demo() -> Dict[str, object]:
    net = DatagramNet(capacity=2)  # tight capacity: drops will happen
    net.attach("host-a")
    net.attach("host-b")
    a = ReliableEndpoint(net, "host-a", "host-b")
    b = ReliableEndpoint(net, "host-b", "host-a")
    a.send(b"datagrams are dumb, hosts are smart. " * 4)
    for _ in range(60):
        a.pump(1)
        b.pump(1)
        if not a.pending and b._recv_seq == a._send_seq:
            break
    got = b.receive()
    return {
        "delivered": got,
        "retransmits": a.retransmits,
        "dropped_by_net": net.switch.dropped,
    }
