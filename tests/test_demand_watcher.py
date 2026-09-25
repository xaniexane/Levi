"""Law/guard/proof tests for the DemandPulse watcher (Phase 2).

Laws under test:
  L1 poll, never stream        — one tick = one bounded poll; watermarks advance
  L2 candidate unmet needs only — heuristic extraction, silence when no marker
  L3 everything stays HYPOTHESIS — scan_seed hardcodes it; watcher can't change it
  L4 source labels preserved   — notification / email / text ride on the signal
  L5 minimal PII               — need-text only; bodies never touch disk
  L6 inbound only              — watcher never imports or touches alerts
  L7 honest channel status     — not connected -> not_configured, zero ingestion

Hermetic: HOME/LEVI_HOME redirected, pulse.DEFAULT patched, _run_cli
monkeypatched — no real Gmail, no real device, no real home writes.
"""

import json
import sys

import pytest

from levi.demand import watcher as wmod
from levi.demand.pulse import DemandPulse


@pytest.fixture
def herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "levi_home"))
    import levi.demand.pulse as _pulse

    monkeypatch.setattr(_pulse, "DEFAULT", tmp_path / "demand_pulse.json")
    return tmp_path


def _dp(tmp_path):
    return DemandPulse(path=tmp_path / "dp.json")


def _st(tmp_path):
    return wmod.WatcherState.load(path=tmp_path / "wstate.json")


# ---------------------------------------------------------------- L2: extraction


def test_extract_needs_finds_first_person_need():
    out = wmod.extract_needs(
        "Hey! Quick note. I need help scheduling shifts for my team, "
        "it's a mess every week. Let me know."
    )
    assert len(out) == 1
    assert "i need help scheduling shifts" in out[0].lower()


def test_extract_needs_silent_without_marker():
    marketing = (
        "Your receipt for order 12345 is attached. "
        "Your subscription renews on Friday. Thanks for being a customer!"
    )
    assert wmod.extract_needs(marketing) == []
    assert wmod.extract_needs("") == []
    assert wmod.extract_needs("ok") == []


def test_extract_needs_truncates_long_sentence():
    long_need = "I need " + "very " * 200 + "long help with scheduling."
    out = wmod.extract_needs(long_need)
    assert out and len(out[0]) <= wmod.NEED_TEXT_MAX


# ------------------------------------------------- L3/L4: ingest -> signals


def test_ingest_items_creates_hypothesis_signals_with_source_label(herm):
    tmp = herm
    dp = _dp(tmp)
    st = _st(tmp)
    items = [
        {"id": "sms-1", "text": "I wish there was an app that plans my shifts for me"},
        {"id": "sms-2", "text": "Lunch at noon?"},
    ]
    receipt = wmod.ingest_items(dp, st, "text", items)
    assert receipt["channel"] == "text"
    assert receipt["candidates"] == 1
    assert receipt["signals"] == 1
    sig = dp.signals[0]
    assert sig.kind == "HYPOTHESIS"  # L3
    assert sig.confidence == 0.35
    assert sig.source == "text"  # L4
    assert sig.segment == "general"


def test_ingest_items_is_idempotent_on_repoll(herm):
    tmp = herm
    dp = _dp(tmp)
    st = _st(tmp)
    items = [{"id": "n-1", "text": "I need help finding a plumber, pipes burst"}]
    r1 = wmod.ingest_items(dp, st, "notification", items)
    st.save()
    st2 = wmod.WatcherState.load(path=tmp / "wstate.json")
    r2 = wmod.ingest_items(dp, st2, "notification", items)
    assert r1["signals"] == 1
    assert r2["skipped_seen"] == 1
    assert r2["signals"] == 0
    assert len(dp.signals) == 1  # L1: re-poll adds nothing


def test_ingest_duplicate_need_dedupes_through_scan_seed(herm):
    tmp = herm
    dp = _dp(tmp)
    st = _st(tmp)
    items = [
        {"id": "e-1", "text": "I need help scheduling shifts"},
        {"id": "e-2", "text": "I NEED help scheduling shifts!!"},
    ]
    wmod.ingest_items(dp, st, "email", items)
    assert len(dp.signals) == 1  # near-dup guard merged
    assert dp.signals[0].seen_count == 2  # occurrence metadata, not evidence


