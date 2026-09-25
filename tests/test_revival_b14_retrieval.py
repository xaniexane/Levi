"""Tests for revival batch B14: ragpipe, hybridfind, vecindex, rerank,
memtiers, memwrite, memsleep, bpe (SI internals: retrieval & memory)."""

import pytest

from core.levi.revival import (
    bpe,
    hybridfind,
    memsleep,
    memtiers,
    memwrite,
    ragpipe,
    rerank,
    vecindex,
)


# ---------------- ragpipe ----------------


def test_chunk_document_splits_on_paragraph_boundaries():
    text = "First paragraph here.\n\nSecond paragraph here.\n\nThird one."
    chunks, doc = ragpipe.chunk_document(text, "d1", max_chars=500)
    assert len(chunks) == 3
    assert all(c.parent_id == "d1" for c in chunks)
    assert all(c.boundary == "sentence" for c in chunks)
    assert [c.chunk_id for c in chunks] == [0, 1, 2]
    assert doc.doc_id == "d1"


def test_chunk_document_forced_cut_labeled_honestly():
    text = "Supercalifragilisticexpialidocious" * 40  # one unbreakable sentence
    chunks, _doc = ragpipe.chunk_document(text, "d2", max_chars=50)
    assert len(chunks) > 1
    assert all(c.boundary == "forced" for c in chunks)


def test_pipeline_runs_five_stages_with_timing_and_failure_reporting():
    chunks, doc = ragpipe.chunk_document("The fox jumps. Dogs bark.", "d1")
    calls = []

    def flaky_retrieve(_q):
        calls.append(1)
        return chunks

    pipe = ragpipe.RAGPipeline(retrieve=flaky_retrieve)
    result = pipe.run("fox", [doc])
    assert result.ok
    assert [s.stage for s in result.stages] == [
        "routing",
        "rewriting",
        "retrieval",
        "reranking",
        "generation",
    ]
    assert all(s.seconds >= 0 for s in result.stages)
    assert result.retrieved

    def boom(_q):
        raise RuntimeError("retriever down")

    bad = ragpipe.RAGPipeline(retrieve=boom)
    failed = bad.run("fox", [doc])
    assert not failed.ok
    err = [s for s in failed.stages if not s.ok][0]
    assert "RuntimeError" in err.error


def test_parent_context_window_expands_chunk():
    chunks, doc = ragpipe.chunk_document(
        "Alpha.\n\nBeta.\n\nGamma.", "d1", max_chars=50
    )
    middle = chunks[1]
    window = doc.context_window(middle, radius=1)
    assert "Alpha." in window and "Beta." in window and "Gamma." in window


# ---------------- hybridfind ----------------


def test_bm25_ranks_exact_term_match_first():
    idx = hybridfind.BM25(
        [
            hybridfind.tokenize(t)
            for t in ["the weather in paris", "paris france capital", "cooking recipes"]
        ]
    )
    ranked = idx.search("paris", top_k=3)
    assert ranked and ranked[0][0] in (0, 1)
    assert idx.search("paris", top_k=1)[0][1] > 0


def test_rrf_fuse_combines_lists_without_comparable_scores():
    dense = [(0, 0.99), (1, 0.01)]
    sparse = [(1, 25.0), (2, 2.0)]
    fused = hybridfind.rrf_fuse([dense, sparse], k=60)
    assert fused[0][0] == 1  # rank 1 in sparse + rank 2 in dense beats either alone
    assert fused[1][0] == 0
    assert fused[2][0] == 2


def test_hybrid_finder_records_per_source_ranks():
    finder = hybridfind.HybridFinder(
        corpus_texts=[
            "rareterm alpha beta",
            "common words common words",
            "alpha rareterm",
        ],
        vectors=[[1.0, 0.0], [0.0, 1.0], [0.9, 0.1]],
    )
    hits = finder.search("rareterm", [1.0, 0.0], top_k=3)
    assert len(hits) == 3
    for h in hits:
        assert h.dense_rank >= 1
        assert h.fused_score > 0


def test_cosine_handles_zero_vectors():
    assert hybridfind.cosine([0.0, 0.0], [1.0, 2.0]) == 0.0
    assert hybridfind.cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


# ---------------- vecindex ----------------


@pytest.fixture()
def toy_vecs():
    return [[float(i), float(i * 2), float(i + 1), float(i - 1)] for i in range(24)]


