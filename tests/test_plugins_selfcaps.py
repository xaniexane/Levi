"""Tests for levi.plugins.selfcaps — self-capability introspection."""

import pytest

from levi.interop.registry import Registry
from levi.plugins.selfcaps import (
    MODULE_NAME,
    PROVIDES,
    SelfcapsError,
    all_modules,
    dependents_chain,
    find_capability,
    list_capabilities,
    module_summary,
    register_capabilities,
    render_index,
    render_module,
    who_provides,
)


def _reg():
    reg = Registry()
    reg.register("memory-store", provides=["memory.write", "memory.read"], requires=[])
    reg.register(
        "rag", provides=["rag.ask", "rag.cited-context"], requires=["memory-store"]
    )
    register_capabilities(reg)
    return reg


def test_all_modules_sorted():
    assert all_modules(_reg()) == ["memory-store", MODULE_NAME, "rag"]


def test_module_summary():
    info = module_summary("rag", _reg())
    assert info == {
        "module": "rag",
        "provides": ["rag.ask", "rag.cited-context"],
        "requires": ["memory-store"],
    }


def test_module_summary_unknown_raises():
    with pytest.raises(SelfcapsError):
        module_summary("nope", _reg())


def test_list_capabilities_prefix():
    caps = list_capabilities(prefix="memory.", registry=_reg())
    assert caps == ["memory.read", "memory.write"]


def test_find_capability():
    hits = find_capability("selfcaps", _reg())
    assert hits == {MODULE_NAME: PROVIDES}


def test_who_provides():
    assert who_provides("rag.ask", _reg()) == "rag"
    assert who_provides("nope.nothing", _reg()) is None


def test_dependents_chain():
    assert dependents_chain("memory-store", _reg()) == ["rag"]
    with pytest.raises(SelfcapsError):
        dependents_chain("ghost", _reg())


def test_render_module():
    card = render_module("rag", _reg())
    assert "== rag ==" in card
    assert "+ rag.ask" in card
    assert "- memory-store" in card


def test_render_index():
    index = render_index(_reg())
    assert f"{MODULE_NAME}: 1 capability" in index


def test_register_capabilities_check_all():
    reg = _reg()
    reg.check_all()  # must not raise
