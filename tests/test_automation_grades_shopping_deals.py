"""Grade-manifest tests for the Shopping & Deals minion batch.

Keeper's order 2026-09-18: every minion climbs
high-grade -> premium -> elite -> enterprise (the top).

This suite asserts the signed grade manifest for the
``shopping_deals`` batch: it loads, its Echo x Mandella signature
verifies, it covers exactly this batch's minion ids, and every record
sits at enterprise (zero exceptions — the truncated intake row
``productivity-calendar-conflict-03`` is not in this batch).
"""

from __future__ import annotations

import json
from pathlib import Path

from levi.automation import grading
from levi.automation.minions import by_category

MANIFEST_PATH = Path(__file__).resolve().parent.parent / (
    "core/levi/automation/grade_data/shopping_deals.json"
)


def _load_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_manifest_loads_and_has_expected_shape():
    data = _load_manifest()
    assert data["batch"] == "shopping_deals"
    assert data["record_count"] == len(data["records"]) == 38
    assert data["record_count"] > 0


def test_manifest_signature_verifies():
    data = _load_manifest()
    assert grading.verify_manifest(data) is True


def test_catalog_signature_verified_flag():
    data = _load_manifest()
    assert data["catalog_signature_verified"] is True


def test_manifest_covers_exactly_this_batch():
    data = _load_manifest()
    batch_ids = {m.id for m in by_category("Shopping & Deals")}
    manifest_ids = {r["minion_id"] for r in data["records"]}
    assert manifest_ids == batch_ids, (
        f"manifest/record id mismatch: "
        f"missing={sorted(batch_ids - manifest_ids)} "
        f"extra={sorted(manifest_ids - batch_ids)}"
    )


def test_every_record_is_enterprise_no_exceptions():
    data = _load_manifest()
    non_enterprise = [
        (r["minion_id"], r["grade"])
        for r in data["records"]
        if r["grade"] != "enterprise"
    ]
    assert not non_enterprise, (
        "minions failed to reach enterprise: "
        + ", ".join(f"{mid}={grade}" for mid, grade in non_enterprise)
    )
    assert data["grade_counts"]["enterprise"] == 38


def test_enterprise_evidence_complete():
    data = _load_manifest()
    for record in data["records"]:
        mid = record["minion_id"]
        assert record["evidence"]["elite"]["rail_ok"] is True, mid
        assert record["evidence"]["enterprise"]["operator_ok"] is True, mid
        assert record["doc"], f"{mid}: empty doc"
        assert record["genesis"]["white_label"], f"{mid}: genesis.white_label unset"
