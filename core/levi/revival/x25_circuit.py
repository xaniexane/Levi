"""Virtual circuits: the network promises reliability.

Studied from: dead-networks-20260916 report.md
[X.25 public packet-switched networks].

The mechanism under study: *virtual circuits* with in-order,
error-corrected delivery. Endpoints stay dumb — the network does the
work: a call opens a circuit between a caller and the addressed
callee, every data packet carries a direction, a sequence number and a
checksum, the receiver acknowledges cumulatively, and missing packets
are retransmitted on timeout. Each direction is sequenced
independently, so a circuit is full duplex. Addresses follow the X.121
shape (decimal digit strings: 4-digit DNIC network prefix + terminal
part). Separate networks join through X.75-style gateways: a switch
forwards packets for foreign DNICs to the neighboring switch, while
circuit state stays home.

Original, from-scratch implementation for LEVI. Delivery is in-process
on an explicit virtual clock (no wall clock); the loss knob is a test
harness, off by default. stdlib-only. No network.

Public surface:
- ``X121Address`` — validated digit-string address; ``dnic`` prefix.
- ``Switch`` — longest-prefix routing, per-direction sequencing state,
  cumulative ACKs, RTO retransmission; ``loss_every`` drop policy.
- ``Network`` — ``attach(name, address)``, ``call(caller, callee)``,
  ``incoming(name)`` for the callee side, ``gateway_to(other, dnic)``,
  ``pump(steps)`` to advance the virtual clock.
- ``VirtualCircuit`` — ``send(bytes)``, ``recv() -> bytes``, ``clear()``.

Honest limits: one switch per network; fixed window; call setup is a
single local operation (no CALL handshake packets); no call
collisions, no charging, no reverse charging.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/x25_circuit"

# packet types
P_DATA = 0x03
P_ACK = 0x04
P_CLEAR = 0x05

# directions inside one circuit
C2S = 0  # caller -> callee
S2C = 1  # callee -> caller

WINDOW = 4  # max unacknowledged data packets per direction
RTO = 5  # virtual ticks before a retransmit


@dataclass(frozen=True)
class X121Address:
    """Decimal digit-string address: 4-digit DNIC + terminal part."""

    digits: str

    def __post_init__(self) -> None:
        if not self.digits.isdigit() or not (4 <= len(self.digits) <= 15):
            raise ValueError(f"bad X.121 address: {self.digits!r}")

    @property
    def dnic(self) -> str:
        return self.digits[:4]

    def __str__(self) -> str:
        return self.digits


@dataclass
class Packet:
    """One network packet: type, circuit, direction, sequence, payload."""

    ptype: int
    circuit: int
    direction: int
    seq: int
    payload: bytes = b""

    def encode(self) -> bytes:
        head = struct.pack(
            ">BBBBI",
            self.ptype,
            self.circuit % 256,
            self.direction,
            self.seq % 256,
            zlib.crc32(self.payload),
        )
        return head + self.payload

    @classmethod
    def decode(cls, raw: bytes) -> "Packet":
        try:
            ptype, circuit, direction, seq, crc = struct.unpack_from(">BBBBI", raw)
        except struct.error as exc:
            raise ValueError(f"bad packet: {exc}") from None
        payload = raw[8:]
        if zlib.crc32(payload) != crc:
            raise ValueError("checksum mismatch")
        return cls(ptype, circuit, direction, seq, payload)


def _fresh_direction() -> Dict:
    return {
        "send_seq": 0,
        "recv_seq": 0,
        "unacked": {},  # seq -> (payload, sent_at)
        "inbox": [],  # ordered payloads ready for the receiving side
        "held": {},  # early arrivals kept for resequencing
    }


class Switch:
    """The smart network core: routes, sequences, ACKs, retransmits.

    ``loss_every`` drops every Nth data packet (0 = never). It exists so
    tests can prove the retransmission machinery works; off by default.
    """

    def __init__(self, loss_every: int = 0) -> None:
        self.net: Optional["Network"] = None  # backref, set by Network
        self.routes: Dict[str, "Network"] = {}  # DNIC prefix -> local network
        self.gateways: Dict[str, "Switch"] = {}  # DNIC prefix -> remote switch
        self._circuits: Dict[int, Dict] = {}
        self._next_circuit = 1
        self.loss_every = loss_every
        self._data_seen = 0
        self.dropped = 0
        self.now = 0

    # -- topology ---------------------------------------------------------
    def add_route(self, dnic: str, net: "Network") -> None:
        self.routes[dnic] = net

    def add_gateway(self, dnic: str, remote: "Switch") -> None:
        """X.75-style: addresses under this DNIC live past another switch."""
        self.gateways[dnic] = remote

    def locate(
        self, addr: X121Address
    ) -> Tuple[Optional["Network"], Optional["Switch"]]:
        """Longest-prefix match: local network or a gateway switch."""
        for prefix in sorted(self.gateways, key=len, reverse=True):
            if addr.digits.startswith(prefix):
                return None, self.gateways[prefix]
        for prefix in sorted(self.routes, key=len, reverse=True):
            if addr.digits.startswith(prefix):
                return self.routes[prefix], None
        return None, None

    # -- circuits ----------------------------------------------------------
    def open_circuit(
        self,
        caller_net: "Network",
        caller: str,
        callee_net: Optional["Network"],
        callee: str,
        callee_addr: X121Address,
    ) -> int:
        cid = self._next_circuit
        self._next_circuit += 1
        self._circuits[cid] = {
            "caller_net": caller_net,
            "caller": caller,
            "callee_net": callee_net,
            "callee": callee,
            "callee_addr": callee_addr,
            "dirs": {C2S: _fresh_direction(), S2C: _fresh_direction()},
            "open": True,
        }
        return cid

    def state(self, cid: int) -> Dict:
        return self._circuits[cid]

    def circuits_for(self, addr: X121Address) -> List[int]:
        """Circuit ids addressed to this X.121 address on this switch."""
        return [
            cid
            for cid, st in self._circuits.items()
            if st["open"] and st["callee_addr"] == addr
        ]

    # -- packet processing --------------------------------------------------
    def input(self, pkt: Packet, from_net: "Network") -> None:
        """Process one packet arriving at the home switch."""
        st = self._circuits.get(pkt.circuit)
        if not st or not st["open"]:
            return
        if pkt.ptype == P_CLEAR:
            st["open"] = False
            return
        if pkt.ptype == P_ACK:
            d = st["dirs"][pkt.direction]
            for seq in [s for s in d["unacked"] if s <= pkt.seq]:
                del d["unacked"][seq]
            return
        if pkt.ptype == P_DATA:
            if self.loss_every:
                self._data_seen += 1
                if self._data_seen % self.loss_every == 0:
                    self.dropped += 1
                    return
            self._sequence(st, pkt)

    def _sequence(self, st: Dict, pkt: Packet) -> None:
        d = st["dirs"][pkt.direction]
        if pkt.seq == d["recv_seq"]:
            d["inbox"].append(pkt.payload)
            d["recv_seq"] += 1
            while d["recv_seq"] in d["held"]:
                d["inbox"].append(d["held"].pop(d["recv_seq"]))
                d["recv_seq"] += 1
        elif pkt.seq > d["recv_seq"]:
            d["held"].setdefault(pkt.seq, pkt.payload)
        # else: duplicate — acknowledged, not duplicated
        ack = Packet(P_ACK, pkt.circuit, pkt.direction, d["recv_seq"] - 1)
        sender_net = st["caller_net"] if pkt.direction == C2S else st["callee_net"]
        sender_name = st["caller"] if pkt.direction == C2S else st["callee"]
        if sender_net is not None:
            sender_net._post(sender_name, ack)

    def retransmit_due(self) -> List[Packet]:
        """Data packets whose RTO expired (re-sent through ``input``)."""
        due = []
        for cid, st in self._circuits.items():
            if not st["open"]:
                continue
            for direction in (C2S, S2C):
                d = st["dirs"][direction]
                for seq in sorted(d["unacked"]):
                    payload, sent_at = d["unacked"][seq]
                    if self.now - sent_at >= RTO:
                        due.append(Packet(P_DATA, cid, direction, seq, payload))
                        d["unacked"][seq] = (payload, self.now)
        return due


class VirtualCircuit:
    """One end of a circuit: a dumb pipe; the network does reliability."""

    def __init__(
        self, home: Switch, cid: int, net: "Network", name: str, side: str
    ) -> None:
        self._home = home
        self.cid = cid
        self._net = net
        self._name = name
        self.side = side  # "caller" or "callee"
        self.open = True

    def _out_dir(self) -> int:
        return C2S if self.side == "caller" else S2C

    def _in_dir(self) -> int:
        return S2C if self.side == "caller" else C2S

    def send(self, data: bytes) -> None:
        if not self.open:
            raise ValueError("circuit is cleared")
        self._net._send(self, data)

    def recv(self) -> bytes:
        if not self.open:
            raise ValueError("circuit is cleared")
        return self._net._recv(self)

    def clear(self) -> None:
        self.open = False
        self._home.input(Packet(P_CLEAR, self.cid, self._out_dir(), 0), self._net)


class Network:
    """One X.25 network: a switch, attached endpoints, a virtual clock."""

    def __init__(self, loss_every: int = 0) -> None:
        self.switch = Switch(loss_every=loss_every)
        self.switch.net = self
        self._endpoints: Dict[str, X121Address] = {}
        self._mail: Dict[str, List[Packet]] = {}  # endpoint -> ACK packets
        self._imports: List[Tuple[str, Switch]] = []  # (dnic, home switch)

    @property
    def now(self) -> int:
        return self.switch.now

    def attach(self, name: str, address: str) -> X121Address:
        addr = X121Address(address)
        self._endpoints[name] = addr
        self.switch.add_route(addr.dnic, self)
        return addr

    def gateway_to(self, other: "Network", dnic: str) -> None:
        """X.75: addresses under `dnic` are reached via the other network."""
        self.switch.add_gateway(dnic, other.switch)
        other._imports.append((dnic, self.switch))

    def call(self, caller: str, callee: str) -> VirtualCircuit:
        """Open a circuit from local endpoint `caller` to an X.121 address."""
        if caller not in self._endpoints:
            raise KeyError(f"unknown endpoint: {caller}")
        addr = X121Address(callee)
        local_net, remote_switch = self.switch.locate(addr)
        if local_net is None and remote_switch is None:
            raise KeyError(f"unroutable address: {callee}")
        callee_net = local_net if local_net is not None else remote_switch.net
        callee_name = self._name_for(callee_net, addr)
        cid = self.switch.open_circuit(self, caller, callee_net, callee_name, addr)
        return VirtualCircuit(self.switch, cid, self, caller, "caller")

    def _name_for(self, net: Optional["Network"], addr: X121Address) -> str:
        if net is not None:
            for name, a in net._endpoints.items():
                if a == addr:
                    return name
        return f"@{addr}"

    def incoming(self, name: str) -> List[VirtualCircuit]:
        """Callee-side handles for circuits addressed to this endpoint."""
        if name not in self._endpoints:
            raise KeyError(f"unknown endpoint: {name}")
        addr = self._endpoints[name]
        out = []
        for dnic, home in [(None, self.switch)] + self._imports:
            if dnic is not None and not addr.digits.startswith(dnic):
                continue
            for cid in home.circuits_for(addr):
                out.append(VirtualCircuit(home, cid, self, name, "callee"))
        return out

    # -- internal machinery -------------------------------------------------
    def _post(self, name: str, pkt: Packet) -> None:
        self._mail.setdefault(name, []).append(pkt)

    def _send(self, vc: VirtualCircuit, data: bytes) -> None:
        st = vc._home.state(vc.cid)
        direction = vc._out_dir()
        d = st["dirs"][direction]
        if len(d["unacked"]) >= WINDOW:
            raise ValueError("send window full; pump() the clock first")
        seq = d["send_seq"]
        d["send_seq"] += 1
        d["unacked"][seq] = (data, vc._home.now)
        vc._home.input(Packet(P_DATA, vc.cid, direction, seq, data), self)

    def _drain(self, vc: VirtualCircuit) -> None:
        for pkt in self._mail.pop(vc._name, []):
            vc._home.input(pkt, self)

    def _recv(self, vc: VirtualCircuit) -> bytes:
        self._drain(vc)
        d = vc._home.state(vc.cid)["dirs"][vc._in_dir()]
        if not d["inbox"]:
            raise ValueError("no data available")
        return d["inbox"].pop(0)

    def pump(self, steps: int = 1) -> None:
        """Advance the virtual clock; retransmit whatever timed out."""
        for _ in range(steps):
            self.switch.now += 1
            for pkt in self.switch.retransmit_due():
                self.switch.input(pkt, self)
            # endpoints process their ACK mail as time passes
            for owner in list(self._mail):
                for pkt in self._mail.pop(owner, []):
                    self.switch.input(pkt, self)


def demo() -> Dict[str, object]:
    net = Network()
    net.attach("here", "234201234567")
    net.attach("there", "234209876543")
    caller_vc = net.call("here", "234209876543")
    callee_vc = net.incoming("there")[0]
    caller_vc.send(b"hello ")
    caller_vc.send(b"circuit")
    got = callee_vc.recv() + callee_vc.recv()
    callee_vc.send(b"ack!")
    back = caller_vc.recv()
    caller_vc.clear()
    return {"delivered": got, "back": back, "open": caller_vc.open}
