"""BLUE-1 batch B: FRONT-FEED (intel intake) regression proofs (RED-1 FF2–FF5).

Each attack below is CLOSED by commit 14044ed3 ("intel intake hardening —
near-dedupe, chain anchor, source quota"). Every test proves the attack
closure AND the legitimate counterpart.

Glyph: 💉 | Agent: cfbc6fb1-6ab7-451d-8c11b83ab41 | 2026-09-23
"""

from datetime import datetime, timedelta, timezone

import pytest

from levi.cybrus import intel


@pytest.fixture(autouse=True)
def _hermetic(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    return tmp_path


def _ts(days_ago=0.0):
    return (datetime.now(timezone.utc)
            - timedelta(days=days_ago)).isoformat()


def _envelope(**over):
    env = {
        "indicator_id": "ind-blue-001",
        "kind": "threat_sentence",
        "text": "evil.example is a phishing domain harvesting credentials.",
        "markers": ["evil.example", "phishing"],
        "source": "demandpulse:threat-feed",
        "published_ts": _ts(),
        "confidence": 1.0,
    }
    env.update(over)
    return env


# ---------------------------------------------------------------------------
# FF2 — near-duplicate intake refused
# ---------------------------------------------------------------------------

def test_blue_ff2_near_duplicate_refused():
    r1 = intel.ingest(_envelope(indicator_id="a1"))
    assert r1["accepted"] is True
    # One-character mutation of the accepted text: still a dupe.
    r2 = intel.ingest(_envelope(
        indicator_id="a2",
        text="evil.example is a phishing domain harvesting credentialz.",
    ))
    assert r2["accepted"] is False
    assert r2["reason"].startswith("duplicate")


def test_blue_ff2_distinct_intel_accepted():
    assert intel.ingest(_envelope(indicator_id="b1"))["accepted"] is True
    r = intel.ingest(_envelope(
        indicator_id="b2",
        text="A new ransomware crew targets hospital backup servers.",
        markers=["ransomware", "hospitals"],
        source="demandpulse:other-feed",
    ))
    assert r["accepted"] is True


# ---------------------------------------------------------------------------
# FF3/FF4 — chain anchor detects truncation and rewrite
# ---------------------------------------------------------------------------

def test_blue_ff3_truncated_chain_fails_verify():
    intel.ingest(_envelope(indicator_id="c1"))
    intel.ingest(_envelope(indicator_id="c2",
                           text="Second distinct indicator about malware.",
                           markers=["malware"]))
    assert intel.verify_chain()["ok"] is True
    path = intel._store_path()
    lines = path.read_text().splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n")
    result = intel.verify_chain()
    assert result["ok"] is False


def test_blue_ff4_rewritten_chain_fails_verify():
    intel.ingest(_envelope(indicator_id="d1"))
    assert intel.verify_chain()["ok"] is True
    path = intel._store_path()
    lines = path.read_text().splitlines()
    # Attacker rewrites the record AND recomputes nothing: the anchor
    # still points at the original tip.
    lines[0] = lines[0].replace("phishing", "benignxx")
    path.write_text("\n".join(lines) + "\n")
    assert intel.verify_chain()["ok"] is False


def test_blue_ff3_legit_append_verifies():
    for i in range(3):
        intel.ingest(_envelope(indicator_id=f"e{i}",
                               text=f"Distinct indicator number {i} "
                                    f"about threat actor {i}.",
                               markers=[f"actor-{i}"]))
    result = intel.verify_chain()
    assert result["ok"] is True
    assert result["records"] == 3


# ---------------------------------------------------------------------------
# FF5 — per-source quota
# ---------------------------------------------------------------------------

def test_blue_ff5_source_quota_enforced():
    # Disjoint marker sets: these are NOT near-dupes of each other, so
    # the only gate that can fire is the per-source quota.
    for i in range(100):
        r = intel.ingest(_envelope(
            indicator_id=f"q{i}",
            text=f"Quota probe {i}: shared sentence shape, unique marker.",
            markers=[f"quota-marker-{i}"],
            source="demandpulse:greedy",
        ))
        assert r["accepted"] is True, f"record {i} refused early: {r['reason']}"
    r = intel.ingest(_envelope(
        indicator_id="q100",
        text="One more quota probe with its own marker.",
        markers=["quota-marker-100"],
        source="demandpulse:greedy",
    ))
    assert r["accepted"] is False
    assert r["reason"].startswith("quota")


def test_blue_ff5_quota_is_per_source():
    for i in range(100):
        intel.ingest(_envelope(
            indicator_id=f"s{i}",
            text=f"Per-source quota probe {i} with unique marker.",
            markers=[f"psq-{i}"],
            source="demandpulse:full",
        ))
    r = intel.ingest(_envelope(
        indicator_id="other-ok",
        text="A different source still has room to contribute.",
        markers=["other-source-ok"],
        source="demandpulse:fresh",
    ))
    assert r["accepted"] is True
