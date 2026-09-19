"""Rural BBS — a dialup store-and-forward network.

Studied from: dead-networks-20260916, report.md [Big Sky Telegraph].

The mechanism, functionally: low-cost dialup links a region of rural
nodes in a store-and-forward mesh. Nobody is online at the same time —
a node queues outbound packets, dials its neighbor during a scheduled
window, dumps the queue, and hangs up; the neighbor holds and forwards.
Messages carry hop counts so loops die. On top of the transport sits
the real cargo: shared message boards, including train-the-trainer
curricula for grassroots digital literacy.

This module is a software analog of that pattern: ``RuralNode`` (local
boards, outbox/inbox, neighbor table with dial windows), ``Packet``
(messages with hop limits), and ``dial`` (the windowed exchange that
moves queued packets one hop). The dialup medium is simulated —
in-memory queues, no sockets — because the mechanism is the
store-and-forward discipline, not the modem.

Honesty: dial windows and transfers are simulated instantaneously
within a call; real modems had noise, drops, and per-minute costs,
none of which this models. Hop limits bound loops but a sparse mesh
can still strand a packet with no path home.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Set

ORIGIN = "levi-revival/rural-bbs"

DEFAULT_MAX_HOPS = 8


@dataclass
class Packet:
    """A store-and-forward unit: payload, route so far, hop budget."""

    _seq = 0

    id: str = field(init=False)
    kind: str = "message"  # message | curriculum | bulletin
    board: str = "general"
    sender: str = ""
    subject: str = ""
    body: str = ""
    origin: str = ""
    destination: Optional[str] = None  # None = flood to all reachable nodes
    hops: int = 0
    max_hops: int = DEFAULT_MAX_HOPS
    created_at: float = field(default_factory=time.time)
    route: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        Packet._seq += 1
        self.id = f"pkt{Packet._seq:06d}"

    @property
    def expired(self) -> bool:
        return self.hops >= self.max_hops

    def hop(self, node: str) -> "Packet":
        self.hops += 1
        self.route.append(node)
        return self


@dataclass
class Neighbor:
    """A dialup peer: reachable only inside its window."""

    name: str
    window_start: float = 0.0  # seconds past midnight, local node time
    window_end: float = 86400.0


class RuralNode:
    """One BBS node: boards, queues, and the discipline of the dial."""

    def __init__(self, name: str, max_hops: int = DEFAULT_MAX_HOPS) -> None:
        self.name = name
        self.max_hops = max_hops
        self.boards: Dict[str, List[Packet]] = defaultdict(list)
        self.outbox: Deque[Packet] = deque()
        self.inbox: Deque[Packet] = deque()
        self.neighbors: Dict[str, Neighbor] = {}
        self.seen: Set[str] = set()
        self.dial_log: List[Dict] = []

    # -- authoring: what the network is FOR --------------------------------

    def post(
        self,
        board: str,
        subject: str,
        body: str,
        sender: Optional[str] = None,
        destination: Optional[str] = None,
        kind: str = "message",
    ) -> Packet:
        """Write locally and queue for the mesh: write once, the dial
        carries it."""
        pkt = Packet(
            kind=kind,
            board=board,
            sender=sender or self.name,
            subject=subject.strip(),
            body=body,
            origin=self.name,
            destination=destination,
            max_hops=self.max_hops,
            route=[self.name],
        )
        self.seen.add(pkt.id)
        self.boards[board].append(pkt)
        if destination != self.name:
            self.outbox.append(pkt)
        return pkt

    def publish_curriculum(
        self, subject: str, lessons: List[str], sender: Optional[str] = None
    ) -> Packet:
        """Train-the-trainer cargo: a curriculum is a packet like any
        other, so it rides the same cheap dialup."""
        body = "\n\n".join(
            f"Lesson {i + 1}: {lesson}" for i, lesson in enumerate(lessons)
        )
        return self.post("curricula", subject, body, sender=sender, kind="curriculum")

    def read_board(self, board: str) -> List[Packet]:
        return list(self.boards[board])

    def board_names(self) -> List[str]:
        return sorted(self.boards)

    # -- the mesh -----------------------------------------------------------

    def add_neighbor(
        self, name: str, window_start: float = 0.0, window_end: float = 86400.0
    ) -> None:
        self.neighbors[name] = Neighbor(name, window_start, window_end)

    def window_open(self, neighbor: str, now: float) -> bool:
        nb = self.neighbors.get(neighbor)
        if nb is None:
            return False
        tod = now % 86400.0
        return nb.window_start <= tod < nb.window_end

    def dial(self, peer: "RuralNode", now: Optional[float] = None) -> Dict:
        """One dialup session: exchange outboxes within the window.

        Each side hands over queued packets addressed onward; packets
        already seen are dropped; hop budgets decrement toward death.
        Returns a session report.
        """
        now = now if now is not None else time.time()
        report = {
            "from": self.name,
            "to": peer.name,
            "sent": 0,
            "received": 0,
            "dropped_seen": 0,
            "dropped_expired": 0,
            "window_open": True,
        }
        if not self.window_open(peer.name, now):
            report["window_open"] = False
            return report
        sent = self._flush_to(peer)
        received = peer._flush_to(self)
        for key, value in (("sent", sent), ("received", received)):
            report[key] = value[0]
            report["dropped_seen"] += value[1]
            report["dropped_expired"] += value[2]
        self.dial_log.append(
            {
                "at": now,
                "peer": peer.name,
                "sent": report["sent"],
                "received": report["received"],
            }
        )
        return report

    def _flush_to(self, peer: "RuralNode") -> tuple:
        """Move my outbox one hop toward the peer. Returns (delivered,
        dropped_seen, dropped_expired)."""
        delivered, dropped_seen, dropped_expired = 0, 0, 0
        remaining: Deque[Packet] = deque()
        while self.outbox:
            pkt = self.outbox.popleft()
            pkt.hop(peer.name)
            if pkt.id in peer.seen:
                dropped_seen += 1
                continue
            if pkt.expired:
                dropped_expired += 1
                continue
            peer._receive(pkt)
            delivered += 1
            # Flood packets keep traveling; addressed ones only if not home.
            if pkt.destination is None or pkt.destination != peer.name:
                peer.outbox.append(pkt)
            else:
                # keep a copy queued in case the destination wants to relay;
                # addressed packets rest here once home.
                pass
        self.outbox = remaining
        return delivered, dropped_seen, dropped_expired

    def _receive(self, pkt: Packet) -> None:
        self.seen.add(pkt.id)
        self.inbox.append(pkt)
        if pkt.destination is None or pkt.destination == self.name:
            self.boards[pkt.board].append(pkt)

    def pending_outbound(self) -> int:
        return len(self.outbox)
