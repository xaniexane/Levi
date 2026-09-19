"""Editions re-forged onto the new canon.

Tests lock the re-forge contract (core/levi/editions/reforge.py):

1. Odd law: every shipping edition resolves to an ODD agent total;
   open-creational (ships nothing) stays empty and exempt.
2. No duplicates, enterprise-only, and the intake-capped row never ships.
3. Counsel mapping: each agent counseled by its class's counsel
   (AI->AICI, SI->SICI, XI->XICI), and slot counsel demands hold.
4. Twin pairs present on every resolved agent.
5. Determinism: forged resolution is stable across runs.
6. Sector intent preserved: authored slots untouched and in order; the
   only change is the appended odd-law seat where the authored total
   was even.
7. NFT license descriptors: white-label buyer naming, blank/LEVI names
   refused, even agent counts fail closed, open-creational has no license.
"""

import sys

import pytest

sys.path.insert(0, "core")

from levi.editions.catalog import EDITIONS
from levi.editions.manifest import Ring
from levi.editions.reforge import (
    COUNSEL_FOR_CLASS,
    INTAKE_CAPPED_ID,
    ODD_LAW_SEAT,
    ReforgeError,
    build_edition_license_descriptor,
    check_slot_counsel_consistency,
    descriptor_for_edition,
    edition_forge_report,
    forged_slots,
    forged_size,
    load_agents,
    resolve_forged_roster,
    slot_counsel,
    verify_forged,
)

SHIPPING_IDS = [eid for eid in EDITIONS if EDITIONS[eid].ring is not Ring.OPEN_CREATIONAL]

ALL_AGENTS = load_agents()


def _resolve_all():
    return {eid: resolve_forged_roster(m, agents=ALL_AGENTS)
            for eid, m in EDITIONS.items() if eid in SHIPPING_IDS}


def test_odd_law_holds_for_every_shipping_edition():
    for eid in SHIPPING_IDS:
        manifest = EDITIONS[eid]
        assert forged_size(manifest) % 2 == 1, eid


def test_forged_resolution_sizes_match():
    for eid in SHIPPING_IDS:
        manifest = EDITIONS[eid]
        resolved = resolve_forged_roster(manifest, agents=ALL_AGENTS)
        assert len(resolved) == forged_size(manifest), eid
        assert len(resolved) % 2 == 1, eid


def test_open_creational_ships_nothing_and_stays_exempt():
    manifest = EDITIONS["open-creational"]
    assert forged_slots(manifest) == []
    assert forged_size(manifest) == 0
    assert resolve_forged_roster(manifest, agents=ALL_AGENTS) == []
    with pytest.raises(ReforgeError):
        build_edition_license_descriptor(
            manifest, buyer_business_name="Some Studio", agents=ALL_AGENTS)


def test_expected_odd_totals():
    # Even-authored totals gain exactly one odd-law seat: 6->7, 8->9.
    expected = {
        "education": 7,
        "law-enforcement": 9,
        "military": 7,
        "government": 7,
        "healthcare": 7,
        "first-responders": 5,
        "legal": 5,
        "nonprofit": 5,
        "business": 7,
        "industrial": 5,
    }
    for eid, total in expected.items():
        assert forged_size(EDITIONS[eid]) == total, eid


def test_no_duplicates_and_intake_capped_refused():
    for eid, resolved in _resolve_all().items():
        ids = [a["agent_id"] for a in resolved]
        assert len(set(ids)) == len(ids), f"{eid}: dupes"
        assert INTAKE_CAPPED_ID not in ids, f"{eid}: intake-capped shipped"


def test_enterprise_only():
    for eid, resolved in _resolve_all().items():
        for a in resolved:
            assert a["grade"] == "enterprise", f"{eid}: {a['agent_id']}"


def test_counsel_matches_class_for_every_agent():
    for eid, resolved in _resolve_all().items():
        for a in resolved:
            expected = COUNSEL_FOR_CLASS[a["class_tag"]]
            assert a["counsel_name"] == expected, (
                f"{eid}: {a['agent_id']} class {a['class_tag']} "
                f"counseled by {a['counsel_name']}, want {expected}")


def test_slot_counsel_consistency():
    for eid in SHIPPING_IDS:
        manifest = EDITIONS[eid]
        resolved = resolve_forged_roster(manifest, agents=ALL_AGENTS)
        problems = check_slot_counsel_consistency(manifest, resolved)
        assert problems == [], f"{eid}: {problems}"


def test_slot_counsel_demands_follow_side():
    m = EDITIONS["education"]
    counsels = {slot_counsel(s) for s in forged_slots(m)}
    assert "AICI" in counsels and "SICI" in counsels
    # the odd-law seat is "either": no counsel demanded, any class allowed
    assert counsels >= {"AICI", "SICI", None}


