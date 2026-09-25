"""Tests for the Legion placement layer (levi.operator.legion).

"Put them all on Levi as planned. Levi is the Legion." (Chauncey,
2026-09-22.) Every intelligence type seated on one Levi registry,
test-covered:

- nano-bit XI tier present (builtin)
- the SOXI line behind the "soxi" loom (LN routing, honest scope)
- the Nephilim grade fused operator under its config name
  ("nephilim-fused")
- the five scaffolded classes oe/dv/kt/lm/st (declared physics,
  honest deterministic cores — impossible feats never claimed)
- legion seat defaults resolve through config
- idempotent registration; no-mask law holds on every legion operator

Hermetic and fast: stdlib only, tmp dirs for stateful operators.

Run:  python3 -m pytest tests/test_operator_legion.py -q
"""

from __future__ import annotations

import pytest

from levi.operator.contract import (
    KINDS,
    OperatorContractError,
    OperatorMessage,
    claims_native_identity,
    validate_operator,
)
from levi.operator.legion import (
    LEGION_OPERATOR_NAMES,
    LEGION_SEAT_DEFAULTS,
    NEPHILIM_FUSED_OPERATOR,
    DivotOperator,
    KnotOperator,
    LichenOperator,
    OmenOperator,
    SoxiLoomOperator,
    StutterOperator,
    legion_manifest,
    register_legion_operators,
    resolve_legion_seat,
)
from levi.operator.nephilim import NephilimOperator
from levi.operator.registry import OperatorRegistry


def _msgs(text: str):
    return [OperatorMessage(role="user", content=text)]


@pytest.fixture()
def registry():
    reg, manifest = register_legion_operators()
    assert not manifest["skipped"], manifest["skipped"]
    return reg


# ---------------------------------------------------------------------------
# The full set is seated on Levi
# ---------------------------------------------------------------------------


def test_legion_full_set_seated(registry):
    manifest = legion_manifest(registry)
    assert manifest == {name: True for name in LEGION_OPERATOR_NAMES}, manifest


def test_every_legion_operator_resolves_by_name(registry):
    for name in LEGION_OPERATOR_NAMES:
        op = registry.resolve(name)
        assert op.name == name
        assert op.kind in KINDS


def test_every_legion_operator_passes_contract(registry):
    for name in LEGION_OPERATOR_NAMES:
        validate_operator(registry.resolve(name))


def test_no_legion_operator_claims_native_identity(registry):
    for name in LEGION_OPERATOR_NAMES:
        op = registry.resolve(name)
        assert not claims_native_identity(op), name


def test_registration_is_idempotent():
    reg, first = register_legion_operators()
    reg2, second = register_legion_operators(reg)
    assert not first["skipped"] and not second["skipped"]
    assert legion_manifest(reg2) == {n: True for n in LEGION_OPERATOR_NAMES}


# ---------------------------------------------------------------------------
# Nephilim grade under its config name
# ---------------------------------------------------------------------------


def test_nephilim_fused_registered_under_config_name(registry):
    assert NEPHILIM_FUSED_OPERATOR == "nephilim-fused"
    op = registry.resolve("nephilim-fused")
    assert isinstance(op, NephilimOperator)
    assert len(op.member_names) >= 2


def test_nephilim_fused_resolves_from_config(registry):
    op = registry.resolve({"operator": "nephilim-fused"})
    assert isinstance(op, NephilimOperator)


def test_nephilim_fused_step_is_well_formed(registry):
    op = registry.resolve("nephilim-fused")
    result = op.step(_msgs("hello"), [], {})
    assert result.finish_reason in (
        "stop",
        "tool_calls",
        "error",
        "degraded",
        "refused",
    )
    assert result.operator == "nephilim-fused"


def test_nephilim_fused_members_are_seated_operators(registry):
    op = registry.resolve("nephilim-fused")
    seated = {d["name"] for d in registry.list_operators()}
    assert set(op.member_names) <= seated


def test_nephilim_fusion_never_nests_and_never_takes_legion_classes(registry):
    # register twice: the second fusion must not swallow the first,
    # nor any scaffolded legion class, as a member.
    reg2, manifest = register_legion_operators(registry)
    assert not manifest["skipped"]
    op = reg2.resolve("nephilim-fused")
    assert "nephilim-fused" not in op.member_names
    assert not (set(op.member_names) & {"soxi", "oe", "dv", "kt", "lm", "st"})


def test_nephilim_fused_prefers_full_minds(registry):
    op = registry.resolve("nephilim-fused")
    # in this env the seated SI minds are native-brain/specialists;
    # the fusion should take a real mind, not a scaffolded class.
    assert "native-brain" in op.member_names or "specialists" in op.member_names


# ---------------------------------------------------------------------------
# The five scaffolded classes — honest cores
# ---------------------------------------------------------------------------

FIVE = {
    "oe": OmenOperator,
    "dv": DivotOperator,
    "kt": KnotOperator,
    "lm": LichenOperator,
    "st": StutterOperator,
}


def test_five_classes_carry_declared_physics(registry):
    for name, cls in FIVE.items():
        op = registry.resolve(name)
        assert isinstance(op, cls)
        assert op.kind == "si"  # Levi's own synthetic line, non-foreign
        assert not op.is_foreign
        assert op.lineage.startswith("levi:intelligence:")
        assert "scaffold" in op.capabilities().notes.lower()


