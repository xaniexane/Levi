"""NeighborOS differentiators tests — home-scoped, deterministic, no network."""

from __future__ import annotations

import json

import pytest

from levi.bounty.hunts import Bounty, BountyState
from levi.neighboros import (
    _seal,
    decay_monitor,
    quote_audit,
    receipt_chain,
    showcase_proof,
    stake_quote,
)


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


# --- receipt-chained delivery --------------------------------------------------

def test_chain_emit_verify_ok(home):
    receipt_chain.emit_receipt("off-1", "analyzed", {"scope": "audit"})
    receipt_chain.emit_receipt("off-1", "quoted", {"price": 120})
    receipt_chain.emit_receipt("off-1", "delivered", {"report": "done"})
    v = receipt_chain.verify_chain("off-1")
    assert v["ok"] is True and v["count"] == 3 and v["breaks"] == []


def test_chain_tamper_breaks_link(home):
    receipt_chain.emit_receipt("off-1", "analyzed", {"a": 1})
    receipt_chain.emit_receipt("off-1", "quoted", {"a": 2})
    path = home / "neighboros" / "receipt_chains" / "off-1.jsonl"
    lines = path.read_text().splitlines()
    rec = json.loads(lines[0])
    rec["receipt"]["stage"] = "showcased"  # tamper with a stored receipt
    lines[0] = json.dumps(rec, sort_keys=True)
    path.write_text("\n".join(lines) + "\n")
    v = receipt_chain.verify_chain("off-1")
    assert v["ok"] is False
    assert any(b["kind"] in ("tampered_envelope", "payload_mismatch")
               for b in v["breaks"])


def test_chain_stage_regression_flagged(home):
    receipt_chain.emit_receipt("off-1", "delivered", {"a": 1})
    receipt_chain.emit_receipt("off-1", "quoted", {"a": 2})  # backwards
    v = receipt_chain.verify_chain("off-1")
    assert v["ok"] is False
    assert any(b["kind"] == "stage_regression" for b in v["breaks"])


def test_chain_guards(home):
    with pytest.raises(ValueError):
        receipt_chain.emit_receipt("off-1", "shipped", {})
    with pytest.raises(ValueError):
        receipt_chain.emit_receipt("", "quoted", {})
    assert receipt_chain.verify_chain("ghost") == {
        "offering_id": "ghost", "ok": True, "count": 0, "breaks": []}


# --- adversarial quote audit ----------------------------------------------------

def _good_quote():
    return {
        "quote_id": "q-1", "price_usd": 120.0, "band_low": 100.0, "band_high": 170.0,
        "line_items": [{"label": "audit", "amount": 80.0},
                       {"label": "report", "amount": 40.0}],
        "timeline_days": 5, "scope_notes": "Code audit of one repo, report included.",
    }


def test_quote_audit_pass(home):
    out = quote_audit.audit_quote(_good_quote())
    assert out["verdict"] == "pass"
    assert out["lean"] == "for"
    assert out["confidence"] >= 0.6
    assert out["trace"]


def test_quote_audit_flagged(home):
    bad = {"quote_id": "q-2", "price_usd": 500.0, "band_low": 100.0,
           "band_high": 170.0, "line_items": [], "timeline_days": 0,
           "scope_notes": ""}
    out = quote_audit.audit_quote(bad)
    assert out["verdict"] == "flagged"
    assert "human review" in out["note"]


def test_quote_audit_math_mismatch_flagged(home):
    q = _good_quote()
    q["line_items"] = [{"label": "audit", "amount": 10.0}]  # total != price
    out = quote_audit.audit_quote(q)
    assert out["verdict"] == "flagged"


def test_quote_audit_guards(home):
    with pytest.raises(ValueError):
        quote_audit.audit_quote({"quote_id": "", "price_usd": 10})
    with pytest.raises(ValueError):
        quote_audit.audit_quote({"quote_id": "q", "price_usd": -5})


# --- showcase-as-proof ------------------------------------------------------------

def test_showcase_consent_gate(home):
    d = showcase_proof.draft_showcase("off-1", "Site lift", "Lifted the site.")
    assert d["status"] == "draft"
    with pytest.raises(ValueError):
        showcase_proof.publish(d["draft_id"])  # no consent yet
    showcase_proof.consent(d["draft_id"], client_note="Looks great.")
    out = showcase_proof.publish(d["draft_id"])  # no bounty -> honest pending
    assert out["published"] is False
    assert out["reason"] == showcase_proof.PENDING_PAID
    assert showcase_proof.get_draft(d["draft_id"])["status"] == "consented"


