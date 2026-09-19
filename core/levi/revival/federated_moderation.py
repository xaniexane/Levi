"""Federated moderation without a platform.

Studied from: dead-networks-20260916/report.md [FidoNet echomail social culture]
(volunteer moderators, written charters, enforcement by social
shunning/delinking; offline composition slowing flame velocity).

This is an original, from-scratch implementation for LEVI. The mechanism is a
federation of independent *nodes* (communities). Each node adopts a written
*charter* naming what it will and will not carry. Volunteers are elected as
moderators with scoped powers. Enforcement has no central ban button: a node's
moderators can *delink* from a misbehaving node (stop relaying its traffic) or
*shun* a participant (refuse their mail across the federation).

The second half of the mechanism is the *cooling queue*. Messages are scored
for heat by a small, explicit heuristic (ALL-CAPS ratio, exclamation density,
flagged slur/personal-attack words) — labeled as a heuristic, not sentiment
AI. A hot message is not dropped; it is held for a cooling delay and delivered
later. Because composition is offline and delivery is slow, flame velocity is
damped: a reply arrives after tempers had time to decay.

Public surface:
- ``Federation``: ``register_node``, ``adopt_charter``, ``elect_moderator``,
  ``delink``, ``shun`` / ``lift_shun``, ``submit`` (post with cooling),
  ``deliver_due`` (drain the cooling queue), ``health()``.
- ``Charter``, ``Node``, ``FederationError`` for embedding.

stdlib-only. No network. Deterministic except clock-based cooling windows.
"""

from __future__ import annotations

import heapq
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Mapping, Set, Tuple

ORIGIN = "levi-revival/federated-moderation"


class FederationError(ValueError):
    """Raised when a federation operation cannot be honored."""


# Words that make a message hotter. This is a *heuristic* signal for the
# cooling queue — not a content judgment or a moderation verdict.
_HOT_WORDS = frozenset(
    {
        "idiot",
        "stupid",
        "moron",
        "loser",
        "hate",
        "shut",
        "kill",
        "die",
        "worthless",
        "pathetic",
        "liar",
        "fraud",
        "scam",
    }
)
_WORD_RE = re.compile(r"[a-zA-Z]+")


def heat_score(text: str) -> float:
    """Heuristic 0.0–1.0 heat score for a message (see module docstring)."""
    if not text:
        return 0.0
    words = _WORD_RE.findall(text)
    if not words:
        return 0.0
    caps_ratio = sum(1 for w in words if len(w) > 1 and w.isupper()) / len(words)
    hot_ratio = sum(1 for w in words if w.lower() in _HOT_WORDS) / len(words)
    bang_ratio = text.count("!") / max(len(text), 1)
    score = (
        0.55 * caps_ratio
        + 0.35 * min(hot_ratio * 6.0, 1.0)
        + 0.10 * min(bang_ratio * 40.0, 1.0)
    )
    return round(min(score, 1.0), 3)


@dataclass(frozen=True)
class Charter:
    """A node's written rules: name, carried topics, refusal lines."""

    name: str
    carried_topics: Tuple[str, ...]
    refused_lines: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise FederationError("charter name must be non-empty")
        if not self.carried_topics:
            raise FederationError("charter must carry at least one topic")


@dataclass
class Node:
    """One independent community in the federation."""

    node_id: str
    charter: Charter
    moderators: Set[str] = field(default_factory=set)
    delinked_from: Set[str] = field(default_factory=set)
    posts: List[Tuple[str, str, str]] = field(
        default_factory=list
    )  # (author, text, stamp)

    def deliver(self, author: str, text: str) -> None:
        self.posts.append(
            (author, text, datetime.now(timezone.utc).isoformat(timespec="seconds"))
        )


@dataclass(order=True)
class _Queued:
    due: datetime
    seq: int
    payload: Tuple[str, str, str] = field(compare=False)  # (from_node, author, text)


