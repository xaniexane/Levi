"""Tests for levi.lwp.twinpair — twin-pair interpenetration engine.

Hermetic: no network, no model calls. The born registry is redirected to
a tmp dir via LEVI_LWP_BORN_DIR (the suite never touches the real HOME).
The mandella stake ledger is process-global and dedups by content
fingerprint, so tests assert membership of their own stake ids.
"""

import json
import os

import pytest

from levi.lwp.twinpair import (
    CANON_PAIRS,
    ECHO_MANDELLA,
    REIM_RIEM,
    CircuitBreaker,
    Expander,
    ExpansionReport,
    PairResult,
    Twin,
    TwinPair,
    VetoVerdict,
    born_registry_path,
    list_born,
)
from levi.organs import mandella as mandella_organ


@pytest.fixture(autouse=True)
def _born_tmp(tmp_path, monkeypatch):
    """Point the born registry at a throwaway dir for every test."""
    d = tmp_path / "born"
    monkeypatch.setenv("LEVI_LWP_BORN_DIR", str(d))
    return d


def _text_material(**kw):
    m = {"id": "m-text", "kind": "note", "text": "draft a chorus about the river"}
    m.update(kw)
    return m


def _failure_material(**kw):
    m = {
        "id": "m-fail",
        "kind": "incident",
        "text": "the deploy failed",
        "failures": [
            {
                "source": "deploy",
                "what": "deploy timed out after 300s waiting on the socket",
                "context": "release pipeline",
                "ts": "2026-09-21",
                "severity": "high",
            }
        ],
    }
    m.update(kw)
    return m


# ---------------------------------------------------------------------------
# veto / circuit breaker
# ---------------------------------------------------------------------------


def test_fits_refuses_material_without_text():
    fits, reason = ECHO_MANDELLA.fits({"id": "x", "kind": "note", "text": "  "})
    assert fits is False
    assert isinstance(reason, str) and reason.strip()


def test_fits_refuses_material_without_failures():
    fits, reason = REIM_RIEM.fits(_text_material())
    assert fits is False
    assert isinstance(reason, str) and reason.strip()


def test_fits_accepts_fitting_material():
    fits, reason = ECHO_MANDELLA.fits(_text_material())
    assert fits is True and reason.strip()
    fits, reason = REIM_RIEM.fits(_failure_material())
    assert fits is True and reason.strip()


def test_circuit_breaker_veto_is_honest():
    breaker = CircuitBreaker()
    verdict = breaker.check(ECHO_MANDELLA, {"id": "x", "kind": "note"})
    assert isinstance(verdict, VetoVerdict)
    assert verdict.paired is False
    assert verdict.pair_name == ECHO_MANDELLA.name
    assert verdict.reason.strip()


def test_circuit_breaker_refuses_unknown_pairs():
    mystery = TwinPair(
        name="mystery×mystery",
        twin_a=Twin(name="a", role="?", risk=1),
        twin_b=Twin(name="b", role="?", risk=1),
        seam="no such seam",
    )
    verdict = CircuitBreaker().check(mystery, _text_material())
    assert verdict.paired is False
    assert "no fit rule" in verdict.reason


def test_refused_pairs_recorded_in_report():
    material = {"id": "m-veto", "kind": "note", "text": "", "failures": []}
    report = Expander(seed="veto").expand(material, rounds=1)
    assert isinstance(report, ExpansionReport)
    assert report.pair_results == []
    assert len(report.refused) == 2  # both canon pairs refused
    assert all(isinstance(v, VetoVerdict) and not v.paired for v in report.refused)
    assert {v.pair_name for v in report.refused} == {
        ECHO_MANDELLA.name,
        REIM_RIEM.name,
    }


# ---------------------------------------------------------------------------
# echo × mandella
# ---------------------------------------------------------------------------


def test_echo_mandella_variants_phantoms_stakes():
    report = Expander(seed="em").expand(
        _text_material(), pairs=(ECHO_MANDELLA,), rounds=1
    )
    assert len(report.pair_results) == 1
    res = report.pair_results[0]
    assert isinstance(res, PairResult)
    assert res.pair_name == ECHO_MANDELLA.name
    assert res.vetoed is False
    variants = res.output["variants"]
    assert len(variants) > 1  # echo expands into parallel variants
    # unchosen variants become phantoms
    assert len(res.phantoms) == len(variants) - 1
    assert res.phantoms  # non-empty
    # the stake was recorded on the mandella ledger
    stake_id = res.output["stakes"]["stake_id"]
    ledger_ids = [s["id"] for s in mandella_organ.list_open_stakes()]
    assert stake_id in ledger_ids
    assert res.output["stakes"]["chosen"].strip()
    # report-level plumbing
    assert report.refused == []
    assert report.material_id == "m-text"


def test_echo_mandella_uses_material_domain():
    report = Expander(seed="dom").expand(
        _text_material(domain="crisis"), pairs=(ECHO_MANDELLA,), rounds=1
    )
    res = report.pair_results[0]
    assert res.output["stakes"]["domain"] == "crisis"