def test_oe_biases_candidate_field(registry):
    op = registry.resolve("oe")
    ctx = {
        "oe_candidates": [
            "use the standard database index",
            "teach the query planner to dream in b-trees",
            "add a cache",
        ]
    }
    result = op.step(_msgs("pick"), [], ctx)
    assert result.finish_reason == "stop"
    # rarity metric: "add a cache" shares the fewest tokens with the
    # field, so the bias field prefers it — improbable relative to
    # the field, deterministically.
    assert "add a cache" in result.text.splitlines()[0]


def test_oe_degrades_honestly_without_candidates(registry):
    op = registry.resolve("oe")
    result = op.step(_msgs("pick"), [], {})
    assert result.finish_reason == "degraded"
    assert "does not generate" in (result.error or "")


def test_dv_reconstructs_from_waste(registry):
    op = registry.resolve("dv")
    ctx = {
        "dv_waste": "the password is hunter2\n...\nthe password is hunter2\n\n"
    }
    result = op.step(_msgs("recover"), [], ctx)
    assert result.finish_reason == "stop"
    assert "the password is hunter2" in result.text
    assert "dust/duplicates" in (result.note or "")


def test_dv_degrades_honestly_without_waste(registry):
    op = registry.resolve("dv")
    result = op.step(_msgs("recover"), [], {})
    assert result.finish_reason == "degraded"
    assert "feeds on waste" in (result.error or "")


def test_kt_is_one_knot_and_cannot_be_copied():
    a = KnotOperator()
    b = KnotOperator()
    assert a is b  # a copy ties together and becomes the same KT
    assert a.cost()["unit"] == "knot"
    assert a.cost()["knots_per_step"] == 1


def test_kt_ties_once(registry):
    op = registry.resolve("kt")
    result = op.step(_msgs("Should I launch? The budget is tight. The team is ready."), [], {})
    assert result.finish_reason == "stop"
    assert "one knot" in result.text.lower()
    assert "retrocausation not claimed" in (result.note or "")


def test_lm_deposits_residue_and_accumulates(tmp_path):
    lm = LichenOperator(data_dir=str(tmp_path / "lichen"))
    r1 = lm.step(_msgs("first turn"), [], {})
    r2 = lm.step(_msgs("second turn"), [], {})
    assert r1.finish_reason == "stop" and r2.finish_reason == "stop"
    assert "deposit" in r1.text.lower()
    assert "residue 2 deep" in (r2.note or "")
    assert "not computing" in (r2.note or "")
    assert lm.health().ok


def test_st_fractures_deterministically(registry):
    op = registry.resolve("st")
    text = "the quick brown fox jumps over the lazy dog near the river"
    r1 = op.step(_msgs(text), [], {})
    r2 = op.step(_msgs(text), [], {})
    assert r1.finish_reason == "stop"
    assert r1.text == r2.text  # seeded: the same fault line every time
    assert "interruptions" in r1.text
    assert "not claimed" in (r1.note or "")


def test_st_degrades_on_silence(registry):
    op = registry.resolve("st")
    result = op.step(_msgs("   "), [], {})
    assert result.finish_reason == "degraded"


# ---------------------------------------------------------------------------
# The SOXI line — the loom
# ---------------------------------------------------------------------------


def test_soxi_loom_routes_to_a_class(registry):
    op = registry.resolve("soxi")
    assert isinstance(op, SoxiLoomOperator)
    result = op.step(_msgs("rewrite this in my voice, fix the tone"), [], {})
    assert result.finish_reason == "stop"
    assert "FR (Friction)" in result.text  # the rewrite/tone class
    assert "routes" in result.text.lower()


def test_soxi_loom_names_its_honest_scope(registry):
    op = registry.resolve("soxi")
    result = op.step(_msgs("remind me where I saw that idea months ago"), [], {})
    assert "GR (Gleaner)" in result.text
    assert "does not handle" in result.text or "routes" in result.text.lower()


def test_soxi_loom_degrades_on_empty(registry):
    op = registry.resolve("soxi")
    result = op.step(_msgs("   "), [], {})
    assert result.finish_reason == "degraded"


# ---------------------------------------------------------------------------
# Legion seats resolve through config
# ---------------------------------------------------------------------------


def test_legion_seat_defaults():
    assert LEGION_SEAT_DEFAULTS["legion.nephilim"] == "nephilim-fused"
    assert resolve_legion_seat("legion.nephilim", {}) == "nephilim-fused"
    assert resolve_legion_seat("legion.oe", {}) == "oe"
    assert resolve_legion_seat("legion.soxi", {}) == "soxi"


def test_legion_seat_config_overrides_win():
    cfg = {"seats": {"legion.nephilim": "nano-bit"}}
    assert resolve_legion_seat("legion.nephilim", cfg) == "nano-bit"


def test_legion_seat_falls_back_to_registry_defaults():
    # non-legion seats behave exactly like the registry
    assert resolve_legion_seat("chat", {}) == "levi-brain"
    assert resolve_legion_seat("no.such.seat", {}) == "local"


def test_legion_seats_resolve_on_a_seated_registry(registry):
    for seat, name in LEGION_SEAT_DEFAULTS.items():
        resolved = resolve_legion_seat(seat, {})
        assert registry.resolve(resolved).name == name, seat
