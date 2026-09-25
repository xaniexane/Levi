"""CYCLADES: the pure datagram and the end-to-end principle.

Origin: France's national research network under Louis Pouzin at IRIA
(later INRIA), ~20 nodes by 1976 with links to NPL London and ESA Rome.
Pouzin coined the *datagram* (data + telegram): packets take any route and
arrive in any order, and losses are fixed end-to-end. The CIGALE switches
chirped like cicadas as packets passed. Layered architecture,
distance-vector routing, end-to-end acknowledgments, sliding windows, and
early congestion control by dropping excess packets — Vint Cerf
acknowledged CYCLADES as a substantial contribution to TCP/IP's design.

What it is in LEVI: a DatagramChannel offering only unreliable best-effort
delivery (it may drop, reorder, or duplicate) plus a HostStack where ALL
reliability lives — end-to-end acks, a sliding window, retransmission on
timeout, and in-order reassembly at the receiving host. The channel stays
trivially simple; the hosts do the work.

Honesty label: LOAD-BEARING — dumb network + smart endpoints with acks,
sliding window, and retransmit-on-timeout is the end-to-end principle made
concrete.

Deny-closed inputs: empty host addresses, windows/timeouts/MTUs below 1,
drop rates outside 0..1, empty payloads, empty destinations, and reading a
flow that was never received all raise ValueError.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

__all__ = ["Datagram", "DatagramChannel", "HostStack"]

DATA = "data"
ACK = "ack"


@dataclass
class Datagram:
    src: str
    dst: str
    seq: int
    kind: str = DATA  # "data" | "ack"
    payload: bytes = b""


class DatagramChannel:
    """Best-effort only: may drop, reorder, duplicate. Fixes nothing."""

    def __init__(
        self, drop_rate: float = 0.0, seed: int = 0, capacity: int = 1024
    ) -> None:
        if not 0.0 <= drop_rate <= 1.0:
            raise ValueError("drop_rate must be in 0..1")
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.drop_rate = drop_rate
        self.capacity = capacity
        self._rng = random.Random(seed)
        self._pending: list[Datagram] = []

    def send(self, datagram: Datagram) -> None:
        # congestion control, CYCLADES-style: drop the excess, no apologies
        if len(self._pending) >= self.capacity:
            return
        self._pending.append(datagram)

    def pump(self) -> list[Datagram]:
        """This tick's arrivals: some lost, the rest shuffled, some doubled."""
        pending, self._pending = self._pending, []
        out: list[Datagram] = []
        for dg in pending:
            if self._rng.random() < self.drop_rate:
                continue
            out.append(dg)
            if self._rng.random() < self.drop_rate / 2:
                out.append(dg)
        self._rng.shuffle(out)
        return out


@dataclass
class _Outbound:
    dst: str
    queue: list[bytes] = field(default_factory=list)
    base: int = 0  # oldest unacknowledged seq
    next_seq: int = 0
    in_flight: dict[int, tuple[Datagram, int]] = field(default_factory=dict)


@dataclass
class _Inbound:
    expected: int = 0
    buffer: dict[int, bytes] = field(default_factory=dict)
    ready: bytearray = field(default_factory=bytearray)


class HostStack:
    """A CYCLADES host: reliability is the endpoint's job."""

    def __init__(
        self, addr: str, window: int = 4, timeout: int = 3, mtu: int = 64
    ) -> None:
        if not isinstance(addr, str) or not addr.strip():
            raise ValueError("host address must be a non-empty string")
        if window < 1:
            raise ValueError("window must be >= 1")
        if timeout < 1:
            raise ValueError("timeout must be >= 1")
        if mtu < 1:
            raise ValueError("mtu must be >= 1")
        self.addr = addr
        self.window = window
        self.timeout = timeout
        self.mtu = mtu
        self._out: dict[str, _Outbound] = {}
        self._in: dict[str, _Inbound] = {}

    # -- sending ---------------------------------------------------------
    def send(self, data: bytes, dst: str) -> None:
        if not isinstance(data, (bytes, bytearray)) or len(data) == 0:
            raise ValueError("payload must be non-empty bytes")
        if not isinstance(dst, str) or not dst.strip():
            raise ValueError("destination must be a non-empty string")
        if dst == self.addr:
            raise ValueError("cannot send datagrams to self")
        flow = self._out.setdefault(dst, _Outbound(dst=dst))
        flow.queue.extend(
            bytes(data[i : i + self.mtu]) for i in range(0, len(data), self.mtu)
        )

    # -- the tick: receive, ack, retransmit, fill window -------------------
    def receive(self, datagrams: list[Datagram]) -> list[Datagram]:
        """Process inbound datagrams; returns acks to transmit."""
        acks: list[Datagram] = []
        for dg in datagrams:
            if dg.dst != self.addr:
                raise ValueError(f"datagram for {dg.dst!r} delivered to {self.addr!r}")
            if dg.kind == ACK:
                flow = self._out.get(dg.src)
                if flow is None or dg.seq not in flow.in_flight:
                    continue  # stale or duplicate ack
                del flow.in_flight[dg.seq]
                while flow.base not in flow.in_flight and flow.base < flow.next_seq:
                    flow.base += 1
            elif dg.kind == DATA:
                inbound = self._in.setdefault(dg.src, _Inbound())
                if dg.seq >= inbound.expected and dg.seq not in inbound.buffer:
                    inbound.buffer[dg.seq] = dg.payload
                while inbound.expected in inbound.buffer:
                    inbound.ready.extend(inbound.buffer.pop(inbound.expected))
                    inbound.expected += 1
                acks.append(Datagram(src=self.addr, dst=dg.src, seq=dg.seq, kind=ACK))
            else:
                raise ValueError(f"unknown datagram kind: {dg.kind!r}")
        return acks

    def emit(self, channel: DatagramChannel) -> None:
        """Send due datagrams: retransmit timed-out ones, fill the window."""
        for flow in self._out.values():
            for seq in sorted(flow.in_flight):
                dg, age = flow.in_flight[seq]
                if age >= self.timeout:
                    channel.send(dg)  # retransmit on timeout
                    flow.in_flight[seq] = (dg, 0)
                else:
                    flow.in_flight[seq] = (dg, age + 1)
            while flow.queue and flow.next_seq - flow.base < self.window:
                payload = flow.queue.pop(0)
                dg = Datagram(
                    src=self.addr,
                    dst=flow.dst,
                    seq=flow.next_seq,
                    kind=DATA,
                    payload=payload,
                )
                flow.in_flight[flow.next_seq] = (dg, 0)
                flow.next_seq += 1
                channel.send(dg)

    def pending_acks(self) -> int:
        return sum(len(f.in_flight) for f in self._out.values())

    # -- reading -----------------------------------------------------------
    def read(self, src: str) -> bytes:
        """In-order reassembled bytes received from src; consumes them."""
        inbound = self._in.get(src)
        if inbound is None:
            raise ValueError(f"no flow received from {src!r}")
        out = bytes(inbound.ready)
        inbound.ready.clear()
        return out