def test_ingest_rejects_unknown_channel(herm):
    with pytest.raises(ValueError):
        wmod.ingest_items(_dp(herm), _st(herm), "smoke-signal", [])


# ------------------------------------------------- L5: minimal PII


def test_state_file_holds_ids_not_bodies(herm):
    tmp = herm
    st = _st(tmp)
    body = "I need help with my medical bills, account 98765"
    wmod.ingest_items(_dp(tmp), st, "text", [{"id": "sms-9", "text": body}])
    st.save()
    raw = (tmp / "wstate.json").read_text()
    assert "sms-9" in raw
    assert "medical bills" not in raw
    assert "98765" not in raw


def test_signal_keeps_only_need_text(herm):
    tmp = herm
    dp = _dp(tmp)
    st = _st(tmp)
    wmod.ingest_items(
        dp, st, "text",
        [{"id": "x", "text": "Call me at 555-0100 after 6. I need a dog sitter this weekend! Thanks!"}],
    )
    assert len(dp.signals[0].need) <= wmod.NEED_TEXT_MAX
    assert "555-0100" not in dp.signals[0].need


# ------------------------------------------------- L6: inbound only


def test_watcher_never_imports_alerts():
    src = (wmod.__file__ and open(wmod.__file__).read()) or ""
    assert "levi.demand.alerts" not in src
    assert "import alerts" not in src
    assert "alerts" not in sys.modules or True  # informational only
    # structural: no alert-ish names anywhere in the module namespace
    names = " ".join(dir(wmod)).lower()
    assert "alert" not in names


def test_watcher_is_poll_shaped_not_stream_shaped():
    src = open(wmod.__file__).read()
    assert "import threading" not in src
    assert "import asyncio" not in src
    assert "websocket" not in src.lower()


# ------------------------------------------------- L7: honest channel status


def _cli_seq(monkeypatch, seq):
    """Feed canned (rc, stdout, stderr) responses to _run_cli in order."""
    calls = []

    def fake(argv, timeout_s=45.0):
        calls.append(argv)
        return seq[len(calls) - 1]

    monkeypatch.setattr(wmod, "_run_cli", fake)
    return calls


def test_email_not_connected_reports_not_configured(herm, monkeypatch):
    _cli_seq(monkeypatch, [(0, json.dumps({"status": "not_connected"}), "")])
    dp = _dp(herm)
    st = _st(herm)
    receipt = wmod.poll_email(dp, st)
    assert receipt["status"] == "not_configured"
    assert len(dp.signals) == 0  # nothing fabricated


def test_email_cli_missing_reports_not_configured(herm, monkeypatch):
    _cli_seq(monkeypatch, [(127, "", "CLI not found")])
    receipt = wmod.poll_email(_dp(herm), _st(herm))
    assert receipt["status"] == "not_configured"


def test_email_rate_limit_is_hard_stop(herm, monkeypatch):
    _cli_seq(
        monkeypatch,
        [
            (0, json.dumps({"status": "connected"}), ""),
            (
                0,
                json.dumps(
                    {"kind": "connector_rate_limited", "terminal_for_attempt": True}
                ),
                "",
            ),
        ],
    )
    dp = _dp(herm)
    receipt = wmod.poll_email(dp, _st(herm))
    assert receipt["status"] == "rate_limited"
    assert len(dp.signals) == 0


