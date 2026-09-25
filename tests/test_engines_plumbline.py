"""Tests for the plumbline invariant-guard engine."""

import pytest

from levi.engines.base import EngineInputError, registry
from levi.engines import plumbline  # noqa: F401  (self-registers on import)


def _run(verdict, laws, **kw):
    engine = registry.get("plumbline")
    return engine.run({"verdict": verdict, "laws": laws, **kw})


def _law(law_id, claim, path, op, value="__absent__"):
    law = {"id": law_id, "claim": claim, "path": path, "op": op}
    if value != "__absent__":
        law["value"] = value
    return law


def test_registered_on_import():
    assert registry.get("plumbline").id == "plumbline"


def test_all_held_verdict():
    verdict = {"group_count": 3, "duplicate_count": 2, "groups": ["a", "b", "c"]}
    laws = [
        _law("g", "three groups", "group_count", "==", 3),
        _law("d", "dupes non-negative", "duplicate_count", ">=", 0),
        _law("n", "three members", "groups", "len==", 3),
    ]
    result = _run(verdict, laws)
    assert result.verdict["status"] == "held"
    assert result.verdict["held_count"] == 3
    assert result.confidence == 1.0


def test_broken_verdict_names_the_law():
    result = _run(
        {"group_count": 2},
        [_law("g", "three groups", "group_count", "==", 3)],
    )
    assert result.verdict["status"] == "broken"
    assert result.verdict["broken_count"] == 1
    law = result.verdict["laws"][0]
    assert law["held"] is False
    assert law["observed"] == 2
    assert "g" in result.trace[1]


def test_confidence_is_held_fraction():
    result = _run(
        {"a": 1, "b": 2},
        [
            _law("one", "a is one", "a", "==", 1),
            _law("two", "b is three", "b", "==", 3),
        ],
    )
    assert result.verdict["status"] == "broken"
    assert result.confidence == 0.5


def test_presence_ops():
    held = _run(
        {"a": 1},
        [
            _law("e", "a exists", "a", "exists"),
            _law("m", "zzz missing", "zzz", "missing"),
        ],
    )
    assert held.verdict["status"] == "held"
    broken = _run(
        {"a": 1},
        [_law("e", "zzz exists", "zzz", "exists")],
    )
    assert broken.verdict["status"] == "broken"
    assert broken.verdict["laws"][0]["observed"] == "<missing>"


def test_missing_path_fails_comparisons():
    # Absence never satisfies a positive claim — even !=.
    result = _run(
        {},
        [
            _law("eq", "nope equals 1", "nope", "==", 1),
            _law("ne", "nope differs from 1", "nope", "!=", 1),
            _law("ge", "nope at least 0", "nope", ">=", 0),
        ],
    )
    assert result.verdict["status"] == "broken"
    assert result.verdict["held_count"] == 0
    for law in result.verdict["laws"]:
        assert law["observed"] == "<missing>"


def test_dot_path_into_lists():
    verdict = {"groups": [{"canonical": "a"}, {"canonical": "b"}]}
    result = _run(
        verdict,
        [
            _law("c0", "first canonical is a", "groups.0.canonical", "==", "a"),
            _law("c9", "ninth group exists", "groups.9.canonical", "exists"),
        ],
    )
    assert result.verdict["held_count"] == 1
    assert result.verdict["broken_count"] == 1


def test_membership_ops():
    result = _run(
        {"stance": "plain", "mode": "x"},
        [
            _law("s", "stance allowed", "stance", "in", ["plain", "sharp"]),
            _law("m", "mode not debug", "mode", "not-in", ["debug", "trace"]),
            _law("b", "mode allowed", "mode", "in", ["plain", "sharp"]),
        ],
    )
    assert result.verdict["held_count"] == 2
    assert result.verdict["laws"][2]["held"] is False


def test_contains_and_length_ops():
    result = _run(
        {"title": "the plumb line", "items": [1, 2, 3]},
        [
            _law("t", "title mentions plumb", "title", "contains", "plumb"),
            _law("i", "three items", "items", "len==", 3),
            _law("s", "title short", "title", "len<=", 5),
        ],
    )
    assert result.verdict["held_count"] == 2
    assert result.verdict["laws"][2]["evidence"] == "len=14"


def test_incomparable_types_fail_honestly():
    result = _run(
        {"name": "levi"},
        [_law("n", "name at least 3", "name", ">=", 3)],
    )
    law = result.verdict["laws"][0]
    assert law["held"] is False
    assert "incomparable" in law["evidence"]


def test_determinism():
    inputs = {
        "verdict": {"a": 1, "b": [1, 2]},
        "laws": [_law("x", "a one", "a", "==", 1)],
    }
    engine = registry.get("plumbline")
    first = engine.run(dict(inputs)).to_dict()
    second = engine.run(dict(inputs)).to_dict()
    first.pop("ran_at")
    second.pop("ran_at")
    assert first == second


def test_empty_laws_refused():
    with pytest.raises(EngineInputError, match="at least one law"):
        _run({"a": 1}, [])


def test_malformed_laws_refused():
    with pytest.raises(EngineInputError, match="unknown op"):
        _run({"a": 1}, [_law("x", "c", "a", "bogus", 1)])
    with pytest.raises(EngineInputError, match="non-empty str"):
        _run({"a": 1}, [{"id": "", "claim": "c", "path": "a", "op": "==", "value": 1}])
    with pytest.raises(EngineInputError, match="needs a 'value'"):
        _run({"a": 1}, [_law("x", "c", "a", "==")])
    with pytest.raises(EngineInputError, match="takes no 'value'"):
        _run({"a": 1}, [_law("x", "c", "a", "exists", 1)])
    with pytest.raises(EngineInputError, match="empty segment"):
        _run({"a": 1}, [_law("x", "c", "a..b", "==", 1)])
    with pytest.raises(EngineInputError, match="duplicate law id"):
        _run(
            {"a": 1},
            [
                _law("x", "c1", "a", "==", 1),
                _law("x", "c2", "a", "==", 1),
            ],
        )


def test_wrong_value_shapes_refused():
    with pytest.raises(EngineInputError, match="as a list"):
        _run({"a": 1}, [_law("x", "c", "a", "in", "nope")])
    with pytest.raises(EngineInputError, match="int >= 0"):
        _run({"a": 1}, [_law("x", "c", "a", "len==", "three")])


def test_max_laws_guard():
    laws = [_law(f"l{i}", "c", "a", "==", 1) for i in range(3)]
    with pytest.raises(EngineInputError, match="exceed max_laws"):
        _run({"a": 1}, laws, max_laws=2)


def test_non_dict_verdict_refused():
    with pytest.raises(EngineInputError, match="'verdict' must be a dict"):
        registry.get("plumbline").run(
            {"verdict": [1, 2], "laws": [_law("x", "c", "a", "==", 1)]}
        )


def test_interop_self_declaration():
    from levi.interop import registry as ireg

    decl = ireg.check("engines-plumbline")
    assert "engines.plumbline.guard" in decl["provides"]
