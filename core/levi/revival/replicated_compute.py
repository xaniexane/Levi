"""replicated_compute — deterministic objects, shared by message.

Studied from: revival-50-more-20260916-0009/report-part1.md [entry #12].

The studied shape: peers run the *same deterministic objects* in a
shared pseudo-time, exchanging only messages — no central server holds
the truth; the truth is whatever every replica computes from the same
ordered message stream. LEVI's version:

* **Deterministic objects.** A ``Replica`` owns plain Python state and a
  ``tick`` counter. Every state change happens through ``apply`` of an
  ``Op`` — no wall-clock reads, no ambient randomness; where chance is
  needed it comes from ``Replica.rand()``, seeded by (state hash, tick),
  so every replica draws the same number.
* **Totally ordered delivery.** ``Mesh.broadcast(op)`` assigns each op a
  sequence number; replicas apply ops strictly in sequence order, so all
  replicas that have seen the same prefix agree exactly.
* **Snapshots and catch-up.** ``snapshot()`` serializes (tick, state,
  state-hash); a lagging replica replays the ops it missed. ``verify``
  compares state hashes across replicas — convergence is checkable, not
  assumed.

Honest limits: ordering is provided by the single ``Mesh`` here — a real
deployment would need a consensus or sequencer protocol for that, which
is deliberately out of scope. What this module owns is the *replica
side*: deterministic application of an ordered op stream.

This is an original, from-scratch implementation for LEVI. Not
artificial. Synthetic.
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List

ORIGIN = "levi-revival/replicated_compute"


# ---------------------------------------------------------------------------
# Ops: the only thing that mutates state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Op:
    """One deterministic state change: name + JSON-safe arguments."""

    name: str
    args: Dict[str, Any] = field(default_factory=dict)

    def digest(self) -> str:
        blob = json.dumps({"name": self.name, "args": self.args}, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Replicas
# ---------------------------------------------------------------------------


class Replica:
    """A deterministic object: state mutates only via ordered ``Op``s."""

    def __init__(self, replica_id: str) -> None:
        self.replica_id = replica_id
        self.tick = 0
        self.state: Dict[str, Any] = {}
        self._handlers = {
            "set": self._op_set,
            "add": self._op_add,
            "roll": self._op_roll,
            "append": self._op_append,
        }

    # -- deterministic randomness -----------------------------------------
    def rand(self) -> random.Random:
        """RNG seeded by (state digest, tick): identical on every replica."""
        seed_src = f"{self.state_digest()}#{self.tick}"
        seed = int(hashlib.sha256(seed_src.encode()).hexdigest()[:16], 16)
        return random.Random(seed)

    # -- op application ----------------------------------------------------
    def apply(self, op: Op) -> None:
        try:
            handler = self._handlers[op.name]
        except KeyError:
            raise ValueError(f"unknown op {op.name!r}") from None
        handler(op.args)
        self.tick += 1

    def _op_set(self, args: Dict[str, Any]) -> None:
        self.state[args["key"]] = args["value"]

    def _op_add(self, args: Dict[str, Any]) -> None:
        key = args["key"]
        self.state[key] = self.state.get(key, 0) + args["delta"]

    def _op_append(self, args: Dict[str, Any]) -> None:
        key = args["key"]
        self.state.setdefault(key, []).append(args["value"])

    def _op_roll(self, args: Dict[str, Any]) -> None:
        """Deterministic dice roll stored under a key."""
        self.state[args["key"]] = self.rand().randint(1, args.get("sides", 6))

    # -- introspection ------------------------------------------------------
    def state_digest(self) -> str:
        blob = json.dumps(self.state, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()

    def snapshot(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "state": copy.deepcopy(self.state),
            "digest": self.state_digest(),
        }

    def restore(self, snap: Dict[str, Any]) -> None:
        self.tick = snap["tick"]
        self.state = copy.deepcopy(snap["state"])


# ---------------------------------------------------------------------------
# Mesh: ordered broadcast to replicas
# ---------------------------------------------------------------------------


class Mesh:
    """Assigns sequence numbers and delivers the op log to every replica."""

    def __init__(self) -> None:
        self.log: List[Op] = []
        self.replicas: Dict[str, Replica] = {}
        self._delivered: Dict[str, int] = {}

    def join(self, replica: Replica) -> None:
        self.replicas[replica.replica_id] = replica
        self._delivered[replica.replica_id] = 0
        # New joiner replays the whole log from the start.
        for op in self.log:
            replica.apply(op)
        self._delivered[replica.replica_id] = len(self.log)

    def broadcast(self, op: Op) -> int:
        """Append to the log and deliver to every replica in order."""
        self.log.append(op)
        seq = len(self.log)
        for rid, replica in self.replicas.items():
            assert self._delivered[rid] == seq - 1, "replica fell behind delivery"
            replica.apply(op)
            self._delivered[rid] = seq
        return seq

    def catch_up(self, replica_id: str) -> int:
        """Replay missed ops to one replica. Returns ops replayed."""
        replica = self.replicas[replica_id]
        missed = self.log[self._delivered[replica_id] :]
        for op in missed:
            replica.apply(op)
        self._delivered[replica_id] = len(self.log)
        return len(missed)

    def simulate_partition(self, replica_id: str, ops: List[Op]) -> None:
        """Hold ops back from one replica (partition), for catch-up tests."""
        # ops still go to the log and to every *other* replica
        for op in ops:
            self.log.append(op)
            seq = len(self.log)
            for rid, replica in self.replicas.items():
                if rid == replica_id:
                    continue
                replica.apply(op)
                self._delivered[rid] = seq

    def digests(self) -> Dict[str, str]:
        return {rid: r.state_digest() for rid, r in self.replicas.items()}

    def converged(self) -> bool:
        """True when every replica's digest matches the log head's."""
        digests = set(self.digests().values())
        return len(digests) == 1


def replica_from_snapshot(replica_id: str, snap: Dict[str, Any]) -> Replica:
    """Rebuild a replica from a snapshot (state transfer without the log)."""
    r = Replica(replica_id)
    r.restore(snap)
    return r