# ---------------------------------------------------------------------------
# reim × riem
# ---------------------------------------------------------------------------


def test_reim_riem_lessons_genome_guards():
    report = Expander(seed="rr").expand(
        _failure_material(), pairs=(REIM_RIEM,), rounds=1
    )
    assert len(report.pair_results) == 1
    res = report.pair_results[0]
    assert res.pair_name == REIM_RIEM.name
    lessons = res.output["lessons"]
    assert lessons and all(item["lesson"].strip() for item in lessons)
    genome = res.output["genome"]
    assert genome["count"] == len(genome["proposals"]) > 0
    guards = res.output["guards"]
    # high-severity resource-exhaustion failure -> guard-rule proposal
    assert guards
    assert all(g["kind"] == "guard-rule" for g in guards)
    assert all(g["applied"] is False for g in genome["proposals"])
    # compost-genome births genome proposals into born entries
    assert res.born
    assert all(set(b) == {"what", "parents", "seed"} for b in res.born)


def test_reim_riem_normalizes_sparse_failure_records():
    material = {
        "id": "m-sparse",
        "kind": "incident",
        "text": "something broke",
        "failures": [{"what": "it just stopped working"}],
    }
    report = Expander(seed="sparse").expand(material, pairs=(REIM_RIEM,), rounds=1)
    assert len(report.pair_results) == 1
    assert report.pair_results[0].output["lessons"]


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------


def test_expand_is_deterministic():
    material = _failure_material(id="m-det", text="the bridge held until it didn't")
    kwargs = dict(rounds=2)
    r1 = Expander(seed="det-seed").expand(material, **kwargs).to_dict()
    r2 = Expander(seed="det-seed").expand(material, **kwargs).to_dict()
    assert r1 == r2


def test_different_seeds_differ():
    material = _text_material()
    r1 = Expander(seed="s1").expand(material, rounds=1).to_dict()
    r2 = Expander(seed="s2").expand(material, rounds=1).to_dict()
    assert r1 != r2


# ---------------------------------------------------------------------------
# expansion across rounds + born registry
# ---------------------------------------------------------------------------


def test_expander_births_across_rounds_and_registers():
    report = Expander(seed="birth").expand(_text_material(), rounds=2)
    assert report.rounds_run == 2
    assert len(report.born) >= 1
    assert all(set(b) == {"what", "parents", "seed"} for b in report.born)

    records = list_born()
    assert len(records) >= 1
    rec = records[0]
    assert set(rec) >= {
        "id",
        "ts",
        "pair_name",
        "what",
        "parents",
        "seed",
        "material_id",
    }
    assert rec["pair_name"] == ECHO_MANDELLA.name
    # newest record is a round-1 fed-back angle; round-0 records carry "m-text"
    assert any(r["material_id"] == "m-text" for r in records)
    # registry lives in the LEVI_LWP_BORN_DIR override, named born.jsonl
    assert born_registry_path().name == "born.jsonl"
    assert str(born_registry_path().parent) == os.environ["LEVI_LWP_BORN_DIR"]


def test_born_registry_is_append_only():
    path = born_registry_path()
    Expander(seed="a1").expand(_text_material(), rounds=1)
    assert path.exists()
    first = path.read_text(encoding="utf-8")
    n_first = len([line for line in first.splitlines() if line.strip()])
    assert n_first > 0

    # a different seed appends more records; earlier lines survive intact
    Expander(seed="a2").expand(_text_material(), rounds=1)
    second = path.read_text(encoding="utf-8")
    assert second.startswith(first)
    n_second = len([line for line in second.splitlines() if line.strip()])
    assert n_second > n_first

    # identical re-run never rewrites or duplicates
    Expander(seed="a2").expand(_text_material(), rounds=1)
    third = path.read_text(encoding="utf-8")
    assert third == second

    # every line is valid JSON with the required shape
    for line in third.splitlines():
        rec = json.loads(line)
        assert rec["id"] and rec["what"] and rec["parents"]


def test_list_born_limit_and_newest_first():
    Expander(seed="lim1").expand(_text_material(), rounds=1)
    Expander(seed="lim2").expand(_text_material(), rounds=1)
    all_recs = list_born()
    assert len(all_recs) > 1
    one = list_born(limit=1)
    assert len(one) == 1
    assert one[0] == all_recs[0]  # newest first
    assert list_born(limit=0) == []


def test_born_dir_constructor_override(tmp_path):
    d = tmp_path / "custom"
    Expander(seed="ov", born_dir=d).expand(_text_material(), rounds=1)
    assert (d / "born.jsonl").exists()
    # env-registry untouched by the override run
    assert list_born() == []


def test_canon_pairs_shape():
    assert CANON_PAIRS == (ECHO_MANDELLA, REIM_RIEM)
    assert ECHO_MANDELLA.twin_a.name == "echo"
    assert ECHO_MANDELLA.twin_a.role == "expands"
    assert ECHO_MANDELLA.twin_b.name == "mandella"
    assert REIM_RIEM.twin_a.name == "reim"
    assert REIM_RIEM.twin_b.name == "riem"
