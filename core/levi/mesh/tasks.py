"""Task farming — split work, farm it to the fleet, collect results.

Deterministic chunking, replication so a dropped node never loses
work, and replica agreement so a lying node can't poison a result:

* each chunk goes to ``replication`` distinct nodes (default 2);
* a chunk is accepted when 2 replicas agree; the dissenter earns a
  trust mismatch;
* a 1-1 replica split farms exactly one tiebreaker;
* a node silent past ``chunk_timeout`` has its chunks reassigned to
  fresh nodes (the dead node is never re-farmed).

Functions run by name from the ``FUNCTIONS`` registry — pure,
deterministic, JSON-safe (chunks travel hex-encoded). Only registered
functions execute: the mesh never evals arbitrary code from peers.
"""

from __future__ import annotations

import hashlib
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple

from .node import MeshNode
from .resources import ResourcePool
from .transport import TransportUnavailable


# -- function registry -------------------------------------------------


def _sha256_hex(data_hex: str) -> str:
    return hashlib.sha256(bytes.fromhex(data_hex)).hexdigest()


def _byte_sum(data_hex: str) -> int:
    return sum(bytes.fromhex(data_hex))


FUNCTIONS: Dict[str, Callable[[str], object]] = {
    "sha256_hex": _sha256_hex,
    "byte_sum": _byte_sum,
}


def chunk_bytes(data: bytes, n: int) -> List[bytes]:
    """Split bytes into n deterministic chunks (first chunks take extras)."""
    if n <= 0:
        raise ValueError("n must be positive")
    base, rem = divmod(len(data), n)
    chunks, offset = [], 0
    for i in range(n):
        size = base + (1 if i < rem else 0)
        chunks.append(data[offset : offset + size])
        offset += size
    return chunks


@dataclass
class TaskSpec:
    task_id: str
    function: str
    chunks: List[str]  # hex-encoded
    replication: int = 2


class NoWorkers(RuntimeError):
    """No fleet nodes available to farm the task."""


class TaskIncomplete(RuntimeError):
    """Some chunks never reached replica agreement before the deadline."""


