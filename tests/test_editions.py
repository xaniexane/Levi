"""Edition system tests: manifests resolve, rings hold, refusals stand.

Wave E1 for editions. These tests lock the edition contract:

1. Every edition manifest validates against the real 471-agent catalog:
   every roster slot resolves to agents, counts are satisfiable.
2. No edition trains on sector data — enforced in validation.
3. Ring discipline: the open-creational edition is the only OPEN ring
   member; military and government editions sit in the GOVERNMENT ring.
4. The file boundary is mechanical: ring_for_path classifies open,
   closed, government, and unknown (deny-open) paths correctly.
5. Every edition names deliberate refusals, each with a reason.
"""

import sys

import pytest

sys.path.insert(0, "core")

from levi.automation.minions import MINIONS
from levi.editions import (
    GOVERNMENT_HARDENING_CHECKLIST,
    Ring,
    ring_for_path,
)
from levi.editions.catalog import EDITIONS, editions_for_ring, get_edition
from levi.editions.manifest import resolve_roster, validate_manifest

EXPECTED_IDS = {
    "education",
    "law-enforcement",
    "military",
    "government",
    "healthcare",
    "first-responders",
    "legal",
    "nonprofit",
    "business",
    "industrial",
    "open-creational",
}


def test_all_editions_present():
    assert set(EDITIONS) == EXPECTED_IDS


def test_every_manifest_validates_clean():
    for eid, manifest in EDITIONS.items():
        problems = validate_manifest(manifest, MINIONS)
        assert problems == [], f"{eid}: {problems}"


def test_roster_resolution_is_deterministic_and_sized():
    for eid, manifest in EDITIONS.items():
        first = resolve_roster(manifest, MINIONS)
        second = resolve_roster(manifest, MINIONS)
        assert [a.id for a in first] == [a.id for a in second]
        assert len(first) == manifest.roster_size(), eid
        assert len({a.id for a in first}) == len(first), f"{eid}: dupes"


def test_no_edition_trains_on_sector_data():
    for eid, manifest in EDITIONS.items():
        assert manifest.data_posture.trains_on_data is False, eid


def test_ring_discipline():
    assert get_edition("open-creational").ring is Ring.OPEN_CREATIONAL
    assert get_edition("military").ring is Ring.GOVERNMENT
    assert get_edition("government").ring is Ring.GOVERNMENT
    open_editions = editions_for_ring(Ring.OPEN_CREATIONAL)
    assert [e.id for e in open_editions] == ["open-creational"]
    assert get_edition("open-creational").roster_size() == 0


def test_ring_for_path_boundaries():
    assert (
        ring_for_path("core/levi/editions/schema/edition-template.json")
        is Ring.OPEN_CREATIONAL
    )
    assert ring_for_path("core/levi/editions/DESIGN.md") is Ring.OPEN_CREATIONAL
    assert ring_for_path("core/levi/editions/catalog.py") is Ring.CLOSED
    assert ring_for_path("core/levi/automation/minions.py") is Ring.CLOSED
    assert ring_for_path("core/levi/editions/government/profile.py") is Ring.GOVERNMENT
    # deny-open: unknown paths classify CLOSED, never OPEN
    assert ring_for_path("core/levi/brain/weights/tiny-gpt.pt") is Ring.CLOSED
    assert ring_for_path("some/random/file.txt") is Ring.CLOSED


def test_government_checklist_has_twelve_gates():
    assert len(GOVERNMENT_HARDENING_CHECKLIST) == 12
    for name, desc in GOVERNMENT_HARDENING_CHECKLIST:
        assert name and desc, "every gate needs a name and a description"
    names = [n for n, _ in GOVERNMENT_HARDENING_CHECKLIST]
    assert "sovereign-off-switch" in names
    assert "no-training-attestation" in names


def test_every_edition_names_its_refusals():
    for eid, manifest in EDITIONS.items():
        assert manifest.excluded, f"{eid}: no refusals named"
        for what, why in manifest.excluded:
            assert what and why, f"{eid}: refusal without a reason"


def test_safety_refusals_present():
    le = get_edition("law-enforcement").to_dict()
    refused = " ".join(r["what"] for r in le["excluded"])
    assert "surveillance" in refused
    mil = get_edition("military").to_dict()
    refused = " ".join(r["what"] for r in mil["excluded"])
    assert "targeting" in refused
    hc = get_edition("healthcare").to_dict()
    refused = " ".join(r["what"] for r in hc["excluded"])
    assert "diagnosis" in refused


def test_to_dict_shape():
    d = get_edition("education").to_dict()
    assert d["ring"] == "closed"
    assert d["roster_size"] == 6
    assert d["data_posture"]["trains_on_data"] is False
    assert isinstance(d["excluded"], list) and d["excluded"]