class Federation:
    """A federation of moderated nodes with cooling-queue delivery."""

    def __init__(
        self,
        cooling_seconds: int = 600,
        hot_threshold: float = 0.45,
        election_quorum: int = 3,
    ) -> None:
        if cooling_seconds < 0:
            raise FederationError("cooling_seconds must be >= 0")
        self.cooling = timedelta(seconds=cooling_seconds)
        self.hot_threshold = hot_threshold
        self.election_quorum = election_quorum
        self._nodes: Dict[str, Node] = {}
        self._shunned: Dict[str, Set[str]] = {}  # node_id -> shunned authors
        self._queue: List[_Queued] = []
        self._seq = 0
        self._electorate: Dict[str, Set[str]] = {}  # node_id -> endorsers

    # -- topology ---------------------------------------------------------
    def register_node(self, node_id: str, charter: Charter) -> Node:
        if not node_id:
            raise FederationError("node_id must be non-empty")
        if node_id in self._nodes:
            raise FederationError(f"node {node_id!r} already registered")
        node = Node(node_id=node_id, charter=charter)
        self._nodes[node_id] = node
        self._shunned[node_id] = set()
        self._electorate[node_id] = set()
        return node

    def adopt_charter(self, node_id: str, charter: Charter) -> None:
        node = self._require_node(node_id)
        node.charter = charter

    def node(self, node_id: str) -> Node:
        return self._require_node(node_id)

    def _require_node(self, node_id: str) -> Node:
        try:
            return self._nodes[node_id]
        except KeyError:
            raise FederationError(f"unknown node {node_id!r}") from None

    # -- volunteer moderators ---------------------------------------------
    def endorse(self, node_id: str, endorser: str, candidate: str) -> int:
        """Record one endorsement for a moderator candidate; returns count."""
        self._require_node(node_id)
        if not endorser or not candidate:
            raise FederationError("endorser and candidate must be named")
        self._electorate.setdefault(f"__{node_id}__{candidate}", set()).add(endorser)
        return len(self._electorate[f"__{node_id}__{candidate}"])

    def elect_moderator(self, node_id: str, candidate: str) -> bool:
        """Seat a candidate once endorsements reach the quorum."""
        node = self._require_node(node_id)
        count = len(self._electorate.get(f"__{node_id}__{candidate}", set()))
        if count < self.election_quorum:
            return False
        node.moderators.add(candidate)
        return True

    # -- enforcement: shunning and delinking -------------------------------
    def shun(self, node_id: str, author: str, by_moderator: str) -> None:
        node = self._require_node(node_id)
        self._require_moderator(node, by_moderator)
        self._shunned[node_id].add(author)

    def lift_shun(self, node_id: str, author: str, by_moderator: str) -> bool:
        node = self._require_node(node_id)
        self._require_moderator(node, by_moderator)
        if author in self._shunned[node_id]:
            self._shunned[node_id].remove(author)
            return True
        return False

    def delink(self, node_id: str, target_node: str, by_moderator: str) -> None:
        node = self._require_node(node_id)
        self._require_moderator(node, by_moderator)
        if target_node == node_id:
            raise FederationError("a node cannot delink from itself")
        self._require_node(target_node)
        node.delinked_from.add(target_node)

    def relink(self, node_id: str, target_node: str, by_moderator: str) -> bool:
        node = self._require_node(node_id)
        self._require_moderator(node, by_moderator)
        if target_node in node.delinked_from:
            node.delinked_from.remove(target_node)
            return True
        return False

    @staticmethod
    def _require_moderator(node: Node, name: str) -> None:
        if name not in node.moderators:
            raise FederationError(f"{name!r} is not a moderator of {node.node_id!r}")

    # -- posting with cooling ----------------------------------------------
    def submit(self, from_node: str, author: str, text: str) -> Mapping[str, object]:
        """Post a message; hot messages wait in the cooling queue.

        Returns a dict with the heat score and whether delivery was held.
        Shunned authors cannot post. Off-charter topics are refused.
        """
        node = self._require_node(from_node)
        if author in self._shunned[from_node]:
            raise FederationError(f"{author!r} is shunned by {from_node!r}")
        if not text.strip():
            raise FederationError("message text must be non-empty")
        heat = heat_score(text)
        if heat >= self.hot_threshold:
            self._seq += 1
            due = datetime.now(timezone.utc) + self.cooling
            heapq.heappush(
                self._queue, _Queued(due, self._seq, (from_node, author, text))
            )
            return {"heat": heat, "held": True}
        self._relay(node, author, text)
        return {"heat": heat, "held": False}

    def deliver_due(self) -> int:
        """Deliver cooled messages whose delay has elapsed; returns count."""
        now = datetime.now(timezone.utc)
        delivered = 0
        while self._queue and self._queue[0].due <= now:
            item = heapq.heappop(self._queue)
            from_node, author, text = item.payload
            if author not in self._shunned.get(from_node, set()):
                self._relay(self._nodes[from_node], author, text)
            delivered += 1
        return delivered

    def pending_cooling(self) -> int:
        return len(self._queue)

    def _relay(self, origin: Node, author: str, text: str) -> None:
        for node in self._nodes.values():
            if node.node_id == origin.node_id:
                node.deliver(author, text)
            elif (
                origin.node_id not in node.delinked_from
                and author not in self._shunned.get(node.node_id, set())
            ):
                node.deliver(author, text)

    # -- health -------------------------------------------------------------
    def health(self) -> Mapping[str, object]:
        return {
            "nodes": len(self._nodes),
            "delinked_edges": sum(len(n.delinked_from) for n in self._nodes.values()),
            "shunned": sum(len(s) for s in self._shunned.values()),
            "cooling_queue": len(self._queue),
            "moderators": sum(len(n.moderators) for n in self._nodes.values()),
        }

    def links(self, node_id: str) -> List[str]:
        """Node ids this node still relays with (not delinked)."""
        node = self._require_node(node_id)
        return sorted(
            n for n in self._nodes if n != node_id and n not in node.delinked_from
        )