def test_hnsw_finds_nearest_neighbor(toy_vecs):
    h = vecindex.HNSW(dim=4)
    for v in toy_vecs:
        h.add(v)
    idx, dist = h.search([1.0, 2.0, 2.0, 0.0], k=1)[0]
    assert idx == 1
    assert dist == pytest.approx(0.0)


def test_hnsw_search_on_empty_index_returns_empty():
    assert vecindex.HNSW(dim=4).search([1.0, 2.0, 3.0, 4.0]) == []


def test_ivf_probing_all_cells_recovers_exact_neighbor(toy_vecs):
    iv = vecindex.IVFIndex(nlist=4)
    iv.train(toy_vecs)
    hits = iv.search([1.0, 2.0, 2.0, 0.0], k=1, nprobe=4)
    assert hits[0][0] == 1


def test_pq_encode_decode_roundtrip_via_adc(toy_vecs):
    pq = vecindex.ProductQuantizer(m=2, ks=4)
    pq.train(toy_vecs)
    pq.add(toy_vecs)
    code = pq.encode(toy_vecs[5])
    assert len(code) == 2
    assert all(0 <= c < 4 for c in code)
    dists = pq.asymmetric_distances(toy_vecs[5])
    assert len(dists) == len(toy_vecs)
    assert dists[5] == min(dists)


def test_ivfpq_index_end_to_end(toy_vecs):
    idx = vecindex.IVFPQIndex()
    idx.train(toy_vecs)
    hits = idx.search([1.0, 2.0, 2.0, 0.0], k=3)
    assert hits
    assert hits == sorted(hits, key=lambda p: p[1])


# ---------------- rerank ----------------


def test_rerank_promotes_pairwise_match_over_first_stage_order():
    rr = rerank.CrossEncoderReranker()
    cands = [
        (0, "completely unrelated cooking text", 0.95),
        (1, "quick fox jumps over the fence", 0.40),
    ]
    out = rr.rerank("quick fox", cands, top_n=2)
    assert out[0].doc_id == 1
    assert out[0].first_stage_rank == 2


def test_scorer_is_pairwise_not_independent():
    score = rerank.term_overlap_scorer
    assert score("quick fox", "a quick fox runs") > score("quick fox", "a dog runs")


def test_agreement_reports_rank_movement():
    rr = rerank.CrossEncoderReranker(scorer=lambda q, d: 0.0)  # all ties
    cands = [(0, "a", 0.9), (1, "b", 0.8)]
    out = rr.rerank("q", cands, top_n=2)
    agg = rr.agreement(out)
    assert agg["top1_changed"] == 0.0  # stable sort keeps first-stage order on ties
    assert rr.agreement([])["kept_ratio"] == 0.0


# ---------------- memtiers ----------------


def test_working_memory_pin_window_and_summary():
    w = memtiers.WorkingMemory(turn_window=2)
    w.pin("name", "Levi")
    w.add_turn("t1")
    w.add_turn("t2")
    w.add_turn("t3")
    w.roll_summary("summary-so-far")
    snap = w.snapshot()
    assert snap["pinned"]["name"] == "Levi"
    assert snap["recent_turns"] == ["t2", "t3"]
    assert snap["summary"] == "summary-so-far"
    assert w.unpin("name") and not w.unpin("name")


def test_archival_tiers_and_search():
    a = memtiers.ArchivalStore()
    a.store_fact("city", "Chauncey lives in Chicago")
    a.store_template("deploy", ["build", "test", "ship"])
    a.log_episode(memtiers.Episode(session_id="s1", turns=["hi"]))
    assert len(a.episodic) == 1
    hits = a.search("chicago")
    assert [i.key for i in hits] == ["city"]
    assert a.get_template("deploy").tier == "procedural"
    assert a.forget_fact("city") and not a.forget_fact("city")


def test_memory_os_pages_only_through_explicit_calls():
    mos = memtiers.MemoryOS()
    mos.archival.store_fact("city", "Chauncey lives in Chicago")
    assert mos.recall("chicago")  # recall finds it...
    assert mos.resident_keys() == []  # ...but nothing auto-injects into context
    assert mos.page_in("city")
    assert "paged:semantic:city" in mos.resident_keys()
    assert mos.page_out("paged:semantic:city", dest_key="city2")
    assert mos.archival.semantic["city2"].meta.get("paged_out") is True
    assert not mos.page_in("missing-key")
    assert [e.direction for e in mos.page_log] == ["in", "out"]


# ---------------- memwrite ----------------


