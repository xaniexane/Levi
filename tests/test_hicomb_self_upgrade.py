"""Hicomb IDE self-upgrade tests — laws -> guards -> machine-checkable proof.

  U1 NO-PROJECTION-APPLIES  proposed/denied/undecided projections refuse apply
  U2 RECEIPTED              every decision carries a timestamped receipt
                            with the projected outcome
  U3 DENIALS-PERSIST        denials keep id/time/reason/outcome; nothing deleted
  U4 REMIX-LINEAGE          recombinations cite parent denied-path ids;
                            parents record remix descendants
  U5 PROJECTED-OUTCOMES     every projection surfaces its projected outcome
  U6 OFFLINE                no network imports in self_upgrade (grep gate)

Naming: neutral identifiers only (denied-path store, remix lineage,
projection recombination) — the mechanism's name is Chauncey's to birth.

Hermetic: isolated store_dir per test, stdlib only.
"""

import pathlib

import pytest

from levi.hicomb.self_upgrade import (
    APPROVED,
    DENIED,
    SelfUpgradeLoop,
)


@pytest.fixture()
def loop(tmp_path):
    return SelfUpgradeLoop(store_dir=tmp_path / "ide")


def _propose(loop, title="faster pollen", outcome="15% faster formatting"):
    return loop.propose_projection(
        title=title, change={"module": "pollen", "tweak": "cache regexes"},
        projected_outcome=outcome)


# ------------------------------------------------------------ U1: apply gate
def test_apply_refuses_undecided_projection(loop):
    p = _propose(loop)
    res = loop.apply_projection(p.id)
    assert res["ok"] is False and res["error"] == "refusing to apply"
    assert "explicit approve" in res["detail"]


def test_apply_refuses_denied_projection(loop):
    p = _propose(loop)
    loop.decide(p.id, approve=False, reason="too risky")
    res = loop.apply_projection(p.id)
    assert res["ok"] is False


def test_approve_then_apply_works_with_receipt(loop):
    p = _propose(loop)
    # U7: approvals require a passed sandbox test first.
    st = loop.sandbox_test_projection(p.id)
    assert st["ok"] and st["sandbox_ok"] is True
    dec = loop.decide(p.id, approve=True, reason="safe win")
    assert dec["ok"] and dec["status"] == APPROVED
    assert dec["receipt"]["projected_outcome"] == "15% faster formatting"
    res = loop.apply_projection(p.id)
    assert res["ok"] is True
    assert res["receipt"]["decision"] == "applied"
    # double-apply refused
    assert loop.apply_projection(p.id)["ok"] is False


def test_decisions_are_terminal(loop):
    p = _propose(loop)
    st = loop.sandbox_test_projection(p.id)
    assert st["ok"] and st["sandbox_ok"] is True
    assert loop.decide(p.id, approve=True)["ok"]
    second = loop.decide(p.id, approve=False, reason="changed mind")
    assert second["ok"] is False and "terminal" in second["error"]


# ------------------------------------------------------------ U2+U3: denials
def test_denial_persists_with_full_record(loop):
    p = _propose(loop, title="risky rewrite",
                 outcome="projected: 2x speed, 30% regression risk")
    dec = loop.decide(p.id, approve=False, reason="regression risk too high")
    assert dec["status"] == DENIED
    receipt = dec["receipt"]
    assert receipt["ts"] and receipt["decision"] == "denied"
    assert receipt["projected_outcome"] == \
        "projected: 2x speed, 30% regression risk"  # U2: outcome on receipt

    denied = loop.denied_paths.get(p.id)
    assert denied is not None  # U3: retrievable
    assert denied.reason == "regression risk too high"
    assert denied.denied_ts
    assert denied.projected_outcome.startswith("projected: 2x")
    assert denied.remix_descendants == []


def test_nothing_rejected_is_deleted(loop):
    p1 = _propose(loop, title="one")
    p2 = _propose(loop, title="two")
    loop.decide(p1.id, approve=False, reason="no")
    loop.decide(p2.id, approve=False, reason="no")
    denied = {d.id for d in loop.denied_paths.list()}
    assert {p1.id, p2.id} <= denied


# ------------------------------------------------------------ U4: remix lineage
def test_recombine_records_lineage_and_descendants(loop):
    a = _propose(loop, title="path A")
    b = _propose(loop, title="path B")
    loop.decide(a.id, approve=False, reason="A too narrow")
    loop.decide(b.id, approve=False, reason="B too slow")
    res = loop.recombine([a.id, b.id], title="A+B remix",
                         change={"module": "pollen", "tweak": "A+B"},
                         projected_outcome="projected: A speed, B safety")
    assert res["ok"]
    child = res["projection"]
    assert child.source == "denied-remix"
    assert child.remix_lineage == [a.id, b.id]  # U4: lineage on the child
    assert set(loop.denied_paths.get(a.id).remix_descendants) == {child.id}
    assert set(loop.denied_paths.get(b.id).remix_descendants) == {child.id}
    # parents survive recombination
    assert loop.denied_paths.get(a.id).reason == "A too narrow"


def test_remix_of_remix_carries_the_chain(loop):
    a = _propose(loop, title="path A")
    b = _propose(loop, title="path B")
    loop.decide(a.id, approve=False, reason="no A")
    loop.decide(b.id, approve=False, reason="no B")
    c = loop.recombine([a.id, b.id], title="C", change={},
                       projected_outcome="C")["projection"]
    loop.decide(c.id, approve=False, reason="C not yet")
    d = loop.recombine([c.id], title="D", change={},
                       projected_outcome="D")["projection"]
    assert d.remix_lineage == [c.id]
    assert c.id in loop.denied_paths.get(a.id).remix_descendants
    assert d.id in loop.denied_paths.get(c.id).remix_descendants
    # full chain retrievable
    assert loop.denied_paths.get(c.id).remix_lineage == [a.id, b.id]


def test_recombine_unknown_parent_refuses(loop):
    res = loop.recombine(["deadbeef"], title="x", change={},
                         projected_outcome="x")
    assert res["ok"] is False and res["missing"] == ["deadbeef"]


# ------------------------------------------------------------ U5: outcomes
def test_every_projection_surfaces_projected_outcome(loop):
    p = _propose(loop, outcome="projected: calmer diffs")
    assert p.projected_outcome == "projected: calmer diffs"
    assert p.as_dict()["projected_outcome"]


def test_store_round_trips(tmp_path):
    loop1 = SelfUpgradeLoop(store_dir=tmp_path / "ide")
    p = _propose(loop1)
    loop1.decide(p.id, approve=False, reason="held")
    loop2 = SelfUpgradeLoop(store_dir=tmp_path / "ide")
    assert loop2.proposals[p.id].status == DENIED
    assert loop2.denied_paths.get(p.id).reason == "held"


# ------------------------------------------------------------ U6: offline
def test_self_upgrade_has_no_network_imports():
    src = (pathlib.Path(__file__).resolve().parents[1] / "core" / "levi"
           / "hicomb" / "self_upgrade.py")
    text = src.read_text(encoding="utf-8")
    for banned in ("import socket", "import requests", "import urllib",
                   "http.client", "import httpx"):
        assert banned not in text, f"network import: {banned}"
