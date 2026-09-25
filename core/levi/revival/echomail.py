"""Networked public conferences for intermittent networks.

Studied from: protocols-hunt-20260916-0041/report.md (Find 1 - FidoNet)

The load-bearing mechanism: named public conferences ("echoes") carry
messages between members; each site keeps the full conference locally,
and sites exchange *what the other site is missing* during brief
connections. Duplicates are suppressed by message identity, not by
trust — a message seen before is never stored twice, no matter how
many paths deliver it.

This is an original, from-scratch LEVI implementation — no historical
code is used or copied. Stdlib only, no network.

Honesty: the mechanism revived is echo-based distribution with
duplicate suppression and incremental exchange. Not revived: real
conference moderator policy machinery — membership rules are caller's
policy, not the store's.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


ORIGIN = "levi-revival/echomail"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class EchomailError(Exception):
    """Base class for echomail failures."""


@dataclass
class EchoMessage:
    """One public conference message."""

    msg_id: str  # globally unique identity; duplicates are suppressed
    echo: str
    sender: str  # display identity
    subject: str
    body: str
    written_at: str = field(default_factory=lambda: datetime.now().isoformat())
    seen_by: list[str] = field(default_factory=list)  # site names traversed


@dataclass
class EchoArea:
    """One named conference: a set of messages, keyed by msg_id."""

    name: str
    description: str = ""
    members: set[str] = field(default_factory=set)
    messages: dict[str, EchoMessage] = field(default_factory=dict)

    def add_member(self, member: str) -> None:
        self.members.add(member)

    def post(self, msg: EchoMessage) -> bool:
        """Store a message; return False if it is a duplicate."""
        if msg.echo != self.name:
            raise EchomailError(
                f"message echo {msg.echo!r} does not match area {self.name!r}"
            )
        if msg.msg_id in self.messages:
            return False  # duplicate suppressed
        self.messages[msg.msg_id] = msg
        return True

    def missing_for(self, other_ids: set[str]) -> list[EchoMessage]:
        """Messages this area has that the other side lacks."""
        return [m for mid, m in sorted(self.messages.items()) if mid not in other_ids]


class EchoHub:
    """One site's view of its conferences.

    ``exchange`` models a brief connection with a peer: both sides learn
    each other's missing messages, record the traversal, and drop
    duplicates — eventual consistency without any coordinator.
    """

    def __init__(self, site: str) -> None:
        self.site = site
        self.areas: dict[str, EchoArea] = {}

    def ensure_area(self, name: str, description: str = "") -> EchoArea:
        return self.areas.setdefault(name, EchoArea(name, description))

    def known_ids(self, echo: str) -> set[str]:
        area = self.areas.get(echo)
        return set(area.messages) if area else set()

    def exchange(self, other: "EchoHub") -> dict[str, int]:
        """Sync every shared echo with ``other``; return counts gained."""
        gained: dict[str, int] = {}
        shared = set(self.areas) & set(other.areas)
        for echo in sorted(shared):
            mine, theirs = self.areas[echo], other.areas[echo]
            my_missing = mine.missing_for(set(theirs.messages))
            their_missing = theirs.missing_for(set(mine.messages))
            for msg in their_missing:
                msg.seen_by.append(self.site)
                mine.post(msg)
            for msg in my_missing:
                msg.seen_by.append(other.site)
                theirs.post(msg)
            gained[echo] = len(their_missing)
        return gained

    def read(self, echo: str, limit: int = 50) -> list[EchoMessage]:
        area = self.areas.get(echo)
        if area is None:
            raise EchomailError(f"no such echo: {echo!r}")
        return sorted(area.messages.values(), key=lambda m: m.written_at)[:limit]
