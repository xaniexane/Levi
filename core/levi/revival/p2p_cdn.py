"""p2p_cdn — hybrid edge offload: let peers carry the bandwidth.

Studied from: hybrid-cost-cutting-combos-20260916-0006/report.md
[§6 — honorable-mention caveat].

Shape studied: peer-assisted content delivery that shifts 55–75% of
edge bandwidth onto viewers' own upstream — relevant only at scale
(the studied caveat: on the order of ~50K concurrent viewers).

Mechanism (simulated in-process, no network):
* content is split into segments; each peer holds a subset (a bitset)
* Swarm.step(): every incomplete peer fetches its rarest missing
  segment — from a neighbor that has it when one exists (peer-served),
  otherwise from the origin (origin-served)
* tit-for-tat-ish choking: a peer that only takes and never gives is
  deprioritized as a source, so freeloaders converge last
* offload_ratio(): peer-served bytes / total bytes served
* flash_crowd(): viewers arrive on a ramp, a few seeders start with the
  full file; reports the measured offload at scale

Honest limits: this is a discrete-step simulation of a rarest-first
piece exchange, not a real network — no latency, no NAT, no churn
modeling beyond join order, no encryption. The 55–75% band is the
studied shape; what the simulation measures depends on the scenario
you feed it (seeders, segments, arrival ramp).

This is an original, from-scratch implementation for LEVI.
Not artificial. Synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

ORIGIN = "levi-revival/p2p_cdn"


@dataclass
class Peer:
    """One viewer in the swarm."""

    peer_id: str
    segments: Set[int] = field(default_factory=set)
    gave: int = 0  # segments uploaded to others
    took: int = 0  # segments downloaded from peers

    def freeloader_score(self) -> float:
        """Higher means takes a lot, gives little — deprioritized source."""
        return self.took / (1 + self.gave)


@dataclass
class SwarmReport:
    ticks: int
    peer_served_bytes: int
    origin_served_bytes: int
    segment_bytes: int

    @property
    def total_bytes(self) -> int:
        return self.peer_served_bytes + self.origin_served_bytes

    @property
    def offload_ratio(self) -> float:
        """Fraction of bytes served peer-to-peer (0..1)."""
        if self.total_bytes == 0:
            return 0.0
        return self.peer_served_bytes / self.total_bytes


class Swarm:
    """A rarest-first piece-exchange swarm, simulated in discrete ticks."""

    def __init__(self, n_segments: int, segment_bytes: int = 256 * 1024):
        if n_segments < 1:
            raise ValueError("n_segments must be >= 1")
        self.n_segments = n_segments
        self.segment_bytes = segment_bytes
        self.peers: List[Peer] = []
        self.peer_served = 0
        self.origin_served = 0
        self.ticks = 0

    def add_peer(self, peer_id: str, seeder: bool = False) -> Peer:
        if any(p.peer_id == peer_id for p in self.peers):
            raise ValueError(f"duplicate peer_id {peer_id!r}")
        peer = Peer(peer_id=peer_id)
        if seeder:
            peer.segments = set(range(self.n_segments))
        self.peers.append(peer)
        return peer

    def is_complete(self, peer: Peer) -> bool:
        return len(peer.segments) >= self.n_segments

    def _rarity(self) -> Dict[int, int]:
        counts = {s: 0 for s in range(self.n_segments)}
        for peer in self.peers:
            for s in peer.segments:
                counts[s] += 1
        return counts

    def step(self) -> int:
        """One tick: every incomplete peer fetches one segment.

        Returns the number of fetches performed this tick.
        """
        rarity = self._rarity()
        fetches = 0
        for peer in self.peers:
            if self.is_complete(peer):
                continue
            missing = [s for s in range(self.n_segments) if s not in peer.segments]
            missing.sort(key=lambda s: rarity[s])
            segment = missing[0]
            # Prefer generous neighbors; freeloaders serve last.
            sources = sorted(
                (p for p in self.peers if p is not peer and segment in p.segments),
                key=lambda p: p.freeloader_score(),
            )
            if sources:
                src = sources[0]
                src.gave += 1
                peer.took += 1
                self.peer_served += self.segment_bytes
            else:
                self.origin_served += self.segment_bytes
            peer.segments.add(segment)
            rarity[segment] += 1
            fetches += 1
        self.ticks += 1
        return fetches

    def run(self, max_ticks: int = 10_000) -> SwarmReport:
        """Step until every peer is complete or the tick budget is spent."""
        while self.ticks < max_ticks and any(
            not self.is_complete(p) for p in self.peers
        ):
            self.step()
        return SwarmReport(
            ticks=self.ticks,
            peer_served_bytes=self.peer_served,
            origin_served_bytes=self.origin_served,
            segment_bytes=self.segment_bytes,
        )


def flash_crowd(
    n_viewers: int,
    n_segments: int = 32,
    n_seeders: int = 3,
    segment_bytes: int = 256 * 1024,
) -> SwarmReport:
    """Simulate a flash crowd: seeders first, viewers join over ticks.

    Viewers arrive a few per tick (the ramp); each tick every present
    peer fetches one segment. Returns the measured offload report.
    """
    if n_viewers < 1:
        raise ValueError("n_viewers must be >= 1")
    swarm = Swarm(n_segments=n_segments, segment_bytes=segment_bytes)
    for i in range(n_seeders):
        swarm.add_peer(f"seeder-{i}", seeder=True)
    joined = 0
    per_tick = max(1, n_viewers // 20)
    while joined < n_viewers or any(not swarm.is_complete(p) for p in swarm.peers):
        for _ in range(min(per_tick, n_viewers - joined)):
            swarm.add_peer(f"viewer-{joined}")
            joined += 1
        swarm.step()
        if swarm.ticks > 100_000:  # pragma: no cover - safety valve
            break
    return SwarmReport(
        ticks=swarm.ticks,
        peer_served_bytes=swarm.peer_served,
        origin_served_bytes=swarm.origin_served,
        segment_bytes=swarm.segment_bytes,
    )
