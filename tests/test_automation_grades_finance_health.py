"""Grade-manifest tests for the finance_health batch.

Finance & Money (38) + Health & Fitness (38) = 76 minions. The rubric
(keeper's order 2026-09-18, core/levi/automation/grading.py) climbs every
minion high-grade -> premium -> elite -> enterprise. The known truncated
intake row (productivity-calendar-conflict-03) is not in this batch, so
zero exceptions are expected: every record must be enterprise.

Schema-fidelity: this test reads the catalog and the manifest; it edits
neither (catalog rows stay verbatim under their Echo x Mandella
signatures).
"""

import json
from pathlib import Path

from levi.automation import grading
from levi.automation.minions import by_category

MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent
    / "core"
    / "levi"
    / "automation"
    / "grade_data"
    / "finance_health.json"
)

BATCH_CATEGORIES = ("Finance & Money", "Health & Fitness")


def _load_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_manifest_loads_and_batch_matches():
    data = _load_manifest()
    assert data["batch"] == "finance_health"
    assert data["record_count"] == 76


def test_manifest_signature_verifies():
    data = _load_manifest()
    assert grading.verify_manifest(data) is True


def test_catalog_signature_verified():
    data = _load_manifest()
    assert data["catalog_signature_verified"] is True


def test_record_ids_match_catalog_batch_exactly():
    data = _load_manifest()
    batch = []
    for category in BATCH_CATEGORIES:
        batch.extend(by_category(category))
    expected_ids = {m.id for m in batch}
    assert expected_ids, "batch selection must not be empty"
    assert len(expected_ids) == 76
    manifest_ids = {r["minion_id"] for r in data["records"]}
    assert manifest_ids == expected_ids, (
        "manifest ids must equal exactly the ids of the two categories"
    )


def test_every_record_is_enterprise():
    data = _load_manifest()
    non_enterprise = [
        (r["minion_id"], r["grade"])
        for r in data["records"]
        if r["grade"] != "enterprise"
    ]
    assert not non_enterprise, (
        "fail loudly: records below enterprise: "
        + ", ".join(f"{mid}={grade}" for mid, grade in non_enterprise)
    )
    counts = data["grade_counts"]
    assert counts["enterprise"] == 76
    assert sum(counts.values()) == 76


def test_enterprise_evidence_complete():
    data = _load_manifest()
    for record in data["records"]:
        mid = record["minion_id"]
        assert record["grade"] == "enterprise", mid
        evidence = record["evidence"]
        assert evidence["elite"]["rail_ok"] is True, mid
        assert evidence["enterprise"]["operator_ok"] is True, mid
        assert record["doc"], f"doc empty for {mid}"
        assert record["genesis"].get("white_label"), (
            f"genesis.white_label missing for {mid}"
        )
