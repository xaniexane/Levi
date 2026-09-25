"""sqlite_replication — distributed replication for the embedded-database model.

Studied from: hybrid-cost-cutting-combos-20260916-0006 report.md (section 2,
named sub-mechanisms: distributed/edge replication variants of the
embedded database).

Functional pattern studied: one leader accepts writes; followers replicate
an ordered log; elections pick a new leader when the old one goes quiet;
reads can be served from nearby replicas. The cost angle is the same as the
embedded model — small nodes, no managed-database subscription.

What this module is: a deterministic, in-process simulation of the
coordination mechanism — terms, elections, log replication, commit by
majority quorum, and read routing — with honest, documented simplifications.
It is the *coordination* half of replication; the single-node WAL-shipping
mechanism lives in ``sqlite_litestream``. The two are deliberately separate:
one ships bytes off one machine, this one agrees on order across machines.

Simplifications (documented, not hidden): no real network — message passing
is direct method calls between ``Node`` objects in one process; timing
(election timeouts, heartbeats) is driven by an explicit ``tick()`` clock
the operator advances, not wall time; conflicts resolve deterministically
by (term, index) last-writer-wins, which is a real merge policy but a
simple one — applications needing stronger semantics must layer them on
top.

This is an original, from-scratch implementation for LEVI. Not artificial.
Synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/sqlite-replication"


class Role(Enum):
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


@dataclass
class Entry:
    """One log entry: (term, index) totally orders the log."""

    term: int
    index: int
    command: str  # opaque write, e.g. "SET k v"
    committed: bool = False


@dataclass
class Node:
    node_id: str
    role: Role = Role.FOLLOWER
    term: int = 0
    voted_for: Optional[str] = None
    log: List[Entry] = field(default_factory=list)
    commit_index: int = 0
    last_heartbeat: int = 0  # tick of last leader contact
    alive: bool = True

    @property
    def last_index(self) -> int:
        return self.log[-1].index if self.log else 0

    @property
    def last_term(self) -> int:
        return self.log[-1].term if self.log else 0


class Cluster:
    """A tiny deterministic replica set with an explicit tick clock."""

    def __init__(self, node_ids: List[str], election_timeout: int = 5) -> None:
        if len(node_ids) < 1:
            raise ValueError("cluster needs at least one node")
        self.nodes: Dict[str, Node] = {nid: Node(node_id=nid) for nid in node_ids}
        self.tick_count = 0
        self.election_timeout = election_timeout
        self.leader_id: Optional[str] = None
        self.lamport = 0  # logical clock for tie-breaking diagnostics

    # -- clock ----------------------------------------------------------------
    def tick(self, n: int = 1) -> None:
        for _ in range(n):
            self.tick_count += 1
            self.lamport += 1
            self._maybe_elect()

    # -- elections -------------------------------------------------------------
    def _maybe_elect(self) -> None:
        leader = self.nodes.get(self.leader_id) if self.leader_id else None
        if leader and leader.alive and leader.role is Role.LEADER:
            leader.last_heartbeat = self.tick_count
            for node in self.nodes.values():
                if node.node_id != self.leader_id and node.alive:
                    node.last_heartbeat = self.tick_count
            return
        # No live leader: the lowest-id live node whose timeout expired starts.
        for nid in sorted(self.nodes):
            node = self.nodes[nid]
            if not node.alive or node.role is Role.LEADER:
                continue
            if self.tick_count - node.last_heartbeat >= self.election_timeout:
                self._start_election(node)
                break

    def _start_election(self, candidate: Node) -> None:
        candidate.term += 1
        candidate.role = Role.CANDIDATE
        candidate.voted_for = candidate.node_id
        votes = 1
        for node in self.nodes.values():
            if node.node_id == candidate.node_id or not node.alive:
                continue
            # Vote if candidate's log is at least as fresh as ours.
            if (candidate.last_term, candidate.last_index) >= (
                node.last_term,
                node.last_index,
            ):
                node.term = candidate.term
                node.voted_for = candidate.node_id
                node.role = Role.FOLLOWER
                votes += 1
        live = sum(1 for n in self.nodes.values() if n.alive)
        if votes > live // 2:
            candidate.role = Role.LEADER
            candidate.last_heartbeat = self.tick_count
            self.leader_id = candidate.node_id
            for node in self.nodes.values():
                if node.node_id != candidate.node_id:
                    node.last_heartbeat = self.tick_count
        else:
            candidate.role = Role.FOLLOWER

    def leader(self) -> Optional[Node]:
        node = self.nodes.get(self.leader_id) if self.leader_id else None
        if node and node.alive and node.role is Role.LEADER:
            return node
        return None

    # -- writes ----------------------------------------------------------------
    def write(self, command: str) -> Entry:
        """Append a write on the leader and replicate to a majority.

        Returns the entry; ``entry.committed`` reports quorum success.
        Raises RuntimeError when there is no live leader.
        """
        leader = self.leader()
        if leader is None:
            raise RuntimeError("no live leader: write rejected")
        entry = Entry(term=leader.term, index=leader.last_index + 1, command=command)
        leader.log.append(entry)
        acks = 1
        live_followers = [
            n for n in self.nodes.values() if n.node_id != leader.node_id and n.alive
        ]
        for follower in live_followers:
            if self._replicate_to(leader, follower, entry):
                acks += 1
        live = sum(1 for n in self.nodes.values() if n.alive)
        if acks > live // 2:
            entry.committed = True
            leader.commit_index = entry.index
            for node in self.nodes.values():
                if node.alive:
                    node.commit_index = min(entry.index, node.last_index)
        return entry

    def _replicate_to(self, leader: Node, follower: Node, entry: Entry) -> bool:
        """Bring one follower's log into agreement (single-entry append).

        Returns False when the follower rejects (stale term) or is dead.
        """
        if not follower.alive:
            return False
        if entry.term < follower.term:
            return False
        # Truncate any conflicting suffix, then append — last-writer-wins
        # by (term, index), deterministic and total.
        follower.log = [e for e in follower.log if e.index < entry.index]
        follower.log.append(
            Entry(term=entry.term, index=entry.index, command=entry.command)
        )
        follower.term = entry.term
        follower.last_heartbeat = self.tick_count
        return True

    # -- reads -----------------------------------------------------------------
    def route_read(self, key_hint: str = "") -> str:
        """Pick a node to serve a read: a live follower when one exists
        (edge-local reads), else the leader. Deterministic by key hint."""
        live = [n for n in self.nodes.values() if n.alive]
        if not live:
            raise RuntimeError("no live nodes")
        followers = [n for n in live if n.role is not Role.LEADER]
        pool = followers or live
        idx = abs(hash(key_hint)) % len(pool) if key_hint else 0
        return pool[idx].node_id

    # -- failure injection ------------------------------------------------------
    def kill(self, node_id: str) -> None:
        self.nodes[node_id].alive = False
        if self.leader_id == node_id:
            self.leader_id = None

    def revive(self, node_id: str) -> None:
        node = self.nodes[node_id]
        node.alive = True
        node.role = Role.FOLLOWER
        node.last_heartbeat = self.tick_count
        # Catch up from the current leader, if any.
        leader = self.leader()
        if leader:
            for entry in leader.log:
                if entry.index > node.last_index:
                    self._replicate_to(leader, node, entry)
            node.commit_index = min(leader.commit_index, node.last_index)

    # -- diagnostics ------------------------------------------------------------
    def divergence(self) -> Dict[str, Tuple[int, int]]:
        """(last_term, last_index) per live node — all equal means converged."""
        return {
            nid: (n.last_term, n.last_index) for nid, n in self.nodes.items() if n.alive
        }