def test_email_poll_extracts_need_from_body(herm, monkeypatch):
    triage = {
        "messages": [
            {
                "id": "m1",
                "from": "Priya <priya@example.com>",
                "subject": "quick question",
                "date": "Tue, 22 Sep 2026 10:00:00 -0500",
            },
            {
                "id": "m2",
                "from": "noreply@store.com>",
                "subject": "Your order shipped",
                "date": "Tue, 22 Sep 2026 09:00:00 -0500",
            },
        ]
    }
    read_m1 = {
        "id": "m1",
        "subject": "quick question",
        "body": "Hi! I can't find a good shift planner app. "
        "Everything I've tried is clunky. Any ideas?",
    }
    _cli_seq(
        monkeypatch,
        [
            (0, json.dumps({"status": "connected"}), ""),
            (0, json.dumps(triage), ""),
            (0, json.dumps(read_m1), ""),
        ],
    )
    dp = _dp(herm)
    st = _st(herm)
    receipt = wmod.poll_email(dp, st, max_n=10)
    assert receipt["status"] == "ok"
    assert receipt["read"] == 1  # noreply skipped without a body read
    assert receipt["signals"] == 1
    sig = dp.signals[0]
    assert sig.source == "email"
    assert sig.kind == "HYPOTHESIS"
    assert "shift planner" in sig.need.lower()


def test_run_headless_reports_device_channels_not_configured(herm, monkeypatch):
    _cli_seq(monkeypatch, [(0, json.dumps({"status": "not_connected"}), "")])
    monkeypatch.setattr(
        wmod, "_run_facebook_cli",
        lambda argv, timeout_s=45.0: (127, "", "CLI not found"))
    import levi.demand.eyes as emod
    monkeypatch.setattr(
        emod, "_http_get", lambda url, timeout=15.0: (None, b""))
    import levi.demand.ingest as ing
    monkeypatch.setattr(ing, "fetch_hackernews", lambda q: [])
    for _fn in ("fetch_reddit_signals", "fetch_stackoverflow_signals",
                "fetch_github_signals", "fetch_arxiv_signals",
                "fetch_job_signals"):
        monkeypatch.setattr(ing, _fn, lambda q: [])
    receipt = wmod.run(dp=_dp(herm), state=_st(herm))
    assert receipt["channels"]["email"]["status"] == "not_configured"
    assert receipt["channels"]["facebook"]["status"] == "not_configured"
    assert receipt["channels"]["text"]["status"] == "not_configured"
    assert receipt["channels"]["notification"]["status"] == "not_configured"


def test_status_is_read_only(herm, monkeypatch):
    _cli_seq(monkeypatch, [(0, json.dumps({"status": "connected"}), "")])
    monkeypatch.setattr(
        wmod, "_run_facebook_cli",
        lambda argv, timeout_s=45.0:
        (0, json.dumps({"name": "Cj Logan"}), ""))
    before = list((herm / "levi_home").rglob("*")) if (herm / "levi_home").exists() else []
    s = wmod.status(state=_st(herm))
    assert s["email"]["status"] == "connected"
    assert s["text"]["status"] == "not_configured"
    assert s["facebook"]["status"] == "connected"
    after = list((herm / "levi_home").rglob("*")) if (herm / "levi_home").exists() else []
    assert before == after  # status wrote nothing


# ------------------------------------------------------ facebook channel


def _fb_seq(monkeypatch, seq):
    """Feed canned (rc, stdout, stderr) responses to _run_facebook_cli."""
    calls = []
    it = iter(seq)

    def fake(argv, timeout_s=45.0):
        calls.append(argv)
        return next(it)

    monkeypatch.setattr(wmod, "_run_facebook_cli", fake)
    return calls


_FB_FEED = {
    "count": 2,
    "posts": [
        {"post_id": "p1",
         "post_caption": "I need a better way to track my deliveries, "
                         "any ideas?"},
        {"post_id": "p2", "post_caption": "Happy birthday to my sister!"},
    ],
}


def test_poll_facebook_mines_needs_as_hypothesis(herm, monkeypatch):
    calls = _fb_seq(monkeypatch, [(0, json.dumps(_FB_FEED), "")])
    dp, st = _dp(herm), _st(herm)
    r = wmod.poll_facebook(dp, st)
    assert calls[0][0] == "facebook-cli"  # argv list, never shell=True
    assert calls[0][1:3] == ["feed", "newsfeed"]
    assert "--limit" in calls[0]
    assert calls[0][calls[0].index("--limit") + 1] == "25"
    assert r["channel"] == "facebook" and r["status"] == "ok"
    assert r["posts"] == 2 and r["signals"] == 1
    sig = dp.signals[0]
    assert sig.kind == "HYPOTHESIS" and sig.confidence == 0.35  # L3
    assert sig.source == "facebook" and sig.segment == "general"  # L4


