"""Tests for the growth corpus export (levi.growth.corpus_export).

The export is the adapter between the growth loop's learnings and the
curriculum builder: redacted, deduped JSONL of self-taught learnings.
All synthetic fixtures; hermetic against a tmp memory store.
"""

from __future__ import annotations

import json

import pytest

from levi.growth.corpus_export import (
    collect_corpus_records,
    export_corpus,
)
from levi.growth.__main__ import main as growth_main
from levi.memory.store import MemoryStore
from levi.memory.types import MemoryType


def _store(tmp_path, data_dir=None):
    store = MemoryStore(data_dir=data_dir or tmp_path / "memory")
    store.add(
        memory_type=MemoryType.SEMANTIC,
        content="The user prefers concise answers in every app.",
        source="growth",
        tags=["growth", "levi-learned", "preference"],
        metadata={
            "confidence": 0.7,
            "corroborated_count": 3,
            "cycle_id": "cyc-a",
            "status": "provisional",
        },
    )
    # duplicate text (different entry) — export must dedupe it
    store.add(
        memory_type=MemoryType.SEMANTIC,
        content="The user prefers concise answers in every app.",
        source="growth",
        tags=["growth", "levi-learned", "preference"],
        metadata={"confidence": 0.7, "cycle_id": "cyc-b", "status": "provisional"},
    )
    # distribution routing slip — not a learning, must be excluded
    store.add(
        memory_type=MemoryType.SEMANTIC,
        content="routing slip for the backup subsystem",
        source="growth",
        tags=["growth", "distribution", "fact"],
        metadata={"confidence": 0.9},
    )
    # curriculum seed — not self-taught, must be excluded
    store.add(
        memory_type=MemoryType.SEMANTIC,
        content="Founders teach: local-first is the binding law.",
        source="growth",
        tags=["growth", "curriculum", "fact"],
        metadata={"confidence": 0.95},
    )
    return store


def test_collect_records_redacted_deduped(tmp_path):
    store = _store(tmp_path)
    recs = collect_corpus_records(store)
    assert len(recs) == 1  # duplicate collapsed, slips/seed excluded
    rec = recs[0]
    assert rec["kind"] == "preference"
    assert rec["confidence"] == 0.7
    assert rec["corroborated_count"] == 3
    assert rec["source"] == "growth"
    assert rec["status"] == "provisional"
    assert rec["cycle_id"] == "cyc-a"
    assert rec["memory_id"]
    assert "concise answers" in rec["text"]


def test_min_confidence_filter(tmp_path):
    store = _store(tmp_path)
    assert collect_corpus_records(store, min_confidence=0.8) == []
    assert len(collect_corpus_records(store, min_confidence=0.7)) == 1


def test_redaction_applied_to_export(tmp_path):
    store = MemoryStore(data_dir=tmp_path / "memory")
    store.add(
        memory_type=MemoryType.SEMANTIC,
        content="User asked Levi to remember: 'contact me at test@example.com'.",
        source="growth",
        tags=["growth", "levi-learned", "fact"],
        metadata={"confidence": 0.75, "cycle_id": "cyc-x", "status": "provisional"},
    )
    recs = collect_corpus_records(store)
    assert len(recs) == 1
    assert "test@example.com" not in recs[0]["text"]
    assert "[email redacted]" in recs[0]["text"]


def test_export_corpus_writes_jsonl(tmp_path):
    store = _store(tmp_path)
    out = tmp_path / "corpus" / "growth-corpus.jsonl"
    summary = export_corpus(out, store)
    assert summary["records"] == 1
    assert out.is_file()
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert set(rec) == {
        "text",
        "kind",
        "confidence",
        "corroborated_count",
        "source",
        "status",
        "cycle_id",
        "memory_id",
    }


def test_export_corpus_deterministic_order(tmp_path):
    store = MemoryStore(data_dir=tmp_path / "memory")
    for i in range(3):
        store.add(
            memory_type=MemoryType.SEMANTIC,
            content=f"Learned statement number {i} about stable workflows.",
            source="growth",
            tags=["growth", "levi-learned", "fact"],
            metadata={"confidence": 0.5, "cycle_id": "cyc-x", "status": "provisional"},
        )
    recs = collect_corpus_records(store)
    ids = [r["memory_id"] for r in recs]
    assert ids == sorted(ids)


def test_export_corpus_validates_args(tmp_path):
    with pytest.raises(ValueError):
        export_corpus("", None)
    with pytest.raises(ValueError):
        collect_corpus_records(None, min_confidence=1.5)


def test_entrypoint_export_corpus(monkeypatch, tmp_path, capsys):
    import levi.memory.store as mem_store

    mem_dir = tmp_path / ".levi" / "memory"
    monkeypatch.setattr(mem_store, "DEFAULT_DATA_DIR", mem_dir)
    _store(tmp_path, data_dir=mem_dir)
    out = tmp_path / "out.jsonl"
    assert (
        growth_main(["export-corpus", "--out", str(out), "--min-confidence", "0.5"])
        == 0
    )
    printed = capsys.readouterr().out
    assert "exported 1 learning(s)" in printed
    assert out.is_file()


def test_entrypoint_export_corpus_needs_out(capsys):
    assert growth_main(["export-corpus"]) == 2
    assert "needs --out" in capsys.readouterr().err