class TaskFarmer:
    """Farms chunked tasks across the fleet from one coordinator node."""

    def __init__(
        self, node: MeshNode, pool: ResourcePool, ledger=None, trust=None
    ) -> None:
        self.node = node
        self.pool = pool
        self.ledger = ledger
        self.trust = trust

    def submit(
        self,
        data: bytes,
        function: str,
        num_chunks: int,
        replication: int = 2,
        timeout: float = 10.0,
        chunk_timeout: float = 2.0,
    ) -> Dict:
        if function not in FUNCTIONS:
            raise ValueError(f"unknown function {function!r}")
        if replication < 1:
            raise ValueError("replication must be >= 1")
        raw_chunks = chunk_bytes(data, num_chunks)
        spec = TaskSpec(
            task_id=uuid.uuid4().hex[:16],
            function=function,
            chunks=[c.hex() for c in raw_chunks],
            replication=replication,
        )
        candidates = self.pool.node_ids()
        # The farmer never farms to itself: the submit loop and the
        # node's own worker thread share one inbox, so a self-assigned
        # chunk races between them and can be silently dropped.
        candidates = [c for c in candidates if c != self.node.node_id]
        if not candidates:
            raise NoWorkers("no nodes in the resource pool")

        n = len(spec.chunks)
        votes: Dict[int, List[Tuple[str, object]]] = {i: [] for i in range(n)}
        accepted: Dict[int, object] = {}
        tried: Dict[int, Set[str]] = {i: set() for i in range(n)}
        dead: Dict[int, Set[str]] = {i: set() for i in range(n)}
        assigned_at: Dict[Tuple[int, str], float] = {}
        reassignments = 0

        def distinct_voters(i: int) -> Set[str]:
            return {nid for nid, _ in votes[i]}

        def assign(i: int) -> None:
            """Top up chunk i to replication coverage (or one tiebreaker)."""
            nonlocal reassignments
            if i in accepted:
                return
            voters = distinct_voters(i)
            outstanding = tried[i] - voters - dead[i]
            if outstanding:
                return  # wait on in-flight nodes before farming more
            need = replication - len(voters)
            if need <= 0 and voters:
                need = 1  # tiebreaker: all replicas voted, none agree
            if need <= 0:
                return
            exclude = tried[i] | dead[i]
            avail = [c for c in candidates if c not in exclude]
            start = (i * replication) % len(avail) if avail else 0
            order = (avail[start:] + avail[:start]) if avail else []
            sent = 0
            for nid in order:
                if sent >= need:
                    break
                tried[i].add(nid)
                assigned_at[(i, nid)] = time.time()
                try:
                    self.node.send(
                        nid,
                        {
                            "type": "task",
                            "task_id": spec.task_id,
                            "chunk_index": i,
                            "function": function,
                            "data_hex": spec.chunks[i],
                        },
                    )
                except TransportUnavailable:
                    # Peer vanished between the pool snapshot and the
                    # send (killed node, expired heartbeat). Mark it
                    # dead for this chunk and farm the next candidate —
                    # the farmer never dies on a vanished peer.
                    tried[i].discard(nid)
                    assigned_at.pop((i, nid), None)
                    dead[i].add(nid)
                    continue
                sent += 1
                reassignments += 1

        for i in range(n):
            assign(i)
        initial_assignments = reassignments

        deadline = time.time() + timeout
        while len(accepted) < n and time.time() < deadline:
            incoming = self.node.recv(timeout=0.2)
            now = time.time()
            if incoming is not None:
                sender, msg = incoming
                if msg.get("type") == "result" and msg.get("task_id") == spec.task_id:
                    i = int(msg["chunk_index"])
                    if i not in accepted and sender not in distinct_voters(i):
                        votes[i].append((sender, msg["result"]))
                        self._check_agreement(spec, i, votes, accepted)
            for i in range(n):
                if i in accepted:
                    continue
                voters = distinct_voters(i)
                outstanding = tried[i] - voters - dead[i]
                if voters and not outstanding and len(voters) >= replication:
                    # Every replica voted but none agree (1-1 split):
                    # farm exactly one tiebreaker. assign() enforces
                    # the "one" via its outstanding check.
                    assign(i)
                    continue
                # reassign chunks whose nodes went silent
                for nid in list(tried[i]):
                    if (
                        nid not in voters
                        and (i, nid) in assigned_at
                        and now - assigned_at[(i, nid)] > chunk_timeout
                    ):
                        del assigned_at[(i, nid)]
                        tried[i].discard(nid)
                        dead[i].add(nid)
                        assign(i)

        if len(accepted) < n:
            missing = [i for i in range(n) if i not in accepted]
            raise TaskIncomplete(f"task {spec.task_id}: chunks {missing} never agreed")
        return {
            "task_id": spec.task_id,
            "results": [accepted[i] for i in range(n)],
            "chunks": n,
            "replication": replication,
            "assignments": initial_assignments,
            "reassignments": reassignments - initial_assignments,
        }

    def _check_agreement(
        self,
        spec: TaskSpec,
        i: int,
        votes: Dict[int, List[Tuple[str, object]]],
        accepted: Dict[int, object],
    ) -> None:
        """Accept chunk i when enough replicas agree; penalize dissenters.

        Agreement needs 2 matching votes at replication >= 2; at
        replication == 1 a single vote settles the chunk (the caller
        asked for no redundancy).
        """
        need = 2 if spec.replication >= 2 else 1
        by_value: Dict[str, Tuple[object, List[str]]] = {}
        for nid, val in votes[i]:
            key = repr(val)
            if key not in by_value:
                by_value[key] = (val, [])
            by_value[key][1].append(nid)
        for val, nids in by_value.values():
            if len(nids) >= need:
                accepted[i] = val
                agreed = set(nids[:2])
                for nid, _ in votes[i]:
                    if nid in agreed:
                        if self.trust is not None:
                            self.trust.record_success(nid)
                        if self.ledger is not None:
                            self.ledger.record(
                                nid, "contributed", 1, task_id=spec.task_id
                            )
                            self.ledger.record(
                                self.node.node_id, "received", 1, task_id=spec.task_id
                            )
                    else:
                        if self.trust is not None:
                            self.trust.record_mismatch(nid)
                return


class Worker:
    """Dumb compute endpoint: runs registered functions for farmers.

    A worker never initiates tasks and never touches the ledger — the
    farmer records contributions when results are accepted.

    A node should farm XOR work, not both at once: the farmer's submit
    loop and the worker thread share the node's single inbox, so a
    node doing both can steal the other's messages.
    """

    def __init__(self, node: MeshNode) -> None:
        self.node = node
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> "Worker":
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            incoming = self.node.recv(timeout=0.5)
            if incoming is None:
                continue
            sender, msg = incoming
            if msg.get("type") != "task":
                continue
            fn = FUNCTIONS.get(msg.get("function", ""))
            if fn is None:
                continue
            try:
                result = fn(msg["data_hex"])
            except Exception as exc:  # a bad chunk must not kill the worker
                result = {"error": str(exc)}
            try:
                self.node.send(
                    sender,
                    {
                        "type": "result",
                        "task_id": msg.get("task_id"),
                        "chunk_index": msg.get("chunk_index"),
                        "result": result,
                    },
                )
            except Exception:
                continue