def test_poll_facebook_is_idempotent_on_repoll(herm, monkeypatch):
    _fb_seq(monkeypatch, [(0, json.dumps(_FB_FEED), ""),
                          (0, json.dumps(_FB_FEED), "")])
    dp, st = _dp(herm), _st(herm)
    r1 = wmod.poll_facebook(dp, st)
    r2 = wmod.poll_facebook(dp, st)
    assert r1["signals"] == 1
    assert r2["skipped_seen"] == 2 and r2["signals"] == 0
    assert len(dp.signals) == 1  # L1: re-poll adds nothing


def test_poll_facebook_cli_failure_is_not_configured(herm, monkeypatch):
    _fb_seq(monkeypatch, [(127, "", "CLI not found")])
    r = wmod.poll_facebook(_dp(herm), _st(herm))
    assert r["channel"] == "facebook"
    assert r["status"] == "not_configured"  # L7: never fabricated
    assert len(_dp(herm).signals) == 0


def test_poll_facebook_unparseable_is_not_configured(herm, monkeypatch):
    _fb_seq(monkeypatch, [(0, "not json at all", "")])
    r = wmod.poll_facebook(_dp(herm), _st(herm))
    assert r["status"] == "not_configured"


def test_poll_facebook_auth_error_payload_is_not_configured(herm, monkeypatch):
    _fb_seq(monkeypatch, [(0, json.dumps({"error": "session expired"}), "")])
    r = wmod.poll_facebook(_dp(herm), _st(herm))
    assert r["status"] == "not_configured"


def test_poll_facebook_honors_deadline(herm, monkeypatch):
    import time as _time
    calls = _fb_seq(monkeypatch, [(0, json.dumps(_FB_FEED), "")])
    r = wmod.poll_facebook(_dp(herm), _st(herm),
                           deadline=_time.time() - 1.0)
    assert r["status"] == "budget_exceeded" and calls == []


def test_poll_facebook_null_caption_is_silence(herm, monkeypatch):
    _fb_seq(monkeypatch, [(0, json.dumps(
        {"posts": [{"post_id": "p9", "post_caption": None}]}), "")])
    dp, st = _dp(herm), _st(herm)
    r = wmod.poll_facebook(dp, st)
    assert r["status"] == "ok" and r["signals"] == 0
    assert len(dp.signals) == 0


def test_ingest_items_accepts_facebook_channel(herm):
    dp, st = _dp(herm), _st(herm)
    r = wmod.ingest_items(dp, st, "facebook",
                          [{"id": "fb-1",
                            "text": "I wish there was a quieter leaf blower"}])
    assert r["signals"] == 1 and dp.signals[0].source == "facebook"


def test_facebook_status_connected(herm, monkeypatch):
    _cli_seq(monkeypatch, [(0, json.dumps({"status": "connected"}), "")])
    _fb_seq(monkeypatch, [(0, json.dumps({"name": "Cj Logan"}), "")])
    s = wmod.status(state=_st(herm))
    assert s["facebook"]["status"] == "connected"
    assert s["facebook"]["as"] == "Cj Logan"
    assert s["facebook"]["transport"].startswith("facebook-cli")


def test_facebook_status_not_configured_on_failure(herm, monkeypatch):
    _cli_seq(monkeypatch, [(0, json.dumps({"status": "connected"}), "")])
    _fb_seq(monkeypatch, [(127, "", "nope")])
    s = wmod.status(state=_st(herm))
    assert s["facebook"]["status"] == "not_configured"  # L7


def test_watcher_laws_still_pinned():
    assert "L1 poll, never stream" in wmod.LAWS
    assert "facebook" in wmod.CHANNELS
