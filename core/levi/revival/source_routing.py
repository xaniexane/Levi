"""Source routing in the address: bang paths.

Studied from: protocols-hunt-20260916-0041 (Find 2 - UUCP section of report.md).
In bang-path routing (``host1!host2!host3!user``) the sender carries the
full route inside the address itself, because no node on the path knows
more than one hop: each node hands the packet to the next named hop and
forgets the rest. The route is chosen by the sender, who does know the
map; intermediate nodes never consult a routing table.

This module implements the address algebra (parse/format/validate) and a
hop-by-hop delivery simulation in which each forwarding step is allowed
to know only the current hop and the next one. Reply routes are the
travelled path reversed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "RoutingError",
    "MalformedAddress",
    "NoSuchHop",
    "BangPath",
    "parse_bang_path",
    "forward_step",
    "deliver",
]

ORIGIN = "levi-revival/bang-paths"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RoutingError(Exception):
    """Base class for source-routing failures."""


class MalformedAddress(RoutingError):
    """The address does not parse as a bang path."""


class NoSuchHop(RoutingError):
    """A hop is not adjacent to the node being asked to forward to it."""


# ---------------------------------------------------------------------------
# Address
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BangPath:
    """A source-routed address: ordered hops plus the final recipient.

    ``hops[0]`` is the first relay after the sender, ``hops[-1]`` the
    last relay before ``recipient``. A direct address has no hops.
    """

    hops: tuple[str, ...]
    recipient: str

    def format(self) -> str:
        return "!".join((*self.hops, self.recipient))


def _check_token(token: str, what: str) -> str:
    token = token.strip()
    if not token or "!" in token or any(ch.isspace() for ch in token):
        raise MalformedAddress(f"invalid {what}: {token!r}")
    return token


def parse_bang_path(address: str) -> BangPath:
    """Parse ``host1!host2!user`` into hops and recipient.

    A single bare token is a direct address (no hops). Empty segments,
    whitespace, or an empty address raise MalformedAddress.
    """
    if not isinstance(address, str) or not address:
        raise MalformedAddress("address must be a non-empty string")
    parts = address.split("!")
    if any(p == "" for p in parts):
        raise MalformedAddress(f"empty segment in {address!r}")
    tokens = [_check_token(p, "segment") for p in parts]
    return BangPath(hops=tuple(tokens[:-1]), recipient=tokens[-1])


# ---------------------------------------------------------------------------
# Delivery: each step knows only the current hop and the next one
# ---------------------------------------------------------------------------


def forward_step(current: str, next_hop: str, neighbours: set[str]) -> str:
    """One forwarding decision at node ``current``.

    The node may know only its own adjacency: it forwards to ``next_hop``
    iff that hop is a direct neighbour, else refuses with NoSuchHop.
    """
    if next_hop not in neighbours:
        raise NoSuchHop(f"{current!r} cannot reach {next_hop!r}: not a neighbour")
    return next_hop


@dataclass
class Delivery:
    """Record of a completed hop-by-hop delivery."""

    route: BangPath
    visited: list[str]
    reversed_route: BangPath = field(init=False)

    def __post_init__(self) -> None:
        # The reply address is the travelled route walked backwards:
        # recipient -> last relay -> ... -> first relay -> sender's entry point.
        self.reversed_route = BangPath(
            hops=tuple(reversed(self.visited[1:])),
            recipient=self.visited[0],
        )


def deliver(
    address: str,
    start: str,
    adjacency: dict[str, set[str]],
) -> Delivery:
    """Deliver a bang-path message hop by hop from ``start``.

    ``adjacency`` maps node -> its known direct neighbours. ``start`` is the
    sender (or entry node); the first hop must be adjacent to it. Each
    intermediate node validates only its own next hop — no node consults a
    routing table. Returns the visited nodes and the reply (reversed) route.
    """
    route = parse_bang_path(address)
    visited: list[str] = [start]
    current = start
    for hop in route.hops:
        current = forward_step(current, hop, adjacency.get(current, set()))
        visited.append(current)
    return Delivery(route=route, visited=visited)
