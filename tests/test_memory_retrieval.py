"""Hermetic tests for levi.memory.retrieval (isolated HOME, no network)."""

from datetime import datetime, timedelta, timezone

import pytest

from levi.memory.store import MemoryStore
from levi.memory.types import MemoryType
from levi.memory import retrieval
from levi.memory.retrieval import (
    expand_query,
    reciprocal_rank_fusion,
    retrieve,
    sparse_vector,
    tokenize,
)


@pytest.fixture()
def store(tmp_path):
    return MemoryStore(data_dir=tmp_path / "memory")


def _add(store, content, tags=None, importance=0.5, age_hours=0, corroboration=0):
    ts = (datetime.now(timezone.utc) - timedelta(hours=age_hours)).isoformat()
    entry = store.add(
        MemoryType.SEMANTIC,
        content,
        importance=importance,
        tags=tags or [],
        metadata={"corroboration": corroboration} if corroboration else {},
    )
    # backdate deterministically
    entry.created_at = ts
    entry.updated_at = ts
    store._persist()
    return entry


# --- tokenize / BM25 basics -------------------------------------------------


def test_tokenize_strips_stopwords_and_stems():
    toks = tokenize("The quick brown foxes are running quickly")
    assert "the" not in toks and "are" not in toks
    assert "fox" in toks  # foxes -> fox
    assert "quick" in toks


def test_bm25_exact_phrase_beats_partial(store):
    _add(store, "irrelevant note about gardening and soil")
    exact = _add(store, "the backup encryption passphrase must never be shared")
    partial = _add(store, "backup plans for the weekend trip")
    res = retrieve("backup encryption passphrase", store, method="bm25")
    assert res, "expected hits"
    assert res[0][0].id == exact.id
    assert any(e.id == partial.id for e, _s, _x in res)


def test_bm25_tag_weighting(store):
    _add(store, "some long rambling text about nothing in particular " * 10)
    tagged = _add(store, "short note", tags=["offsite-backup"])
    res = retrieve("offsite backup", store, method="bm25")
    assert res[0][0].id == tagged.id


# --- hybrid / vector --------------------------------------------------------


def test_hybrid_beats_single_signals_on_paraphrase(store):
    # "automobile" never appears; BM25 alone struggles, vector catches it.
    target = _add(store, "my automobile needs new brakes before winter")
    _add(store, "unrelated note about baking sourdough bread")
    bm25 = retrieve("car brakes", store, method="bm25", limit=5)
    vec = retrieve("car brakes", store, method="vector", limit=5)
    hyb = retrieve("car brakes", store, method="hybrid", limit=5)
    assert hyb and hyb[0][0].id == target.id
    # hybrid must be at least as good as the best single signal
    bm25_pos = min(
        [i for i, (e, _s, _x) in enumerate(bm25) if e.id == target.id] or [99]
    )
    vec_pos = min([i for i, (e, _s, _x) in enumerate(vec) if e.id == target.id] or [99])
    best_single = min(bm25_pos, vec_pos)
    hyb_pos = [i for i, (e, _s, _x) in enumerate(hyb) if e.id == target.id][0]
    assert hyb_pos <= best_single


def test_sparse_vector_deterministic():
    a = sparse_vector("hello world")
    b = sparse_vector("hello world")
    assert a == b
    # near-duplicate with typo still similar
    c = sparse_vector("hello wordl")
    sim = sum(x * y for x, y in zip(a, c))
    assert sim > 0.5


def test_rrf_fusion_order():
    fused = reciprocal_rank_fusion([[("a", 9.0), ("b", 1.0)], [("b", 5.0), ("a", 0.1)]])
    # b is rank2+rank1, a is rank1+rank2 → tie broken by id: a first
    assert [eid for eid, _s in fused] == ["a", "b"]


# --- recency / importance ----------------------------------------------------


def test_recency_prefers_newer(store):
    old = _add(
        store,
        "deployment runbook for the web service",
        importance=0.5,
        age_hours=24 * 30,
    )
    new = _add(
        store, "deployment runbook for the web service", importance=0.5, age_hours=1
    )
    res = retrieve("deployment runbook", store, method="hybrid")
    assert res[0][0].id == new.id
    assert res[1][0].id == old.id


def test_recency_method_orders_by_age(store):
    e_old = _add(store, "alpha entry one", age_hours=100)
    e_new = _add(store, "alpha entry two", age_hours=1)
    res = retrieve("alpha", store, method="recency")
    assert [e.id for e, _s, _x in res[:2]] == [e_new.id, e_old.id]


def test_corrorobation_boosts_rank(store):
    _plain = _add(store, "widget calibration procedure", importance=0.5)
    corrob = _add(
        store, "widget calibration procedure", importance=0.5, corroboration=5
    )
    res = retrieve("widget calibration", store, method="bm25")
    assert res[0][0].id == corrob.id


# --- query expansion --------------------------------------------------------


def test_expand_query_synonyms_and_multi():
    subs = expand_query("buy a laptop")
    assert subs and any("purchase" in s for s in subs)
    multi = expand_query("backup strategy or restore plan")
    assert len(multi) == 2


def test_multi_query_fused(store):
    a = _add(store, "nightly backup strategy with encryption")
    b = _add(store, "disaster restore plan and drills")
    res = retrieve("backup strategy or restore plan", store, method="hybrid")
    ids = [e.id for e, _s, _x in res]
    assert a.id in ids and b.id in ids


# --- fail-closed --------------------------------------------------------------


@pytest.mark.parametrize("bad", ["", "   ", None, 123, ["x"]])
def test_retrieve_fail_closed_on_bad_query(store, bad):
    _add(store, "something retrievable")
    assert retrieve(bad, store) == []
    assert retrieval.LAST_ERROR


def test_retrieve_bad_method_and_store(store):
    _add(store, "something retrievable")
    assert retrieve("something", store, method="nope") == []
    assert retrieve("something", None) == []
    assert retrieve("something", object()) == []


def test_retrieve_empty_store(tmp_path):
    store = MemoryStore(data_dir=tmp_path / "empty")
    assert retrieve("anything", store) == []


def test_explanations_name_signals(store):
    _add(store, "the backup encryption passphrase must never be shared")
    res = retrieve("backup passphrase", store, method="hybrid")
    assert res
    _entry, _score, expl = res[0]
    assert "rrf=" in expl and "bm25_rank=" in expl
