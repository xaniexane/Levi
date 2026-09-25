"""Grade-manifest tests for the Productivity batch b (prod[42:]).

Every minion climbed to ``enterprise`` except the truncated verbatim
intake row ``productivity-calendar-conflict-03`` when it lands in this
half — it stays honestly capped at ``intake`` and is never "fixed".
"""
from __future__ import annotations

import json
from pathlib import Path

from levi.automation import grading
from levi.automation.minions import by_category

MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent
    / "core" / "levi" / "automation" / "grade_data" / "productivity_b.json"
)

# The intake row preserved verbatim as authored (honestly capped, never fixed).
TRUNCATED_INTAKE_ID = "productivity-calendar-conflict-03"


def _batch_ids():
    prod = sorted(by_category("Productivity"), key=lambda m: m.id)
    return [m.id for m in prod[42:]]


def _load():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_loads_and_is_signed():
    data = _load()
    assert data["batch"] == "productivity_b"
    assert data["record_count"] == len(data["records"]) == 41
    assert data["signature_id"], "manifest carries no Echo x Mandella signature"


def test_manifest_signature_verifies():
    data = _load()
    assert grading.verify_manifest(data) is True
    assert data["catalog_signature_verified"] is True


def test_record_id_set_matches_batch():
    data = _load()
    record_ids = {r["minion_id"] for r in data["records"]}
    assert record_ids == set(_batch_ids())


def test_grades():
    data = _load()
    for record in data["records"]:
        if record["minion_id"] == TRUNCATED_INTAKE_ID:
            assert record["grade"] == "intake"
            assert record["evidence"]["high_grade"].get("cap_reason"), (
                f"{TRUNCATED_INTAKE_ID} capped at intake but no cap_reason recorded"
            )
        else:
            assert record["grade"] == "enterprise", (
                f"{record['minion_id']} grade {record['grade']!r}"
            )


def test_enterprise_evidence():
    data = _load()
    for record in data["records"]:
        if record["grade"] != "enterprise":
            continue
        mid = record["minion_id"]
        elite = record["evidence"].get("elite", {})
        assert elite.get("rail_ok") is True, f"{mid}: elite.rail_ok missing"
        enterprise = record["evidence"].get("enterprise", {})
        assert enterprise.get("operator_ok") is True, (
            f"{mid}: enterprise.operator_ok missing"
        )
        assert record["doc"], f"{mid}: doc record empty"
        assert record["genesis"].get("white_label"), (
            f"{mid}: genesis.white_label missing"
        )
