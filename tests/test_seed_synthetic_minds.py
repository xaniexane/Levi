"""Hermetic tests for the synthetic-minds knowledge seed batch.

No real HOME writes: HOME is sandboxed to tmp_path before seeding, so the
brain corpus lands in the sandbox. No network, no randomness.
"""

from levi.brain import seed_synthetic_minds
from levi.brain.seed_synthetic_minds import format_index, iter_synthetic_minds, seed

KINDS = {"OBSERVED", "INFERENCE", "HYPOTHESIS"}


def test_unit_count():
    assert len(seed_synthetic_minds._RAW) == 20


def test_entry_shapes():
    for text, kind, tags in seed_synthetic_minds._RAW:
        assert text and len(text) >= 80
        assert kind in KINDS, kind
        assert "minds" in tags
        assert (
            "synthetic-intelligence" in tags
            or "uncommon-minds" in tags
            or "dead-minds" in tags
        )


def test_honest_labeling():
    kinds = {kind for _t, kind, _tg in seed_synthetic_minds._RAW}
    # every honesty tier the corpus law defines is exercised here
    assert kinds == KINDS


def test_no_hardcoded_owner_identity():
    for text, _k, _t in seed_synthetic_minds._RAW:
        blob = text.lower()
        assert "@" not in blob
        for needle in ("chauncey", "core@levi", "gmail"):
            assert needle not in blob


def test_no_seed_claims_levi_identity():
    for text, _k, _t in seed_synthetic_minds._RAW:
        assert "i am levi" not in text.lower()


def test_format_index_reports_count():
    lines = format_index().splitlines()
    assert lines[1] == "units=20"


def test_iter_limit():
    assert len(list(iter_synthetic_minds(limit=5))) == 5
    assert len(list(iter_synthetic_minds())) == 20


def test_seed_writes_corpus_sandboxed(monkeypatch, tmp_path):
    import levi.brain.corpus as corpus_mod

    monkeypatch.setattr(corpus_mod, "DEFAULT", tmp_path / "corpus.jsonl")
    assert seed() == 20
    lines = (tmp_path / "corpus.jsonl").read_text().strip().splitlines()
    assert len(lines) == 20
    assert all('"source": "seed_synthetic_minds"' in line for line in lines)
