"""Guard tests for the canon COMPONENT registry (L1-L3).

L1: the engine tensor stays exactly 32x64x128; components are never engines.
L2: every component carries a source; no invented descriptions (PENDING markers enforced).
L3: DemandPulse product and DemandPulse engine are recorded separately, never conflated.
"""

import pytest

from levi.legion.skill_pool import canon_registry as cr
from levi.legion.skill_pool.engine_map import ENGINE_TENSOR_SHAPE


def test_tensor_shape_pinned_at_32x64x128():
    assert cr.ENGINE_TENSOR_SHAPE == (32, 64, 128)
    assert ENGINE_TENSOR_SHAPE == (32, 64, 128)
    tensor = cr.get_component("engine_tensor")
    assert tensor["canon_status"] == cr.HISTORIC_CANON


def test_no_engine_kind_components_ever():
    # L1: there is never a 33rd engine.
    for comp in cr.components():
        assert comp["kind"] != "engine", comp["id"]
    with pytest.raises(ValueError):
        cr.register_canon_component(
            id="bogus_engine_33",
            display="Bogus",
            kind="engine",
            canon_status=cr.HISTORIC_CANON,
            description="must not register",
            source="test",
        )


def test_every_component_carries_a_source():
    # L2: no sourceless entries.
    for comp in cr.components():
        assert comp["source"] and comp["source"].strip(), comp["id"]


def test_pending_markers_enforced():
    # L2: nothing invented — pending entries carry the marker.
    lab = cr.get_component("creation_lab")
    assert lab["canon_status"] == cr.DEFINITION_PENDING
    assert lab["description"].startswith("PENDING")
    for edition in ("edition_enterprise", "edition_government", "edition_personal"):
        e = cr.get_component(edition)
        assert e["kind"] == "edition"
        assert e["canon_status"] == cr.ESSENCE_PENDING
    pending = cr.pending_definitions()
    assert {c["id"] for c in pending} == {
        "creation_lab",
        "edition_enterprise",
        "edition_government",
        "edition_personal",
    }


def test_echo_and_alpha_are_his_words():
    echo = cr.get_component("echo")
    assert echo["kind"] == "entity"
    assert echo["canon_status"] == cr.HISTORIC_CANON
    alpha = cr.get_component("alpha")
    assert alpha["kind"] == "entity"
    assert alpha["canon_status"] == cr.HISTORIC_CANON
    assert "same being" in echo["description"]


def test_demandpulse_product_and_engine_not_conflated():
    # L3.
    dp = cr.get_component("demandpulse")
    assert dp["kind"] == "product+engine"
    assert "distinct" in dp["description"].lower()
    assert "scan" in dp["description"].lower()


def test_register_extension_point():
    entry = cr.register_canon_component(
        id="test_new_addition",
        display="Test new addition",
        kind="component",
        canon_status=cr.DEFINITION_PENDING,
        description="PENDING his definition.",
        source="test",
    )
    assert cr.get_component("test_new_addition") is entry
    del cr.CANON_COMPONENTS["test_new_addition"]
    with pytest.raises(ValueError):
        cr.register_canon_component(
            id="engine_tensor",
            display="Dup",
            kind="component",
            canon_status=cr.HISTORIC_CANON,
            description="x",
            source="test",
        )
    with pytest.raises(ValueError):
        cr.register_canon_component(
            id="test_bad_pending",
            display="Bad",
            kind="component",
            canon_status=cr.DEFINITION_PENDING,
            description="no marker here",  # missing PENDING -> must raise
            source="test",
        )
    assert "test_new_addition" not in cr.CANON_COMPONENTS


def test_dump_load_round_trip():
    snap = cr.dump()
    before = {k: dict(v) for k, v in snap["components"].items()}
    cr.load(snap)
    after = cr.dump()
    assert after["components"] == before
    assert after["engine_tensor_shape"] == [32, 64, 128]
    with pytest.raises(ValueError):
        cr.load({"engine_tensor_shape": [32, 64, 64], "components": {}})


def test_unknown_component_fails_loudly():
    with pytest.raises(KeyError):
        cr.get_component("no_such_component")
    with pytest.raises(ValueError):
        cr.components(kind="engine")
