"""Tests for the fallen-deliberation methods (hunt 2026-09-17).

Covers methods/delphi.py, methods/ngt.py, methods/crawford.py,
methods/futuresearch.py: protocol happy paths plus deny-closed refusals.
"""

import pytest

from levi.methods.delphi import DelphiRound
from levi.methods.ngt import NGTSession
from levi.methods.crawford import CrawfordSession
from levi.methods.futuresearch import FutureSearch


# ---------------------------------------------------------------- delphi
def test_delphi_round_feedback_and_convergence():
    r = DelphiRound(
        members=["a", "b", "c", "d"], question="Q3 growth?", convergence_iqr=1.0
    )
    for m, v in [("a", 10.0), ("b", 11.0), ("c", 10.5), ("d", 12.0)]:
        r.submit(m, v, rationale="gut")
    stats = r.close()
    assert stats["n"] == 4
    assert stats["median"] == pytest.approx(10.75)
    assert stats["iqr"] == pytest.approx(1.625)
    assert not r.converged()
    r2 = r.next_round()
    assert r2.round_no == 2
    for m, v in [("a", 10.6), ("b", 10.8), ("c", 10.7), ("d", 11.0)]:
        r2.submit(m, v)
    r2.close()
    assert r2.converged()
    assert len(r.rationales()) == 4


def test_delphi_refusals():
    with pytest.raises(ValueError):
        DelphiRound(members=["only"], question="q")
    with pytest.raises(ValueError):
        DelphiRound(members=["a", "b"], question="")
    r = DelphiRound(members=["a", "b"], question="q")
    with pytest.raises(ValueError):
        r.close()  # zero submissions
    r.submit("a", 5)
    with pytest.raises(ValueError):
        r.submit("a", 6)  # duplicate in round
    with pytest.raises(ValueError):
        r.submit("ghost", 6)  # not a member
    with pytest.raises(ValueError):
        r.submit("b", "high")  # non-numeric
    r.submit("b", 7)
    r.close()
    with pytest.raises(ValueError):
        r.submit("a", 9)  # closed round: revise in the next round
    with pytest.raises(ValueError):
        r.close()  # already closed
    with pytest.raises(ValueError):
        r.next_round().close()  # zero submissions in new round


# ---------------------------------------------------------------- ngt
def _ngt_session():
    s = NGTSession(members=["amy", "bo", "cy"], question="What should LEVI build next?")
    s.generate("amy", ["deliberation kit", "voice notes"])
    s.generate("bo", ["deliberation kit", "game night"])
    s.generate("cy", ["fairtrade ledger"])
    return s


def test_ngt_full_protocol():
    s = _ngt_session()
    ideas = s.round_robin()
    # round-robin interleave: one per member per pass
    assert [i.author for i in ideas] == ["amy", "bo", "cy", "amy", "bo"]
    s.merge_duplicates(keep_id=1, drop_ids=[4])  # dedupe "deliberation kit"
    s.finish_clarification()
    # private ranking
    s.vote("amy", [1, 5, 2, 3])
    s.vote("bo", [3, 1, 5, 2])
    s.vote("cy", [5, 1, 3, 2])
    results = s.tally()
    assert results[0]["id"] == 1  # deliberation kit wins the Borda sum
    assert results[0]["points"] >= results[1]["points"]


def test_ngt_stage_refusals():
    s = NGTSession(members=["a", "b"], question="q")
    s.generate("a", ["x"])
    with pytest.raises(ValueError):
        s.round_robin()  # b has not generated
    with pytest.raises(ValueError):
        s.vote("a", [1])  # voting before round-robin
    s.generate("b", ["y"])
    s.round_robin()
    with pytest.raises(ValueError):
        s.tally()  # not in vote stage
    s.finish_clarification()
    with pytest.raises(ValueError):
        s.vote("a", [99])  # unlisted idea
    s.vote("a", [1, 2])
    with pytest.raises(ValueError):
        s.vote("a", [2, 1])  # double vote
    with pytest.raises(ValueError):
        s.tally()  # b has not voted
    s.vote("b", [2, 1])
    assert len(s.tally()) == 2


# ---------------------------------------------------------------- crawford
def test_crawford_rounds_sort_report():
    s = CrawfordSession(target="What slows the build?")
    s.open_round()
    s.write("flaky tests")
    s.write("flaky tests")
    s.write("slow CI")
    assert len(s.collect()) == 3
    s.open_round()
    s.write("flaky tests")
    assert len(s.collect()) == 1
    with pytest.raises(ValueError):
        s.write("too late")  # no round open
    counts = s.sort({"tooling": [0, 1, 3], "infra": [2]})
    assert counts == {"tooling": 3, "infra": 1}
    report = s.report()
    assert report[0]["category"] == "tooling"
    assert report[0]["count"] == 3


def test_crawford_refusals():
    with pytest.raises(ValueError):
        CrawfordSession(target="")
    s = CrawfordSession(target="t")
    with pytest.raises(ValueError):
        s.write("x")  # no round open
    s.open_round()
    with pytest.raises(ValueError):
        s.write("   ")  # empty slip
    with pytest.raises(ValueError):
        s.open_round()  # round still open
    with pytest.raises(ValueError):
        s.sort({"a": [0]})  # sort before collect
    s.collect()
    with pytest.raises(ValueError):
        s.sort({})  # no categories
    with pytest.raises(ValueError):
        s.sort({"a": [7]})  # index out of range


# ---------------------------------------------------------------- futuresearch
def _arein():
    return {
        "authority": ["board"],
        "resources": ["ops"],
        "expertise": ["eng"],
        "information": ["data"],
        "need": ["users"],
    }


def test_futuresearch_full_arc():
    fs = FutureSearch(topic="LEVI 2027 strategy", stakeholders=_arein())
    assert fs.stage == "past"
    fs.record("past", ["founded 2026", "first hunt wave"])
    fs.record("present", ["corpus at scale", "no cloud dependency"])
    assert fs.stage == "future"
    fs.record("future", ["self-hosting galaxy", "100 warehouses"])
    fs.record("common_ground", ["local-first always", "honest receipts"])
    assert fs.common_ground() == ["local-first always", "honest receipts"]
    fs.record("action", ["ship deliberation kit", "schedule next search"])
    assert fs.complete()


def test_futuresearch_arein_gate_and_order():
    bad = _arein()
    del bad["need"]
    with pytest.raises(ValueError):
        FutureSearch(topic="t", stakeholders=bad)
    fs = FutureSearch(topic="t", stakeholders=_arein())
    with pytest.raises(ValueError):
        fs.record("action", ["skip ahead"])  # no problem-solving before the arc
    with pytest.raises(ValueError):
        fs.record("future", ["jump"])  # present arc not digested
    with pytest.raises(ValueError):
        fs.record("past", [])  # empty artifact
    fs.record("past", ["p"])
    with pytest.raises(ValueError):
        fs.common_ground()  # not established yet
    fs.record("present", ["pr"])
    fs.record("future", ["f"])
    with pytest.raises(ValueError):
        fs.record("past", ["late"])  # can't revisit
