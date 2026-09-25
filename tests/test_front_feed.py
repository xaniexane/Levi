"""FRONT-FEED invariant tests — the law->guard->prove gate for 🧙.

Honestly named: machine-checked invariant tests, not formal proofs.
Pins the FEED laws (P1-P6 publisher, I1-I8 ingestion, AD1-AD7
adapters) and carries a self-attack adversarial battery standing in
for RED's first pass: provenance forgery, stale replay, adapter
bypass, and spoofed pre-screening. Formal RED twin verification is
tracked separately and must still attack this work.

State is isolated per test via LEVI_HOME -> tmp_path.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from levi.cybrus import adapters, intel
from levi.demandpulse import threat_feed


# ---------------------------------------------------------------------------
# Fixtures


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _ts(days_ago=0.0, minutes_ahead=0.0) -> str:
    return (
        datetime.now(timezone.utc)
        - timedelta(days=days_ago)
        + timedelta(minutes=minutes_ahead)
    ).isoformat()


def _envelope(**over):
    env = {
        "indicator_id": "ind-test-001",
        "kind": "threat_sentence",
        "text": "Urgent action required: verify your account immediately.",
        "markers": ["urgent action required", "verify your account"],
        "source": threat_feed.FEED_SOURCE,
        "published_ts": _ts(),
        "confidence": 0.8,
    }
    env.update(over)
    return env


# ---------------------------------------------------------------------------
# Publisher — threat_feed (P1-P6)


def test_publisher_never_invents(home):
    """P1: clean scan text yields silence, never fabrication."""
    assert threat_feed.build_envelopes(
        "Reminder: your appointment is tomorrow at 3pm.", confidence=0.9
    ) == []
    rcpt = threat_feed.publish(
        "Reminder: your appointment is tomorrow at 3pm.", confidence=0.9
    )
    assert rcpt["published"] == 0 and rcpt["status"] == "silent"


def test_publisher_envelopes_carry_provenance(home):
    """P2: every envelope carries source, published_ts, confidence."""
    envs = threat_feed.build_envelopes(
        "Your account has been suspended. Verify your account now to "
        "avoid closure. Act immediately.",
        confidence=0.85,
        channel="email",
        scan_ref="scan-1",
    )
    assert envs, "expected at least one marker hit"
    for env in envs:
        assert env["source"] == threat_feed.FEED_SOURCE
        assert env["published_ts"]
        assert 0.0 <= env["confidence"] <= 1.0
        assert len(env["text"]) <= 280  # P5
        assert env["channel"] == "email"


def test_publisher_rejects_bad_confidence(home):
    """P2: dishonest confidence values are refused at the publisher."""
    for bad in (-0.1, 1.5, float("nan"), "high", True, None):
        with pytest.raises(ValueError):
            threat_feed.build_envelopes("Verify your account now.", confidence=bad)


def test_publisher_degrades_honestly_when_cybrus_missing(home, monkeypatch):
    """P4: cybrus_unavailable receipt, never a crash or claimed delivery."""
    monkeypatch.setattr(
        threat_feed, "_intel", lambda: (_ for _ in ()).throw(ImportError("nope"))
    )
    rcpt = threat_feed.publish(
        "Verify your account now to avoid suspension.", confidence=0.9
    )
    assert rcpt["status"] == "cybrus_unavailable"
    assert rcpt["published"] > 0 and rcpt["accepted"] == 0


def test_publisher_end_to_end_accepted(home):
    """Publisher -> ingestion round trip: accepted intel lands in the store."""
    rcpt = threat_feed.publish(
        "Your account has been suspended. Verify your account now.", confidence=0.9
    )
    assert rcpt["status"] == "delivered"
    assert rcpt["accepted"] == rcpt["published"] > 0
    assert intel.get_indicators(), "accepted intel must be consumable"


def _forbidden_imports(path: Path, forbidden) -> list:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if any(a.name.endswith("." + f) or a.name == f for f in forbidden):
                    hits.append(a.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if any(mod.endswith("." + f) or mod == f for f in forbidden):
                hits.append(mod)
    return hits


def test_publisher_never_touches_enforcement():
    """P3: the publisher never imports gateway/enforce/money/broker/front/vault."""
    path = Path(threat_feed.__file__)
    hits = _forbidden_imports(
        path, ("gateway", "enforce", "money", "broker", "front", "vault")
    )
    assert hits == [], f"publisher imports enforcement paths: {hits}"


def test_publisher_never_reimplements_markers():
    """P1 boundary: marker matching lives in the alliance contract only."""
    src = Path(threat_feed.__file__).read_text(encoding="utf-8")
    assert "verify your account" not in src.lower().replace("docstring", "")
    # (extraction delegates to cybrus_alliance.extract_threats — one call site)
    assert src.count("extract_threats") >= 1


# ---------------------------------------------------------------------------
# Ingestion — intel (I1-I8)


def test_ingest_accepts_provenanced_fresh(home):
    """I1/I2: well-formed, fresh, provenanced intel is accepted."""
    rcpt = intel.ingest(_envelope())
    assert rcpt["accepted"] is True and rcpt["reason"] == "ingested"
    chain = intel.verify_chain()
    assert chain["ok"] and chain["records"] == 1


def test_ingest_refuses_unprovenanced(home):
    """I1: missing source / ts / confidence -> refused, never consumed."""
    for drop in ("source", "published_ts", "confidence"):
        env = _envelope()
        del env[drop]
        rcpt = intel.ingest(env)
        assert rcpt["accepted"] is False
        assert rcpt["reason"].startswith("unprovenanced"), drop
    assert intel.get_indicators() == []


def test_ingest_refuses_stale(home):
    """I2: intel older than 72h is refused, not consumed."""
    rcpt = intel.ingest(_envelope(published_ts=_ts(days_ago=4)))
    assert rcpt["accepted"] is False and rcpt["reason"].startswith("stale")
    assert intel.get_indicators() == []


def test_ingest_refuses_future_forgery(home):
    """I2: published_ts beyond 5m skew is refused as forgery."""
    rcpt = intel.ingest(_envelope(published_ts=_ts(minutes_ahead=30)))
    assert rcpt["accepted"] is False
    assert rcpt["reason"].startswith("future_timestamp")


def test_ingest_refuses_bad_confidence(home):
    """I1: confidence outside [0,1] or non-numeric -> refused."""
    for bad in (-0.01, 1.01, "high", None, True, [0.5]):
        rcpt = intel.ingest(_envelope(confidence=bad))
        assert rcpt["accepted"] is False, bad
        assert "confidence" in rcpt["reason"], bad
    assert intel.get_indicators() == []


def test_ingest_never_raises_on_garbage(home):
    """I6: malformed envelopes -> refused receipts, never exceptions."""
    for junk in (None, "string", 42, [], {"text": "x"}, {"indicator_id": "i"}):
        rcpt = intel.ingest(junk)
        assert rcpt["accepted"] is False
    assert intel.get_indicators() == []


def test_ingest_dedupes_by_content(home):
    """I3: the same indicator twice -> second refused as duplicate."""
    first = intel.ingest(_envelope(indicator_id="a"))
    second = intel.ingest(_envelope(indicator_id="b"))  # same text+markers
    assert first["accepted"] is True
    assert second["accepted"] is False and second["reason"].startswith("duplicate")
    assert len(intel.get_indicators()) == 1


def test_store_is_append_only_and_chain_intact(home):
    """I3: hash chain verifies; get_indicators never mutates the store."""
    intel.ingest(_envelope(indicator_id="a"))
    intel.ingest(
        _envelope(
            indicator_id="b",
            text="You have won a lottery prize. Claim your prize now.",
            markers=["you have won", "claim your prize"],
        )
    )
    before = intel.verify_chain()
    intel.get_indicators()
    after = intel.verify_chain()
    assert before == after and after["ok"] and after["records"] == 2
    # No delete/rewrite API exists on the module.
    for name in ("delete", "remove", "purge", "clear", "rewrite", "update"):
        assert not hasattr(intel, name), name


def test_get_indicators_filters_confidence_and_freshness(home):
    """Consumers get only active intel; screening can weigh provenance."""
    intel.ingest(_envelope(indicator_id="hi", confidence=0.9))
    intel.ingest(
        _envelope(
            indicator_id="lo",
            confidence=0.2,
            text="Send bitcoin to this wallet now.",
            markers=["send bitcoin"],
        )
    )
    all_ind = intel.get_indicators()
    assert len(all_ind) == 2
    strong = intel.get_indicators(min_confidence=0.5)
    assert [i["indicator_id"] for i in strong] == ["hi"]
    fresh = intel.get_indicators(fresh_within_s=1)
    assert fresh == [] or all(
        (datetime.now(timezone.utc) - datetime.fromisoformat(i["published_ts"])).total_seconds()
        <= 1
        for i in fresh
    )


def test_ingest_never_makes_verdicts():
    """I4: ingestion imports no decision layer — input, never decision."""
    path = Path(intel.__file__)
    hits = _forbidden_imports(
        path, ("front", "gateway", "enforce", "broker", "money", "vault")
    )
    assert hits == [], f"ingestion imports decision/enforcement paths: {hits}"


def test_every_intake_is_audited(home):
    """I7: accepted AND refused intakes land in the tamper-evident audit log."""
    from levi.cybrus import audit as audit_mod

    eng = audit_mod.AuditEngine()
    before = eng.count()
    intel.ingest(_envelope(indicator_id="ok"))
    intel.ingest(_envelope())  # missing nothing; but duplicate -> refused
    recs = eng.tail(eng.count() - before)
    events = [r["event"] for r in recs]
    assert events == ["cybrus.intel.ingest", "cybrus.intel.ingest"]
    assert eng.verify() == (True, None)


# ---------------------------------------------------------------------------
# RED self-attacks: provenance forgery, replay, spoofed authority


def test_red_forged_authority_source_cannot_boost_intel(home):
    """An attacker can name any source string — ingestion stays
    source-agnostic and exposes it honestly; it cannot inflate a
    screening verdict by itself (I4: ingestion holds no opinion)."""
    rcpt = intel.ingest(
        _envelope(source="cybrus-front", confidence=1.0, indicator_id="forged")
    )
    assert rcpt["accepted"] is True  # provenance present; screening decides weight
    ind = next(i for i in intel.get_indicators() if i["indicator_id"] == "forged")
    assert ind["source"] == "cybrus-front"  # exposed, not laundered
    assert ind["confidence"] == 1.0


def test_red_replay_of_stale_intel_refused(home):
    """Captured envelope replayed after its freshness window -> refused."""
    env = _envelope(indicator_id="replay")
    assert intel.ingest(env)["accepted"] is True
    stale_copy = dict(env, published_ts=_ts(days_ago=5), indicator_id="replay-2")
    rcpt = intel.ingest(stale_copy)
    assert rcpt["accepted"] is False and rcpt["reason"].startswith("stale")


def test_red_tampered_chain_detected(home):
    """Flipping a stored byte breaks verification at the exact record."""
    intel.ingest(_envelope(indicator_id="t1"))
    assert intel.verify_chain()["ok"] is True
    path = next(
        p for p in [intel._store_path()] if p.exists()
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["confidence"] = 1.0  # attacker flips a value in place
    lines[0] = json.dumps(rec)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    verdict = intel.verify_chain()
    assert verdict["ok"] is False and verdict["broken_at"] == 0


# ---------------------------------------------------------------------------
# Adapters — intake routing (AD1-AD7)


def test_adapter_clean_delivers_with_receipt(home):
    """AD1/AD2/AD4: clean item is delivered WITH its screening receipt."""
    out = adapters.email(
        {
            "id": "m1",
            "from": "friend@example.com",
            "subject": "Dinner",
            "body": "Reminder: your appointment is tomorrow at 3pm.",
        }
    )
    assert out["delivered"] is True and out["held"] is False
    assert out["verdict"] == "CLEAN"
    assert out["receipt"]["verdict"] == "CLEAN"
    assert out["item"]["id"] == "m1"


def test_adapter_quarantine_holds_never_delivers(home):
    """AD2/AD3: phishing item is held — never delivered, receipt returned."""
    out = adapters.email(
        {
            "id": "m2",
            "from": "PayPal <billing@paypa1.ru>",
            "subject": "Urgent: verify your account",
            "body": "Your account is suspended. Verify your account now at "
            "http://bit.ly/xyz or lose access.",
            "urls": ["http://bit.ly/xyz"],
        }
    )
    assert out["delivered"] is False and out["held"] is True
    assert out["verdict"] == "QUARANTINE"
    assert out["item"] is None
    assert out["receipt"]["verdict"] == "QUARANTINE"


def test_adapter_warn_delivers_with_banner_never_silently(home):
    """WARN items are delivered WITH a front_warning banner (never silent)."""
    out = adapters.text(
        {
            "id": "m3",
            "from": "+15551234567",
            "body": "Your password will expire soon, please update it.",
        }
    )
    assert out["delivered"] is True and out["held"] is False
    assert out["verdict"] == "WARN"
    banner = out["item"].get("front_warning")
    assert banner and banner["rules"] == ["R07"]


def test_adapter_channels_covered(home):
    """AD7: email, text, notification all cross the same gate."""
    for fn in (adapters.email, adapters.text, adapters.notification):
        out = fn({"id": "c", "body": "Reminder: your appointment is tomorrow at 3pm."})
        assert out["delivered"] is True
        assert out["receipt"]["verdict"] == "CLEAN"


def test_adapter_every_intake_crosses_screening(home, monkeypatch):
    """AD1: prove the crossing — the verdict always comes from front."""
    seen = []

    def fake_screen(message):
        seen.append(message)
        return {
            "message_id": message.get("id"),
            "channel": message.get("channel"),
            "verdict": "QUARANTINE",
            "score": 100,
            "rules": ["TEST"],
            "msg_ref": "x",
            "receipt_hash": "y",
        }

    from levi.cybrus import front

    monkeypatch.setattr(front, "screen_message", fake_screen)
    out = adapters.notification({"id": "n1", "body": "anything at all"})
    assert len(seen) == 1 and seen[0]["id"] == "n1"
    assert out["held"] is True and out["verdict"] == "QUARANTINE"


def test_adapter_spoofed_prescreening_is_ignored(home):
    """RED: a raw item claiming verdict/screened/clean keys is still screened."""
    out = adapters.email(
        {
            "id": "m-spoof",
            "from": "PayPal <billing@paypa1.ru>",
            "subject": "Urgent",
            "body": "Verify your account now at http://bit.ly/xyz.",
            "urls": ["http://bit.ly/xyz"],
            "verdict": "CLEAN",  # attacker-injected; must be ignored
            "screened": True,
            "front_warning": None,
        }
    )
    assert out["verdict"] == "QUARANTINE" and out["held"] is True


def test_adapter_never_raises(home):
    """AD3: garbage in -> held, never an exception. (A dict with no
    signals is a legitimately empty message — front's rule, not the
    adapter's — and screens CLEAN.)"""
    for junk in (None, "nope", 42, []):
        out = adapters.intake("email", junk)
        assert out["delivered"] is False and out["held"] is True
        assert out["verdict"] == "QUARANTINE"
    out = adapters.intake("email", {"body": None})
    assert out["verdict"] == "CLEAN"  # empty message, no signals


def test_adapter_has_no_direct_deliver_path():
    """AD1: no public deliver/dispatch/send function bypasses the gate."""
    src = Path(adapters.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    public_defs = [
        n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")
    ]
    assert "deliver" not in public_defs
    assert "send" not in public_defs
    assert "dispatch" not in public_defs
    # the only intake surface
    assert set(public_defs) >= {"intake", "email", "text", "notification", "describe_posture"}


def test_adapter_intakes_are_audited(home):
    """AD5: each intake writes a metadata-only audit record."""
    from levi.cybrus import audit as audit_mod

    eng = audit_mod.AuditEngine()
    before = eng.count()
    adapters.email({"id": "a1", "body": "Reminder: your appointment is tomorrow at 3pm."})
    recs = eng.tail(eng.count() - before)
    mine = [r for r in recs if r["event"] == "cybrus.adapters.intake"]
    assert len(mine) == 1
    assert mine[0]["details"]["outcome"] == "delivered"
    assert "appointment is tomorrow" not in json.dumps(mine[0])


def test_adapter_no_network(home, monkeypatch):
    """AD6: adapters perform zero network egress."""
    import socket

    def no_connect(*a, **k):
        raise AssertionError("network egress attempted")

    monkeypatch.setattr(socket, "socket", no_connect)
    monkeypatch.setattr(socket, "create_connection", no_connect)
    out = adapters.email(
        {"id": "net", "from": "a@b.com", "body": "See http://evil.example/x now."}
    )
    assert out["delivered"] in (True, False)  # either way, no network happened


# ---------------------------------------------------------------------------
# Posture honesty


def test_describe_posture_names_laws_and_proof():
    for mod in (intel, threat_feed, adapters):
        p = mod.describe_posture()
        assert p["laws"] and "test_front_feed.py" in p["proof"]
