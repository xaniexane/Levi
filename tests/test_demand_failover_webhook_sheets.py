"""Tests for the webhook + sheets legs of levi.demand.failover.

Proves the four laws extend to the two new legs:
  L1 — webhook 2xx delivered / non-2xx continues the chain; sheets sits
       last in the order after whatsapp.
  L2 — 2xx only counts as delivered; anything else is failed/held.
  L3 — chain-log entries record every attempt including the new legs.
  L4 — unconfigured legs name their exact env var and skip cleanly;
       secrets never appear in details (redaction covers both legs).
"""

import json
import os

import pytest

from levi.demand import failover as fo


def _clear_env(monkeypatch):
    for key in (
        "LEVI_ALERT_NUMBER",
        "LEVI_SMTP_HOST",
        "LEVI_SMTP_PORT",
        "LEVI_SMTP_USER",
        "LEVI_SMTP_PASS",
        "LEVI_SMTP_FROM",
        "LEVI_SMTP_TO",
        "LEVI_SMTP_TLS",
        "LEVI_WHATSAPP_API_URL",
        "LEVI_WHATSAPP_API_TOKEN",
        "LEVI_WHATSAPP_READY",
        "LEVI_ALERT_WEBHOOK_URL",
        "LEVI_SHEETS_WEBHOOK_URL",
        "LEVI_SHEETS_SPREADSHEET_ID",
    ):
        monkeypatch.delenv(key, raising=False)


# ---- L1: order ------------------------------------------------------------


def test_order_is_sms_email_whatsapp_webhook_sheets():
    assert fo.DEFAULT_ORDER == ("sms", "email", "whatsapp", "webhook", "sheets")
    for ch in fo.DEFAULT_ORDER:
        assert ch in fo.SENDERS, f"order channel {ch!r} has no sender"
        assert ch in fo.CHANNELS, f"order channel {ch!r} not in CHANNELS"


def test_check_laws_ok_with_new_legs(tmp_path):
    res = fo.check_laws(chain_log=tmp_path / "chains.jsonl")
    assert res["ok"], res["problems"]


# ---- webhook leg ----------------------------------------------------------


def test_webhook_unconfigured_names_exact_var(monkeypatch):
    _clear_env(monkeypatch)
    status, detail = fo.send_webhook("T", "B")
    assert status == "unconfigured"
    assert "LEVI_ALERT_WEBHOOK_URL" in detail


