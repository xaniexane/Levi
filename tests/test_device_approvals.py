"""Tests for the two-way SMS approval loop (laws B1-B9). Inbound SMS and
outbound sends are mocked; nothing touches a real phone."""

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

import levi.device.alerter as alerter
import levi.device.approvals as appr
from levi.device.approvals import (
    ExcludedCategoryError,
    NoNumberError,
    TermuxAbsent,
    audit,
    check_laws,
    is_expired,
    is_text_approvable,
    load_pending,
    new_id,
    normalize_category,
    normalize_number,
    parse_verdict,
    process_inbox,
    read_seen,
    request_approval,
    sweep_expired,
)


@pytest.fixture()
def iso(tmp_path, monkeypatch):
    """Isolated LEVI_HOME + device dir, quiet hours off."""
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LEVI_DEVICE_DIR", str(tmp_path / "device"))
    monkeypatch.setenv("LEVI_ALERT_QUIET", "off")
    monkeypatch.setenv("LEVI_ALERT_NUMBER", "555-010-0199")
    monkeypatch.delenv("LEVI_ALERT_TZ", raising=False)
    monkeypatch.delenv("LEVI_APPROVAL_TTL_HOURS", raising=False)
    return tmp_path


class FakeSms:
    def __init__(self):
        self.calls = []

    def __call__(self, number, text):
        self.calls.append((number, text))


def _mk_pending(iso, aid="A7K2Q9", **kw):
    rec = {
        "id": aid, "uid": "t:1", "title": "Restart watcher",
        "source": "ops", "category": "ops", "body": "",
        "created": appr._utcnow(),
        "expires": (datetime.now(timezone.utc)
                    + timedelta(hours=24)).isoformat(timespec="seconds"),
        "status": "pending",
    }
    rec.update(kw)
    pending = load_pending()
    pending[aid] = rec
    appr.save_pending(pending)
    return aid


# --- B2: category exclusion -------------------------------------------------

@pytest.mark.parametrize("cat", ["money", "destructive", "public",
                                 "MONEY", " Public ", "", "   "])
def test_excluded_categories_refused(iso, cat):
    assert not is_text_approvable(cat)
    with pytest.raises(ExcludedCategoryError):
        request_approval(uid="u", title="t", source="s", category=cat)


@pytest.mark.parametrize("cat", ["ops", "info", "reminder", " OPS "])
def test_safe_categories_allowed(iso, cat):
    assert is_text_approvable(cat)
    aid = request_approval(uid="u", title="t", source="s", category=cat)
    assert appr._ID_RE.fullmatch(aid)


def test_check_laws_ok(iso):
    report = check_laws()
    assert report["ok"], report["problems"]


# --- alerter wiring ----------------------------------------------------------

def test_wiring_needs_approval_text(iso, monkeypatch):
    """needs_approval + safe category -> 'Reply YES <id> or NO <id>' text,
    id registered pending."""
    alerter.SOURCES.clear()
    monkeypatch.setattr(
        alerter, "SOURCES", {"test": alerter.AlertSource(
            name="test", path=iso / "x",
            reader=lambda: [{"uid": "t:9", "title": "Restart watcher",
                             "body": "stalled", "needs_approval": True,
                             "category": "ops"}])})
    fake = FakeSms()
    result = alerter.drain(sms_sender=fake, binary_present=True)
    assert result.sent == ["t:9"]
    assert len(fake.calls) == 1
    number, text = fake.calls[0]
    assert number == "555-010-0199"
    m = appr._ID_RE.search(text)
    assert m, f"no approval id in text: {text!r}"
    assert f"YES {m.group(1)}" in text and f"NO {m.group(1)}" in text
    pending = load_pending()
    assert pending[m.group(1)]["status"] == "pending"


