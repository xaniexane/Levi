"""Tests for the winnow engine — near-duplicate clustering.

Proofs for the laws declared in ``levi/engines/winnow.py``:
1. partition, 2. determinism, 3. no-deletion, 4. honest-merge,
5. canonical keeper. Plus the deny-closed input gates.
"""

import pytest

import levi.engines.winnow  # noqa: F401  (self-registers on import)
from levi.engines import registry
from levi.engines.base import EngineInputError


def _run(**inputs):
    return registry.run("winnow", inputs)


def _items(*pairs):
    return [{"id": i, "text": t} for i, t in pairs]


def test_winnow_registers():
    assert "winnow" in {e.id for e in registry.list()}


def test_exact_duplicates_merge():
    result = _run(
        items=_items(
            ("a", "the quick brown fox"),
            ("b", "the quick brown fox"),
            ("c", "entirely different words here"),
        )
    )
    groups = result.verdict["groups"]
    assert result.verdict["item_count"] == 3
    assert result.verdict["duplicate_count"] == 1
    assert result.verdict["group_count"] == 2
    merged = next(g for g in groups if len(g["members"]) == 2)
    assert merged["canonical"] == "a"  # canonical law: smallest id
    assert merged["members"] == ["a", "b"]
    assert merged["duplicate_count"] == 1


def test_partition_law_every_item_in_exactly_one_group():
    # Property-style: a mixed set, every id appears exactly once.
    items = _items(
        ("n1", "deploy the release tonight"),
        ("n2", "deploy the release tonight!"),
        ("n3", "water the garden beds"),
        ("n4", "water the garden beds."),
        ("n5", "call the dentist tomorrow"),
        ("n6", "quantum tunneling explained"),
    )
    result = _run(items=items, threshold=0.85)
    seen = []
    for g in result.verdict["groups"]:
        seen.extend(g["members"])
    assert sorted(seen) == sorted(i["id"] for i in items)
    assert len(seen) == len(set(seen))  # no item in two groups


def test_determinism_same_inputs_byte_identical_verdict():
    kwargs = {
        "items": _items(
            ("b", "alpha beta gamma"),
            ("a", "alpha beta gamma delta"),
            ("c", "unrelated string of words"),
            ("d", "alpha beta gamma"),
        ),
        "threshold": 0.8,
    }
    first = _run(**kwargs).verdict
    second = _run(**kwargs).verdict
    assert first == second


def test_honest_merge_below_threshold_never_merges():
    result = _run(
        items=_items(
            ("a", "the cat sat on the mat"),
            ("b", "quantum field theory notes"),
        ),
        threshold=0.99,
    )
    assert result.verdict["group_count"] == 2
    assert result.verdict["duplicate_count"] == 0
    assert result.confidence == 1.0


def test_honest_merge_trace_names_ratio():
    result = _run(
        items=_items(("a", "hello world"), ("b", "hello world")),
    )
    merge_lines = [t for t in result.trace if t.startswith("merged")]
    assert len(merge_lines) == 1
    assert "ratio=1.000" in merge_lines[0]
    assert "≥ 0.85" in merge_lines[0]


def test_no_deletion_law_counts_add_up():
    items = _items(
        ("a", "same text here"),
        ("b", "same text here"),
        ("c", "same text here"),
        ("d", "wholly other content entirely"),
    )
    v = _run(items=items).verdict
    assert v["item_count"] == 4
    assert v["group_count"] + v["duplicate_count"] == v["item_count"]
    assert sum(len(g["members"]) for g in v["groups"]) == v["item_count"]


def test_confidence_is_mean_merge_ratio():
    result = _run(items=_items(("a", "hello world"), ("b", "hello world")))
    assert result.confidence == 1.0  # single perfect merge
    mixed = _run(
        items=_items(
            ("a", "the quick brown fox jumps"),
            ("b", "the quick brown fox jumps!"),
            ("c", "completely different sentence here"),
        ),
        threshold=0.8,
    )
    assert 0.8 <= mixed.confidence <= 1.0


def test_deny_closed_duplicate_ids_refused():
    with pytest.raises(EngineInputError):
        _run(items=_items(("a", "x"), ("a", "y")))


def test_deny_closed_empty_items_refused():
    with pytest.raises(EngineInputError):
        _run(items=[])


def test_deny_closed_bad_threshold_refused():
    for bad in (0, 1.5, -0.1, "high", None):
        with pytest.raises(EngineInputError):
            _run(items=_items(("a", "x"), ("b", "y")), threshold=bad)


def test_deny_closed_malformed_items_refused():
    with pytest.raises(EngineInputError):
        _run(items=[{"id": "a"}])  # missing text
    with pytest.raises(EngineInputError):
        _run(items=[{"id": "", "text": "x"}])  # empty id
    with pytest.raises(EngineInputError):
        _run(items=[{"id": "a", "text": 42}])  # non-str text
    with pytest.raises(EngineInputError):
        _run(items="not a list")


def test_deny_closed_oversize_refused():
    items = [{"id": f"i{n}", "text": f"text number {n}"} for n in range(10)]
    with pytest.raises(EngineInputError):
        _run(items=items, max_items=5)


def test_run_winnow_skill_executes():
    from levi.skill.registry import SkillRegistry

    reg = SkillRegistry()
    skill = reg.get("compressed.run-winnow")
    assert skill is not None
    out = skill.handler(
        {"items": _items(("a", "pack it to the brim"), ("b", "pack it to the brim"))}
    )
    assert "[winnow] verdict" in out
    assert "0 deleted" in out


def test_run_winnow_skill_refuses_gracefully():
    from levi.skill.registry import SkillRegistry

    reg = SkillRegistry()
    skill = reg.get("compressed.run-winnow")
    out = skill.handler({"items": []})
    assert "refused" in out


def test_winnow_playbooks_registered():
    from levi.skill.compressed_skills import COMPRESSED_SKILLS

    ids = {s.id for s in COMPRESSED_SKILLS}
    assert {
        "compressed.engine-winnow",
        "compressed.connector-diskwatch",
        "compressed.run-winnow",
    } <= ids
