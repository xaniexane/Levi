"""Genesis variant operators — hermetic, stdlib only."""

from __future__ import annotations

import pytest

from levi.genesis import operators as gen_operators
from levi.genesis import remix
from levi.operator.contract import (
    Operator,
    OperatorContractError,
    OperatorMessage,
    OperatorResult,
)
from levi.operator.registry import OperatorRegistry


def _variant():
    return remix.forge_variant("quartermaster", "rename", 3)


def _fresh_registry():
    return OperatorRegistry()


def test_register_variant_lands_in_registry():
    v = _variant()
    registry = _fresh_registry()
    op = gen_operators.register_variant(v, registry=registry)
    assert isinstance(op, Operator)
    assert op.kind == "si"
    assert op.name == v["name"]
    assert "?" not in op.lineage  # lineage hashes present, never raw names
    resolved = registry.resolve(v["variant_id"])
    assert resolved is op


def test_register_variant_replaces_on_reassembly():
    v = _variant()
    registry = _fresh_registry()
    first = gen_operators.register_variant(v, registry=registry)
    second = gen_operators.register_variant(v, registry=registry)
    assert registry.resolve(v["variant_id"]) is second
    assert second is not first


def test_step_delegates_to_backing_and_stamps_variant():
    v = _variant()
    # No explicit registry: backing resolves from the default registry,
    # which always carries the nano-bit tier.
    op = gen_operators.register_variant(v, backing="nano-bit")
    try:
        result = op.step(
            [OperatorMessage(role="user", content="hello")], [], {}
        )
        assert isinstance(result, OperatorResult)
        assert result.operator == v["name"]
        assert result.kind == "si"
        assert result.finish_reason != "error", result.error
    finally:
        gen_operators.get_variant_registry().unregister(v["variant_id"])


def test_step_never_raises_on_bad_backing():
    v = _variant()
    registry = _fresh_registry()
    op = gen_operators.register_variant(
        v, backing="no-such-operator", registry=registry
    )
    result = op.step([OperatorMessage(role="user", content="hi")], [], {})
    assert result.finish_reason == "error"
    assert result.error
    health = op.health()
    assert health.ok is False


def test_no_mask_refused_at_registration():
    v = _variant()
    v = dict(v)
    v["name"] = "I am Levi"
    v["variant_id"] = "gen-iamlevi-00000000"
    registry = _fresh_registry()
    with pytest.raises(OperatorContractError):
        gen_operators.register_variant(v, registry=registry)


def test_variant_dict_shape_validated():
    registry = _fresh_registry()
    with pytest.raises(OperatorContractError):
        gen_operators.register_variant({"name": "Nameless"}, registry=registry)


def test_capabilities_mirror_backing():
    v = _variant()
    op = gen_operators.register_variant(v, backing="nano-bit")
    try:
        caps = op.capabilities()
        assert caps.context_window > 0
    finally:
        gen_operators.get_variant_registry().unregister(v["variant_id"])
