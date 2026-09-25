"""Tests for the legion_collective package — hermetic, no network, tmp stores."""

import json

import pytest

from levi.legion_collective import canon, conventions as C, manifest, surface_guard
from levi.legion_collective.canon import SIGN_ATTESTATION, CanonLock
from levi.legion_collective.registry import RegistryError, WorkstreamRegistry
from levi.legion_collective.surface_guard import (
    VERDICT_FAIL,
    VERDICT_NEEDS_REVIEW,
    VERDICT_PASS,
)


@pytest.fixture()
def reg(tmp_path):
    return WorkstreamRegistry(store_path=tmp_path / "registry.json")


@pytest.fixture()
def lock(tmp_path):
    return CanonLock(canon_path=tmp_path / "canon.json")


# --- conventions -----------------------------------------------------------
def test_conventions():
    assert C.PLATFORM_CUT == 0.12
    assert C.PLATFORM_CUT_PHYSICAL is None  # OPEN — unset, invent nothing
    assert C.LOOPBACK_HOST == "127.0.0.1"
    assert C.NETWORK_BINDS == ()
    assert C.STATUSES == ("planned", "active", "retired")  # ternary
    assert C.TELEMETRY is False
    assert C.OPT_IN_DEFAULT is False


# --- registry basics -------------------------------------------------------
def test_register_get_list(reg):
    reg.register({"slug": "hub", "title": "HUB KFX2"}, actor="rex")
    got = reg.get("hub")
    assert got["slug"] == "hub"
    assert got["status"] == C.STATUS_PLANNED  # default: planned, not active
    assert got["surface"] == C.SURFACE_GENERAL
    assert got["registered_by"] == "rex"
    assert got["history"] and got["history"][0]["event"] == "registered"
    assert [e["slug"] for e in reg.list()] == ["hub"]
    assert reg.get("nope") is None


def test_register_rejects_bad_input(reg):
    with pytest.raises(RegistryError):
        reg.register({"slug": "Bad Slug!", "title": "x"}, actor="rex")
    with pytest.raises(RegistryError):
        reg.register({"slug": "ok", "title": "  "}, actor="rex")
    with pytest.raises(RegistryError):
        reg.register({"slug": "ok", "title": "x", "status": "launched"}, actor="rex")
    with pytest.raises(RegistryError):
        reg.register({"slug": "ok", "title": "x", "bogus": 1}, actor="rex")
    with pytest.raises(RegistryError):
        reg.register({"slug": "ok", "title": "x", "twin": "ghost"}, actor="rex")


def test_register_duplicate_rejected(reg):
    reg.register({"slug": "hub", "title": "HUB KFX2"}, actor="rex")
    with pytest.raises(RegistryError):
        reg.register({"slug": "hub", "title": "HUB again"}, actor="rex")


def test_twin_must_exist(reg):
    reg.register({"slug": "alpha", "title": "Alpha"}, actor="rex")
    reg.register({"slug": "omega", "title": "Omega", "twin": "alpha"}, actor="rex")
    assert reg.get("omega")["twin"] == "alpha"


def test_store_is_plain_json(reg, tmp_path):
    reg.register({"slug": "hub", "title": "HUB KFX2"}, actor="rex")
    raw = json.loads((tmp_path / "registry.json").read_text(encoding="utf-8"))
    # any sibling can read this with plain json — no private protocol
    assert raw["schema_version"] == C.SCHEMA_VERSION
    assert raw["workstreams"]["hub"]["title"] == "HUB KFX2"
    # reload round-trips
    reg2 = WorkstreamRegistry(store_path=tmp_path / "registry.json")
    assert reg2.get("hub")["title"] == "HUB KFX2"


def test_atomic_save_leaves_no_tmp(reg, tmp_path):
    reg.register({"slug": "hub", "title": "HUB KFX2"}, actor="rex")
    assert not list(tmp_path.glob("*.tmp"))


# --- paired promotion ------------------------------------------------------
def test_promotion_needs_distinct_pair(reg):
    reg.register({"slug": "hub", "title": "HUB KFX2"}, actor="rex")
    reg.propose("hub", actor="rex")
    with pytest.raises(RegistryError):
        reg.verify("hub", actor="rex")  # same identity cannot verify
    assert reg.get("hub")["status"] == C.STATUS_PLANNED
    reg.propose("hub", actor="rex")
    out = reg.verify("hub", actor="chauncey")
    assert out["status"] == C.STATUS_ACTIVE


def test_verify_without_proposal_fails(reg):
    reg.register({"slug": "hub", "title": "HUB KFX2"}, actor="rex")
    with pytest.raises(RegistryError):
        reg.verify("hub", actor="chauncey")


def test_retire_requires_explicit_confirm(reg):
    reg.register({"slug": "hub", "title": "HUB KFX2"}, actor="rex")
    with pytest.raises(RegistryError):
        reg.retire("hub", actor="rex")
    out = reg.retire("hub", actor="rex", confirm=True)
    assert out["status"] == C.STATUS_RETIRED


def test_list_filter_by_status(reg):
    reg.register({"slug": "a", "title": "A"}, actor="rex")
    reg.register({"slug": "b", "title": "B"}, actor="rex")
    reg.propose("b", actor="rex")
    reg.verify("b", actor="chauncey")
    assert [e["slug"] for e in reg.list(status=C.STATUS_ACTIVE)] == ["b"]
    assert [e["slug"] for e in reg.list(status=C.STATUS_PLANNED)] == ["a"]


