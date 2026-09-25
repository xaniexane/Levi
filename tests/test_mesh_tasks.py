"""Mesh task-farming tests: correctness, replication survival, liars."""

import hashlib
import time

import pytest

from levi.mesh.ledger import ContributionLedger
from levi.mesh.node import MeshNode
from levi.mesh.resources import ResourceOffer, ResourcePool
from levi.mesh.tasks import (
    NoWorkers,
    TaskFarmer,
    Worker,
    chunk_bytes,
)
from levi.mesh.transport import LocalTransport
from levi.mesh.trust import TrustMonitor


def build_fleet(n, rdv_dir, ledger=None, trust=None, heartbeat_interval=0.15):
    nodes, workers = [], []
    for i in range(n):
        node = MeshNode(
            f"tf-dev-{i}",
            f"tf-node-{i}",
            LocalTransport(rendezvous_dir=rdv_dir),
            heartbeat_interval=heartbeat_interval,
        )
        node.join()
        workers.append(Worker(node).start())
        nodes.append(node)
    time.sleep(0.8)
    for node in nodes:
        node.discover(timeout=0.4)
    pool = ResourcePool()
    for node in nodes:
        pool.advertise(
            ResourceOffer(
                node_id=node.node_id, cpu_units=2.0, memory_mb=512.0, tags=("test",)
            )
        )
    return nodes, workers, pool


def teardown(nodes, workers):
    for w in workers:
        try:
            w.stop()
        except Exception:
            pass
    for node in nodes:
        try:
            node.leave()
        except Exception:
            pass


def test_chunk_bytes_deterministic():
    data = b"abcdefghij"
    assert chunk_bytes(data, 3) == [b"abcd", b"efg", b"hij"]
    assert b"".join(chunk_bytes(data, 4)) == data
    assert chunk_bytes(b"", 3) == [b"", b"", b""]
    with pytest.raises(ValueError):
        chunk_bytes(data, 0)


def test_farm_correctness_and_ledger(tmp_path):
    nodes, workers, pool = build_fleet(4, tmp_path / "rdv")
    ledger = ContributionLedger(path=tmp_path / "ledger.jsonl")
    trust = TrustMonitor()
    farmer = TaskFarmer(nodes[0], pool, ledger=ledger, trust=trust)
    # farmer node stays compute-free in this harness: drop it from pool
    pool.withdraw(nodes[0].node_id)
    workers[0].stop()
    try:
        data = b"the fleet is the cloud " * 500
        out = farmer.submit(
            data,
            "sha256_hex",
            num_chunks=6,
            replication=2,
            timeout=15.0,
            chunk_timeout=1.5,
        )
        reference = [hashlib.sha256(c).hexdigest() for c in chunk_bytes(data, 6)]
        assert out["results"] == reference
        assert out["chunks"] == 6
        # every accepted chunk paid its two workers
        total = sum(ledger.contributed(n.node_id) for n in nodes[1:])
        assert total == 6 * 2
        assert ledger.received(nodes[0].node_id) == 6 * 2
    finally:
        teardown(nodes, workers)


def test_dead_node_routed_around(tmp_path):
    """Victim dead before submit but still in the pool snapshot.

    The farmer's first send to it raises TransportUnavailable; the
    farmer marks it dead and farms the next candidate — no crash,
    correct results, zero contribution from the corpse.
    """
    nodes, workers, pool = build_fleet(4, tmp_path / "rdv")
    ledger = ContributionLedger(path=tmp_path / "ledger.jsonl")
    farmer = TaskFarmer(nodes[0], pool, ledger=ledger)
    pool.withdraw(nodes[0].node_id)
    workers[0].stop()
    victim = len(workers) - 1
    workers[victim].stop()
    nodes[victim].leave()  # rendezvous file gone, but pool still lists it
    try:
        data = b"x" * 20000
        out = farmer.submit(
            data,
            "byte_sum",
            num_chunks=8,
            replication=2,
            timeout=20.0,
            chunk_timeout=1.5,
        )
        reference = [sum(c) for c in chunk_bytes(data, 8)]
        assert out["results"] == reference
        assert ledger.contributed(nodes[victim].node_id) == 0
    finally:
        teardown(nodes, workers)


class StalledWorker(Worker):
    """Heartbeats stay fresh, but tasks are swallowed, never answered."""

    def _loop(self):
        while not self._stop.is_set():
            incoming = self.node.recv(timeout=0.5)
            if incoming is None:
                continue
            _sender, msg = incoming
            if msg.get("type") == "task":
                continue  # accept the task, never reply


def test_stalled_node_gets_refarmed(tmp_path):
    """A hung (not dead) node triggers chunk_timeout reassignment."""
    nodes, workers, pool = build_fleet(4, tmp_path / "rdv")
    workers[2].stop()
    stalled = StalledWorker(nodes[2]).start()
    workers[2] = stalled
    farmer = TaskFarmer(nodes[0], pool)
    pool.withdraw(nodes[0].node_id)
    workers[0].stop()
    try:
        data = b"y" * 20000
        out = farmer.submit(
            data,
            "byte_sum",
            num_chunks=8,
            replication=2,
            timeout=25.0,
            chunk_timeout=1.5,
        )
        reference = [sum(c) for c in chunk_bytes(data, 8)]
        assert out["results"] == reference
        assert out["reassignments"] >= 1  # stalled node's chunks re-farmed
    finally:
        teardown(nodes, workers)


class LyingWorker(Worker):
    """Returns garbage for every chunk — the fleet must route around it."""

    def _loop(self):
        while not self._stop.is_set():
            incoming = self.node.recv(timeout=0.5)
            if incoming is None:
                continue
            sender, msg = incoming
            if msg.get("type") != "task":
                continue
            try:
                self.node.send(
                    sender,
                    {
                        "type": "result",
                        "task_id": msg.get("task_id"),
                        "chunk_index": msg.get("chunk_index"),
                        "result": "deadbeef" * 8,  # wrong on purpose
                    },
                )
            except Exception:
                continue


def test_liar_gets_outvoted_and_flagged(tmp_path):
    nodes, workers, pool = build_fleet(4, tmp_path / "rdv")
    # swap one honest worker for a liar
    workers[2].stop()
    liar = LyingWorker(nodes[2]).start()
    workers[2] = liar
    trust = TrustMonitor()
    farmer = TaskFarmer(nodes[0], pool, trust=trust)
    pool.withdraw(nodes[0].node_id)
    workers[0].stop()
    try:
        data = b"honest work " * 300
        out = farmer.submit(
            data,
            "sha256_hex",
            num_chunks=4,
            replication=2,
            timeout=20.0,
            chunk_timeout=1.5,
        )
        reference = [hashlib.sha256(c).hexdigest() for c in chunk_bytes(data, 4)]
        assert out["results"] == reference  # truth won via tiebreakers
        assert trust._mismatched[nodes[2].node_id] >= 1  # liar penalized
    finally:
        teardown(nodes, workers)


def test_no_workers_raises(tmp_path):
    node = MeshNode(
        "solo-dev", "solo", LocalTransport(rendezvous_dir=tmp_path / "rdv-solo")
    )
    node.join()
    try:
        farmer = TaskFarmer(node, ResourcePool())
        with pytest.raises(NoWorkers):
            farmer.submit(b"data", "sha256_hex", 2)
        with pytest.raises(ValueError):
            farmer.submit(b"data", "no-such-fn", 2)
    finally:
        node.leave()
