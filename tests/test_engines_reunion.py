"""Tests for the reunion engine: verdicts over divergent copies."""

from __future__ import annotations

import pytest

from levi.engines import reunion as reunion_mod  # noqa: F401 — registration
from levi.engines.base import EngineInputError, registry


def run(versions, base=None):
    inputs = {"versions": versions}
    if base is not None:
        inputs["base"] = base
    return registry.run("reunion", inputs)


def v(vid, text):
    return {"id": vid, "text": text}


def test_converged_identical_copies():
    r = run([v("a", "same text"), v("b", "same text")])
    assert r.verdict["status"] == "converged"
    assert r.confidence == 1.0
    assert r.verdict["merged_text"] == "same text"
    assert r.verdict["conflicts"] == []
    assert len(r.verdict["groups"]) == 1


def test_single_line_names_divergent_copy():
    r = run([v("left", "hello world"), v("right", "hello WORLD")])
    assert r.verdict["status"] == "single-line"
    assert r.verdict["reference_id"] == "left"  # smallest id, disclosed
    assert r.verdict["divergent_ids"] == ["right"]
    assert r.verdict["merged_text"] is None  # named, never adopted
    assert r.confidence == 0.85


def test_reconcilable_merges_disjoint_regions():
    r = run(
        [
            v("a", "aa bb cc"),
            v("b", "AA bb cc"),
            v("c", "aa bb CC"),
        ]
    )
    assert r.verdict["status"] == "reconcilable"
    assert r.verdict["merged_text"] == "AA bb CC"
    assert len(r.verdict["regions"]) == 2
    owners = {tuple(sorted(x["version_ids"])) for x in r.verdict["regions"]}
    assert owners == {("b",), ("c",)}
    assert r.confidence == 0.7


def test_conflicted_holds_for_keeper_no_merge():
    r = run(
        [
            v("a", "aa bb cc"),
            v("b", "aa BB cc"),
            v("c", "aa bB cc"),
        ]
    )
    assert r.verdict["status"] == "conflicted"
    assert r.verdict["merged_text"] is None  # honest-hold law
    assert len(r.verdict["conflicts"]) == 1
    competitors = {c["id"] for c in r.verdict["conflicts"][0]["competitors"]}
    assert competitors == {"b", "c"}
    assert r.confidence == 0.4


def test_base_given_used_as_reference():
    r = run(
        [v("x", "AA bb cc"), v("y", "aa bb CC")],
        base="aa bb cc",
    )
    assert r.verdict["status"] == "reconcilable"
    assert r.verdict["base_given"] is True
    assert r.verdict["merged_text"] == "AA bb CC"
    assert "given base" in r.trace[0]


def test_determinism_same_inputs_identical_verdict():
    versions = [v("a", "aa bb cc"), v("b", "AA bb cc"), v("c", "aa bb CC")]
    first = run(versions).verdict
    second = run(list(reversed(versions))).verdict
    assert first == second


def test_deny_closed_single_version():
    with pytest.raises(EngineInputError):
        run([v("only", "one")])


def test_deny_closed_duplicate_ids():
    with pytest.raises(EngineInputError):
        run([v("a", "x"), v("a", "y")])


def test_deny_closed_non_string_text():
    with pytest.raises(EngineInputError):
        run([v("a", "x"), {"id": "b", "text": 42}])


def test_deny_closed_bad_base():
    with pytest.raises(EngineInputError):
        run([v("a", "x"), v("b", "y")], base=123)


def test_no_deletion_every_version_accounted():
    versions = [v("a", "aa bb cc"), v("b", "aa BB cc"), v("c", "aa bB cc")]
    r = run(versions)
    seen = {vid for g in r.verdict["groups"] for vid in g["ids"]}
    assert seen == {"a", "b", "c"}
    assert all(len(g["sha256"]) == 64 for g in r.verdict["groups"])


def test_engine_registered_with_schema():
    eng = registry.get("reunion")
    assert eng.required == ("versions",)
    assert eng.risk == "info"
