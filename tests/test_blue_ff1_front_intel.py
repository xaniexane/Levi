"""BLUE verification for FF1: FRONT consumes the canonical intel store.

The feed feeds FRONT: an indicator ingested into ``levi.cybrus.intel``
reaches FRONT's R11 screening (end-to-end: write indicator -> FRONT
flags a matching inbound). The legacy dp_threat_feed file stays a
working fallback, and a corrupt/empty store fails closed — bad intel is
refused, never guessed; it can only ever add nothing.

State is isolated per test via LEVI_HOME -> tmp_path.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from levi.cybrus import front, intel


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _ts(minutes_ago=0.0) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


def _envelope(**over):
    env = {
        "indicator_id": "ff1-blue-001",
        "kind": "threat_sentence",
        "text": "Phishing lure at evil-login.example reported by the watch.",
        "markers": ["evil-login.example", "phishing lure"],
        "source": "levi.demandpulse.threat_feed",
        "published_ts": _ts(),
        "confidence": 0.9,
    }
    env.update(over)
    return env


def _cleanish_email(**over):
    msg = {
        "id": "msg-blue-1",
        "channel": "email",
        "from": "nobody@ordinary.example",
        "reply_to": "",
        "subject": "Tuesday notes",
        "body": "Hi, just checking in about Tuesday.",
        "urls": [],
        "attachments": [],
    }
    msg.update(over)
    return msg


# ---------------------------------------------------------------------------
# Primary: canonical intel store -> FRONT R11


def test_indicator_reaches_front_domain_match(home):
    receipt = intel.ingest(_envelope())
    assert receipt["accepted"] is True
    assert intel.get_indicators(), "store must hold the ingested indicator"

    r = front.screen_message(
        _cleanish_email(**{"from": "scam@evil-login.example"})
    )
    assert "R11" in r["rules"], f"expected R11 hit, got rules={r['rules']}"
    assert r["score"] >= front.WARN_AT
    assert r["verdict"] in ("WARN", "QUARANTINE")
    assert r["intel_digest"] is not None
    assert len(r["intel_digest"]) == 16


def test_indicator_reaches_front_keyword_match(home):
    intel.ingest(
        _envelope(
            indicator_id="ff1-blue-002",
            markers=["fake invoice"],
            text="Scam reports mention a fake invoice pattern.",
        )
    )
    r = front.screen_message(
        _cleanish_email(body="Please review the attached fake invoice details.")
    )
    assert "R11" in r["rules"], f"expected R11 hit, got rules={r['rules']}"
    assert r["score"] >= front.WARN_AT


def test_primary_beats_fallback_when_both_present(home, monkeypatch):
    # Both stores carry DIFFERENT domains: only the canonical store's
    # domain may fire. This pins the primary-first ordering.
    intel.ingest(_envelope())

    from levi.cybrus import dp_threat_feed

    doc = {
        "format": dp_threat_feed._INTEL_FORMAT,
        "round": "legacy-round",
        "source_digest": "a" * 64,
        "signal_count": 1,
        "threat_signal_count": 1,
        "threat_signals": [],
        "domains": ["legacy-scam.example"],
        "keywords": ["legacy bait phrase"],
    }
    dp_threat_feed._write_intel(doc)

    r_primary = front.screen_message(
        _cleanish_email(**{"from": "scam@evil-login.example"})
    )
    assert "R11" in r_primary["rules"]

    r_legacy = front.screen_message(
        _cleanish_email(**{"from": "scam@legacy-scam.example"})
    )
    # The legacy file is NOT consulted while the canonical store has
    # usable intel — no R11, no crash, verdict stays clean.
    assert "R11" not in r_legacy["rules"]
    assert r_legacy["verdict"] == "CLEAN"


# ---------------------------------------------------------------------------
# Fallback: legacy dp_threat_feed file still works


def test_legacy_fallback_still_feeds_r11(home):
    assert intel.get_indicators() == [], "canonical store must start empty"
    from levi.cybrus import dp_threat_feed

    doc = {
        "format": dp_threat_feed._INTEL_FORMAT,
        "round": "legacy-round",
        "source_digest": "b" * 64,
        "signal_count": 1,
        "threat_signal_count": 1,
        "threat_signals": [],
        "domains": ["legacy-scam.example"],
        "keywords": [],
    }
    dp_threat_feed._write_intel(doc)

    r = front.screen_message(
        _cleanish_email(**{"from": "scam@legacy-scam.example"})
    )
    assert "R11" in r["rules"], f"expected legacy R11, got rules={r['rules']}"
    assert r["intel_digest"] == "b" * 16


# ---------------------------------------------------------------------------
# Fail-closed on malformed / empty intel


def test_corrupt_store_fails_closed(home):
    path = intel._store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00\xff not json \xfe\x01 garbage\n[[[broken")

    # Corrupt store -> no intel, no crash, no phantom R11.
    r = front.screen_message(_cleanish_email())
    assert "R11" not in r["rules"]
    assert r["verdict"] == "CLEAN"
    assert r["intel_digest"] is None

    # The gate itself is intact: base rules still screen with no intel.
    hostile = front.screen_message(
        _cleanish_email(
            **{"channel": "text", "from": "PayPal", "subject": "", "body": "hi"}
        )
    )
    assert "R01" in hostile["rules"]
    assert hostile["score"] >= front.WARN_AT


def test_empty_store_means_no_r11(home):
    assert intel.get_indicators() == []
    r = front.screen_message(_cleanish_email())
    assert "R11" not in r["rules"]
    assert r["verdict"] == "CLEAN"
    assert r["score"] == 0
    assert r["intel_digest"] is None


def test_malformed_indicator_entries_are_refused(home):
    # A store line that is valid JSON but not a sane indicator must be
    # refused by the converter, never guessed into a hit.
    path = intel._store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    import json

    bad = {
        "indicator_id": "ff1-bad-001",
        "markers": 12345,  # not a list — malformed
        "published_ts": _ts(),
        "confidence": 0.9,
        "text": "garbage",
        "prev": "0" * 64,
        "hash": "f" * 64,
    }
    path.write_text(json.dumps(bad) + "\n", encoding="utf-8")
    r = front.screen_message(
        _cleanish_email(body="garbage everywhere in this message body")
    )
    assert "R11" not in r["rules"]
    assert r["verdict"] == "CLEAN"


def test_stale_indicators_do_not_feed_front(home):
    # An ingested-but-now-stale indicator is refused by the store's own
    # freshness gate (I2) and must not reach R11.
    receipt = intel.ingest(
        _envelope(
            indicator_id="ff1-blue-stale",
            published_ts=_ts(minutes_ago=0.0),  # fresh at ingest...
            markers=["stale-domain.example"],
            text="Will be force-aged by monkeypatched clock.",
        )
    )
    assert receipt["accepted"] is True
    # Age the store beyond STALE_AFTER_S by patching _utcnow in intel.
    import levi.cybrus.intel as intel_mod

    real_utcnow = intel_mod._utcnow

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        intel_mod, "_utcnow", lambda: real_utcnow() + timedelta(hours=73)
    )
    try:
        assert intel_mod.get_indicators() == []
        r = front.screen_message(
            _cleanish_email(**{"from": "scam@stale-domain.example"})
        )
        assert "R11" not in r["rules"]
        assert r["verdict"] == "CLEAN"
    finally:
        monkeypatch.undo()


def test_malformed_envelope_never_enters_store(home):
    receipt = intel.ingest({"text": "no provenance at all"})
    assert receipt["accepted"] is False
    assert intel.get_indicators() == []
    r = front.screen_message(_cleanish_email())
    assert r["verdict"] == "CLEAN"
