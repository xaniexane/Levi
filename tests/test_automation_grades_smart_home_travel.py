"""Grade-manifest tests for the Smart Home & IoT + Travel & Local minion batch.

Batch slug: smart_home_travel. All 78 minions are expected at grade
``enterprise`` (the top); the known truncated intake row
``productivity-calendar-conflict-03`` is not in this batch, so zero
exceptions are expected — any record below enterprise fails loudly.
"""

import json
from pathlib import Path

from levi.automation import grading
from levi.automation.minions import by_category

MANIFEST_PATH = Path("core/levi/automation/grade_data/smart_home_travel.json")

CATEGORIES = ("Smart Home & IoT", "Travel & Local")


def _load():
    with MANIFEST_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def test_manifest_loads_and_verifies():
    data = _load()
    assert data["record_count"] == len(data["records"]) == 78
    assert grading.verify_manifest(data) is True
    assert data["catalog_signature_verified"] is True


def test_record_ids_match_batch_exactly():
    data = _load()
    expected = {m.id for cat in CATEGORIES for m in by_category(cat)}
    assert len(expected) == 78
    actual = {r["minion_id"] for r in data["records"]}
    assert actual == expected, (
        f"manifest id drift: missing={sorted(expected - actual)} "
        f"extra={sorted(actual - expected)}"
    )


def test_every_record_is_enterprise():
    data = _load()
    below = [
        (r["minion_id"], r["grade"])
        for r in data["records"]
        if r["grade"] != "enterprise"
    ]
    assert below == [], f"minions not at enterprise: {below}"


def test_enterprise_evidence_and_doc_present():
    data = _load()
    problems = []
    for r in data["records"]:
        mid = r["minion_id"]
        if r["grade"] != "enterprise":
            continue
        elite = r["evidence"].get("elite", {})
        ent = r["evidence"].get("enterprise", {})
        if elite.get("rail_ok") is not True:
            problems.append((mid, "elite.rail_ok"))
        if ent.get("operator_ok") is not True:
            problems.append((mid, "enterprise.operator_ok"))
        if not r.get("doc"):
            problems.append((mid, "doc empty"))
        if not r.get("genesis", {}).get("white_label"):
            problems.append((mid, "genesis.white_label empty"))
    assert problems == [], f"enterprise evidence gaps: {problems}"
