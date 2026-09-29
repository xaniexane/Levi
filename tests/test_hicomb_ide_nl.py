"""Hicomb IDE NL→IR tests — laws -> guards -> machine-checkable proof.

  N1 ORIGINAL-FORMS  the fragment's command forms parse correctly
  N2 IR-IS-JOB      the IR is the BuildJob dict
  N3 TIER-GATES     E5/E6 apply refuses without approved HITL (fail-closed)
  N4 NO-SILENT-COERCE  empty intent / unknown tier raise, never coerce
  N5 LEARN          misses composted; genome steers the next plan
  N6 OFFLINE        no network imports in ide_nl (grep gate)

Hermetic: isolated store_dir + workspace per test, stdlib only.
"""


import pytest

from levi.hicomb.ide_nl import (
    IdeJournal,
    apply_job,
    intent_source,
    ir_of,
    parse_intent,
    plan_intent,
    record_ir_miss,
    steer_route,
)
from levi.quetta_pan.reim import ReimCompost
from levi.quetta_pan.riem import RiemGenome


@pytest.fixture()
def store(tmp_path):
    return tmp_path / "ide_store"


def compost_count(store) -> int:
    p = store / ".ide_ir_compost.jsonl"
    return ReimCompost(p).count() if p.exists() else 0


# ------------------------------------------------------------ N1: original forms
def test_original_alphaengine_forms(store):
    assert parse_intent("build engine quetta", store) == {
        "kind": "engine", "name": "quetta", "goal": "build engine quetta"}
    assert parse_intent("build module pollen", store)["kind"] == "module"
    assert parse_intent("build service forge", store)["kind"] == "service"
    p = parse_intent("build a tiny landing page", store)
    assert p["kind"] == "project" and p["goal"] == "a tiny landing page"
    p2 = parse_intent("a tiny landing page", store)
    assert p2["kind"] == "project" and p2["goal"] == "a tiny landing page"


# ------------------------------------------------------------ N4: no silent coerce
def test_empty_intent_raises_and_composts(store):
    with pytest.raises(ValueError):
        parse_intent("   ", store)
    assert compost_count(store) == 1  # N5: the miss is composted


def test_unknown_tier_raises_and_composts(store, tmp_path):
    with pytest.raises(ValueError):
        plan_intent("build engine x", tier="X9",
                    workspace=tmp_path, store_dir=store)
    assert compost_count(store) == 1  # N5


def test_record_ir_miss_never_drops(store):
    e = record_ir_miss("???", "test reason", store)
    assert e["rule_id"] == "nl_intent" and "test reason" in e["failed_why"]
    assert compost_count(store) == 1


def test_ir_miss_journals_when_loop_unavailable(store, monkeypatch):
    """N5 best-effort: without the sibling's loop the miss is journaled,
    never dropped — and the N4 contract (ValueError) still holds."""
    import levi.hicomb.ide_nl as ide_nl_mod
    from levi.hicomb.qp_compat import QuettaPanUnavailable

    def _no_loop(_store_dir=None):
        raise QuettaPanUnavailable("levi.hicomb.quetta_loop")

    monkeypatch.setattr(ide_nl_mod, "_ide_qp", _no_loop)
    e = record_ir_miss("???", "test reason", store)
    assert e["action"] == "ir_miss" and e["ok"] is False
    journaled = [r for r in IdeJournal(store).read()
                 if r["action"] == "ir_miss"]
    assert journaled, "miss must be journaled when the loop is absent"
    # The primary contract survives: empty intent still raises ValueError.
    with pytest.raises(ValueError):
        parse_intent("   ", store)


# ------------------------------------------------------------ N2: the IR is the job
def test_plan_returns_job_and_ir_dict(store, tmp_path):
    job = plan_intent("build engine pollen", tier="E4",
                      workspace=tmp_path, store_dir=store)
    assert job.tier == "E4" and job.status == "planned"
    ir = ir_of(job)
    assert ir["id"] == job.id and ir["tier"] == "E4"
    assert "build engine pollen" in ir["goal"]
    assert isinstance(ir["plan_steps"], list) and ir["plan_steps"]
    assert any("IDE steer" in s for s in ir["plan_steps"])
    # the receipt log saw the parse and the plan
    actions = [r["action"] for r in IdeJournal(store).read()]
    assert "parse" in actions and "plan" in actions


def test_intent_source_is_honest_rules(store):
    src = intent_source()
    assert src["source"] == "rules"  # N6: no model claimed


# ------------------------------------------------------------ N3: tier gates fail closed
def test_e5_plan_waits_for_hitl_and_apply_refuses(store, tmp_path):
    job = plan_intent("build service forge", tier="E5",
                      workspace=tmp_path, store_dir=store)
    assert job.status == "awaiting_hitl" and job.requires_hitl
    report = apply_job(job.id, workspace=tmp_path, store_dir=store)
    # fail-closed: the apply is refused either way the gate phrases it
    assert ("HITL not approved" in report or "HITL still pending" in report)
    assert "refusing to apply" in report or "then re-apply" in report
    # N5: the refused apply is composted as an IR miss
    assert compost_count(store) == 1
    assert job.status != "applied"


def test_e4_apply_writes_under_workspace(store, tmp_path):
    ws = tmp_path / "ws"
    job = plan_intent("build module pollen", tier="E4",
                      workspace=ws, store_dir=store)
    report = apply_job(job.id, workspace=ws, store_dir=store)
    assert "Applied job" in report
    assert (ws / "pollen").is_dir()
    # success folded into the genome (N5)
    g = RiemGenome(store / ".ide_ir_genome.json")
    assert g.consult("apply:E4", "plan") == "boost"


# ------------------------------------------------------------ N5: genome steers
def test_genome_suppresses_repeatedly_failed_route(store, tmp_path):
    # two failed applies of the same route -> suppress
    for _ in range(2):
        record_ir_miss("x", "route nl_route:project:E5 refused", store)
        RiemGenome(store / ".ide_ir_genome.json").learn(
            "nl_route:project:E5", "nl", False, "refused twice")
    steer = steer_route("project", "E5", store)
    assert steer["verdict"] == "suppress"
    assert "withheld" in steer["reason"]
    # the plan is still produced (plan-first) but flagged
    job = plan_intent("build a thing", tier="E4",
                      workspace=tmp_path, store_dir=store)
    assert any("IDE steer" in s for s in job.plan_steps)


# ------------------------------------------------------------ N6: offline
def test_ide_nl_has_no_network_imports():
    import pathlib
    src = pathlib.Path(__file__).resolve().parents[1] / \
        "core" / "levi" / "hicomb" / "ide_nl.py"
    text = src.read_text(encoding="utf-8")
    for banned in ("import socket", "import requests", "import urllib",
                   "http.client", "import httpx"):
        assert banned not in text, f"network import in ide_nl: {banned}"