def test_wiring_money_is_chat_only(iso, monkeypatch):
    """money category -> 'needs your word in chat', no id, no registry."""
    alerter.SOURCES.clear()
    monkeypatch.setattr(
        alerter, "SOURCES", {"test": alerter.AlertSource(
            name="test", path=iso / "x",
            reader=lambda: [{"uid": "t:8", "title": "Send $50",
                             "body": "", "needs_approval": True,
                             "category": "money"}])})
    fake = FakeSms()
    alerter.drain(sms_sender=fake, binary_present=True)
    assert len(fake.calls) == 1
    assert "needs your word in chat" in fake.calls[0][1]
    assert "YES" not in fake.calls[0][1]
    assert load_pending() == {}


# --- B1: sender lockdown ------------------------------------------------------

def test_spoofed_sender_ignored(iso):
    aid = _mk_pending(iso)
    fake = FakeSms()
    inbox = [{"number": "+1 (999) 000-1234", "body": f"YES {aid}", "date": "1"}]
    stats = process_inbox(sms_sender=fake, list_reader=lambda: inbox)
    assert stats["ignored_spoof"] == 1
    assert stats["approved"] == []
    assert fake.calls == []  # never answered, never acted on
    assert load_pending()[aid]["status"] == "pending"  # untouched
    lines = (appr.audit_path().read_text(encoding="utf-8")).splitlines()
    entry = json.loads(lines[-1])
    assert entry["verdict"] == "ignored" and entry["sender"] == "other"
    assert "555-010-0199" not in appr.audit_path().read_text()


def test_self_variants_accepted(iso):
    """+1 prefix / dashes / spaces all normalize to his number."""
    for raw in ["555-010-0199", "+15550100199", "(555) 010-0199", "555 010 0199"]:
        assert normalize_number(raw) == "5550100199"


# --- verdicts -----------------------------------------------------------------

def test_yes_from_self_approves(iso):
    aid = _mk_pending(iso)
    fake = FakeSms()
    inbox = [{"number": "555-010-0199", "body": f"yes {aid} please",
              "date": "1"}]
    stats = process_inbox(sms_sender=fake, list_reader=lambda: inbox)
    assert stats["approved"] == [aid]
    rec = load_pending()[aid]
    assert rec["status"] == "approved" and "decided" in rec
    assert fake.calls[-1] == ("555-010-0199", f"Approved {aid}.")
    entry = json.loads(appr.audit_path().read_text().splitlines()[-1])
    assert entry["verdict"] == "approved" and entry["sender"] == "self"


def test_no_from_self_denies(iso):
    aid = _mk_pending(iso)
    fake = FakeSms()
    inbox = [{"number": "5550100199", "body": f"NO {aid}", "date": "1"}]
    stats = process_inbox(sms_sender=fake, list_reader=lambda: inbox)
    assert stats["denied"] == [aid]
    assert load_pending()[aid]["status"] == "denied"
    assert fake.calls[-1][1] == f"Denied {aid}."


def test_replay_silently_dropped(iso):
    aid = _mk_pending(iso)
    fake = FakeSms()
    msg = {"number": "555-010-0199", "body": f"YES {aid}", "date": "1"}
    process_inbox(sms_sender=fake, list_reader=lambda: [msg])
    n_calls = len(fake.calls)
    # same text seen again (re-read) -> no new text, no state change
    stats = process_inbox(sms_sender=fake, list_reader=lambda: [msg])
    assert len(fake.calls) == n_calls
    assert stats["approved"] == [] and stats["nothing_pending"] == 0
    assert load_pending()[aid]["status"] == "approved"


def test_unknown_id_gets_nothing_pending(iso):
    fake = FakeSms()
    inbox = [{"number": "555-010-0199", "body": "YES AZZZZZ", "date": "1"}]
    stats = process_inbox(sms_sender=fake, list_reader=lambda: inbox)
    assert stats["nothing_pending"] == 1
    assert fake.calls[-1][1] == "Nothing pending for AZZZZZ."


