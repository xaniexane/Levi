"""X.25 virtual circuits: the network promises reliability.

Origin: CCITT's 1976 packet standard behind the world's public data
networks — Telenet (1975), Tymnet, TRANSPAC, DATAPAC, PSS, AUSTPAC — giving
the 1980s genuine global data coverage through X.121 addressing and X.75
gateways. The mechanism: virtual circuits with in-order, error-corrected
delivery. The network promises reliability, so the endpoints stay dumb —
X.25's 1984 revision deleted datagrams outright. Frame Relay replaced it in
the early 1990s; pockets survive in aviation and AX.25 ham radio.

What it is in LEVI: a VirtualCircuit with open/close, packet send over a
simulated lossy channel, and in-order delivery with retransmission. The
endpoint never reorders anything itself — ``deliver`` only ever releases
the contiguous prefix, ``missing`` names the gaps, and ``retransmit``
replays them. The circuit keeps the promise; the endpoint stays dumb.

Honesty label: USEFUL PATTERN — the promise (in-order, error-corrected,
endpoint-dumb) is the real X.25 mechanism; the lossy channel and
retransmission loop are a simulation harness, not a wire protocol.

Deny-closed inputs: malformed X.121 addresses, duplicate opens, sends on
unknown or closed circuits, empty payloads, retransmits of unknown or
already-acknowledged sequence numbers, and operations on unknown circuit
ids all raise ValueError.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field

__all__ = [
    "Packet",
    "LossyChannel",
    "VirtualCircuit",
    "MTU",
    "is_x121_address",
]

MTU = 128  # bytes per packet payload


def is_x121_address(addr: str) -> bool:
    """X.121-style address: 4..14 decimal digits."""
    return isinstance(addr, str) and addr.isdigit() and 4 <= len(addr) <= 14


@dataclass
class Packet:
    circuit_id: str
    seq: int
    data: bytes


@dataclass
class _CircuitState:
    local: str
    remote: str
    open: bool = True
    send_seq: int = 0
    sent: dict[int, bytes] = field(default_factory=dict)  # for retransmit
    acked: set[int] = field(default_factory=set)
    recv_expected: int = 0
    recv_buffer: dict[int, bytes] = field(default_factory=dict)
    ready: bytearray = field(default_factory=bytearray)


class LossyChannel:
    """Simulated wire: drops, shuffles, and duplicates packets."""

    def __init__(self, loss_rate: float = 0.0, seed: int = 0) -> None:
        if not 0.0 <= loss_rate <= 1.0:
            raise ValueError("loss_rate must be in 0..1")
        self.loss_rate = loss_rate
        self._rng = random.Random(seed)

    def deliver(self, packets: list[Packet]) -> list[Packet]:
        out: list[Packet] = []
        for p in packets:
            if self._rng.random() < self.loss_rate:
                continue  # dropped on the wire
            out.append(p)
            if self._rng.random() < self.loss_rate / 2:
                out.append(p)  # duplicated on the wire
        self._rng.shuffle(out)
        return out


class VirtualCircuit:
    """X.25-style virtual circuits: the network keeps the promise."""

    def __init__(self) -> None:
        self._circuits: dict[str, _CircuitState] = {}

    def _require(self, circuit_id: str) -> _CircuitState:
        state = self._circuits.get(circuit_id)
        if state is None:
            raise ValueError(f"unknown circuit: {circuit_id!r}")
        if not state.open:
            raise ValueError(f"circuit {circuit_id!r} is closed")
        return state

    def open(self, local: str, remote: str) -> str:
        if not is_x121_address(local):
            raise ValueError(f"bad X.121 address {local!r}: 4..14 decimal digits")
        if not is_x121_address(remote):
            raise ValueError(f"bad X.121 address {remote!r}: 4..14 decimal digits")
        if local == remote:
            raise ValueError("local and remote addresses must differ")
        for cid, st in self._circuits.items():
            if st.open and {st.local, st.remote} == {local, remote}:
                raise ValueError(
                    f"circuit already open between {local} and {remote}: {cid}"
                )
        cid = uuid.uuid4().hex[:12]
        self._circuits[cid] = _CircuitState(local=local, remote=remote)
        return cid

    def close(self, circuit_id: str) -> None:
        state = self._require(circuit_id)
        state.open = False

    def send(self, circuit_id: str, data: bytes) -> list[Packet]:
        state = self._require(circuit_id)
        if not isinstance(data, (bytes, bytearray)) or len(data) == 0:
            raise ValueError("send payload must be non-empty bytes")
        packets: list[Packet] = []
        for i in range(0, len(data), MTU):
            chunk = bytes(data[i : i + MTU])
            seq = state.send_seq
            state.send_seq += 1
            state.sent[seq] = chunk
            packets.append(Packet(circuit_id=circuit_id, seq=seq, data=chunk))
        return packets

    def retransmit(self, circuit_id: str, seq: int) -> Packet:
        """Replay one unacknowledged packet (the network's repair crew)."""
        state = self._require(circuit_id)
        if seq not in state.sent:
            raise ValueError(f"circuit {circuit_id!r}: unknown seq {seq}")
        if seq in state.acked:
            raise ValueError(f"circuit {circuit_id!r}: seq {seq} already acknowledged")
        return Packet(circuit_id=circuit_id, seq=seq, data=state.sent[seq])

    def ingest(self, circuit_id: str, packets: list[Packet]) -> None:
        """Accept packets arriving from the wire. The endpoint does not
        reorder — out-of-order packets wait in the buffer."""
        state = self._require(circuit_id)
        for p in packets:
            if p.circuit_id != circuit_id:
                raise ValueError(
                    f"packet for circuit {p.circuit_id!r} ingested into {circuit_id!r}"
                )
            if p.seq < state.recv_expected or p.seq in state.recv_buffer:
                continue  # duplicate or already delivered: ignore
            state.recv_buffer[p.seq] = p.data
        # release only the contiguous prefix — in-order, always
        while state.recv_expected in state.recv_buffer:
            state.ready.extend(state.recv_buffer.pop(state.recv_expected))
            state.recv_expected += 1

    def missing(self, circuit_id: str, through_seq: int) -> list[int]:
        """Sequence numbers awaited up to through_seq: retransmit requests."""
        state = self._require(circuit_id)
        if through_seq < 0:
            raise ValueError("through_seq must be >= 0")
        return [
            s
            for s in range(state.recv_expected, through_seq + 1)
            if s not in state.recv_buffer
        ]

    def deliver(self, circuit_id: str) -> bytes:
        """In-order bytes available so far; consumes them."""
        state = self._require(circuit_id)
        out = bytes(state.ready)
        state.ready.clear()
        return out

    def mark_acked(self, circuit_id: str, seq: int) -> None:
        """Record that the far end received seq (lets retransmit deny)."""
        state = self._require(circuit_id)
        if seq not in state.sent:
            raise ValueError(f"circuit {circuit_id!r}: unknown seq {seq}")
        state.acked.add(seq)