def test_write_loop_add_update_noop():
    w = memwrite.MemoryWriter()
    (r1,) = w.write("Chauncey likes espresso.")
    assert r1.decision == memwrite.ADD
    (r2,) = w.write("Chauncey likes pour over coffee.")
    assert r2.decision == memwrite.UPDATE
    assert r2.old_text == "chauncey likes espresso"
    (r3,) = w.write("Chauncey likes pour over coffee.")
    assert r3.decision == memwrite.NOOP
    recs = w.retrieve("chauncey")
    assert len(recs) == 1 and recs[0].version == 2


def test_negation_deletes_stored_fact():
    w = memwrite.MemoryWriter()
    w.write("My dog is named Rex.")
    w.write("My dog is not named Rex.")
    assert w.retrieve("dog") == []
    decs = w.decisions_for("dog")
    assert decs[-1].decision == memwrite.DELETE
    assert decs[-1].old_text is not None


def test_scopes_are_isolated():
    w = memwrite.MemoryWriter()
    w.write("Chauncey likes espresso.", scope=memwrite.SESSION)
    w.write("Chauncey likes tea.", scope=memwrite.GLOBAL)
    session_recs = w.retrieve("chauncey", scope=memwrite.SESSION)
    assert [r.text for r in session_recs] == ["chauncey likes espresso"]
    assert len(w.retrieve("chauncey")) == 2  # both scopes visible together
    assert all(r.scope for r in w.retrieve("chauncey"))


def test_resolution_log_is_audit_trail():
    w = memwrite.MemoryWriter()
    w.write("Chauncey likes espresso.")
    w.write("Chauncey likes tea.")
    reasons = [r.reason for r in w.log]
    assert len(reasons) == 2 and all(reasons)


# ---------------- memsleep ----------------


def test_consolidation_runs_only_when_due():
    c = memsleep.Consolidator(threshold_tokens=1000, keep_recent=2)
    c.log_turn("Short turn one.")
    assert not c.consolidate_if_due()
    assert c.runs == 0


def test_consolidation_compacts_turns_into_facts():
    c = memsleep.Consolidator(threshold_tokens=40, keep_recent=2)
    for i in range(8):
        c.log_turn(f"Turn {i}: the fox jumps over the lazy dog in the morning sun.")
    assert c.consolidate_if_due()
    assert c.runs == 1
    assert len(c.episodic) == 2  # only recent turns kept raw
    assert len(c.facts) == 1
    assert c.facts[0].source_turns == 6
    assert len(c.episode_summaries) == 1
    # second call: not due again immediately
    assert not c.consolidate_if_due()


def test_recall_facts_ranks_by_query_overlap():
    c = memsleep.Consolidator()
    c.facts.append(
        memsleep.SemanticFact(text="fox jumps high", source_turns=1, weight=1.0)
    )
    c.facts.append(
        memsleep.SemanticFact(text="dog sleeps deep", source_turns=1, weight=9.0)
    )
    top = c.recall_facts("fox", limit=1)
    assert top[0].text == "fox jumps high"  # overlap beats raw weight


def test_decay_favors_recent_over_stale():
    c = memsleep.Consolidator(decay_half_life_turns=10.0)
    assert c._decay(0.0) == pytest.approx(1.0)
    assert c._decay(10.0) == pytest.approx(0.5)
    assert c._decay(20.0) < c._decay(10.0)


# ---------------- bpe ----------------


@pytest.fixture()
def trained_bpe():
    t = bpe.BPETokenizer(vocab_size=300)
    t.train(["the quick brown fox jumps over the lazy dog"] * 20 + ["hello world"] * 5)
    return t


def test_train_learns_merges_from_frequency(trained_bpe):
    assert len(trained_bpe.merges) > 0
    assert len(trained_bpe.vocab) <= 300


def test_encode_decode_roundtrip(trained_bpe):
    text = "the quick fox"
    assert trained_bpe.decode(trained_bpe.encode(text)) == text
    assert trained_bpe.token_boundary_ok(text)


def test_byte_fallback_handles_unseen_unicode(trained_bpe):
    text = "xyz 🦊 unseenword99"
    ids = trained_bpe.encode(text)
    assert ids  # never a KeyError: every input is encodable
    assert trained_bpe.decode(ids) == text


def test_heal_prefix_backs_up_to_whole_tokens(trained_bpe):
    full = "the quick fox".encode("utf-8")
    healed = trained_bpe.heal_prefix(full[:-1])  # cut mid-token
    assert len(healed) < len(full)
    roundtripped = trained_bpe.decode(
        trained_bpe.encode(healed.decode("utf-8"))
    ).encode("utf-8")
    assert roundtripped == healed
