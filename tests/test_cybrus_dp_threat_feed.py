"""Cybrus DP-THREAT-FEED invariant tests — the law->guard->prove gate.

Honestly named: machine-checked invariant tests, not formal proofs.
Every feed law (T1-T6) is pinned; the FRONT R11 integration is
exercised end to end. State is isolated per test via LEVI_HOME.
"""

from __future__ import annotations

import json
import stat

import pytest

from levi.cybrus import dp_threat_feed as feed
from levi.cybrus import demand_guard as dg
from levi.cybrus import front
from levi.cybrus.tokens import TokenEngine


# ---------------------------------------------------------------------------
# Fixtures / helpers


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _threat_store():
    return {
        "updated_at": "2026-09-22T21:00:00+00:00",
        "signals": [
            {
                "id": "sig-phish-1",
                "need": "I got a phishing text pretending to be my bank, "
                        "told me to verify at chase-verify.ru/login",
                "kind": "HYPOTHESIS",
                "confidence": 0.8,
                "seen_count": 12,
            },
            {
                "id": "sig-benign-1",
                "need": "I need help scheduling shifts",
                "kind": "HYPOTHESIS",
                "confidence": 0.35,
                "seen_count": 81,
            },
            {
                "id": "sig-scam-2",
                "need": "Fake invoice scam going around, do not click "
                        "links in invoice mail from bill-pay.top",
                "kind": "OBSERVED",
                "confidence": 0.9,
                "seen_count": 5,
            },
        ],
        "opportunities": [],
        "score_cards": [],
    }


def _write_store(home, doc):
    p = home / ".levi" / "demand_pulse.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def _issue(scope):
    _, plaintext = TokenEngine().issue(
        scopes=[scope], ttl_seconds=3600, kind="api", label=f"test:{scope}"
    )
    return plaintext


def _refresh(home, doc=None, scope=dg.SCOPE_READ):
    _write_store(home, _threat_store() if doc is None else doc)
    return feed.refresh_intel(_issue(scope))


# ---------------------------------------------------------------------------
# T-laws declared and complete


def test_laws_declared_and_complete(home):
    ids = [lid for lid, _ in feed.LAWS]
    assert ids == ["T1", "T2", "T3", "T4", "T5", "T6"]


# ---------------------------------------------------------------------------
# Extraction


def test_extract_detects_threat_signal(home):
    threats = feed.extract_threat_signals(_threat_store())
    ids = [t["id"] for t in threats]
    assert ids == ["sig-phish-1", "sig-scam-2"]  # sorted, benign excluded
    phish = threats[0]
    assert "phishing" in phish["matched"]
    assert "chase-verify.ru" in phish["domains"]
    scam = threats[1]
    assert "fake invoice" in scam["matched"]
    assert "do not click" in scam["matched"]
    assert "bill-pay.top" in scam["domains"]


def test_extract_metadata_only(home):
    threats = feed.extract_threat_signals(_threat_store())
    for t in threats:
        assert set(t) <= {"id", "kind", "matched", "domains"}
    blob = json.dumps(threats)
    assert "pretending to be my bank" not in blob  # T2: no signal text
    assert "scheduling shifts" not in blob


def test_extract_deterministic(home):
    a = feed.extract_threat_signals(_threat_store())
    b = feed.extract_threat_signals(_threat_store())
    assert a == b


def test_extract_handles_malformed_store(home):
    assert feed.extract_threat_signals({}) == []
    assert feed.extract_threat_signals({"signals": "nope"}) == []
    assert feed.extract_threat_signals({"signals": [None, {"id": "x"}]}) == []


# ---------------------------------------------------------------------------
# Guard-crossed refresh (T1)


def test_refresh_requires_grant_receipt(home):
    _write_store(home, _threat_store())
    with pytest.raises(dg.DemandGuardError):
        feed.refresh_intel(None)
    with pytest.raises(dg.DemandGuardError):
        feed.refresh_intel("forged-token-not-issued-by-cybrus")


def test_refresh_requires_read_scope(home):
    _write_store(home, _threat_store())
    with pytest.raises(dg.DemandGuardError):
        feed.refresh_intel(_issue(dg.SCOPE_WRITE))  # write != read


def test_refresh_writes_intel_file_0600(home):
    summary = _refresh(home)
    p = home / ".levi" / "cybrus" / "front_intel.json"
    assert p.exists()
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert doc["format"] == "cybrus.front_intel/1"
    assert doc["domains"] == sorted(doc["domains"])
    assert doc["keywords"] == sorted(doc["keywords"])
    assert "chase-verify.ru" in doc["domains"]
    assert "phishing" in doc["keywords"]
    assert summary["threat_signals"] == 2
    assert summary["signals_scanned"] == 3


