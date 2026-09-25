"""Alpha symbiotic proof: Alpha never builds from an unvalidated or
quarantined blueprint; every build carries a receipt or it didn't happen.

Proof method (honest name): black-box behavioral tests over
``compile_blueprint_guarded`` — four runs covering each guard in the
chain plus the happy path. Each run asserts receipts in the shared
substrate, not just return values. This is NOT formal verification; it
is regression proof that the guard logic holds.
"""

import pytest

from levi.revival.omega import generators as gen
from levi.revival.omega import substrate as sub


def _valid_blueprint():
    return {
        "name": "sym-test",
        "title": "Sym Test",
        "prompt": "a test app for the alpha symbiotic loop",
        "product_types": ["cli"],
        "components": [],
        "layers": [],
        "artifacts": [],
    }


def _blueprint_receipt(substrate, quarantined=False, challenger="nexus"):
    """Echo publishes a blueprint receipt into the shared pool."""
    receipt = substrate.record_receipt(
        organ="echo",
        kind="blueprint",
        payload={"name": "sym-test"},
        risk=sub.RISK_STANDARD,
    )
    if quarantined:
        substrate.challenge(challenger, receipt.id, "suspect provenance")
    return receipt


def test_quarantined_blueprint_refused_with_receipt():
    substrate = sub.SharedSubstrate()
    bp_rcpt = _blueprint_receipt(substrate, quarantined=True)

    result = gen.compile_blueprint_guarded(
        substrate, _valid_blueprint(), bp_rcpt.id, approved_by="test"
    )

    assert result["ok"] is False
    assert result["refusal"] == "blueprint quarantined or unknown"
    assert result["receipt_id"]
    # A refusal is itself recorded — Alpha writes, always.
    refusal = substrate.get_receipt(result["receipt_id"])
    assert refusal.organ == "alpha"
    assert refusal.kind == "build_refusal"
    # Nothing was built.
    assert not substrate.receipts(organ="alpha", kind="build")


def test_unknown_blueprint_receipt_refused_with_receipt():
    substrate = sub.SharedSubstrate()
    result = gen.compile_blueprint_guarded(
        substrate, _valid_blueprint(), "rcpt_does_not_exist", approved_by="test"
    )
    assert result["ok"] is False
    assert result["refusal"] == "blueprint quarantined or unknown"
    assert substrate.get_receipt(result["receipt_id"]).kind == "build_refusal"
    assert not substrate.receipts(organ="alpha", kind="build")


def test_invalid_blueprint_challenged_back_to_echo():
    substrate = sub.SharedSubstrate()
    bp_rcpt = _blueprint_receipt(substrate)

    bad = {"name": "sym-test"}  # missing title, prompt, product_types, ...
    result = gen.compile_blueprint_guarded(
        substrate, bad, bp_rcpt.id, approved_by="test"
    )

    assert result["ok"] is False
    assert result["challenged"] is True
    assert result["errors"]
    # Interrogation path: Alpha's challenge quarantined Echo's blueprint.
    quarantined_ids = [r.id for r in substrate.quarantined()]
    assert bp_rcpt.id in quarantined_ids
    challenges = substrate.challenges(status="open")
    assert any(
        c.challenger == "alpha" and c.target_receipt_id == bp_rcpt.id
        for c in challenges
    )
    # Nothing was built — no build receipt, no build_refusal either:
    # the invalid blueprint never reached the ceiling gate.
    assert not substrate.receipts(organ="alpha", kind="build")
    assert not substrate.receipts(organ="alpha", kind="build_refusal")


def test_elevated_risk_without_approval_refused():
    substrate = sub.SharedSubstrate()
    bp_rcpt = _blueprint_receipt(substrate)

    result = gen.compile_blueprint_guarded(
        substrate, _valid_blueprint(), bp_rcpt.id, approved_by=None
    )

    assert result["ok"] is False
    assert result["refusal"] == "approval required"
    assert result["ceiling"] == sub.RISK_ELEVATED
    refusal = substrate.get_receipt(result["receipt_id"])
    assert refusal.organ == "alpha"
    assert refusal.kind == "build_refusal"
    assert refusal.payload["ceiling"] == sub.RISK_ELEVATED
    assert not substrate.receipts(organ="alpha", kind="build")


def test_happy_path_build_carries_receipt():
    substrate = sub.SharedSubstrate()
    bp_rcpt = _blueprint_receipt(substrate)

    result = gen.compile_blueprint_guarded(
        substrate, _valid_blueprint(), bp_rcpt.id, approved_by="test"
    )

    assert result["ok"] is True
    assert result["files"]  # the cli scaffold actually produced files
    assert "sym-test/sym_test.py" in result["files"]
    receipt_id = result["receipt_id"]
    receipt = substrate.get_receipt(receipt_id)
    assert receipt is not None
    assert receipt.organ == "alpha"
    assert receipt.kind == "build"
    assert receipt.approved_by == "test"
    assert receipt.risk == sub.RISK_ELEVATED
    # File manifest: name -> byte length, covering every produced file.
    manifest = receipt.payload["files"]
    assert set(manifest) == set(result["files"])
    assert all(n > 0 for n in manifest.values())
    assert receipt.payload["blueprint_receipt"] == bp_rcpt.id
    assert receipt.payload["generator"] == gen.ORIGIN
    # The build receipt is consumable: the loop's next organ can take it.
    assert substrate.is_consumable(receipt_id) is True
