"""Proof for the DemandPulse -> DDD bridge (law -> guard -> prove).

Pins the four bridge laws as properties, not examples:
  B1 truth never upgrades — signal snapshot identical before/after drafting;
     non-HYPOTHESIS signals are refused, never converted.
  B2 draft-only — every created draft is held, approval None, recipient None,
     and the ledger gate reports it ineligible; the bridge module never
     calls approve_exact_text / mark_sent / set_outreach_gate (source pin).
  B3 direction-fit beside scores — deterministic: same text + same profile
     -> identical scores; combined math is exactly 0.5*o + 0.5*f; only
     "pursue" verdicts draft.
  B4 outcome feedback — sync mirrors explicit states idempotently;
     non-bridge drafts are never touched.

Agent-Glyph: 🎰
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from levi.demand import bridge as bridge_mod
from levi.demand import direction as direction_mod
from levi.demand import outcomes as outcomes_mod
from levi.demand.pulse import DemandSignal

SCRATCH = Path(
    "/home/hatch/workspace/.jarvis/idea-executions/"
    "ef9dbe8a-360d-4bff-9925-fd596e7add95/scratch"
)
sys.path.insert(0, str(SCRATCH))
from ledger import Ledger  # noqa: E402


@pytest.fixture()
def tmp_env(tmp_path, monkeypatch):
    ledger_path = tmp_path / "ledger_store.json"
    outcomes_path = tmp_path / "demand_outcomes.jsonl"
    monkeypatch.setenv("DDD_LEDGER_PATH", str(ledger_path))
    monkeypatch.setenv("LEVI_OUTCOMES_PATH", str(outcomes_path))
    ledger = Ledger(str(ledger_path))
    return ledger, outcomes_path


@pytest.fixture()
def profile():
    return direction_mod.build_seed_profile()


def _sig(**kw):
    base = dict(
        id="sigtest01",
        need="local business needs a better website",
        kind="HYPOTHESIS",
        confidence=0.35,
        number=90.0,
        source="text",
        segment="general",
    )
    base.update(kw)
    return DemandSignal(**base)


# The direction profile's top terms; stuffing a need with them yields fit ~1.
_PURSUIT_TERMS = (
    "offline local-first self-sufficient training brain weights records "
    "provider on-device termux synthetic intelligence demandpulse demand "
    "signal scoring customer product direction compass pulse opportunity "
    "growth harvest reflect consolidate journal memory learn nightly boot "
    "camp legion creature creatures ip nft launch universe coin ascent card "
    "original originals lineage recovery archive preserve provenance grok "
    "chat history dynasty mvp production rollout wave agent agents hardening"
)


def _pursue_sig(**kw):
    kw.setdefault("need", "prospect: " + _PURSUIT_TERMS)
    kw.setdefault("number", 100.0)
    return _sig(**kw)


# ---------------------------------------------------------------- B1

def test_b1_signal_snapshot_identical_after_draft(tmp_env, profile):
    ledger, outcomes_path = tmp_env
    sig = _pursue_sig()
    before = copy.deepcopy(sig.__dict__)
    bridge_mod.draft_for_signal(sig, ledger, profile,
                                outcomes_path=outcomes_path)
    after = copy.deepcopy(sig.__dict__)
    assert before == after, "bridge mutated the signal — B1 violated"
    assert sig.kind == "HYPOTHESIS" and sig.confidence == 0.35


def test_b1_non_hypothesis_refused_never_converted(tmp_env, profile):
    ledger, outcomes_path = tmp_env
    for kind in ("OBSERVED", "INFERENCE"):
        sig = _pursue_sig(id=f"sig-{kind or 'empty'}", kind=kind)
        with pytest.raises(ValueError, match="B1"):
            bridge_mod.draft_for_signal(sig, ledger, profile,
                                        outcomes_path=outcomes_path)
        assert sig.kind == kind  # refused, not converted
    assert ledger.data["drafts"] == []


# ---------------------------------------------------------------- B2

def test_b2_draft_is_held_unapproved_ineligible(tmp_env, profile):
    ledger, outcomes_path = tmp_env
    sig = _pursue_sig()
    res = bridge_mod.draft_for_signal(sig, ledger, profile,
                                      outcomes_path=outcomes_path)
    assert res["drafted"] is True
    d = ledger.get(res["draft_id"])
    assert d["state"] == "held"
    assert d["approval"] is None
    assert d["recipient"] is None
    assert d["flags"]["accuracy_ok"] is False
    ok, reasons = ledger.eligibility(d["id"])
    assert ok is False and reasons, "auto-draft must never be send-eligible"


def test_b2_source_pins_no_approve_send_gate_calls():
    # AST pin: the bridge module's CODE never references the send-path
    # functions (docstring mentions are fine — only call sites count).
    import ast
    tree = ast.parse(Path(bridge_mod.__file__).read_text(encoding="utf-8"))
    forbidden = {"approve_exact_text", "mark_sent", "set_outreach_gate"}
    hits = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in forbidden:
            hits.add(node.id)
        if isinstance(node, ast.Attribute) and node.attr in forbidden:
            hits.add(node.attr)
    assert not hits, f"B2 violated: bridge code references {sorted(hits)}"


def test_b2_every_draft_traceable_to_its_signal(tmp_env, profile):
    ledger, outcomes_path = tmp_env
    sig = _pursue_sig()
    res = bridge_mod.draft_for_signal(sig, ledger, profile,
                                      outcomes_path=outcomes_path)
    d = ledger.get(res["draft_id"])
    assert d["flags"]["bridge_signal_id"] == sig.id
    assert d["flags"]["verdict_math"] == res["scored"]["math"]


def test_b2_duplicate_signal_returns_existing_no_redraft(tmp_env, profile):
    ledger, outcomes_path = tmp_env
    sig = _pursue_sig()
    first = bridge_mod.draft_for_signal(sig, ledger, profile,
                                        outcomes_path=outcomes_path)
    second = bridge_mod.draft_for_signal(sig, ledger, profile,
                                         outcomes_path=outcomes_path)
    assert first["drafted"] is True
    assert second["drafted"] is False
    assert second["reason"] == "already bridged"
    assert second["draft_id"] == first["draft_id"]
    assert len(ledger.data["drafts"]) == 1


# ---------------------------------------------------------------- B3

def test_b3_scoring_deterministic_and_math_exact(tmp_env, profile):
    ledger, _ = tmp_env
    sig = _pursue_sig()
    a = bridge_mod.score_for_bridge(sig, profile)
    b = bridge_mod.score_for_bridge(sig, profile)
    assert a == b, "same text + same profile must score identically"
    opp, fit = a["opportunity"], a["direction_fit"]
    assert a["combined"] == round(0.5 * opp + 0.5 * fit, 4)
    assert a["math"] == f"0.5*{opp:.4f} + 0.5*{fit:.4f} = {a['combined']:.4f}"
    assert a["fit_reasons"], "every fit score carries its reasons"


def test_b3_only_pursue_drafts(tmp_env, profile):
    ledger, outcomes_path = tmp_env
    # pursue: opp=1.0, fit~1.0 -> combined ~1.0
    pursue = _pursue_sig(id="s-pursue")
    # watch: opp=0.8, fit=0.0 -> combined=0.40 (watch band)
    watch = _sig(id="s-watch", need="random unrelated thing zzz",
                 number=80.0)
    # drop: opp=0.2, fit=0.0 -> combined=0.10
    drop = _sig(id="s-drop", need="random unrelated thing zzz",
                number=20.0)
    # unscored: no number -> never drafted
    unscored = _sig(id="s-noscore", need="random unrelated thing zzz")
    unscored.number = None

    class FakeDP:
        def live_signals(self):
            return [pursue, watch, drop, unscored]

    receipt = bridge_mod.scan_and_draft(FakeDP(), ledger, profile,
                                        outcomes_path=outcomes_path)
    assert receipt["drafted"] == 1
    assert receipt["draft_ids"] == [bridge_mod._draft_id_for("s-pursue")]
    assert len(ledger.data["drafts"]) == 1
    reasons = {r["signal_id"]: r["reason"]
               for r in receipt["skipped_ids"]}
    assert "watch" in reasons["s-watch"] and "pursue" in reasons["s-watch"]
    assert "drop" in reasons["s-drop"] and "pursue" in reasons["s-drop"]
    assert "unscored" in reasons["s-noscore"]


def test_b3_no_score_inflation_on_repeat_scans(tmp_env, profile):
    ledger, outcomes_path = tmp_env
    sig = _pursue_sig()
    first = bridge_mod.score_for_bridge(sig, profile)
    # scan again — the bridge holds no state that could inflate scores
    second = bridge_mod.score_for_bridge(sig, profile)
    assert first["combined"] == second["combined"]
    assert first["direction_fit"] == second["direction_fit"]


# ---------------------------------------------------------------- B4

def test_b4_sync_mirrors_explicit_states_idempotently(tmp_env, profile):
    ledger, outcomes_path = tmp_env
    sig = _pursue_sig()
    res = bridge_mod.draft_for_signal(sig, ledger, profile,
                                      outcomes_path=outcomes_path)
    did = res["draft_id"]
    # non-bridge draft present: sync must never touch it
    ledger.add_draft("ddd-x01", "Some Biz", "email", "text $49 audit",
                     state="draft")
    # held -> nothing to mirror
    r1 = bridge_mod.sync_outcomes(ledger, outcomes_path=outcomes_path)
    assert r1["mirrored"] == 0
    # explicit approval -> converted mirrored
    ledger.approve_exact_text(did, "Chauncey")
    r2 = bridge_mod.sync_outcomes(ledger, outcomes_path=outcomes_path)
    assert r2["mirrored"] == 1
    # idempotent: second sync mirrors nothing new
    r3 = bridge_mod.sync_outcomes(ledger, outcomes_path=outcomes_path)
    assert r3["mirrored"] == 0
    rows = [row for row in outcomes_mod.read_rows(outcomes_path)
            if row.get("card_id") == sig.id]
    converted = [row for row in rows if row["event"] == "converted"]
    assert len(converted) == 1
    assert "approved" in converted[0]["note"]


def test_b4_payment_is_explicit_call_only(tmp_env):
    _, outcomes_path = tmp_env
    first = bridge_mod.record_bridge_payment(
        "sig-pay", note="Cash App $DirectDepositDaemon",
        outcomes_path=outcomes_path)
    assert first["recorded"] is True
    second = bridge_mod.record_bridge_payment(
        "sig-pay", outcomes_path=outcomes_path)
    assert second["recorded"] is False  # no duplicate payment rows
    rows = [r for r in outcomes_mod.read_rows(outcomes_path)
            if r.get("card_id") == "sig-pay"]
    assert len([r for r in rows if r["event"] == "converted"]) == 1


def test_b4_sighting_row_recorded_on_draft(tmp_env, profile):
    ledger, outcomes_path = tmp_env
    sig = _pursue_sig()
    bridge_mod.draft_for_signal(sig, ledger, profile,
                                outcomes_path=outcomes_path)
    rows = [r for r in outcomes_mod.read_rows(outcomes_path)
            if r.get("card_id") == sig.id and r["event"] == "sighting"]
    assert len(rows) == 1
    assert "bridge" in rows[0]["markers"]