def test_chatter_ignored_silently(iso):
    fake = FakeSms()
    inbox = [{"number": "555-010-0199", "body": "hey call me later",
              "date": "1"}]
    stats = process_inbox(sms_sender=fake, list_reader=lambda: inbox)
    assert fake.calls == []
    assert stats["texts_sent"] == 0


def test_bare_yes_without_id_ignored(iso):
    assert parse_verdict("YES") == ("yes", None)
    fake = FakeSms()
    inbox = [{"number": "555-010-0199", "body": "yes", "date": "2"}]
    process_inbox(sms_sender=fake, list_reader=lambda: inbox)
    assert fake.calls == []  # no id -> not a command -> leave alone


# --- B4: expiry ------------------------------------------------------------------

def test_expiry_auto_deny(iso):
    aid = _mk_pending(
        iso, expires=(datetime.now(timezone.utc)
                      - timedelta(minutes=1)).isoformat(timespec="seconds"))
    fake = FakeSms()
    stats = process_inbox(sms_sender=fake, list_reader=lambda: [])
    rec = load_pending()[aid]
    assert rec["status"] == "denied" and rec["reason"] == "expired"
    assert any("expired" in t for _, t in fake.calls)
    assert stats["texts_sent"] == 1


def test_expired_cannot_be_approved_after(iso):
    aid = _mk_pending(
        iso, expires=(datetime.now(timezone.utc)
                      - timedelta(minutes=1)).isoformat(timespec="seconds"))
    fake = FakeSms()
    inbox = [{"number": "555-010-0199", "body": f"YES {aid}", "date": "9"}]
    stats = process_inbox(sms_sender=fake, list_reader=lambda: inbox)
    assert stats["approved"] == []
    assert load_pending()[aid]["status"] == "denied"


def test_sweep_standalone(iso):
    aid = _mk_pending(
        iso, expires=(datetime.now(timezone.utc)
                      - timedelta(minutes=5)).isoformat(timespec="seconds"))
    fake = FakeSms()
    stats = sweep_expired("555-010-0199", sms_sender=fake)
    assert stats["expired"] == [aid]
    assert load_pending()[aid]["reason"] == "expired"


# --- B7/B8/B9 ----------------------------------------------------------------------

def test_number_never_in_logs(iso, capsys):
    aid = _mk_pending(iso)
    fake = FakeSms()
    inbox = [{"number": "+1-999-000-1234", "body": f"YES {aid}", "date": "1"},
             {"number": "555-010-0199", "body": f"YES {aid}", "date": "2"}]
    process_inbox(sms_sender=fake, list_reader=lambda: inbox)
    out, err = capsys.readouterr()
    blob = out + err + appr.audit_path().read_text()
    assert "555-010-0199" not in blob
    assert "5550100199" not in blob


def test_no_number_fails_closed(iso, monkeypatch):
    monkeypatch.delenv("LEVI_ALERT_NUMBER")
    with pytest.raises(NoNumberError):
        process_inbox(list_reader=lambda: [])
    assert appr.main(["--inbox"]) == 2


def test_exact_argv_list(iso, monkeypatch):
    import subprocess
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv

        class P:
            stdout = "[]"
        return P()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("shutil.which", lambda b: "/usr/bin/" + b)
    appr.read_inbox(25)
    assert seen["argv"] == ["termux-sms-list", "-l", "25"]


def test_missing_list_binary_raises(iso, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda b: None)
    with pytest.raises(TermuxAbsent):
        appr.read_inbox()


def test_malformed_inbox_json_tolerated(iso, monkeypatch):
    import subprocess

    class P:
        stdout = "not json{"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: P())
    monkeypatch.setattr("shutil.which", lambda b: "/x")
    assert appr.read_inbox() == []


def test_seen_log_grows(iso):
    fake = FakeSms()
    inbox = [{"number": "555-010-0199", "body": "hello", "date": "3"}]
    process_inbox(sms_sender=fake, list_reader=lambda: inbox)
    assert len(read_seen()) == 1
