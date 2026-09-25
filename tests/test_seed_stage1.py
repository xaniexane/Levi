"""Hermetic tests for the Stage-1 knowledge seed batch.

No real HOME writes: HOME is sandboxed to tmp_path before seeding, so the
brain corpus lands in the sandbox. No network, no randomness.
"""

from levi.brain import seed_stage1
from levi.brain.seed_stage1 import format_index, seed


def test_exactly_25_entries():
    assert len(seed_stage1._RAW) == 25


def test_serial_format_and_uniqueness():
    serials = [text.split(" ", 1)[0] for text, _k, _t in seed_stage1._RAW]
    assert len(serials) == len(set(serials))  # never reused
    for s in serials:
        assert s.startswith("KB-")
        parts = s.split("-")
        assert len(parts) == 6  # KB-DOMAIN-YYYY-ALPHA-INSTANCE-CHECK
        assert parts[2] == "2026"


def test_entry_shapes():
    for text, kind, tags in seed_stage1._RAW:
        assert text and kind == "OBSERVED"
        assert "stage1" in tags and "nano" in tags
        # no hardcoded owner identity or emails (privacy law)
        blob = text.lower()
        assert "@" not in blob
        for needle in ("chauncey", "core@levi", "gmail"):
            assert needle not in blob


def test_safety_topics_labeled_education_only():
    safety = [
        (text, tg)
        for text, _k, tg in seed_stage1._RAW
        if {"safety", "first-aid", "cpr", "repair", "infection"} & set(tg)
    ]
    assert len(safety) >= 2
    for text, _tg in safety:
        assert "EDUCATION ONLY" in text


def test_tier_counts_via_tags():
    tags = [tg for _t, _k, tg in seed_stage1._RAW]
    assert all("nano" in tg for tg in tags)  # all 25 ingest as nano literacy units


def test_no_seed_claims_levi_identity():
    for text, _k, _t in seed_stage1._RAW:
        assert "levi" not in text.lower()


def test_format_index_25_lines():
    lines = format_index().splitlines()
    assert len(lines) == 25
    assert all(line.startswith("KB-") for line in lines)


def test_seed_writes_corpus_sandboxed(monkeypatch, tmp_path):
    import levi.brain.corpus as corpus_mod

    corpus_file = tmp_path / "corpus.jsonl"
    monkeypatch.setattr(corpus_mod, "DEFAULT", corpus_file)
    n = seed(limit=3)
    assert n == 3
    assert corpus_file.exists()
    lines = corpus_file.read_text().strip().splitlines()
    assert len(lines) == 3
    assert all('"source": "seed_stage1"' in line for line in lines)


def test_seed_full_batch_count(monkeypatch, tmp_path):
    import levi.brain.corpus as corpus_mod

    monkeypatch.setattr(corpus_mod, "DEFAULT", tmp_path / "corpus.jsonl")
    assert seed() == 25
