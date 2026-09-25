"""Hermetic tests for AARP self-assigned addressing (AppleTalk revival)."""

import json
import random

import pytest

from levi.telegraph.aarp import (
    AarpError,
    claim_address,
    live_claims,
    release,
    renew,
)

POOL = ["addr-%d" % i for i in range(8)]


def test_claim_returns_pool_address(tmp_path):
    claim = claim_address("node-a", POOL, tmp_path, rng=random.Random(1))
    assert claim.address in POOL
    assert claim.node == "node-a"
    assert claim.probes_sent == 10
    # Probes are transient: none left behind on the wire.
    assert list(tmp_path.glob(".aarp-probe-*")) == []


def test_two_nodes_get_different_addresses(tmp_path):
    a = claim_address("node-a", POOL, tmp_path, rng=random.Random(1))
    b = claim_address("node-b", POOL, tmp_path, rng=random.Random(1))
    assert a.address != b.address


def test_conflict_never_overwrites(tmp_path):
    a = claim_address("node-a", ["only"], tmp_path, rng=random.Random(1))
    # A second node probing the same single address backs off and fails.
    with pytest.raises(AarpError):
        claim_address("node-b", ["only"], tmp_path, rng=random.Random(2))
    assert live_claims(tmp_path)["only"]["node"] == "node-a"
    assert a.address == "only"


def test_stale_claim_does_not_block(tmp_path):
    claim_address(
        "node-a", ["x"], tmp_path, lease_seconds=60, now=1_000_000,
        rng=random.Random(1),
    )
    # The lease expired: the address recycles.
    b = claim_address(
        "node-b", ["x"], tmp_path, lease_seconds=60, now=1_000_000 + 61,
        rng=random.Random(1),
    )
    assert b.address == "x"
    assert live_claims(tmp_path, now=1_000_000 + 61)["x"]["node"] == "node-b"


def test_unprobed_claim_is_refused_by_reader(tmp_path):
    path = tmp_path / "aarp-claims.json"
    path.write_text(
        json.dumps(
            {"sq": {"node": "squat", "claimed_ts": 1_000_000,
                    "lease_seconds": 3600, "probes_sent": 0}}
        )
    )
    # The squatter's claim is invisible: the address is free.
    claim = claim_address(
        "node-a", ["sq"], tmp_path, now=1_000_000, rng=random.Random(1)
    )
    assert claim.address == "sq"


def test_empty_pool_refused(tmp_path):
    with pytest.raises(AarpError):
        claim_address("node-a", [], tmp_path)


def test_renew_refreshes_lease(tmp_path):
    claim_address(
        "node-a", ["x"], tmp_path, lease_seconds=60, now=1_000_000,
        rng=random.Random(1),
    )
    renewed = renew("node-a", "x", tmp_path, lease_seconds=600, now=1_000_050)
    assert renewed.claimed_ts == 1_000_050
    assert renewed.lease_seconds == 600
    # Still live past the original lease.
    assert "x" in live_claims(tmp_path, now=1_000_000 + 100)


def test_renew_foreign_claim_refused(tmp_path):
    claim_address("node-a", ["x"], tmp_path, now=1_000_000, rng=random.Random(1))
    with pytest.raises(AarpError):
        renew("node-b", "x", tmp_path)


def test_release_frees_address(tmp_path):
    claim_address("node-a", ["x"], tmp_path, now=1_000_000, rng=random.Random(1))
    release("node-a", "x", tmp_path)
    assert live_claims(tmp_path, now=1_000_000) == {}
    # Another node may now claim it.
    b = claim_address("node-b", ["x"], tmp_path, now=1_000_000,
                      rng=random.Random(1))
    assert b.address == "x"


def test_release_foreign_claim_refused(tmp_path):
    claim_address("node-a", ["x"], tmp_path, now=1_000_000, rng=random.Random(1))
    with pytest.raises(AarpError):
        release("node-b", "x", tmp_path)


def test_node_name_required(tmp_path):
    with pytest.raises(AarpError):
        claim_address("", POOL, tmp_path)


def test_missing_wire_dir_is_created(tmp_path):
    claim = claim_address("node-a", POOL, tmp_path / "wire", rng=random.Random(3))
    assert claim.address in POOL