# --- KFX² seed -------------------------------------------------------------
def test_seed_kfx2_fourteen_workstreams(reg):
    added = reg.seed_kfx2()
    assert len(added) == 14
    entries = reg.list()
    assert len(entries) == 14
    by_slug = {e["slug"]: e for e in entries}
    assert by_slug["legion"]["status"] == C.STATUS_ACTIVE  # this build exists
    for slug, e in by_slug.items():
        if slug != "legion":
            assert e["status"] == C.STATUS_PLANNED, slug  # rest: planned only
        assert e["capabilities"] == []  # owners declare their own; invent nothing
        assert e["plan_doc"]
    # Plaiground = adult, Echoverse = SFW, never merged
    assert by_slug["plaiground"]["surface"] == C.SURFACE_ADULT
    assert by_slug["echoverse"]["surface"] == C.SURFACE_GENERAL
    # idempotent
    assert reg.seed_kfx2() == []
    assert len(reg.list()) == 14


# --- manifests -------------------------------------------------------------
def test_manifest_validate_and_attach(reg):
    reg.seed_kfx2()
    m = manifest.new_manifest(
        "legion",
        [
            {
                "name": "collective-registry",
                "status": "exists",
                "detail": "this registry",
            },
            {"name": "universe-launch", "status": "planned"},
        ],
    )
    assert manifest.validate_manifest(m) == []
    out = manifest.attach(reg, "legion", m, actor="rex")
    assert len(out["capabilities"]) == 2
    assert out["history"][-1]["event"].startswith("manifest attached")
    readable = manifest.readable("legion", reg)
    assert readable["slug"] == "legion"
    assert readable["capabilities"][0]["name"] == "collective-registry"


def test_manifest_validation_errors():
    assert manifest.validate_manifest({})  # not empty
    bad = manifest.new_manifest(
        "x",
        [
            {"name": "", "status": "exists"},
            {"name": "dup", "status": "exists"},
            {"name": "dup", "status": "bogus"},
            {"name": "ok", "status": "exists", "weird": 1},
        ],
    )
    errors = manifest.validate_manifest(bad)
    assert len(errors) >= 4


def test_attach_rejects_mismatched_slug(reg):
    reg.seed_kfx2()
    m = manifest.new_manifest("hub", [{"name": "c", "status": "planned"}])
    with pytest.raises(RegistryError):
        manifest.attach(reg, "legion", m, actor="rex")
    with pytest.raises(RegistryError):
        manifest.attach(reg, "ghost", m, actor="rex")


# --- canon lock ------------------------------------------------------------
def test_canon_starts_unsigned_and_gates_locked(lock):
    state = lock.state()
    assert state["positioning_statement"] is None
    assert state["signed_by"] is None
    for gate in canon.GATES:
        assert lock.gate(gate) == "locked"


def test_canon_signing_fails_closed(lock):
    with pytest.raises(RegistryError):
        lock.sign_positioning("", SIGN_ATTESTATION)
    with pytest.raises(RegistryError):
        lock.sign_positioning("some line", "yeah sure")
    assert lock.state()["signed_by"] is None


def test_canon_signing_with_exact_attestation(lock):
    line = "They sell the chip; we grow the lineage."
    state = lock.sign_positioning(line, SIGN_ATTESTATION)
    assert state["positioning_statement"] == line
    assert state["signed_by"] == "Chauncey"
    assert state["signed_at"]


def test_canon_gates_cannot_release_in_code(lock):
    for gate in canon.GATES:
        with pytest.raises(RegistryError):
            lock.release_gate(gate)
    with pytest.raises(RegistryError):
        lock.gate("not_a_gate")


# --- surface guard ---------------------------------------------------------
def test_guard_pass_clean_with_inventory():
    inv = {"deny": {"codenames": ["Project Nightjar"]}, "review": {}}
    verdict, hits = surface_guard.scan_text("hello world", inv)
    assert verdict == VERDICT_PASS
    assert hits == []


def test_guard_fail_on_deny_hit():
    inv = {"deny": {"codenames": ["Project Nightjar"]}, "review": {}}
    verdict, hits = surface_guard.scan_text("notes on Project Nightjar", inv)
    assert verdict == VERDICT_FAIL
    assert hits and hits[0]["category"] == "codenames"


def test_guard_structural_deny_built_in():
    verdict, _ = surface_guard.scan_text(
        "-----BEGIN RSA PRIVATE KEY-----\nfake", {"deny": {}, "review": {}}
    )
    assert verdict == VERDICT_FAIL


def test_guard_review_verdict():
    inv = {"deny": {}, "review": {"internal": ["internal codename"]}}
    verdict, hits = surface_guard.scan_text("an internal codename list", inv)
    assert verdict == VERDICT_NEEDS_REVIEW
    assert hits[0]["category"] == "internal"


def test_guard_fails_closed_without_inventory():
    verdict, hits = surface_guard.scan_text("totally innocent text", None)
    assert verdict == VERDICT_NEEDS_REVIEW  # cannot prove clean: no pass
    assert hits[0]["category"] == "no_inventory"


def test_guard_scan_mapping():
    inv = {"deny": {"codenames": ["Nightjar"]}, "review": {}}
    payload = {"title": "hello", "nested": {"note": "Nightjar plans", "ok": 1}}
    verdict, hits = surface_guard.scan_mapping(payload, inv)
    assert verdict == VERDICT_FAIL
    assert any(h["path"] == "$.nested.note" for h in hits)


def test_guard_never_mutates_payload():
    inv = {"deny": {"x": ["y"]}, "review": {}}
    payload = {"a": "y here"}
    snapshot = json.dumps(payload, sort_keys=True)
    surface_guard.scan_mapping(payload, inv)
    assert json.dumps(payload, sort_keys=True) == snapshot
