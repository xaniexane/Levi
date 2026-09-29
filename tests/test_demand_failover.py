"""Tests for levi.demand.failover — SMS/email/WhatsApp failover chain.
Proves the four laws:
  L1 failover order — a channel failure tries the next; first confirmed
     delivery wins and later channels are not attempted.
  L2 no fake receipts — "delivered" only on downstream confirmation;
     "queued" is never "delivered".
  L3 no loss — every dispatch appends a chain record, whatever the outcome.
  L4 credential honesty — unconfigured channels name what's missing and are
     skipped cleanly; secrets never appear in details.
"""

import json
import os
import subprocess

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
    ):
        monkeypatch.delenv(key, raising=False)


def _ok_sender(channel):
    def _send(title, body):
        return ("delivered", f"{channel} confirmed")
    return _send


def _fail_sender(channel):
    def _send(title, body):
        return ("failed", f"{channel} exploded")
    return _send


# ---- L1: failover order -------------------------------------------------


def test_failover_first_channel_wins_later_not_attempted(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    calls = []

    def sms(title, body):
        calls.append("sms")
        return ("delivered", "sms ok")

    def email(title, body):
        calls.append("email")
        return ("delivered", "email ok")

    report = fo.dispatch(
        "a1",
        "k1",
        "T",
        "B",
        senders={"sms": sms, "email": email, "whatsapp": _ok_sender("whatsapp")},
        chain_log=tmp_path / "chains.jsonl",
    )
    assert report.final == "delivered"
    assert report.delivered_via == "sms"
    assert calls == ["sms"]  # email never attempted
    assert len(report.attempts) == 1


def test_failover_failure_tries_next(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    report = fo.dispatch(
        "a1",
        "k1",
        "T",
        "B",
        senders={
            "sms": _fail_sender("sms"),
            "email": _ok_sender("email"),
            "whatsapp": _ok_sender("whatsapp"),
        },
        chain_log=tmp_path / "chains.jsonl",
    )
    assert report.final == "delivered"
    assert report.delivered_via == "email"
    assert [a.channel for a in report.attempts] == ["sms", "email"]
    assert report.attempts[0].status == "failed"


def test_failover_all_fail_held_with_reasons(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    log = tmp_path / "chains.jsonl"
    report = fo.dispatch(
        "a1",
        "k1",
        "T",
        "B",
        senders={
            "sms": _fail_sender("sms"),
            "email": _fail_sender("email"),
            "whatsapp": _fail_sender("whatsapp"),
        },
        chain_log=log,
    )
    assert report.final == "held"
    assert report.delivered_via is None
    assert len(report.attempts) == 5
    by_ch = {a.channel: a.status for a in report.attempts}
    assert by_ch["sms"] == "failed"
    assert by_ch["email"] == "failed"
    assert by_ch["whatsapp"] == "failed"
    # the custom senders table in this test only covers three legs, so the
    # two new legs are unknown channels — recorded as failed attempts,
    # never a crash (L1: unknown channels never kill the dispatch)
    assert by_ch["webhook"] == "failed"
    assert by_ch["sheets"] == "failed"
    wh = next(a for a in report.attempts if a.channel == "webhook")
    assert "unknown channel" in wh.detail
    # L3: chain record persisted even on total failure
    rec = json.loads(log.read_text(encoding="utf-8").strip())
    assert rec["final"] == "held"
    assert [a["channel"] for a in rec["attempts"]] == [
        "sms", "email", "whatsapp", "webhook", "sheets",
    ]


def test_failover_unknown_channel_does_not_crash(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    report = fo.dispatch(
        "a1",
        "k1",
        "T",
        "B",
        order=("sms", "pigeon"),
        senders={"sms": _ok_sender("sms")},
        chain_log=tmp_path / "chains.jsonl",
    )
    assert report.final == "delivered"  # unknown channel never reached


# ---- L2: no fake receipts -------------------------------------------------


def test_queued_is_never_delivered(tmp_path, monkeypatch):
    _clear_env(monkeypatch)

    def wa(title, body):
        return ("queued", "queued_for_whatsapp_relay")

    report = fo.dispatch(
        "a1",
        "k1",
        "T",
        "B",
        order=("whatsapp",),
        senders={"whatsapp": wa},
        chain_log=tmp_path / "chains.jsonl",
    )
    assert report.final == "held"  # queued != delivered
    assert report.delivered_via is None


def test_sender_exception_continues_chain(tmp_path, monkeypatch):
    _clear_env(monkeypatch)

    def boom(title, body):
        raise RuntimeError("kaboom")

    report = fo.dispatch(
        "a1",
        "k1",
        "T",
        "B",
        senders={"sms": boom, "email": _ok_sender("email")},
        chain_log=tmp_path / "chains.jsonl",
    )
    assert report.final == "delivered"
    assert report.delivered_via == "email"
    assert "sender_error" in report.attempts[0].detail


# ---- L4: credential honesty -----------------------------------------------


def test_email_unconfigured_names_missing_vars(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    status, detail = fo.send_email("T", "B")
    assert status == "unconfigured"
    assert "LEVI_SMTP_HOST" in detail
    assert "LEVI_SMTP_USER" in detail
    assert "LEVI_SMTP_PASS" in detail


def test_sms_unconfigured_without_number(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    status, detail = fo.send_sms("T", "B", binary_present=True)
    assert status == "unconfigured"
    assert "LEVI_ALERT_NUMBER" in detail


def test_sms_termux_absent_is_failed_not_delivered(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("LEVI_ALERT_NUMBER", "+15551234567")
    status, detail = fo.send_sms("T", "B", binary_present=False)
    assert status == "failed"
    assert "termux_absent" in detail


def test_sms_real_send_confirmed_by_exit_zero(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("LEVI_ALERT_NUMBER", "+15551234567")
    seen = []

    def fake_run(argv):
        seen.append(argv)

    status, detail = fo.send_sms(
        "T", "B", binary_present=True, runner=fake_run
    )
    assert status == "delivered"
    assert seen[0][:3] == ["termux-sms-send", "-n", "+15551234567"]


def test_sms_send_failure_reported_not_claimed(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("LEVI_ALERT_NUMBER", "+15551234567")

    def fake_run(argv):
        raise subprocess.CalledProcessError(1, argv)

    status, detail = fo.send_sms(
        "T", "B", binary_present=True, runner=fake_run
    )
    assert status == "failed"
    assert "sms_send_failed" in detail


def test_email_sends_via_smtp_and_confirms(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("LEVI_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("LEVI_SMTP_USER", "chauncey@example.com")
    monkeypatch.setenv("LEVI_SMTP_PASS", "s3cret-pw")
    monkeypatch.setenv("LEVI_SMTP_TO", "chauncey@example.com")
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            self.host, self.port = host, port

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            pass

        def login(self, user, pw):
            assert user == "chauncey@example.com"
            assert pw == "s3cret-pw"

        def send_message(self, msg):
            sent.append(msg)

    status, detail = fo.send_email("T", "B", smtp_factory=FakeSMTP)
    assert status == "delivered"
    assert "smtp.example.com" in detail
    assert sent and sent[0]["Subject"] == "[DemandPulse] T"


def test_email_failure_never_leaks_password(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("LEVI_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("LEVI_SMTP_USER", "u")
    monkeypatch.setenv("LEVI_SMTP_PASS", "s3cret-pw")

    class FakeSMTP:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            pass

        def login(self, user, pw):
            raise RuntimeError(f"auth failed for {pw} at {user}")

        def send_message(self, msg):
            pass

    status, detail = fo.send_email("T", "B", smtp_factory=FakeSMTP)
    assert status == "failed"
    assert "s3cret-pw" not in detail  # L4: secrets never in records
    assert "[redacted]" in detail


def test_whatsapp_gated_without_setup(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    status, detail = fo.send_whatsapp("T", "B")
    assert status == "needs_setup"
    assert "side chat" in detail  # exact setup step, not vague "not_configured"


def test_whatsapp_queues_when_relay_ready(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("LEVI_WHATSAPP_READY", "1")
    qpath = tmp_path / "wa_queue.jsonl"
    status, detail = fo.send_whatsapp("T", "B", queue_path=qpath)
    assert status == "queued"
    rec = json.loads(qpath.read_text(encoding="utf-8").strip())
    assert rec["title"] == "T"
    assert rec["status"] == "queued_for_whatsapp_relay"


def test_whatsapp_api_delivers_on_2xx(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("LEVI_WHATSAPP_API_URL", "https://wa.example.com/send")
    monkeypatch.setenv("LEVI_WHATSAPP_API_TOKEN", "tok123")
    status, detail = fo.send_whatsapp(
        "T", "B", http_post=lambda url, payload, token: 200
    )
    assert status == "delivered"


def test_whatsapp_api_failure_reported(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("LEVI_WHATSAPP_API_URL", "https://wa.example.com/send")
    monkeypatch.setenv("LEVI_WHATSAPP_API_TOKEN", "tok123")
    status, detail = fo.send_whatsapp(
        "T", "B", http_post=lambda url, payload, token: 500
    )
    assert status == "failed"
    assert "tok123" not in detail  # L4


# ---- chain log + laws -------------------------------------------------------


def test_chain_log_appends_every_dispatch(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    log = tmp_path / "chains.jsonl"
    for i in range(2):
        fo.dispatch(
            f"a{i}",
            f"k{i}",
            "T",
            "B",
            senders={"sms": _ok_sender("sms")},
            chain_log=log,
        )
    lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2  # L3: append-only, one record per dispatch


def test_check_laws_ok(tmp_path):
    report = fo.check_laws(chain_log=tmp_path / "chains.jsonl")
    assert report["ok"], report["problems"]
    assert len(report["laws"]) == 4


def test_engine_deliver_failover_all_unconfigured_held(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    # neuter rung 2 so no real sheet append happens in tests
    monkeypatch.setattr(fo, "_sheets_cli_append", lambda sid, row: False)
    from levi.demand.alerts import AlertEngine, AlertEvent

    eng = AlertEngine(path=tmp_path / "alerts.json")
    alert = eng.create("reminder", "chain test", message="hi",
                       at="2026-09-24T06:00:00",
                       channels=("sms", "email", "whatsapp"))
    event = AlertEvent(
        alert_id=alert.id,
        alert_name=alert.name,
        kind="reminder",
        title="Reminder",
        lines=["hi"],
        dedup_key="k-test",
    )
    chain = eng.deliver_failover(event, chain_log=tmp_path / "chains.jsonl")
    assert chain["final"] == "held"  # nothing configured on sandbox
    assert [a["channel"] for a in chain["attempts"]] == [
        "sms", "email", "whatsapp", "webhook", "sheets",
    ]
    # unconfigured/gated channels are skipped cleanly, never crash
    assert all(a["status"] == "skipped" for a in chain["attempts"])