def test_webhook_2xx_is_delivered(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("LEVI_ALERT_WEBHOOK_URL", "http://127.0.0.1:9/hook")
    seen = {}

    def fake_post(url, payload):
        seen["url"] = url
        seen["payload"] = payload
        return 200

    status, detail = fo.send_webhook(
        "Title", "Body", alert_id="al-1", severity="high",
        channel_chain=["sms", "email"], http_post=fake_post,
    )
    assert status == "delivered"
    assert "HTTP 200" in detail
    p = seen["payload"]
    assert p["alert_id"] == "al-1"
    assert p["title"] == "Title"
    assert p["body"] == "Body"
    assert p["severity"] == "high"
    assert p["timestamp"]
    assert p["channel_chain"] == ["sms", "email"]


def test_webhook_non_2xx_fails_and_chain_continues(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("LEVI_ALERT_WEBHOOK_URL", "http://127.0.0.1:9/hook")

    def fake_post(url, payload):
        return 500

    monkeypatch.setitem(fo.SENDERS, "webhook",
                        lambda t, b, **kw: fo.send_webhook(t, b, http_post=fake_post, **kw))
    monkeypatch.setitem(fo.SENDERS, "sheets",
                        lambda t, b, **kw: ("delivered", "sheets ok"))
    # sms/email/whatsapp all unconfigured -> skipped; webhook fails -> sheets wins
    report = fo.dispatch(
        "al-2", "dk-2", "T", "B",
        order=("sms", "email", "whatsapp", "webhook", "sheets"),
        chain_log=tmp_path / "chains.jsonl",
    )
    assert report.final == "delivered"
    assert report.delivered_via == "sheets"
    by_ch = {a.channel: a.status for a in report.attempts}
    assert by_ch["webhook"] == "failed"
    assert by_ch["sheets"] == "delivered"
    # webhook failure detail carries the status code, not a fake success
    wh = next(a for a in report.attempts if a.channel == "webhook")
    assert "500" in wh.detail


def test_webhook_exception_never_kills_chain(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("LEVI_ALERT_WEBHOOK_URL", "http://127.0.0.1:9/hook")

    def boom(url, payload):
        raise ConnectionError("refused")

    status, detail = fo.send_webhook("T", "B", http_post=boom)
    assert status == "failed"
    assert "webhook_error" in detail


# ---- sheets leg -----------------------------------------------------------


def test_sheets_unconfigured_names_both_rungs_and_skips(monkeypatch):
    _clear_env(monkeypatch)
    status, detail = fo.send_sheets(
        "T", "B", cli_append=lambda sid, row: False
    )
    assert status == "unconfigured"
    # names BOTH missing pieces: the webhook URL rung and the CLI rung
    assert "LEVI_SHEETS_WEBHOOK_URL" in detail
    assert "hatch_gws_cli" in detail


def test_sheets_rung2_cli_append_delivers(monkeypatch):
    _clear_env(monkeypatch)
    seen = {}

    def fake_append(spreadsheet_id, row):
        seen["sid"] = spreadsheet_id
        seen["row"] = row
        return True

    status, detail = fo.send_sheets(
        "Title", "Body", alert_id="al-7", severity="high",
        channel_chain=["sms"], cli_append=fake_append,
    )
    assert status == "delivered"
    assert "DemandPulse" in detail
    # default sheet used when the env override is absent
    assert seen["sid"] == fo.DEFAULT_SHEETS_SPREADSHEET_ID
    row = seen["row"]
    assert len(row) == 6
    assert row[1] == "high"      # severity
    assert row[2] == "Title"
    assert row[3] == "Body"
    assert row[4] == "sheets"    # delivered_via
    assert row[5] == "mirrored"
    assert row[0]  # timestamp


def test_sheets_rung2_env_override_picks_sheet(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("LEVI_SHEETS_SPREADSHEET_ID", "override-sheet-id")
    seen = {}

    def fake_append(spreadsheet_id, row):
        seen["sid"] = spreadsheet_id
        return True

    status, _ = fo.send_sheets("T", "B", cli_append=fake_append)
    assert status == "delivered"
    assert seen["sid"] == "override-sheet-id"


def test_sheets_rung2_exception_is_failed_not_delivered(monkeypatch):
    _clear_env(monkeypatch)

    def bad_append(spreadsheet_id, row):
        raise RuntimeError("cli exploded")

    status, detail = fo.send_sheets("T", "B", cli_append=bad_append)
    assert status == "failed"
    assert "sheets_error" in detail


def test_sheets_rung1_webhook_url_takes_precedence(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("LEVI_SHEETS_WEBHOOK_URL", "https://script.google.com/x")
    calls = []

    def fake_post(url, payload):
        calls.append("post")
        return 200

    def fake_append(spreadsheet_id, row):
        calls.append("append")
        return True

    status, _ = fo.send_sheets("T", "B", http_post=fake_post,
                               cli_append=fake_append)
    assert status == "delivered"
    assert calls == ["post"]  # rung 1 wins; rung 2 never attempted


def test_sheets_payload_includes_delivered_via(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("LEVI_SHEETS_WEBHOOK_URL", "https://script.google.com/x")
    seen = {}

    def fake_post(url, payload):
        seen["payload"] = payload
        return 200

    status, detail = fo.send_sheets(
        "Title", "Body", alert_id="al-3", severity="info",
        channel_chain=["sms", "webhook"], http_post=fake_post,
    )
    assert status == "delivered"
    assert "HTTP 200" in detail
    p = seen["payload"]
    assert p["delivered_via"] == "sheets"
    assert p["alert_id"] == "al-3"
    assert p["title"] == "Title"
    assert p["body"] == "Body"
    assert p["severity"] == "info"
    assert p["timestamp"]
    assert p["channel_chain"] == ["sms", "webhook"]


def test_sheets_dispatch_receives_chain_context(tmp_path, monkeypatch):
    """dispatch() feeds webhook/sheets the alert_id, severity, and the
    chain attempted so far."""
    _clear_env(monkeypatch)
    captured = {}

    def fake_webhook(title, body, **kw):
        captured.update(kw)
        return ("failed", "nope")

    def fake_sheets(title, body, **kw):
        captured["sheets_kw"] = kw
        return ("delivered", "sheets ok")

    monkeypatch.setitem(fo.SENDERS, "webhook", fake_webhook)
    monkeypatch.setitem(fo.SENDERS, "sheets", fake_sheets)
    report = fo.dispatch(
        "al-9", "dk-9", "T", "B", order=("webhook", "sheets"),
        severity="high", chain_log=tmp_path / "chains.jsonl",
    )
    assert report.final == "delivered"
    assert captured["alert_id"] == "al-9"
    assert captured["severity"] == "high"
    assert captured["channel_chain"] == []  # webhook ran first
    assert captured["sheets_kw"]["channel_chain"] == ["webhook"]
    assert captured["sheets_kw"]["alert_id"] == "al-9"


# ---- L3: chain log ----------------------------------------------------------


def test_chain_log_records_new_legs(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    # neuter rung 2 so no real sheet append happens in tests
    monkeypatch.setattr(fo, "_sheets_cli_append", lambda sid, row: False)
    log = tmp_path / "chains.jsonl"
    report = fo.dispatch("al-4", "dk-4", "T", "B",
                         order=fo.DEFAULT_ORDER, chain_log=log)
    assert report.final == "held"  # everything unconfigured/gated
    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert [a["channel"] for a in rec["attempts"]] == list(fo.DEFAULT_ORDER)
    # skipped-cleanly statuses recorded, never fake failures
    by_ch = {a["channel"]: a["status"] for a in rec["attempts"]}
    assert by_ch["webhook"] == "skipped"
    assert by_ch["sheets"] == "skipped"
    assert by_ch["sms"] == "skipped"


# ---- L4: redaction ----------------------------------------------------------


def test_secret_redaction_covers_new_legs(monkeypatch):
    _clear_env(monkeypatch)
    secret = "s3cr3t-pass-value-xyz"
    monkeypatch.setenv("LEVI_SMTP_PASS", secret)
    monkeypatch.setenv("LEVI_ALERT_WEBHOOK_URL", "http://127.0.0.1:9/hook")
    monkeypatch.setenv("LEVI_SHEETS_WEBHOOK_URL", "https://script.google.com/x")

    def boom(url, payload):
        raise RuntimeError(f"downstream blew up, token was {secret}!!")

    for sender in (fo.send_webhook, fo.send_sheets):
        status, detail = sender("T", "B", http_post=boom)
        assert status == "failed"
        assert "[redacted]" in detail
        assert secret not in detail


# ---- alerts.py wiring -------------------------------------------------------


def test_alerts_channels_include_new_legs():
    from levi.demand import alerts as am

    assert "webhook" in am.CHANNELS
    assert "sheets" in am.CHANNELS
    assert "webhook" in am.FAILOVER_CHANNELS
    assert "sheets" in am.FAILOVER_CHANNELS


def test_alert_accepts_new_channels(tmp_path):
    from levi.demand import alerts as am

    eng = am.AlertEngine(path=tmp_path / "alerts.json")
    a = eng.create("reminder", "n1", at="2026-09-24T08:00:00",
                   message="hi", channels=("webhook", "sheets"))
    assert a.channels == ("webhook", "sheets")


def test_deliver_maps_unconfigured_to_not_configured(tmp_path, monkeypatch):
    from levi.demand import alerts as am

    _clear_env(monkeypatch)
    # neuter rung 2 so no real sheet append happens in tests
    monkeypatch.setattr(fo, "_sheets_cli_append", lambda sid, row: False)
    eng = am.AlertEngine(path=tmp_path / "alerts.json")
    a = eng.create("reminder", "n2", at="2026-09-24T08:00:00",
                   message="hi", channels=("console", "file"))
    ev = am.AlertEvent(alert_id=a.id, alert_name=a.name, kind="reminder",
                       title="T", lines=["b"], dedup_key="k1")
    status = eng.deliver(ev, channels=("webhook", "sheets"),
                         outbox=tmp_path / "outbox.jsonl")
    assert status["webhook"] == "not_configured"
    assert status["sheets"] == "not_configured"


def test_deliver_failover_severity_reaches_webhook(tmp_path, monkeypatch):
    from levi.demand import alerts as am

    _clear_env(monkeypatch)
    captured = {}

    def fake_webhook(title, body, **kw):
        captured.update(kw)
        return ("delivered", "ok")

    monkeypatch.setitem(fo.SENDERS, "webhook", fake_webhook)
    monkeypatch.setitem(fo.SENDERS, "sms",
                        lambda t, b, **kw: ("failed", "nope"))
    eng = am.AlertEngine(path=tmp_path / "alerts.json")
    ev = am.AlertEvent(alert_id="al-5", alert_name="n", kind="threshold",
                       title="T", lines=["b"], dedup_key="k5")
    chain = eng.deliver_failover(ev, order=("sms", "webhook"),
                                 chain_log=tmp_path / "chains.jsonl")
    assert chain["final"] == "delivered"
    assert chain["delivered_via"] == "webhook"
    assert captured["severity"] == "high"  # threshold -> high
    assert captured["alert_id"] == "al-5"