def test_showcase_publish_paid_bounty(home):
    d = showcase_proof.draft_showcase("off-2", "Hardening", "Hardened the box.")
    showcase_proof.consent(d["draft_id"])
    bounty = Bounty(id="b-1", title="Hardening", problem="Harden it.",
                    state=BountyState.PAID.value,
                    payment_receipt={"synthetic": True, "movement": "executed"})
    out = showcase_proof.publish(d["draft_id"], bounty=bounty)
    assert out["published"] is True
    assert showcase_proof.get_draft(d["draft_id"])["status"] == "published"


def test_showcase_publish_unpaid_bounty_refused(home):
    d = showcase_proof.draft_showcase("off-3", "Audit", "Audited.")
    showcase_proof.consent(d["draft_id"])
    bounty = Bounty(id="b-2", title="Audit", problem="Audit it.",
                    state=BountyState.DELIVERED.value)
    out = showcase_proof.publish(d["draft_id"], bounty=bounty)
    assert out["published"] is False
    assert "not paid" in out["reason"]


# --- decay-monitored delivery -------------------------------------------------------

def test_decay_monitor_healthy_no_nudge(home):
    now = 1_700_000_000.0
    decay_monitor.register_delivery("del-1", "off-1", check_interval_days=30, now=now)
    decay_monitor.record_heartbeat("del-1", True, "all green", now=now)
    assert decay_monitor.nudges(now=now + 86400) == []


def test_decay_monitor_unhealthy_nudges(home):
    now = 1_700_000_000.0
    decay_monitor.register_delivery("del-1", "off-1", now=now)
    decay_monitor.record_heartbeat("del-1", False, "cert expired", now=now)
    nudges = decay_monitor.nudges(now=now + 1)
    assert len(nudges) == 1 and nudges[0]["reason"] == "unhealthy"


def test_decay_monitor_overdue_nudges(home):
    now = 1_700_000_000.0
    decay_monitor.register_delivery("del-1", "off-1", check_interval_days=30, now=now)
    nudges = decay_monitor.nudges(now=now + 31 * 86400)
    assert len(nudges) == 1 and nudges[0]["reason"] == "overdue"
    with pytest.raises(KeyError):
        decay_monitor.record_heartbeat("ghost", True)
    with pytest.raises(ValueError):
        decay_monitor.register_delivery("del-1", "off-1")  # duplicate


# --- stake-under-fog quoting ----------------------------------------------------------

def test_stake_quote_settle_hit(home):
    assert stake_quote.provider_balance("uni") == 100
    s = stake_quote.stake_quote("uni", "q-1", 120.0, 50)
    assert s["balance"] == 50 and s["implicit_confidence"] == 0.5
    out = stake_quote.settle_quote("uni", "q-1", 130.0)  # drift 8.3% < 15%
    assert out["hit"] is True and out["payout"] == 100 and out["balance"] == 150


def test_stake_quote_settle_miss(home):
    stake_quote.stake_quote("uni", "q-1", 120.0, 40)
    out = stake_quote.settle_quote("uni", "q-1", 200.0)  # drift 66% > 15%
    assert out["hit"] is False and out["payout"] == 0 and out["balance"] == 60


def test_stake_quote_guards(home):
    stake_quote.stake_quote("uni", "q-1", 120.0, 10)
    with pytest.raises(ValueError):
        stake_quote.stake_quote("uni", "q-1", 120.0, 10)  # open stake
    with pytest.raises(ValueError):
        stake_quote.stake_quote("uni", "q-2", 0, 10)  # non-positive price
    with pytest.raises(KeyError):
        stake_quote.settle_quote("uni", "ghost", 100.0)


def test_stake_quote_calibration(home):
    stake_quote.stake_quote("uni", "q-1", 100.0, 80)
    stake_quote.settle_quote("uni", "q-1", 105.0)   # p=0.8 hit -> 0.04
    stake_quote.stake_quote("uni", "q-2", 100.0, 90)
    stake_quote.settle_quote("uni", "q-2", 200.0)   # p=0.9 miss -> 0.81
    rep = stake_quote.calibration_report("uni")
    assert rep["n"] == 2
    assert rep["brier"] == round((0.04 + 0.81) / 2, 3)
