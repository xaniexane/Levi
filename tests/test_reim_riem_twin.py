"""Tests for the REIM/RIEM twin variant (core/levi/twins/reim_riem.py).

Hermetic: every store lives under tmp_path (no HOME writes). Each test
proves one declared TWIN INVARIANT from the module docstring:
1. no lesson compacts without a composted failure behind it
2. genome consulted before generation
3. bidirectional link never silently broken
4. fail-closed on guard errors
Plus: end-to-end cycle, journal integrity, and shared stores with a
QuettaPanEngine (the twin variant extends the engine's loop).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from levi.operator.contract import OperatorContractError
from levi.twins.reim_riem import (
    LinkBrokenError,
    ReimRiemPair,
    ReimTwin,
)


def _failure(mid: str, rule: str = "PY_BARE_EXCEPT", ctx: str = "py") -> dict:
    return {
        "mutation_id": mid,
        "rule_id": rule,
        "file": "a.py",
        "context": ctx,
        "tried_what": f"apply safe fix for {rule}",
        "failed_why": f"parse check failed: python parse failed ({mid})",
    }


def _pair(tmp_path: Path, pair_id: str = "test-pair") -> ReimRiemPair:
    return ReimRiemPair(store_dir=tmp_path / "store", pair_id=pair_id)


# ---- spawn: contract-validated, link recorded both ways --------------------


def test_spawn_validates_contract_and_links_both_ways(tmp_path):
    pair = _pair(tmp_path)
    # contract gate ran at spawn: direct validation passes too
    pair.twin_a.validate()
    pair.twin_b.validate()
    assert pair.twin_a.kind == "si" and pair.twin_b.kind == "si"
    assert pair.twin_a.symbiont_id == pair.twin_b.name
    assert pair.twin_b.symbiont_id == pair.twin_a.name
    assert pair.twin_a.link_mode == pair.twin_b.link_mode == "symbiotic"
    assert pair.verify_link() is True
    # capability declarations are the intelligence-type tools
    assert "failure_compost" in pair.twin_a.capabilities().tools
    assert "dream_compress" in pair.twin_b.capabilities().tools
    # honest step/health surface
    assert pair.twin_a.health().ok and pair.twin_b.health().ok
    assert "compost twin" in pair.twin_a.step([], [], {}).text
    assert "dream twin" in pair.twin_b.step([], [], {}).text


def test_contract_rejects_broken_twin():
    bad = ReimTwin(
        name="",
        symbiont_id="x",
        compost=None,  # type: ignore[arg-type]
    )
    with pytest.raises(OperatorContractError):
        bad.validate()


# ---- invariant 1: no compact without compost --------------------------------


def test_no_compact_without_compost(tmp_path):
    pair = _pair(tmp_path)
    fake = dict(_failure("never-composted"))
    fake["inverse_lesson"] = "invented lesson, never composted"
    with pytest.raises(ValueError, match="uncomposted"):
        pair.twin_b.fold_compost(fake, pair.compost)
    # genome untouched: no slot was created by the refused fold
    assert pair.genome.patterns() == {}
    assert not (tmp_path / "store" / ".quetta_genome.json").exists()


def test_no_compact_without_inverse_lesson(tmp_path):
    pair = _pair(tmp_path)
    entry = pair.twin_a.ingest_failure(_failure("m1"))
    stripped = {k: v for k, v in entry.items() if k != "inverse_lesson"}
    with pytest.raises(ValueError, match="inverse lesson"):
        pair.twin_b.fold_compost(stripped, pair.compost)
    assert pair.genome.patterns() == {}


# ---- invariant 2: genome consulted before generation ------------------------


def test_genome_consulted_before_generation(tmp_path):
    pair = _pair(tmp_path)
    assert pair.advise("R_NEW", "py")["verdict"] == "unknown"
    assert pair.advise("R_NEW", "py")["proceed"] is True
    # two composted failures -> the pair refuses to proceed
    pair.cycle(_failure("m1", rule="R_SUP"))
    pair.cycle(_failure("m2", rule="R_SUP"))
    advice = pair.advise("R_SUP", "py")
    assert advice["verdict"] == "suppress"
    assert advice["proceed"] is False
    assert "genome" in advice["reason"]
    # a recorded success boosts instead
    pair.genome.record_success("R_WIN", "py", "clean")
    assert pair.advise("R_WIN", "py")["verdict"] == "boost"


# ---- invariant 3: bidirectional link never silently broken -------------------


def test_bidirectional_link_visible_both_ways(tmp_path):
    pair = _pair(tmp_path)
    for i in range(3):
        res = pair.cycle(_failure(f"m{i}"))
        assert pair.verify_link() is True
        # one event id, visible on both twins and in the journal
        assert pair.twin_a.last_event_id == res["event_id"]
        assert pair.twin_b.last_event_id == res["event_id"]
    exchanges = [
        r for r in pair.read_journal() if r["event"] == "exchange"
    ]
    assert len(exchanges) == 3
    # three distinct exchanges; the tail matches both twins' pointer
    assert len({e["event_id"] for e in exchanges}) == 3
    assert exchanges[-1]["event_id"] == pair.twin_a.last_event_id
    assert exchanges[-1]["event_id"] == pair.twin_b.last_event_id


def test_link_break_detected_symbiont(tmp_path):
    pair = _pair(tmp_path)
    pair.cycle(_failure("m1"))
    pair.twin_a.symbiont_id = "impostor"
    with pytest.raises(LinkBrokenError, match="symbiont"):
        pair.verify_link()


def test_link_break_detected_event_divergence(tmp_path):
    pair = _pair(tmp_path)
    pair.cycle(_failure("m1"))
    pair.twin_b.last_event_id = "ev-tampered"
    with pytest.raises(LinkBrokenError, match="diverged"):
        pair.verify_link()


# ---- invariant 4: fail-closed -------------------------------------------------


def test_fail_closed_on_invalid_failure(tmp_path):
    pair = _pair(tmp_path)
    with pytest.raises(ValueError):
        pair.twin_a.ingest_failure({"mutation_id": "m1"})  # missing keys
    # nothing half-written: compost empty, genome empty, no exchange
    assert pair.twin_a.compost_count() == 0
    assert pair.genome.patterns() == {}
    assert [
        r for r in pair.read_journal() if r["event"] == "exchange"
    ] == []


def test_fail_closed_fold_refused_leaves_genome_untouched(tmp_path):
    pair = _pair(tmp_path)
    pair.cycle(_failure("m1", rule="R_OK"))
    before = pair.genome.patterns()
    with pytest.raises(ValueError, match="uncomposted"):
        pair.twin_b.fold_compost(
            {**_failure("mX", rule="R_OK"), "inverse_lesson": "x"},
            pair.compost,
        )
    # compost stands (append-only), genome unchanged by the refusal
    assert pair.twin_a.compost_count() == 1
    assert pair.genome.stats("R_OK", "py")["failures"] == 1
    assert pair.genome.patterns() == before


# ---- end-to-end cycle ----------------------------------------------------------


def test_cycle_end_to_end(tmp_path):
    pair = _pair(tmp_path)
    res = pair.cycle(_failure("m1"))
    entry = res["entry"]
    assert "instead:" in entry["inverse_lesson"]
    assert entry["failure_class"] == "parse"
    assert res["genome_slot"]["failures"] == 1
    assert pair.genome.stats("PY_BARE_EXCEPT", "py")["failures"] == 1
    # the twin's own stores agree
    assert pair.twin_a.compost_count() == 1
    assert pair.twin_a.recent_lessons(1)[0]["mutation_id"] == "m1"


def test_journal_is_append_only_and_parseable(tmp_path):
    pair = _pair(tmp_path)
    pair.cycle(_failure("m1"))
    pair.advise("R", "py")
    records = pair.read_journal()
    assert records[0]["event"] == "pair_spawned"
    kinds = [r["event"] for r in records]
    assert kinds == ["pair_spawned", "exchange", "consult"]
    for r in records:
        assert r["pair_id"] == "test-pair"
        assert r["ts"]


# ---- the twin variant extends the engine's loop (shared stores) ---------------


def test_pair_shares_engine_stores(tmp_path):
    from levi.quetta_pan import QuettaPanEngine

    proj = tmp_path / "proj"
    proj.mkdir()
    store = tmp_path / "store"
    store.mkdir()
    pair = ReimRiemPair(store_dir=store, pair_id="shared")
    pair.cycle(_failure("m9"))
    # a fresh engine on the same store sees the twin's compost+genome
    eng = QuettaPanEngine(project_root=proj, store_dir=store)
    assert eng.compost.count() == 1
    assert eng.genome.stats("PY_BARE_EXCEPT", "py")["failures"] == 1
    # and the engine's own suppression now fires from the twin's lesson
    assert eng.genome.consult("PY_BARE_EXCEPT", "py") in ("unknown", "suppress")
    eng.genome.learn("PY_BARE_EXCEPT", "py", False, "second lesson")
    assert eng.genome.consult("PY_BARE_EXCEPT", "py") == "suppress"
