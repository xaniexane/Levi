"""Delay-tolerant routing — the paired mind at the protocol layer.

The PROPOSER drafts a forwarding plan; the VERIFIER checks it against
policy before a single byte moves. No plan transmits without both minds
agreeing — the tower never forwards on one mind's say-so.

Routing honors the tri-state link model: UP peers carry everything,
DEGRADED peers carry EMERGENCY only, DOWN peers carry nothing. Route
choices are deterministic (lowest node id wins) so two towers always
agree on the same plan for the same state — no deceptive routing, and
every decision is written to the audit log.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .protocol import (
    MAX_PAYLOAD,
    LinkState,
    Packet,
    PolicyDenied,
    Priority,
)

# Dedupe window: (src, seq) pairs remembered to kill loops and floods.
SEEN_CAPACITY = 4096


@dataclass(frozen=True)
class RoutePlan:
    next_hop: bytes
    note: str


class Proposer:
    """Drafts where a packet should go next. Never transmits — only proposes."""

    def propose(
        self,
        packet: Packet,
        links: dict[bytes, LinkState],
        exclude: frozenset[bytes] = frozenset(),
    ) -> RoutePlan | None:
        """Pick the next hop. Returns None when there is honestly no route."""
        candidates = [
            peer_id
            for peer_id, state in links.items()
            if peer_id not in exclude and peer_id != packet.src
        ]
        up = [p for p in candidates if links[p] is LinkState.UP]
        if up:
            nxt = min(up)
            return RoutePlan(next_hop=nxt, note=f"UP peer {nxt.hex()}")
        # The third state earns its keep: degraded links still move
        # emergency traffic when nothing healthy remains.
        if packet.priority is Priority.EMERGENCY:
            degraded = [p for p in candidates if links[p] is LinkState.DEGRADED]
            if degraded:
                nxt = min(degraded)
                return RoutePlan(
                    next_hop=nxt,
                    note=f"DEGRADED peer {nxt.hex()} (emergency only)",
                )
        return None


class Verifier:
    """Checks a proposed plan against policy. Refusals raise PolicyDenied."""

    def verify(
        self,
        plan: RoutePlan,
        packet: Packet,
        *,
        channel_joined: bool,
        loopback_ok: bool,
    ) -> None:
        if packet.ttl <= 0:
            raise PolicyDenied("hop budget exhausted — packet dies here")
        if len(packet.payload) > MAX_PAYLOAD:
            raise PolicyDenied("packet exceeds maximum payload")
        if not channel_joined:
            raise PolicyDenied("not a member of this channel — refusing to relay")
        if not loopback_ok:
            raise PolicyDenied("non-loopback transport refused by owner policy")
        if plan.next_hop == packet.src:
            raise PolicyDenied("plan routes back to the source — loop refused")
        if not plan.next_hop:
            raise PolicyDenied("empty next hop")


class Forwarder:
    """Loop and flood suppression: every (src, seq) is forwarded at most once."""

    def __init__(self, capacity: int = SEEN_CAPACITY):
        self._capacity = capacity
        self._seen: set[tuple[bytes, int]] = set()
        self._order: deque[tuple[bytes, int]] = deque()

    def seen(self, src: bytes, seq: int) -> bool:
        return (bytes(src), seq) in self._seen

    def mark(self, src: bytes, seq: int) -> None:
        key = (bytes(src), seq)
        if key in self._seen:
            return
        self._seen.add(key)
        self._order.append(key)
        while len(self._order) > self._capacity:
            self._seen.discard(self._order.popleft())


__all__ = ["RoutePlan", "Proposer", "Verifier", "Forwarder", "SEEN_CAPACITY"]
