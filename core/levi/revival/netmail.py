"""Address-routed private mail for networks that sleep.

Studied from: protocols-hunt-20260916-0041/report.md (Find 1 - FidoNet)

The load-bearing mechanism: private messages are addressed
*hierarchically* (zone:network/node.point) and routed store-and-forward
across machines that connect only occasionally. Each hop keeps the mail
until the next hop picks it up; delivery is eventual, confirmed by
receipt, never assumed.

This is an original, from-scratch LEVI implementation — no historical
code is used or copied. Stdlib only, no network.

Honesty: the mechanism revived is hierarchical address routing with
store-and-forward hand-offs and delivery receipts. Not revived: real
modem handshakes or binary packet formats — routing decisions are the
revival target, not the wire encoding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime


ORIGIN = "levi-revival/netmail"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class NetmailError(Exception):
    """Base class for netmail failures."""


_ADDRESS_RE = re.compile(r"^(?:(\d+):)?(?:(\d+)/)?(\d+)(?:\.(\d+))?$")


@dataclass(frozen=True)
class NetAddress:
    """Hierarchical node address: zone:network/node.point."""

    zone: int
    network: int
    node: int
    point: int = 0

    @classmethod
    def parse(cls, text: str) -> "NetAddress":
        match = _ADDRESS_RE.match(text.strip())
        if not match:
            raise NetmailError(f"invalid netmail address: {text!r}")
        zone, network, node, point = match.groups()
        return cls(
            zone=int(zone or 0),
            network=int(network or 0),
            node=int(node),
            point=int(point or 0),
        )

    def same_hub(self, other: "NetAddress") -> bool:
        """Share the same zone:network/node (points ignored)."""
        return (self.zone, self.network, self.node) == (
            other.zone,
            other.network,
            other.node,
        )

    def __str__(self) -> str:
        base = f"{self.zone}:{self.network}/{self.node}"
        return f"{base}.{self.point}" if self.point else base


@dataclass
class NetmailMessage:
    """One private store-and-forward message."""

    msg_id: str
    sender: NetAddress
    recipient: NetAddress
    subject: str
    body: str
    sent_at: str = field(default_factory=lambda: datetime.now().isoformat())
    path: list[str] = field(default_factory=list)  # hops it has passed
    receipt: str | None = None  # filled on confirmed delivery


# ---------------------------------------------------------------------------
# Node inbox/outbox
# ---------------------------------------------------------------------------


class NetmailNode:
    """One machine in the netmail mesh.

    Holds an inbox (received), an outbox (queued for next hop), and
    knows its neighbors so it can pick a next hop toward a recipient:
    prefer a neighbor on the same hub, else the neighbor with the
    smallest zone gap (a simple greedy heuristic — this is routing
    strategy, not real topology discovery).
    """

    def __init__(self, address: NetAddress) -> None:
        self.address = address
        self.neighbors: dict[str, NetAddress] = {}  # name -> address
        self.inbox: list[NetmailMessage] = []
        self.outbox: list[NetmailMessage] = []

    # -- topology ---------------------------------------------------------

    def add_neighbor(self, name: str, address: NetAddress) -> None:
        self.neighbors[name] = address

    def next_hop(self, recipient: NetAddress) -> str:
        """Pick the best neighbor name toward ``recipient``."""
        if not self.neighbors:
            raise NetmailError(f"{self.address}: no neighbors to route via")
        for name, addr in self.neighbors.items():
            if addr.same_hub(recipient):
                return name

        # Greedy heuristic: minimize zone, then network, then node distance.
        def cost(addr: NetAddress) -> tuple[int, int, int]:
            return (
                abs(addr.zone - recipient.zone),
                abs(addr.network - recipient.network),
                abs(addr.node - recipient.node),
            )

        return min(self.neighbors, key=lambda n: cost(self.neighbors[n]))

    # -- queueing -----------------------------------------------------------

    def send(self, msg: NetmailMessage) -> None:
        """Place a message in the outbox for the next connection."""
        if msg.sender != self.address and not any(
            n == msg.sender for n in self.neighbors.values()
        ):
            # Allow originating here or relaying — both are legitimate.
            pass
        msg.path.append(str(self.address))
        self.outbox.append(msg)

    # -- connection -----------------------------------------------------------

    def connect(self, neighbor_name: str, other: "NetmailNode") -> None:
        """Simulate a poll: push outbox mail bound toward the neighbor.

        The neighbor accepts mail it either owns or can forward; anything
        addressed to us stays; everything else rides the next hop. This
        models one connection event, not a real link.
        """
        if neighbor_name not in self.neighbors:
            raise NetmailError(f"unknown neighbor: {neighbor_name}")
        if self.neighbors[neighbor_name] != other.address:
            raise NetmailError("neighbor address mismatch — refusing link")
        remaining: list[NetmailMessage] = []
        for msg in self.outbox:
            hop = self.next_hop(msg.recipient)
            if hop == neighbor_name:
                other._receive(msg)
            else:
                remaining.append(msg)
        self.outbox = remaining

    def _receive(self, msg: NetmailMessage) -> None:
        msg.path.append(str(self.address))
        if msg.recipient == self.address:
            msg.receipt = datetime.now().isoformat()
            self.inbox.append(msg)
        else:
            self.outbox.append(msg)  # keep forwarding next connection

    # -- queries ------------------------------------------------------------

    def unread(self) -> list[NetmailMessage]:
        return list(self.inbox)

    def pending_for(self, recipient: NetAddress) -> list[NetmailMessage]:
        return [m for m in self.outbox if m.recipient == recipient]
