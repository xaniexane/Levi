"""Tests for the Genesis odd-law set assembler (levi.genesis.odd_sets).

Keeper's canon: odd counts of agents in Genesis — 1, 3, 5, 7, 9 …
never even. Fail-closed on every violation.
"""

from __future__ import annotations

import copy

import pytest

from levi.genesis import odd_sets
from levi.genesis.odd_sets import (
    GenesisOddLawError,
    assemble_genesis_set,
    check_count,
    check_white_label,
    enterprise_pool,
    load_agent_registry,
    load_grade_index,
    plan_class_counts,
    verify_genesis_package,
)


@pytest.fixture(scope="module")
def registry():
    return load_agent_registry()


@pytest.fixture(scope="module")
def grade_index():
    return load_grade_index()


@pytest.fixture(scope="module")
def pool(registry, grade_index):
    return enterprise_pool(registry, grade_index)


def _kw(**over):
    kw = {"customer_name": "Acme Schools", "sector": "education", "tier": "genesis"}
    kw.update(over)
    return kw


# -- the odd law itself ----------------------------------------------------

@pytest.mark.parametrize("bad", [0, 2, 4, 100, -1, -3, "3", 3.0, None, True, [3]])
def test_even_and_invalid_counts_refused(bad):
    with pytest.raises(GenesisOddLawError):
        check_count(bad)


@pytest.mark.parametrize("good", [1, 3, 5, 7, 9, 101])
def test_odd_counts_accepted(good):
    assert check_count(good) == good


@pytest.mark.parametrize("count", [3, 5, 7])
def test_assembly_happy_path(count, registry, grade_index):
    pkg = assemble_genesis_set(count, registry=registry, grade_index=grade_index,
                               **_kw())
    assert pkg["odd_law"]["count"] == count
    assert len(pkg["agents"]) == count
    assert len({a["agent_id"] for a in pkg["agents"]}) == count
    assert all(a["grade"] == "enterprise" for a in pkg["agents"])
    assert all(a["twin_pair"]["pair_id"] for a in pkg["agents"])
    assert all(a["genesis_descriptor"] for a in pkg["agents"])
    verdict = verify_genesis_package(pkg, registry=registry, grade_index=grade_index)
    assert verdict["ok"], verdict["problems"]


def test_deterministic_draw(registry, grade_index):
    kw = _kw()
    a = assemble_genesis_set(5, registry=registry, grade_index=grade_index, **kw)
    b = assemble_genesis_set(5, registry=registry, grade_index=grade_index, **kw)
    assert a["package_id"] == b["package_id"]
    assert ([e["agent_id"] for e in a["agents"]]
            == [e["agent_id"] for e in b["agents"]])


def test_class_balance_follows_plan(pool):
    by_class = {}
    for agent in pool:
        by_class.setdefault(agent["class_tag"], []).append(agent)
    plan = plan_class_counts(5, by_class)
    # Pools: AI 220, XI 130, SI 120 — base 1 each, remainder to AI, XI.
    assert plan == {"AI": 2, "SI": 1, "XI": 2}
    assert plan_class_counts(3, by_class) == {"AI": 1, "SI": 1, "XI": 1}
    assert plan_class_counts(1, by_class) == {"AI": 1, "SI": 0, "XI": 0}


def test_counsel_mapping_consistent(registry, grade_index):
    pkg = assemble_genesis_set(7, registry=registry, grade_index=grade_index,
                               **_kw())
    for entry in pkg["agents"]:
        assert entry["counsel"] == odd_sets.CLASS_COUNSEL[entry["class_tag"]]


def test_intake_row_never_drawn(registry, grade_index):
    pkg = assemble_genesis_set(9, registry=registry, grade_index=grade_index,
                               **_kw())
    ids = [a["agent_id"] for a in pkg["agents"]]
    assert odd_sets.INTAKE_CAPPED_ID not in ids


# -- explicit selection -----------------------------------------------------

def test_explicit_agent_ids(pool, registry, grade_index):
    ids = sorted(a["agent_id"] for a in pool[:3])
    pkg = assemble_genesis_set(3, agent_ids=ids, registry=registry,
                               grade_index=grade_index, **_kw())
    assert [a["agent_id"] for a in pkg["agents"]] == ids
    assert verify_genesis_package(pkg, registry=registry,
                                  grade_index=grade_index)["ok"]


def test_explicit_duplicates_refused(pool, registry, grade_index):
    ids = [pool[0]["agent_id"], pool[1]["agent_id"], pool[0]["agent_id"]]
    with pytest.raises(GenesisOddLawError, match="duplicate"):
        assemble_genesis_set(3, agent_ids=ids, registry=registry,
                             grade_index=grade_index, **_kw())


