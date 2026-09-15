"""Tests for the tiny-brain training pipeline.

torch-dependent tests skip cleanly when torch is unavailable (same pattern
as test_vault.py): the core suite must stay green on a bare stdlib python.
The micro training run is kept FAST (<2 min) by using a small fixture
corpus and 20 steps.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch", reason="torch not installed; tiny-brain training needs it")

TRAIN_DIR = Path(__file__).resolve().parent.parent / "core" / "levi" / "brain" / "train"
sys.path.insert(0, str(TRAIN_DIR))

import prepare_corpus  # noqa: E402
import train as tiny_train  # noqa: E402
import eval as tiny_eval  # noqa: E402


@pytest.fixture()
def fixture_corpus(tmp_path: Path) -> Path:
    """A small but real corpus: identity-style records + course-ish text."""
    path = tmp_path / "corpus.jsonl"
    paras = [
        "Operating systems manage hardware resources and provide abstractions "
        "like processes, virtual memory, and file systems to applications.",
        "Compilers translate high-level source code through lexing, parsing, "
        "semantic analysis, optimization, and code generation.",
        "Machine learning models learn patterns from data by minimizing a "
        "loss function with gradient-based optimization.",
        "Distributed systems coordinate independent machines over a network, "
        "trading off consistency, availability, and partition tolerance.",
    ]
    with open(path, "w", encoding="utf-8") as fh:
        for i, p in enumerate(paras * 60):  # ~60KB of real-ish text
            fh.write(json.dumps({"text": f"{p} Variation {i}.", "kind": "course"}) + "\n")
    return path


def test_prepare_corpus_emits_valid_jsonl_and_identity_records(tmp_path: Path):
    from levi.persona.kai9000 import all_variants

    out = tmp_path / "out"
    # run against the real raw/ + briefs/ dirs (may be mid-ingest; that's fine)
    rc = prepare_corpus.main(["--out", str(out)])
    assert rc == 0
    jsonl = out / "corpus.jsonl"
    assert jsonl.is_file()
    kinds = {}
    n = 0
    with open(jsonl, encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)  # raises if invalid JSONL
            assert "text" in rec and rec["text"].strip()
            kinds[rec.get("kind")] = kinds.get(rec.get("kind"), 0) + 1
            n += 1
    assert n > 0
    # identity records must track the KAI-9000 register count exactly
    assert kinds.get("identity", 0) == len(all_variants()) >= 14
    stats = json.loads((out / "corpus_stats.json").read_text(encoding="utf-8"))
    assert stats["chunks"] == n
    assert stats["identity_records"] == kinds["identity"]


def test_micro_training_run_decreases_loss(fixture_corpus: Path, tmp_path: Path):
    log = tiny_train.train(fixture_corpus, steps=20, out_dir=tmp_path / "w",
                           batch_size=8, seed=7)
    assert log["loss_last"] < log["loss_first"], (
        f"loss did not decrease: {log['loss_first']:.4f} -> {log['loss_last']:.4f}")
    assert (tmp_path / "w" / "tiny-gpt.pt").is_file()
    assert (tmp_path / "w" / "train_log.json").is_file()


def test_eval_handles_missing_weights_gracefully(tmp_path: Path, fixture_corpus: Path):
    rc = tiny_eval.main(["--data", str(fixture_corpus), "--out", str(tmp_path / "empty")])
    assert rc == 2  # plainspoken refusal, no fabricated numbers


def test_eval_produces_samples(tmp_path: Path, fixture_corpus: Path):
    w = tmp_path / "w"
    tiny_train.train(fixture_corpus, steps=20, out_dir=w, batch_size=8, seed=7)
    rc = tiny_eval.main(["--data", str(fixture_corpus), "--out", str(w)])
    assert rc == 0
    samples = (w / "samples.md").read_text(encoding="utf-8")
    assert "held-out loss" in samples
    assert (w / "eval.json").is_file()
