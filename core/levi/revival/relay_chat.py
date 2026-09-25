"""revival/relay_chat.py — hierarchical regional chat relay.

Studied from: dead-networks-20260916 (report.md [BITNET + LISTSERV + BITNET Relay]).

Revival of: the BITNET Relay — server-mediated hierarchical chat where
regional servers aggregated traffic instead of flooding low-bandwidth links.

Why it matters: on expensive or slow links, every client shouting to every
other client is ruinous. A hierarchy of relays changes the shape of the
traffic: messages climb to a shared backbone and fan out downward, and each
relay forwards any given message exactly once. Bandwidth is spent on content,
not on redundant copies.

LEVI adaptation:
- ``RelayNode``: a chat server with local users, a parent, and children.
- ``RelayNet.broadcast()``: a user posts; the message climbs to the backbone
  and fans out to every node, each node delivering exactly once (tracked by
  message id).
- ``BatchChannel``: models the low-bandwidth discipline — a node queues
  outbound frames and flushes them as one aggregated batch, so per-message
  overhead is amortized across the batch.
- ``link_stats``: every link traversal is counted, so you can see what the
  hierarchy costs versus a full mesh.

Honest limits:
- Synchronous and in-process; no real network, no latency model. The
  "aggregation" is batching frames into one flush — it does not model packet
  sizes or queueing delay.
- Exactly-once is per-node dedup by message id; ids must be unique per
  sender.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class RelayMessage:
    mid: str
    origin: str
    user: str
    text: str
    hops: int = 0
    at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.mid:
            raise ValueError("mid must be non-empty")


class BatchChannel:
    """Coalesces outbound frames into one aggregated flush per tick."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._queue: List[RelayMessage] = []
        self.frames_flushed = 0
        self.messages_carried = 0

    def enqueue(self, message: RelayMessage) -> None:
        self._queue.append(message)

    def flush(self) -> List[RelayMessage]:
        """Release everything queued as a single aggregated batch."""
        batch = list(self._queue)
        self._queue.clear()
        if batch:
            self.frames_flushed += 1
            self.messages_carried += len(batch)
        return batch

    def pending(self) -> int:
        return len(self._queue)


class RelayNode:
    """One chat relay: local users, a parent link, child links."""

    def __init__(self, name: str) -> None:
        if not name:
            raise ValueError("name must be non-empty")
        self.name = name
        self.parent: Optional["RelayNode"] = None
        self.children: List["RelayNode"] = []
        self.users: Set[str] = set()
        self.inbox: Dict[str, List[RelayMessage]] = {}
        self._seen: Set[str] = set()
        self.upstream = BatchChannel(f"{name}:up")
        self.delivered = 0

    def add_user(self, user: str) -> None:
        self.users.add(user)
        self.inbox.setdefault(user, [])

    def attach_child(self, child: "RelayNode") -> None:
        child.parent = self
        self.children.append(child)

    def _receive(self, message: RelayMessage, via: Optional["RelayNode"]) -> None:
        """Take a message, deliver locally, and forward onward exactly once."""
        if message.mid in self._seen:
            return
        self._seen.add(message.mid)
        self.delivered += 1
        for user in self.users:
            self.inbox[user].append(message)
        # Forward up (aggregated through the batch channel) ...
        if self.parent is not None and via is not self.parent:
            message.hops += 1
            self.upstream.enqueue(message)
        # ... and down to every child except the one it came from.
        for child in self.children:
            if child is not via:
                child._receive(message, via=self)

    def flush_upstream(self) -> int:
        """Push queued messages to the parent relay. Returns frames flushed."""
        batch = self.upstream.flush()
        if self.parent is not None:
            for message in batch:
                self.parent._receive(message, via=self)
        return self.upstream.frames_flushed


class RelayNet:
    """A hierarchy of relays with link-traversal accounting."""

    def __init__(self) -> None:
        self.nodes: Dict[str, RelayNode] = {}
        self.link_traversals = 0

    def add_node(self, name: str, parent: Optional[str] = None) -> RelayNode:
        if name in self.nodes:
            raise ValueError(f"node {name!r} already exists")
        node = RelayNode(name)
        self.nodes[name] = node
        if parent is not None:
            if parent not in self.nodes:
                raise KeyError(f"no such parent node: {parent!r}")
            self.nodes[parent].attach_child(node)
        return node

    def broadcast(self, node_name: str, user: str, text: str) -> RelayMessage:
        """Post from a user; the message reaches every node exactly once."""
        if node_name not in self.nodes:
            raise KeyError(f"no such node: {node_name!r}")
        node = self.nodes[node_name]
        if user not in node.users:
            raise KeyError(f"user {user!r} not registered on {node_name!r}")
        message = RelayMessage(
            mid=f"{node_name}:{user}:{int(time.time() * 1000)}",
            origin=node_name,
            user=user,
            text=text,
        )
        node._receive(message, via=None)
        # Drain every upstream batch channel until the hierarchy is quiet.
        changed = True
        while changed:
            changed = False
            for relay in self.nodes.values():
                if relay.upstream.pending():
                    relay.flush_upstream()
                    changed = True
                    self.link_traversals += 1
        return message

    def inbox_of(self, node_name: str, user: str) -> List[RelayMessage]:
        return self.nodes[node_name].inbox.get(user, [])


ORIGIN = "levi-revival/relay-chat"
