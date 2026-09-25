"""Tests for the attest hash-chain attestation engine."""

from hashlib import sha256

import pytest

from levi.engines.base import EngineInputError, registry
from levi.engines import attest  # noqa: F401  (self-registers on import)


def _link(prev_id: str, prev_body: str) -> str:
    return sha256(f"{prev_id}\n{prev_body}".encode("utf-8")).hexdigest()


def _chain(n: int = 3, genesis: str = "genesis-anchor"):
    receipts = []
    prev = genesis
    for i in range(n):
        receipts.append({"id": f"r{i}", "body": f"body-{i}", "prev": prev})
        prev = _link(f"r{i}", f"body-{i}")
    return receipts, genesis


def _run(receipts, genesis):
    return registry.get("attest").run({"receipts": receipts, "genesis": genesis})


def test_registered_on_import():
    assert registry.get("attest").id == "attest"


def test_intact_chain():
    receipts, genesis = _chain(4)
    result = _run(receipts, genesis)
    assert result.verdict["status"] == "intact"
    assert result.verdict["receipt_count"] == 4
    assert result.confidence == 1.0
    assert result.trace[-1].startswith("4 receipts")


def test_determinism_law():
    receipts, genesis = _chain(3)
    a = _run(receipts, genesis)
    b = _run(receipts, genesis)
    # ran_at timestamps legitimately differ; verdict + trace must not
    assert a.verdict == b.verdict
    assert a.trace == b.trace
    assert a.confidence == b.confidence


def test_anchor_law_wrong_genesis_breaks_at_zero():
    receipts, _ = _chain(3)
    result = _run(receipts, "forged-anchor")
    assert result.verdict["status"] == "broken"
    assert result.verdict["break_index"] == 0
    assert result.verdict["reason"] == "anchor-mismatch"
    assert result.verdict["expected"] == "forged-anchor"
    assert result.verdict["actual"] == receipts[0]["prev"]


def test_link_law_tampered_body_breaks_at_index():
    receipts, genesis = _chain(4)
    receipts[1] = dict(receipts[1], body="TAMPERED")
    result = _run(receipts, genesis)
    assert result.verdict["status"] == "broken"
    assert result.verdict["break_index"] == 2
    assert result.verdict["reason"] == "link-mismatch"
    # Honest-report law: expected is the recomputed hash of the true
    # predecessor, never invented.
    assert result.verdict["expected"] == _link("r1", "TAMPERED")
    assert result.verdict["actual"] == receipts[2]["prev"]


def test_first_break_law_reports_earliest():
    receipts, genesis = _chain(4)
    receipts[1] = dict(receipts[1], body="TAMPERED-1")
    receipts[3] = dict(receipts[3], prev="also-forged")
    result = _run(receipts, genesis)
    assert result.verdict["break_index"] == 2  # not 3


def test_empty_chain_verdict():
    result = _run([], "genesis-anchor")
    assert result.verdict["status"] == "empty"
    assert result.confidence == 1.0


def test_refuses_non_list_receipts():
    with pytest.raises(EngineInputError):
        _run("not-a-list", "genesis-anchor")


def test_refuses_empty_genesis():
    receipts, _ = _chain(1)
    with pytest.raises(EngineInputError):
        registry.get("attest").run({"receipts": receipts, "genesis": ""})


def test_refuses_malformed_receipt():
    with pytest.raises(EngineInputError):
        _run([{"id": "r0", "body": "x"}], "genesis-anchor")


def test_refuses_missing_inputs():
    with pytest.raises(EngineInputError):
        registry.get("attest").run({"receipts": []})
