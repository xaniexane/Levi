"""CSNET: the adapter pattern at national scale.

Origin: the Computer Science Network (1981-1991), NSF-funded by Landweber
and colleagues to network the computer-science departments ARPANET excluded
— ~200 sites at peak across 15 countries. It had three parts: Phonenet
dial-up email relay (MMDF), a white-pages name server at Wisconsin, and
TCP/IP-over-X.25 tunneling from Purdue across commercial Telenet circuits.
Instead of demanding a new network, CSNET glued heterogeneous transports
(dial-up, X.25 public data nets, ARPANET) under one interface, tunneled one
protocol over another, and multiplexed sessions to dodge per-circuit setup
charges. It was also the first community-network Coordination and
Information Center — the prototype ISP.

What it is in LEVI: a TransportAdapter registry. Transports register with
cost profiles (per-session setup cost, per-KB cost, reliability, capacity);
``select_route`` picks the cheapest transport that meets a reliability
floor; ``tunnel`` wraps a payload for carriage on a named transport and
``untunnel`` restores it; ``multiplex`` batches sessions onto one carrier to
amortize the setup cost.

Honesty label: LOAD-BEARING — adapter registry + cost-aware route
selection + tunneling roundtrip is a concrete, transferable mechanism.

Deny-closed inputs: empty or duplicate transport ids, negative costs,
reliability outside 0..1, non-positive payload sizes, reliability floors
outside 0..1, no transport meeting the floor, unknown carriers, empty
sessions, sessions larger than the carrier's capacity, and untunneling a
frame whose carrier is unknown all raise ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "Transport",
    "TunnelFrame",
    "MultiplexBatch",
    "AdapterRegistry",
    "MAX_SESSIONS_PER_BATCH",
]

MAX_SESSIONS_PER_BATCH = 64


@dataclass
class Transport:
    id: str
    name: str
    setup_cost: float  # per-session cost (circuit setup, dial charges)
    cost_per_kb: float
    reliability: float  # 0..1
    max_kb: float  # largest payload this transport carries per session


@dataclass
class TunnelFrame:
    carrier_id: str
    payload: bytes


@dataclass
class MultiplexBatch:
    carrier_id: str
    sessions: tuple[bytes, ...]
    sessions_saved: int  # setup charges avoided vs one circuit each


class AdapterRegistry:
    """Heterogeneous transports under one interface, CSNET-style."""

    def __init__(self) -> None:
        self._transports: dict[str, Transport] = {}

    def register(self, transport: Transport) -> Transport:
        tid = transport.id
        if not isinstance(tid, str) or not tid.strip():
            raise ValueError("transport id must be a non-empty string")
        if tid in self._transports:
            raise ValueError(f"duplicate transport: {tid!r}")
        if not transport.name or not transport.name.strip():
            raise ValueError(f"transport {tid!r}: name must be non-empty")
        if transport.setup_cost < 0:
            raise ValueError(f"transport {tid!r}: setup_cost must be >= 0")
        if transport.cost_per_kb < 0:
            raise ValueError(f"transport {tid!r}: cost_per_kb must be >= 0")
        if not 0.0 <= transport.reliability <= 1.0:
            raise ValueError(f"transport {tid!r}: reliability must be in 0..1")
        if transport.max_kb <= 0:
            raise ValueError(f"transport {tid!r}: max_kb must be positive")
        self._transports[tid] = transport
        return transport

    def transports(self) -> list[Transport]:
        return list(self._transports.values())

    def _require_carrier(self, carrier_id: str) -> Transport:
        carrier = self._transports.get(carrier_id)
        if carrier is None:
            raise ValueError(f"unknown carrier: {carrier_id!r}")
        return carrier

    def select_route(self, size_kb: float, min_reliability: float = 0.0) -> Transport:
        """Cheapest transport that meets the reliability floor."""
        if not isinstance(size_kb, (int, float)) or size_kb <= 0:
            raise ValueError(f"size_kb must be positive, got {size_kb!r}")
        if not 0.0 <= min_reliability <= 1.0:
            raise ValueError("min_reliability must be in 0..1")
        eligible = [
            t
            for t in self._transports.values()
            if t.reliability >= min_reliability and t.max_kb >= size_kb
        ]
        if not eligible:
            raise ValueError(
                f"no transport meets reliability>={min_reliability} for {size_kb} KB"
            )
        return min(eligible, key=lambda t: t.setup_cost + t.cost_per_kb * size_kb)

    def route_cost(self, transport_id: str, size_kb: float) -> float:
        t = self._require_carrier(transport_id)
        if size_kb <= 0:
            raise ValueError("size_kb must be positive")
        return t.setup_cost + t.cost_per_kb * size_kb

    def tunnel(self, payload: bytes, carrier_id: str) -> TunnelFrame:
        """Wrap a payload for carriage on the named transport."""
        carrier = self._require_carrier(carrier_id)
        if not isinstance(payload, (bytes, bytearray)) or len(payload) == 0:
            raise ValueError("tunnel payload must be non-empty bytes")
        if len(payload) / 1024 > carrier.max_kb:
            raise ValueError(
                f"payload {len(payload)} bytes exceeds carrier {carrier_id!r} "
                f"capacity of {carrier.max_kb} KB"
            )
        return TunnelFrame(carrier_id=carrier_id, payload=bytes(payload))

    @staticmethod
    def untunnel(frame: TunnelFrame, registry: "AdapterRegistry") -> bytes:
        """Restore the original payload; the carrier must still be known."""
        if not isinstance(frame, TunnelFrame):
            raise ValueError(f"not a tunnel frame: {frame!r}")
        registry._require_carrier(frame.carrier_id)
        return frame.payload

    def multiplex(self, sessions: list[bytes], carrier_id: str) -> list[MultiplexBatch]:
        """Batch sessions onto one carrier to dodge per-circuit setup cost."""
        carrier = self._require_carrier(carrier_id)
        if not sessions:
            raise ValueError("multiplex needs at least one session")
        for s in sessions:
            if not isinstance(s, (bytes, bytearray)) or len(s) == 0:
                raise ValueError("sessions must be non-empty bytes")
            if len(s) / 1024 > carrier.max_kb:
                raise ValueError(
                    f"session of {len(s)} bytes exceeds carrier {carrier_id!r} "
                    f"capacity of {carrier.max_kb} KB"
                )
        batches: list[MultiplexBatch] = []
        current: list[bytes] = []
        current_kb = 0.0
        for s in sessions:
            kb = len(s) / 1024
            if current and (
                current_kb + kb > carrier.max_kb
                or len(current) >= MAX_SESSIONS_PER_BATCH
            ):
                batches.append(
                    MultiplexBatch(
                        carrier_id=carrier_id,
                        sessions=tuple(current),
                        sessions_saved=len(current) - 1,
                    )
                )
                current, current_kb = [], 0.0
            current.append(bytes(s))
            current_kb += kb
        if current:
            batches.append(
                MultiplexBatch(
                    carrier_id=carrier_id,
                    sessions=tuple(current),
                    sessions_saved=len(current) - 1,
                )
            )
        return batches
