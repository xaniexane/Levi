"""Proof for the staleness engine: the seven declared laws, machine-checked."""

import pytest

from levi.engines.staleness import STALENESS_ENGINE, _score
from levi.engines.base import EngineInputError, registry


def _item(item_id, seen_at):
    return {"id": item_id, "seen_at": seen_at}


NOW = "2026-09-27T12:00:00+00:00"

FRESH_ITEM = _item("a", "2026-09-27T06:00:00+00:00")  # 6h ago
STALE_ITEM = _item("b", "2026-09-25T12:00:00+00:00")  # 2d ago
EXPIRED_ITEM = _item("c", "2026-09-10T12:00:00+00:00")  # 17d ago


def _run(items, **kw):
    kw.setdefault("now", NOW)
    kw.setdefault("policy", "day")
    return STALENESS_ENGINE.run({"items": items, **kw})


def test_engine_is_registered():
    assert registry.get("staleness") is STALENESS_ENGINE


def test_classification_fresh_stale_expired():
    result = _run([FRESH_ITEM, STALE_ITEM, EXPIRED_ITEM])
    states = {e["id"]: e["state"] for e in result.verdict["items"]}
    assert states == {"a": "fresh", "b": "stale", "c": "expired"}


def test_nothing_pruned_all_items_present():
    result = _run([FRESH_ITEM, STALE_ITEM, EXPIRED_ITEM])
    assert result.verdict["total"] == 3
    assert result.verdict["nothing_pruned"] is True
    assert len(result.verdict["items"]) == 3


def test_evidence_carried_per_item():
    result = _run([STALE_ITEM])
    entry = result.verdict["items"][0]
    for key in (
        "id",
        "state",
        "age_sec",
        "score",
        "seen_at",
        "fresh_sec",
        "stale_sec",
        "policy",
    ):
        assert key in entry, f"missing evidence {key}"


def test_counts_summarize():
    result = _run([FRESH_ITEM, STALE_ITEM, EXPIRED_ITEM])
    assert result.verdict["counts"] == {"fresh": 1, "stale": 1, "expired": 1}


def test_score_decay_is_linear():
    # fresh boundary 86400s, stale boundary 604800s under policy 'day'
    assert _score(0.0, 604800.0) == 1.0
    assert _score(604800.0, 604800.0) == 0.0
    assert _score(604800.0 + 1.0, 604800.0) == 0.0
    half = _score(302400.0, 604800.0)
    assert half == pytest.approx(0.5)


def test_confidence_is_mean_score():
    result = _run([FRESH_ITEM, EXPIRED_ITEM])
    scores = [e["score"] for e in result.verdict["items"]]
    assert result.confidence == pytest.approx(sum(scores) / 2)


def test_determinism_byte_identical():
    first = _run([FRESH_ITEM, STALE_ITEM])
    second = _run([FRESH_ITEM, STALE_ITEM])
    a, b = first.to_dict(), second.to_dict()
    a.pop("ran_at"), b.pop("ran_at")
    assert a == b


def test_custom_policy_respected():
    result = _run(
        [_item("x", "2026-09-27T11:00:00+00:00")],
        policy={"fresh_sec": 1800, "stale_sec": 3600},
    )
    entry = result.verdict["items"][0]
    assert entry["state"] == "expired"  # 3600s age == stale_sec
    assert entry["policy"] == "custom"


def test_missing_seen_at_refused():
    with pytest.raises(EngineInputError):
        _run([{"id": "ghost"}])


def test_bad_stamp_refused():
    with pytest.raises(EngineInputError):
        _run([_item("bad", "not-a-date")])


def test_future_stamp_refused():
    with pytest.raises(EngineInputError):
        _run([_item("ahead", "2026-09-28T12:00:00+00:00")])


def test_missing_id_refused():
    with pytest.raises(EngineInputError):
        _run([{"seen_at": "2026-09-27T11:00:00+00:00"}])


def test_duplicate_ids_refused():
    with pytest.raises(EngineInputError):
        _run([FRESH_ITEM, dict(FRESH_ITEM)])


def test_unknown_policy_refused():
    with pytest.raises(EngineInputError):
        _run([FRESH_ITEM], policy="eon")


def test_custom_policy_bad_shape_refused():
    with pytest.raises(EngineInputError):
        _run([FRESH_ITEM], policy={"fresh_sec": 3600})
    with pytest.raises(EngineInputError):
        _run([FRESH_ITEM], policy={"fresh_sec": 99999, "stale_sec": 100})
    with pytest.raises(EngineInputError):
        _run([FRESH_ITEM], policy=42)


def test_items_not_a_list_refused():
    with pytest.raises(EngineInputError):
        _run("not-a-list")


def test_non_dict_item_refused():
    with pytest.raises(EngineInputError):
        _run(["just-a-string"])


def test_max_items_guard_refused():
    items = [_item(f"i{n}", "2026-09-27T11:00:00+00:00") for n in range(5)]
    with pytest.raises(EngineInputError):
        _run(items, max_items=4)


def test_trace_names_every_item():
    result = _run([FRESH_ITEM, STALE_ITEM])
    joined = " ".join(result.trace)
    assert "a" in joined and "b" in joined
    assert "fresh" in joined and "stale" in joined


def test_empty_items_succeeds_silently():
    result = _run([])
    assert result.verdict["total"] == 0
    assert result.verdict["counts"] == {"fresh": 0, "stale": 0, "expired": 0}
    assert result.confidence == 1.0


def test_boundary_is_inclusive_fresh():
    # exactly at the fresh boundary counts as fresh
    result = _run([_item("edge", "2026-09-26T12:00:00+00:00")])
    assert result.verdict["items"][0]["state"] == "fresh"


def test_boundary_at_stale_is_expired():
    # exactly at the stale boundary counts as expired (past trust)
    result = _run([_item("edge", "2026-09-20T12:00:00+00:00")])
    assert result.verdict["items"][0]["state"] == "expired"


def test_interop_declaration_present():
    from levi.interop.registry import modules

    assert "engines-staleness" in modules()
