"""Grade manifest tests — productivity batch A (first half).

Covers the first 42 Productivity minions by id. Asserts the manifest
loads, its Echo x Mandella signature verifies, the catalog signature
verified at write time, the record id set equals exactly the 42 minion
ids, and that every record climbed to ``enterprise`` except
``productivity-calendar-conflict-03`` — a truncated verbatim intake row
preserved as authored, honestly capped at ``intake`` with a recorded
``cap_reason`` (do not "fix" it; schema-fidelity law holds).
"""

from __future__ import annotations

import json
import os

import pytest

from levi.automation import grading
from levi.automation.minions import by_category

MANIFEST_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "core",
    "levi",
    "automation",
    "grade_data",
    "productivity_a.json",
)

EXPECTED_IDS = sorted(
    m.id for m in sorted(by_category("Productivity"), key=lambda m: m.id)[:42]
)

# The one honestly-capped row: truncated verbatim intake, preserved as
# authored. Grade ``intake``, with a cap_reason, per the rubric law.
INTAKE_ID = "productivity-calendar-conflict-03"


@pytest.fixture(scope="module")
def manifest():
    with open(MANIFEST_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def test_manifest_loads_and_signs(manifest):
    assert manifest["batch"] == "productivity_a"
    assert manifest["record_count"] == 42
    assert grading.verify_manifest(manifest) is True


def test_catalog_signature_verified(manifest):
    assert manifest["catalog_signature_verified"] is True


def test_record_id_set_matches_batch(manifest):
    ids = sorted(r["minion_id"] for r in manifest["records"])
    assert ids == EXPECTED_IDS


def test_grades_enterprise_except_honest_intake(manifest):
    for record in manifest["records"]:
        if record["minion_id"] == INTAKE_ID:
            assert record["grade"] == "intake"
            cap_reason = record["evidence"]["high_grade"].get("cap_reason")
            assert cap_reason and cap_reason.strip(), "cap_reason must be recorded"
        else:
            assert record["grade"] == "enterprise", (
                f"{record['minion_id']} stopped at {record['grade']}"
            )


def test_enterprise_records_have_top_bar(manifest):
    for record in manifest["records"]:
        if record["grade"] != "enterprise":
            continue
        evidence = record["evidence"]
        assert evidence["elite"]["rail_ok"] is True, record["minion_id"]
        assert evidence["enterprise"]["operator_ok"] is True, record["minion_id"]
        assert record["doc"], f"{record['minion_id']}: doc must be non-empty"
        assert record["genesis"].get("white_label"), (
            f"{record['minion_id']}: genesis.white_label must be set"
        )