def test_refresh_is_idempotent_byte_identical(home):
    _refresh(home)
    p = home / ".levi" / "cybrus" / "front_intel.json"
    first = p.read_bytes()
    _refresh(home)
    assert p.read_bytes() == first  # T3


def test_refresh_summary_metadata_only(home):
    summary = _refresh(home)
    blob = json.dumps(summary)
    assert "pretending to be my bank" not in blob
    assert "scheduling shifts" not in blob


def test_refresh_empty_threats_writes_empty_intel(home):
    doc = {"updated_at": "2026-09-22T21:00:00+00:00", "signals": [
        {"id": "b1", "need": "I need help scheduling shifts", "kind": "HYPOTHESIS"}]}
    summary = _refresh(home, doc=doc)
    assert summary["threat_signals"] == 0
    assert summary["domains"] == [] and summary["keywords"] == []


# ---------------------------------------------------------------------------
# FRONT R11 integration


def _msg(**kw):
    base = {
        "id": "m1",
        "channel": "email",
        "from": "friend@example.com",
        "reply_to": "",
        "subject": "Dinner Saturday?",
        "body": "Hey, are we still on for dinner Saturday? Let me know!",
        "urls": [],
        "attachments": [],
    }
    base.update(kw)
    return base


def test_R11_domain_hit_warns(home):
    _refresh(home)  # intel now knows chase-verify.ru
    r = front.screen_message(_msg(**{
        "from": "support@chase-verify.ru",
        "subject": "Hello",
        "body": "Just saying hello, nothing urgent.",
    }))
    assert "R11" in r["rules"]
    assert r["verdict"] == "WARN"  # R11 alone = 30: flagged, never silent
    assert r["intel_digest"]  # receipt names the intel consulted


def test_R11_keyword_hit(home):
    _refresh(home)  # intel keywords include "phishing"
    r = front.screen_message(_msg(body="Have you seen this phishing report?"))
    assert "R11" in r["rules"]


def test_R11_adds_score_only(home):
    _refresh(home)
    clean = front.screen_message(_msg())
    assert clean["score"] == 0 and clean["verdict"] == "CLEAN"
    assert "R11" not in clean["rules"]
    # a stacked attack stays QUARANTINE with intel present — intel never
    # downgrades or forces CLEAN (T4)
    attack = front.screen_message(_msg(**{
        "from": "IRS Agent <agent@micros0ft.com>",
        "reply_to": "agent@other-domain.net",
        "subject": "FINAL NOTICE: arrest warrant",
        "body": "Legal action imminent. Confirm your identity now: "
                "http://bit.ly/irs-form. Reply with your SSN.",
    }))
    assert attack["verdict"] == "QUARANTINE"


def test_R11_absent_without_intel(home):
    r = front.screen_message(_msg(**{
        "from": "support@chase-verify.ru",
        "subject": "Hello",
        "body": "Just saying hello.",
    }))
    assert "R11" not in r["rules"]
    assert r["intel_digest"] is None
    assert r["verdict"] == "CLEAN"  # no behavior change without intel


def test_R11_corrupt_intel_degrades_gracefully(home):
    p = home / ".levi" / "cybrus"
    p.mkdir(parents=True, exist_ok=True)
    (p / "front_intel.json").write_text("{not json", encoding="utf-8")
    r = front.screen_message(_msg(body="phishing report here"))
    assert "R11" not in r["rules"]  # corrupt intel -> no intel, screen works
    assert r["verdict"] in ("CLEAN", "WARN", "QUARANTINE")


def test_intel_digest_covered_by_receipt_hash(home):
    _refresh(home)
    r = front.screen_message(_msg(**{
        "from": "support@chase-verify.ru", "body": "hello",
    }))
    assert r["receipt_hash"] == front._receipt_hash(r)
    assert r["intel_digest"] == feed.load_intel()["source_digest"][:16]


def test_load_intel_never_raises(home):
    assert feed.load_intel() == {}
    assert feed.load_intel(home / "nope.json") == {}


def test_describe_posture(home):
    _refresh(home)
    d = feed.describe_posture()
    assert d["laws"] == ["T1", "T2", "T3", "T4", "T5", "T6"]
    assert d["egress"].startswith("none")
    assert d["intel"]["present"] is True
    assert d["intel"]["threat_signals"] == 2
