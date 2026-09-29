"""LEVI omega-bulk skill pack tests (Omega bulk import, 2026-09-25).

``omega_bulk_skills.OMEGA_BULK_SKILLS`` is built data-driven from
``core/levi/skill/omega_bulk_data.jsonl`` (exactly 10,000 records drawn
from Chauncey's parked Omega archive). These tests are the PROOF gate:

- exactly 10,000 skills register, ids unique, id scheme
  ``omega-bulk.<slug>``;
- honesty invariants: category == "omega-bulk", INFO risk, no
  permissions, no confirmation, description prefixed
  "Omega catalog stub:";
- stub dispatch returns the catalog instructions text with the stub
  banner and never claims execution;
- all 1,233 pre-existing registry skills are unaffected;
- data file is intact: 10,000 lines, valid JSON, unique ids.

Run:  python3 -m pytest tests/test_omega_bulk_skills.py -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Repo-relative import of the uninstalled core package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "core") not in sys.path:
    sys.path.insert(0, str(ROOT / "core"))

from levi.skill.registry import SkillRegistry, SkillRisk  # noqa: E402
from levi.skill import omega_bulk_skills  # noqa: E402

DATA_PATH = ROOT / "core" / "levi" / "skill" / "omega_bulk_data.jsonl"
STUB_PREFIX = "Omega catalog stub:"


def _records():
    recs = []
    with DATA_PATH.open(encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if raw:
                recs.append(json.loads(raw))
    return recs


def test_data_file_has_exactly_10000_records():
    recs = _records()
    assert len(recs) == 10_000, f"expected 10000 records, got {len(recs)}"
    ids = [r["id"] for r in recs]
    assert len(set(ids)) == 10_000, "duplicate ids in data file"
    for r in recs:
        assert r["id"].startswith("omega-bulk."), r["id"]
        assert r["name"] and r["instructions"], r["id"]


def test_pack_registers_exactly_10000():
    assert len(omega_bulk_skills.OMEGA_BULK_SKILLS) == 10_000
    assert omega_bulk_skills.expected_count() == 10_000
    ids = [s.id for s in omega_bulk_skills.OMEGA_BULK_SKILLS]
    assert len(set(ids)) == 10_000, "duplicate skill ids in pack"


def test_honesty_invariants_across_pack():
    for s in omega_bulk_skills.OMEGA_BULK_SKILLS:
        assert s.category == "omega-bulk", s.id
        assert s.risk_level == SkillRisk.INFO, s.id
        assert s.permissions == [], s.id
        assert s.requires_confirmation is False, s.id
        assert s.description.startswith(STUB_PREFIX), s.id
        assert "omega" in s.tags and "catalog-stub" in s.tags, s.id


def test_stub_dispatch_never_claims_execution():
    reg = SkillRegistry()
    sample = omega_bulk_skills.OMEGA_BULK_SKILLS[0]
    out = reg.invoke(sample.id)
    assert "Omega catalog stub" in out
    assert "nothing was executed" in out
    lowered = out.lower()
    assert "executed successfully" not in lowered
    assert "action completed" not in lowered


def test_registry_totals_and_preexisting_unaffected():
    reg = SkillRegistry()
    assert len(reg.list()) == 11_233, f"total {len(reg.list())}"
    assert len(reg.list(category="omega-bulk")) == 10_000
    # Pre-existing skills resolve exactly as before the import.
    assert reg.get("status") is not None
    assert reg.get("factory.intake_triage") is not None
    assert reg.get("status").category == "system"
    # No id collisions between packs.
    all_ids = [s.id for s in reg.list()]
    assert len(set(all_ids)) == len(all_ids)


def test_expected_ids_match_data_file():
    assert omega_bulk_skills.expected_ids() == [
        s.id for s in omega_bulk_skills.OMEGA_BULK_SKILLS
    ]
