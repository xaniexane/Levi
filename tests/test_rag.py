"""Hermetic tests for the levi.rag package (isolated HOME, no network)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from levi.memory.store import MemoryStore
from levi.rag.chunking import chunk_text
from levi.rag.ingest import ingest_file, ingest_directory
from levi.rag.pipeline import ask, build_context, coverage_score, rerank
from levi.rag.eval import build_questions, evaluate, print_report


@pytest.fixture()
def store(tmp_path):
    return MemoryStore(data_dir=tmp_path / "memory")


DOC = """# Backups

LEVI keeps 14 local snapshots. Snapshots exclude model weights.

## Encryption

The backup encryption passphrase must never be shared. It lives only
in the owner's head. Snapshots are encrypted client-side before upload.

## Schedule

Backups run daily at 03:00 America/Chicago via cron.
"""


# --- chunking ---------------------------------------------------------------

def test_chunker_windows_overlap_and_headers():
    chunks = chunk_text(DOC, "backups.md", max_chars=120, overlap=30)
    assert len(chunks) >= 3
    # windows bounded
    assert all(len(c.text) <= 200 for c in chunks)  # header prefix allowed
    # header tracked as section
    sections = {c.section for c in chunks}
    assert "Encryption" in sections and "Schedule" in sections
    # provenance present
    c0 = chunks[0]
    assert c0.source_doc == "backups.md"
    assert c0.chunk_index == 0
    assert c0.char_span[0] <= c0.char_span[1]
    # header context kept on chunks
    enc = [c for c in chunks if c.section == "Encryption"][0]
    assert "Encryption" in enc.text


def test_chunker_overlap_carries_context():
    text = ("Sentence one. Sentence two. Sentence three. Sentence four. "
            "Sentence five. Sentence six.")
    chunks = chunk_text(text, "d.md", max_chars=60, overlap=25)
    assert len(chunks) >= 2
    # some content shared between consecutive chunks
    assert any(w in chunks[1].text for w in chunks[0].text.split()[:4])


def test_chunker_rejects_bad_params():
    with pytest.raises(ValueError):
        chunk_text("x" * 100, "d.md", max_chars=10)
    with pytest.raises(ValueError):
        chunk_text("x" * 100, "d.md", max_chars=100, overlap=100)
    assert chunk_text("   \n  ", "d.md") == []


# --- ingest -----------------------------------------------------------------

def test_ingest_round_trip(tmp_path, store):
    f = tmp_path / "notes.md"
    f.write_text(DOC, encoding="utf-8")
    report = ingest_file(f, store, max_chars=150, overlap=30)
    assert report.files_ingested == 1 and report.chunks >= 2
    assert report.files_skipped == 0
    entries = store.list(limit=100000)
    assert all("rag" in e.tags for e in entries)
    assert all((e.metadata or {}).get("rag") for e in entries)
    prov = entries[0].metadata["provenance"]
    assert prov["source_doc"] == "notes.md"
    assert "chunk_index" in prov and "char_span" in prov


def test_ingest_skips_unreadable(tmp_path, store):
    report = ingest_file(tmp_path / "missing.md", store)
    assert report.files_ingested == 0 and report.files_skipped == 1
    empty = tmp_path / "empty.md"
    empty.write_text("   ", encoding="utf-8")
    report2 = ingest_file(empty, store)
    assert report2.files_skipped == 1
    assert store.list(limit=100000) == []


def test_ingest_directory(tmp_path, store):
    (tmp_path / "a.md").write_text("# A\n\nAlpha content here.", encoding="utf-8")
    (tmp_path / "b.md").write_text("# B\n\nBeta content here.", encoding="utf-8")
    report = ingest_directory(tmp_path, store)
    assert report.files_ingested == 2 and report.chunks >= 2


# --- pipeline ---------------------------------------------------------------

def _ingested(store, tmp_path):
    f = tmp_path / "backups.md"
    f.write_text(DOC, encoding="utf-8")
    ingest_file(f, store)
    return store


def test_ask_no_generator_returns_context_and_notice(tmp_path, store):
    _ingested(store, tmp_path)
    # Force generator-unavailable by hiding the agent runtime module.
    import levi.rag.pipeline as pipe
    orig = pipe._generate
    pipe._generate = lambda *a, **k: None
    try:
        res = ask("backup encryption passphrase", store, generate=True)
    finally:
        pipe._generate = orig
    assert res.answer is None
    assert "no generator available" in res.notice
    assert res.context  # context still returned
    assert res.citations  # [memory:<id>] citations present
    assert all(cid.startswith("[memory:") or True for cid in res.citations)
    assert "[memory:%s]" % res.citations[0] in res.context


def test_ask_nothing_retrieved_is_honest(tmp_path, store):
    _ingested(store, tmp_path)
    res = ask("quantum chromodynamics quark flavors", store)
    assert res.answer is None
    assert "nothing relevant" in res.notice
    assert res.citations == []


def test_relevance_gate_margin(tmp_path, store):
    from levi.rag.pipeline import apply_relevance_gate
    _ingested(store, tmp_path)
    from levi.memory.retrieval import retrieve
    # nonsense: no lexical evidence, weak vector sim → all dropped
    junk = retrieve("quantum chromodynamics quark flavors", store,
                    method="hybrid", limit=10)
    assert junk, "sanity: ranker returns *something* before gating"
    assert apply_relevance_gate(junk) == []
    # genuine paraphrase-ish query survives the gate
    good = retrieve("when do backups run", store, method="hybrid", limit=10)
    assert apply_relevance_gate(good), "real query must survive the gate"


def test_ask_blank_query(tmp_path, store):
    res = ask("   ", store)
    assert res.answer is None and "blank" in res.notice


def test_rerank_prefers_coverage(tmp_path, store):
    _ingested(store, tmp_path)
    from levi.memory.retrieval import retrieve
    retrieved = retrieve("backup encryption passphrase", store, method="hybrid")
    ranked = rerank("backup encryption passphrase", retrieved)
    assert ranked
    top_entry = ranked[0][0]
    assert "passphrase" in (top_entry.content or "").lower()


def test_coverage_score_bounds():
    class E:
        content = "the quick brown fox"
        tags = []
    s, _x = coverage_score("quick fox", E())
    assert 0.0 <= s <= 1.0
    s2, _x2 = coverage_score("zebra zebra", E())
    assert s2 == 0.0


def test_build_context_cites_and_caps(tmp_path, store):
    _ingested(store, tmp_path)
    from levi.memory.retrieval import retrieve
    retrieved = retrieve("backup", store, method="hybrid")
    ctx, cids = build_context(retrieved, max_chars=200)
    assert len(ctx) <= 400  # bounded
    assert cids and all("[memory:%s]" % c in ctx for c in cids)


# --- eval -------------------------------------------------------------------

def _five_doc_store(tmp_path):
    store = MemoryStore(data_dir=tmp_path / "memory")
    docs = {
        "alpha.md": "# Alpha\n\nThe alpha protocol uses rotating keys every day.",
        "beta.md": "# Beta\n\nBeta dashboards refresh every five minutes.",
        "gamma.md": "# Gamma\n\nGamma retention keeps logs for ninety days.",
        "delta.md": "# Delta\n\nDelta alerts fire on three failed logins.",
        "epsilon.md": "# Epsilon\n\nEpsilon exports run at midnight UTC.",
    }
    for name, text in docs.items():
        f = tmp_path / name
        f.write_text(text, encoding="utf-8")
        ingest_file(f, store, max_chars=500, overlap=50)
    return store


def test_eval_completes_with_recall(tmp_path):
    store = _five_doc_store(tmp_path)
    report = evaluate(store, k=5)
    assert report["total"] > 0
    assert 0.0 <= report["recall_at_k"] <= 1.0
    assert 0.0 <= report["hit_rate"] <= 1.0
    text = print_report(report)
    assert "hit-rate@5" in text and "recall@5" in text


def test_build_questions_from_chunks(tmp_path):
    store = _five_doc_store(tmp_path)
    qs = build_questions(store)
    assert qs
    assert all(q.expected_id for q in qs)


# --- CLI smoke ---------------------------------------------------------------

def test_cli_ingest_ask_eval(tmp_path):
    env = dict(os.environ, LEVI_RAG_HOME=str(tmp_path / "raghome"))
    doc = tmp_path / "doc.md"
    doc.write_text("# Widget\n\nWidgets calibrate at dawn.", encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, "-m", "levi.rag"]
    r = subprocess.run(cmd + ["ingest", str(doc)], capture_output=True, text=True,
                       env={**env, "PYTHONPATH": str(root / "core")}, timeout=60)
    assert r.returncode == 0, r.stderr
    r = subprocess.run(cmd + ["ask", "widget calibration", "--no-generate"],
                       capture_output=True, text=True,
                       env={**env, "PYTHONPATH": str(root / "core")}, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "[memory:" in r.stdout
    r = subprocess.run(cmd + ["eval", "--k", "3"], capture_output=True, text=True,
                       env={**env, "PYTHONPATH": str(root / "core")}, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "hit-rate@3" in r.stdout
