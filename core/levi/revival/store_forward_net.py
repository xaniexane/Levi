"""Store-and-forward network: a single-path tree that holds your mail.

Studied from: dead-networks-20260916/report.md [BITNET + LISTSERV + BITNET Relay]

The studied shape: an academic network over leased phone lines where
every node has exactly one path to every other node (a tree). There is
no end-to-end session: each hop stores the message, then forwards it
when its line is free. Gateways to the outside world "trickle" data
through at a capped rate, and remote file servers answer by mail.

LEVI-native re-expression: a tree topology with next-hop routing
derived from parent pointers, per-node store-and-forward queues with
hop limits and TTLs, a tick-driven forwarder that moves one message one
hop per turn, and a trickle gateway that drains an external queue at a
byte budget per tick. File-server requests are modeled as messages
whose reply comes back along the reverse path.

Honest limits: ticks are discrete simulation steps, not line time;
routing is a tree so there is no path choice to optimize; "delivery"
means arrival in the destination node's inbox, nothing more.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple


ORIGIN = "levi-revival/store-forward-net"


@dataclass
class Message:
    msg_id: str
    sender: str
    recipient: str
    body: str
    hops_left: int = 16
    trace: List[str] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.body.encode())


class TreeNetwork:
    """Single-path tree: node -> parent, routing = walk up to the LCA."""

    def __init__(self) -> None:
        self.parent: Dict[str, Optional[str]] = {}
        self.inbox: Dict[str, List[Message]] = {}
        self.spool: Dict[str, Deque[Message]] = {}
        self.dropped: List[Tuple[Message, str]] = []

    def add_node(self, name: str, parent: Optional[str] = None) -> None:
        if name in self.parent:
            raise ValueError(f"node already exists: {name!r}")
        if parent is not None and parent not in self.parent:
            raise KeyError(f"unknown parent: {parent!r}")
        self.parent[name] = parent
        self.inbox[name] = []
        self.spool[name] = deque()

    def _path_to_root(self, node: str) -> List[str]:
        path = [node]
        while self.parent[path[-1]] is not None:
            path.append(self.parent[path[-1]])  # type: ignore[arg-type]
        return path

    def next_hop(self, source: str, dest: str) -> str:
        """Next node toward dest along the single tree path."""
        if source == dest:
            return source
        up = self._path_to_root(source)
        down = self._path_to_root(dest)
        up_set = set(up)
        lca = next(n for n in down if n in up_set)
        if lca == source:
            # dest is below us: step down toward it
            idx = down.index(source)
            return down[idx - 1]
        return self.parent[source]  # type: ignore[return-value]

    def send(self, msg: Message) -> None:
        if msg.sender not in self.parent:
            raise KeyError(f"unknown sender: {msg.sender!r}")
        if msg.recipient not in self.parent:
            raise KeyError(f"unknown recipient: {msg.recipient!r}")
        if msg.sender == msg.recipient:
            self.inbox[msg.sender].append(msg)
            return
        msg.trace.append(msg.sender)
        self.spool[msg.sender].append(msg)

    def forward_tick(self) -> int:
        """Each node forwards at most one queued message one hop. Returns moved count."""
        moved = 0
        for node in list(self.parent):
            if not self.spool[node]:
                continue
            msg = self.spool[node].popleft()
            msg.hops_left -= 1
            if msg.hops_left < 0:
                self.dropped.append((msg, "hop limit exhausted"))
                continue
            hop = self.next_hop(node, msg.recipient)
            msg.trace.append(hop)
            moved += 1
            if hop == msg.recipient:
                self.inbox[hop].append(msg)
            else:
                self.spool[hop].append(msg)
        return moved

    def drain(self, max_ticks: int = 10_000) -> int:
        ticks = 0
        while any(self.spool[n] for n in self.parent) and ticks < max_ticks:
            self.forward_tick()
            ticks += 1
        return ticks

    def collect(self, node: str) -> List[Message]:
        msgs = self.inbox[node]
        self.inbox[node] = []
        return msgs


class TrickleGateway:
    """Gateway to an external network, drained at a byte budget per tick.

    The trickle discipline: the outside world never floods the tree;
    bytes leave at a fixed rate, oldest first, messages stay whole.
    """

    def __init__(self, bytes_per_tick: int) -> None:
        if bytes_per_tick <= 0:
            raise ValueError("budget must be positive")
        self.budget = bytes_per_tick
        self.queue: Deque[Message] = deque()
        self.released: List[Message] = []

    def submit(self, msg: Message) -> None:
        self.queue.append(msg)

    def tick(self) -> List[Message]:
        spent = 0
        out: List[Message] = []
        while self.queue:
            head = self.queue[0]
            if out and spent + head.size > self.budget:
                break
            # The first message of a tick always goes through, even when it
            # alone exceeds the budget — otherwise big messages would starve.
            msg = self.queue.popleft()
            spent += msg.size
            out.append(msg)
            self.released.append(msg)
        return out


class FileServer:
    """Remote file server reached by mail: request in, file back by mail."""

    def __init__(self, node: str, files: Dict[str, str]) -> None:
        self.node = node
        self.files = dict(files)

    def handle(self, msg: Message) -> Optional[Message]:
        """Answer a GET request; None if the message is not a request."""
        if not msg.body.startswith("GET "):
            return None
        name = msg.body[4:].strip()
        body = self.files.get(name, f"ERROR: no such file {name!r}")
        return Message(
            msg_id=f"re:{msg.msg_id}",
            sender=self.node,
            recipient=msg.sender,
            body=body,
        )