def test_explicit_length_mismatch_refused(pool, registry, grade_index):
    ids = [a["agent_id"] for a in pool[:5]]
    with pytest.raises(GenesisOddLawError, match="length"):
        assemble_genesis_set(3, agent_ids=ids, registry=registry,
                             grade_index=grade_index, **_kw())


def test_non_enterprise_refused(pool, registry, grade_index):
    ids = [odd_sets.INTAKE_CAPPED_ID,
           pool[0]["agent_id"], pool[1]["agent_id"]]
    with pytest.raises(GenesisOddLawError, match="not enterprise-grade"):
        assemble_genesis_set(3, agent_ids=ids, registry=registry,
                             grade_index=grade_index, **_kw())


def test_unknown_agent_refused(registry, grade_index):
    pool_ids = [a["agent_id"] for a in enterprise_pool(registry, grade_index)[:2]]
    with pytest.raises(GenesisOddLawError, match="not enterprise-grade"):
        assemble_genesis_set(3, agent_ids=pool_ids + ["no-such-agent"],
                             registry=registry, grade_index=grade_index, **_kw())


def test_count_exceeds_pool_refused(registry, grade_index):
    with pytest.raises(GenesisOddLawError, match="exceeds the enterprise pool"):
        assemble_genesis_set(999, registry=registry, grade_index=grade_index,
                             **_kw())


# -- white-label law ----------------------------------------------------------

def test_white_label_happy_path():
    assert check_white_label("Acme Schools", "Acme Schools Genesis 5") == []


def test_white_label_problems():
    assert check_white_label("", "Genesis 5")  # missing customer
    probs = check_white_label("Acme", "Genesis 5")
    assert any("customer name" in p for p in probs)  # name not carried
    probs = check_white_label("Acme", "LEVI Genesis 5")
    assert any("branding" in p for p in probs)


def test_assembly_refuses_blank_customer(registry, grade_index):
    with pytest.raises(GenesisOddLawError):
        assemble_genesis_set(3, customer_name="  ", registry=registry,
                             grade_index=grade_index)


# -- verification round-trip ---------------------------------------------------

def _tampered(pkg):
    return copy.deepcopy(pkg)


def test_verify_catches_even_count(registry, grade_index):
    pkg = _tampered(assemble_genesis_set(
        3, registry=registry, grade_index=grade_index, **_kw()))
    pkg["odd_law"]["count"] = 4
    verdict = verify_genesis_package(pkg, registry=registry, grade_index=grade_index)
    assert not verdict["ok"]
    assert any("even" in p or "declared count" in p for p in verdict["problems"])


def test_verify_catches_dropped_agent(registry, grade_index):
    pkg = _tampered(assemble_genesis_set(
        5, registry=registry, grade_index=grade_index, **_kw()))
    pkg["agents"].pop()
    verdict = verify_genesis_package(pkg, registry=registry, grade_index=grade_index)
    assert not verdict["ok"]


def test_verify_catches_intake_swap(registry, grade_index, pool):
    pkg = _tampered(assemble_genesis_set(
        3, registry=registry, grade_index=grade_index, **_kw()))
    reg = load_agent_registry()
    intake = next(a for a in reg["agents"]
                  if a["agent_id"] == odd_sets.INTAKE_CAPPED_ID)
    bad = dict(pkg["agents"][0])
    bad["agent_id"] = intake["agent_id"]
    bad["grade"] = "intake"
    pkg["agents"][0] = bad
    verdict = verify_genesis_package(pkg, registry=registry, grade_index=grade_index)
    assert not verdict["ok"]
    assert any("intake-capped" in p or "not enterprise" in p
               for p in verdict["problems"])


def test_verify_catches_package_id_tamper(registry, grade_index):
    pkg = _tampered(assemble_genesis_set(
        3, registry=registry, grade_index=grade_index, **_kw()))
    pkg["package_id"] = "genesis-odd-deadbeefcafe"
    verdict = verify_genesis_package(pkg, registry=registry, grade_index=grade_index)
    assert not verdict["ok"]
    assert any("package_id" in p for p in verdict["problems"])


def test_verify_catches_counsel_mismatch(registry, grade_index):
    pkg = _tampered(assemble_genesis_set(
        3, registry=registry, grade_index=grade_index, **_kw()))
    entry = next(e for e in pkg["agents"] if e["class_tag"] == "AI")
    assert odd_sets.CLASS_COUNSEL["AI"] == "AICI"
    entry["counsel"] = "XICI"  # wrong counsel for an AI-class agent
    verdict = verify_genesis_package(pkg, registry=registry, grade_index=grade_index)
    assert not verdict["ok"]
    assert any("counsel" in p for p in verdict["problems"])


def test_enterprise_pool_excludes_intake(pool):
    assert len(pool) == 470
    assert all(a["grade"] == "enterprise" for a in pool)
    assert odd_sets.INTAKE_CAPPED_ID not in {a["agent_id"] for a in pool}
