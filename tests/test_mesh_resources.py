"""Focused tests for fleet-mesh resource matching, replication-1
semantics, and the founder-gated ledger truth view."""

from __future__ import annotations

import pytest

from levi.mesh.ledger import ContributionLedger
from levi.mesh.resources import ResourceOffer, ResourcePool
from levi.mesh.tasks import TaskFarmer


def make_pool() -> ResourcePool:
    pool = ResourcePool()
    pool.advertise(
        ResourceOffer(node_id="big", cpu_units=8.0, memory_mb=16384.0, tags=("gpu",))
    )
    pool.advertise(ResourceOffer(node_id="mid", cpu_units=4.0, memory_mb=8192.0))
    pool.advertise(ResourceOffer(node_id="small", cpu_units=1.0, memory_mb=1024.0))
    return pool


def test_match_filters_and_ranks_deterministically():
    pool = make_pool()
    assert pool.match(cpu_units=2.0) == ["big", "mid"]
    assert pool.match(cpu_units=2.0, tags=("gpu",)) == ["big"]
    assert pool.match(memory_mb=32768.0) == []
    # headroom ranking: big first; deterministic tie-break on node_id
    assert pool.match() == ["big", "mid", "small"]


def test_match_limit_and_withdraw():
    pool = make_pool()
    assert pool.match(limit=2) == ["big", "mid"]
    pool.withdraw("big")
    assert pool.match() == ["mid", "small"]


def test_replication_one_accepts_single_vote(tmp_path, monkeypatch):
    """replication=1: one honest vote settles the chunk; no tiebreaker
    is farmed when nothing disagrees."""
    from tests.test_mesh_tasks import build_fleet

    nodes, workers, pool = build_fleet(2, tmp_path / "rdv1")
    # farmer node stays compute-free: drop it from the pool and stop its
    # worker, since farmer and worker share the node's inbox.
    pool.withdraw(nodes[0].node_id)
    workers[0].stop()
    farmer = TaskFarmer(nodes[0], pool)
    try:
        result = farmer.submit(
            b"x" * 64,
            "sha256_hex",
            num_chunks=4,
            replication=1,
            chunk_timeout=1.0,
            timeout=20.0,
        )
        assert result["chunks"] == 4
        assert len(result["results"]) == 4
        assert result["reassignments"] == 0
    finally:
        for w in workers:
            w.stop()
        for n in nodes:
            n.leave()


def test_truth_view_is_founder_gated(tmp_path):
    ledger = ContributionLedger(tmp_path / "ledger.jsonl")
    ledger.record("n1", "contributed", 3)
    with pytest.raises(PermissionError):
        ledger.truth_view(founder=False)
    entries = ledger.truth_view(founder=True)
    assert entries and entries[0]["node_id"] == "n1"