def test_twin_pairs_present_on_every_agent():
    for eid, resolved in _resolve_all().items():
        for a in resolved:
            assert a.get("pair_id"), f"{eid}: {a['agent_id']} no pair_id"
            left = a.get("left") or {}
            right = a.get("right") or {}
            assert left.get("hemisphere_id"), f"{eid}: {a['agent_id']} no left"
            assert right.get("hemisphere_id"), f"{eid}: {a['agent_id']} no right"


def test_verify_forged_is_clean_for_all():
    for eid in SHIPPING_IDS:
        problems = verify_forged(
            EDITIONS[eid],
            resolve_forged_roster(EDITIONS[eid], agents=ALL_AGENTS))
        assert problems == [], f"{eid}: {problems}"


def test_resolution_is_deterministic():
    for eid in SHIPPING_IDS:
        first = resolve_forged_roster(EDITIONS[eid], agents=ALL_AGENTS)
        second = resolve_forged_roster(EDITIONS[eid], agents=ALL_AGENTS)
        assert [a["agent_id"] for a in first] == [a["agent_id"] for a in second]


def test_sector_intent_preserved():
    for eid in SHIPPING_IDS:
        manifest = EDITIONS[eid]
        forged = forged_slots(manifest)
        authored = list(manifest.roster)
        # every authored slot survives, in order, with its intent fields
        assert forged[: len(authored)] == authored, eid
        for slot in authored:
            assert slot.category and slot.purpose, f"{eid}: slot lost intent"
        # the only addition is the odd-law seat, appended where needed
        if manifest.roster_size() % 2 == 0:
            assert forged[-1] == ODD_LAW_SEAT, eid
            assert len(forged) == len(authored) + 1
        else:
            assert forged == authored, eid


def test_authored_catalog_data_untouched():
    # The re-forge adapts; it never rewrites the keeper's authored data.
    assert EDITIONS["education"].roster_size() == 6
    assert EDITIONS["law-enforcement"].roster_size() == 8
    assert EDITIONS["business"].roster_size() == 6
    assert EDITIONS["industrial"].roster_size() == 5
    assert EDITIONS["open-creational"].roster_size() == 0


def test_license_descriptor_white_label_naming():
    d = descriptor_for_edition(
        "education", buyer_business_name="Harborlight Academy", agents=ALL_AGENTS)
    assert d["buyer_business"] == "Harborlight Academy"
    assert "Harborlight Academy" in d["license"]["note"]
    assert d["edition"]["id"] == "education"
    assert d["odd_law"]["agent_count"] % 2 == 1
    assert d["odd_law"]["agent_count"] == 7
    assert set(d["counsel_map"]) <= {"AICI", "SICI", "XICI"}
    assert len(d["twin_pairs"]) == 7
    for pair in d["twin_pairs"]:
        assert pair["pair_id"] and pair["left"]["hemisphere_id"] \
            and pair["right"]["hemisphere_id"]
    # no LEVI branding on the customer-facing surface
    assert "levi" not in d["buyer_business"].lower()
    assert "levi" not in d["license"]["note"].lower()


def test_license_descriptor_rejects_bad_names():
    for bad in ("", "   ", "Levi Systems Inc", "LEVI"):
        with pytest.raises(Exception):
            descriptor_for_edition(
                "legal", buyer_business_name=bad, agents=ALL_AGENTS)


def test_license_descriptor_enforces_odd_law():
    # An even agent list cannot be licensed, even explicitly handed in.
    manifest = EDITIONS["legal"]
    even = resolve_forged_roster(manifest, agents=ALL_AGENTS)[:4]
    assert len(even) == 4
    with pytest.raises(ReforgeError):
        build_edition_license_descriptor(
            manifest, buyer_business_name="Cedar & Vine LLP",
            resolved=even, agents=ALL_AGENTS)
    # ...while the genuine odd roster licenses fine
    d = build_edition_license_descriptor(
        manifest, buyer_business_name="Cedar & Vine LLP",
        agents=ALL_AGENTS)
    assert d["odd_law"]["agent_count"] == 5


def test_license_descriptor_unknown_edition():
    with pytest.raises(ReforgeError):
        descriptor_for_edition("fishing", buyer_business_name="Pond Co.",
                               agents=ALL_AGENTS)


def test_forge_report_shape():
    r = edition_forge_report(EDITIONS["business"], agents=ALL_AGENTS)
    assert r["edition_id"] == "business"
    assert r["agent_count"] == 7
    assert r["odd_law_holds"] is True
    assert r["odd_law_seat_added"] is True
    assert r["problems"] == []
    assert len(r["agent_ids"]) == 7
    r2 = edition_forge_report(EDITIONS["industrial"], agents=ALL_AGENTS)
    assert r2["odd_law_seat_added"] is False
    assert r2["agent_count"] == 5
