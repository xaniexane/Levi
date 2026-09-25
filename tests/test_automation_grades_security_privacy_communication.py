"""Grade-manifest tests — Security & Privacy (39) + Communication (39) minions.

Keeper's order 2026-09-18: every minion climbs
high-grade -> premium -> elite -> enterprise (the top).
This batch's 78 minions are all expected at enterprise; the known
truncated intake row (productivity-calendar-conflict-03) is not in this
batch, so any non-enterprise record fails loudly.
"""

from __future__ import annotations

import json
import os

from levi.automation import grading
from levi.automation.minions import by_category

MANIFEST_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "core",
    "levi",
    "automation",
    "grade_data",
    "security_privacy_communication.json",
)


def _manifest():
    with open(MANIFEST_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _expected_ids():
    batch = by_category("Security & Privacy") + by_category("Communication")
    assert len(batch) == 78, f"expected 78 minions in batch, got {len(batch)}"
    return {m.id for m in batch}


def test_manifest_loads_and_signature_verifies():
    data = _manifest()
    assert data["batch"] == "security_privacy_communication"
    assert data["record_count"] == 78
    assert data["catalog_signature_verified"] is True
    assert grading.verify_manifest(data) is True


def test_record_ids_match_categories_exactly():
    data = _manifest()
    expected = _expected_ids()
    got = {r["minion_id"] for r in data["records"]}
    assert got == expected, (
        f"id mismatch: missing={sorted(expected - got)[:10]} "
        f"extra={sorted(got - expected)[:10]}"
    )


def test_every_record_is_enterprise():
    data = _manifest()
    below = [(r["minion_id"], r["grade"]) for r in data["records"] if r["grade"] != "enterprise"]
    assert not below, f"{len(below)} minion(s) did not reach enterprise: {below}"


def test_enterprise_evidence_and_packaging():
    data = _manifest()
    for record in data["records"]:
        mid = record["minion_id"]
        assert record["grade"] == "enterprise", mid
        evidence = record["evidence"]
        assert evidence["elite"]["rail_ok"] is True, f"{mid}: elite.rail_ok"
        assert evidence["enterprise"]["operator_ok"] is True, f"{mid}: enterprise.operator_ok"
        assert record["doc"], f"{mid}: doc record must be non-empty"
        assert record["genesis"].get("white_label"), f"{mid}: genesis.white_label must be set"
