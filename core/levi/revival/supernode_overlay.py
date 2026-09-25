"""The elected backbone: supernodes carry the overlay.

Studied from: dead-networks-20260916/report.md (Skype)

The load-bearing mechanism: most peers are weak (behind NAT, low
uptime), so the overlay elects a few *supernodes* — well-connected,
long-lived machines — that hold the peer index and relay traffic the
weak peers cannot exchange directly. Elections are local and periodic:
any eligible peer may promote itself; demotion follows missed
heartbeats. No central registry is needed.

This is an original, from-scratch LEVI implementation — no historical
code is used or copied. Stdlib only, no network.

Honesty: the mechanism revived is eligibility-based supernode election
with heartbeat liveness and index/relay duties. Not revived: real NAT
traversal — "reachability" is a peer attribute, not a measured probe.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


ORIGIN = "levi-revival/supernode-overlay"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class OverlayError(Exception):
    """Base class for overlay failures."""


class PeerRole(str, Enum):
    ORDINARY = "ordinary"
    SUPERNODE = "supernode"


@dataclass
class Peer:
    """One participant in the overlay."""

    peer_id: str
    reachable: bool = True  # not stuck behind NAT
    uptime_rounds: int = 0  # longevity; supernodes must be proven
    bandwidth: int = 1  # abstract capacity units
    heartbeats_missed: int = 0
    role: PeerRole = PeerRole.ORDINARY

    def eligible(self, min_uptime: int = 3) -> bool:
        return (
            self.reachable and self.bandwidth >= 2 and self.uptime_rounds >= min_uptime
        )


class SupernodeOverlay:
    """The overlay: peers, elections, index, and relay.

    The index maps peer_id -> list of supernodes holding its record
    (ordinaries register with their nearest supernode). Relay carries a
    message from one ordinary to another through a supernode when no
    direct path exists (either side unreachable); delivered directly
    otherwise.
    """

    MAX_MISSED = 3  # heartbeats before a supernode is demoted

    def __init__(self) -> None:
        self.peers: dict[str, Peer] = {}
        self.index: dict[str, list[str]] = {}  # peer_id -> supernode ids
        self.relayed: int = 0
        self.direct: int = 0

    # -- membership ------------------------------------------------------------

    def join(self, peer: Peer) -> None:
        if peer.peer_id in self.peers:
            raise OverlayError(f"duplicate peer: {peer.peer_id}")
        self.peers[peer.peer_id] = peer
        self._register(peer.peer_id)

    def leave(self, peer_id: str) -> None:
        peer = self.peers.pop(peer_id, None)
        if peer is None:
            raise OverlayError(f"unknown peer: {peer_id}")
        self.index.pop(peer_id, None)
        for holders in self.index.values():
            if peer_id in holders:
                holders.remove(peer_id)
        if peer.role == PeerRole.SUPERNODE:
            self.elect()  # repair the backbone promptly

    # -- election ---------------------------------------------------------------

    def supernodes(self) -> list[str]:
        return [
            p
            for p, peer in sorted(self.peers.items())
            if peer.role == PeerRole.SUPERNODE
        ]

    def elect(self, target: int = 3, min_uptime: int = 3) -> list[str]:
        """Promote the best eligible peers until the backbone is full.

        Picks the highest-bandwidth, longest-lived eligible peers; ties
        break on peer_id so elections are deterministic.
        """
        current = set(self.supernodes())
        candidates = sorted(
            (
                p
                for p, peer in self.peers.items()
                if peer.role == PeerRole.ORDINARY
                and peer.heartbeats_missed == 0  # recently-demoted must re-earn trust
                and peer.eligible(min_uptime)
            ),
            key=lambda p: (-self.peers[p].bandwidth, -self.peers[p].uptime_rounds, p),
        )
        for peer_id in candidates:
            if len(current) >= target:
                break
            self.peers[peer_id].role = PeerRole.SUPERNODE
            current.add(peer_id)
        # Re-register everyone against the fresh backbone.
        for peer_id in list(self.index):
            self._register(peer_id)
        return sorted(current)

    def heartbeat(self, peer_id: str, alive: bool = True) -> None:
        """Record one heartbeat; demote supernodes that go quiet."""
        peer = self.peers.get(peer_id)
        if peer is None:
            raise OverlayError(f"unknown peer: {peer_id}")
        if alive:
            peer.heartbeats_missed = 0
            peer.uptime_rounds += 1
        else:
            peer.heartbeats_missed += 1
            if (
                peer.role == PeerRole.SUPERNODE
                and peer.heartbeats_missed >= self.MAX_MISSED
            ):
                peer.role = PeerRole.ORDINARY
                self.elect()

    # -- index / relay ------------------------------------------------------------

    def _register(self, peer_id: str) -> None:
        supers = self.supernodes()
        self.index[peer_id] = supers[:2] if supers else []

    def lookup(self, peer_id: str) -> list[str]:
        """Supernodes holding the index record for a peer."""
        return list(self.index.get(peer_id, []))

    def route(self, sender: str, recipient: str) -> str:
        """Decide direct vs relayed; return the path taken as text.

        Returns "direct" when both ends are reachable, else the id of
        the supernode that relays. Raises when there is no route at
        all (no supernode and at least one end unreachable).
        """
        if sender not in self.peers or recipient not in self.peers:
            raise OverlayError("unknown sender or recipient")
        src, dst = self.peers[sender], self.peers[recipient]
        if src.reachable and dst.reachable:
            self.direct += 1
            return "direct"
        supers = self.supernodes()
        if not supers:
            raise OverlayError("no route: no supernodes in the overlay")
        self.relayed += 1
        return supers[0]

    def stats(self) -> dict[str, int]:
        return {
            "peers": len(self.peers),
            "supernodes": len(self.supernodes()),
            "direct": self.direct,
            "relayed": self.relayed,
        }
