"""Hermetic tests for levi.brain.train.v2.corpus_manager (stdlib only)."""

import json

import pytest

from levi.brain.train.v2.corpus_manager import (
    CorpusError,
    Doc,
    PolicyError,
    build_manifest,
    check_policy,
    dedupe,
    doc_sha256,
    load_jsonl_docs,
    load_manifest,
    save_manifest,
    split_docs,
    verify_manifest,
    write_split_jsonl,
)


def _write_corpus(path, texts, tags_per_doc=None):
    with open(path, "w", encoding="utf-8") as fh:
        for i, text in enumerate(texts):
            obj = {"text": text, "kind": "course"}
            if tags_per_doc and i < len(tags_per_doc):
                obj["tags"] = tags_per_doc[i]
            fh.write(json.dumps(obj) + "\n")
    return path


def _docs(texts):
    return [Doc(id=doc_sha256(t), text=t) for t in texts]


# ---------------------------------------------------------------- policy


def test_news_tag_rejected():
    with pytest.raises(PolicyError, match="news"):
        check_policy(["courses", "news"])


def test_news_tag_case_insensitive():
    with pytest.raises(PolicyError, match="news"):
        check_policy(["NEWS"])


def test_news_path_hint_rejected():
    with pytest.raises(PolicyError, match="news"):
        check_policy(["courses"], source_path="corpora/daily_news.jsonl")


def test_clean_corpus_passes():
    check_policy(["courses", "seed-knowledge"], source_path="corpora/c.jsonl")


def test_build_manifest_rejects_news_tagged(tmp_path):
    p = _write_corpus(tmp_path / "c.jsonl", ["hello world"])
    with pytest.raises(PolicyError):
        build_manifest("x", "v1", [p], tags=["news"])


# ---------------------------------------------------------------- dedupe


def test_dedupe_removes_exact_duplicates():
    docs = _docs(["alpha beta", "gamma delta", "alpha beta", "  alpha   beta "])
    unique, removed = dedupe(docs)
    assert removed == 2  # exact dup + whitespace-variant dup
    assert [d.text for d in unique] == ["alpha beta", "gamma delta"]


def test_dedupe_keeps_first_occurrence():
    docs = [
        Doc(id="a", text="same", source="s1"),
        Doc(id="b", text="same", source="s2"),
    ]
    unique, removed = dedupe(docs)
    assert removed == 1
    assert unique[0].source == "s1"


def test_doc_sha256_stable():
    assert doc_sha256("a  b") == doc_sha256("a b")


# ---------------------------------------------------------------- loading


def test_load_jsonl_docs(tmp_path):
    p = _write_corpus(
        tmp_path / "c.jsonl", ["one", "two"], tags_per_doc=[["courses"], []]
    )
    (p.open("a", encoding="utf-8").write('{"text": ""}\nnot json\n'))
    docs = load_jsonl_docs(p)
    assert [d.text for d in docs] == ["one", "two"]
    assert docs[0].tags == ("courses",)
    assert docs[0].meta["kind"] == "course"
    assert docs[0].source.endswith(":1")


def test_load_missing_file():
    with pytest.raises(CorpusError, match="not found"):
        load_jsonl_docs("/nonexistent/c.jsonl")


# ---------------------------------------------------------------- manifests


def test_build_save_load_manifest(tmp_path):
    p1 = _write_corpus(tmp_path / "a.jsonl", ["alpha", "beta gamma"])
    p2 = _write_corpus(tmp_path / "b.jsonl", ["delta"])
    m = build_manifest(
        "courses", "2026-09-15", [p1, p2], tags=["courses"], base_dir=tmp_path
    )
    assert m.n_docs == 3
    assert m.n_chars == len("alpha") + len("beta gamma") + len("delta")
    assert len(m.files) == 2
    assert all(len(f.sha256) == 64 for f in m.files)
    assert m.policy == "news-excluded"
    mp = save_manifest(m, tmp_path / "m.manifest.json")
    loaded = load_manifest(mp)
    assert loaded.name == "courses"
    assert loaded.version == "2026-09-15"
    assert loaded.n_docs == 3
    assert loaded.tags == ("courses",)


def test_verify_manifest_clean_and_tampered(tmp_path):
    p = _write_corpus(tmp_path / "a.jsonl", ["alpha"])
    m = build_manifest("c", "v1", [p], base_dir=tmp_path)
    assert verify_manifest(m, base_dir=tmp_path) == []
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"text": "sneaky addition"}) + "\n")
    problems = verify_manifest(m, base_dir=tmp_path)
    assert any("hash mismatch" in pr for pr in problems)


def test_verify_manifest_missing_file(tmp_path):
    p = _write_corpus(tmp_path / "a.jsonl", ["alpha"])
    m = build_manifest("c", "v1", [p], base_dir=tmp_path)
    p.unlink()
    assert any("missing file" in pr for pr in verify_manifest(m, base_dir=tmp_path))


def test_verify_manifest_flags_news_tag(tmp_path):
    p = _write_corpus(tmp_path / "a.jsonl", ["alpha"])
    m = build_manifest("c", "v1", [p], base_dir=tmp_path)
    m.tags = ("news",)
    assert any("policy violation" in pr for pr in verify_manifest(m, base_dir=tmp_path))


# ---------------------------------------------------------------- splits


def test_split_deterministic_and_sized():
    docs = _docs([f"doc number {i} with some words" for i in range(100)])
    a = split_docs(docs, train=0.8, val=0.1, test=0.1, seed=42)
    b = split_docs(docs, train=0.8, val=0.1, test=0.1, seed=42)
    assert [d.id for d in a["train"]] == [d.id for d in b["train"]]
    assert len(a["train"]) == 80 and len(a["val"]) == 10 and len(a["test"]) == 10
    ids = [d.id for s in a.values() for d in s]
    assert len(set(ids)) == 100  # disjoint, no loss


def test_split_different_seed_differs():
    docs = _docs([f"doc {i}" for i in range(50)])
    a = split_docs(docs, seed=1)["train"]
    b = split_docs(docs, seed=2)["train"]
    assert [d.id for d in a] != [d.id for d in b]


def test_split_fractions_must_sum_to_one():
    docs = _docs(["a", "b"])
    with pytest.raises(CorpusError, match="sum to 1"):
        split_docs(docs, train=0.5, val=0.5, test=0.5)


def test_write_split_jsonl_roundtrip(tmp_path):
    docs = _docs(["alpha beta", "gamma"])
    docs[0].tags = ("courses",)
    p = write_split_jsonl(docs, tmp_path / "train.jsonl")
    back = load_jsonl_docs(p)
    assert [d.text for d in back] == ["alpha beta", "gamma"]
    assert back[0].tags == ("courses",)
