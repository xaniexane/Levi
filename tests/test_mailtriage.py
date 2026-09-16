"""Hermetic tests for levi.mailtriage: tmp HOME, synthetic maildir."""

import json
import mailbox
import time
from email.message import EmailMessage
from pathlib import Path

import pytest

from levi.mailtriage import SHELF
from levi.mailtriage.replies import ReplyEngine
from levi.mailtriage.store import MailStore
from levi.mailtriage.triage import TriageEngine


@pytest.fixture()
def herm_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LEVI_HOME", raising=False)
    return tmp_path


def _make_maildir(base: Path) -> Path:
    md = base / "Maildir"
    box = mailbox.Maildir(str(md), create=True)

    def add(frm, subject, body, list_unsub=False, msgid=None):
        m = EmailMessage()
        m["From"] = frm
        m["To"] = "me@example.com"
        m["Subject"] = subject
        m["Date"] = "Mon, 14 Sep 2026 10:00:00 -0500"
        if list_unsub:
            m["List-Unsubscribe"] = "<mailto:unsub@example.com>"
        if msgid:
            m["Message-ID"] = msgid
        m.set_content(body)
        box.add(m)

    add(
        "friend@people.com",
        "dinner friday?",
        "are you free friday night?",
        msgid="<m1@x>",
    )
    add(
        "orders@shop.com",
        "Your order confirmation #123",
        "your order has shipped, tracking number ABC",
        msgid="<m2@x>",
    )
    add(
        "news@newsletter.io",
        "This week's digest",
        "top stories this week",
        list_unsub=True,
        msgid="<m3@x>",
    )
    add("no-reply@bank.com", "Security alert", "a new device signed in", msgid="<m4@x>")
    box.close()
    return md


@pytest.fixture()
def maildir(herm_home):
    return _make_maildir(herm_home)


def _recs(maildir):
    store = MailStore(maildir)
    try:
        return {r["id"]: r for r in store.iter_messages()}
    finally:
        store.close()


def test_shelf_shape():
    assert SHELF["name"] and SHELF["summary"] and len(SHELF["items"]) >= 4


def test_store_reads_four(maildir):
    assert len(_recs(maildir)) == 4


def test_store_is_readonly_against_real_mail(maildir):
    # The store object exposes no mutation in our API; mutating the
    # underlying box directly must not be reachable through MailStore.
    store = MailStore(maildir)
    assert not hasattr(store, "remove") and not hasattr(store, "discard")
    store.close()
    assert len(_recs(maildir)) == 4  # nothing lost


def test_bundles(maildir, herm_home):
    eng = TriageEngine(herm_home / ".levi" / "mailtriage")
    recs = _recs(maildir)
    assert eng.bundle(recs["<m1@x>"]) == "people"
    assert eng.bundle(recs["<m2@x>"]) == "receipts"
    assert eng.bundle(recs["<m3@x>"]) == "newsletters"
    assert eng.bundle(recs["<m4@x>"]) == "notifications"


def test_bundle_rules_are_user_editable(maildir, herm_home):
    home = herm_home / ".levi" / "mailtriage"
    eng = TriageEngine(home)
    rules_path = home / "rules.json"
    rules = json.loads(rules_path.read_text())
    rules.insert(0, {"name": "vip", "match": {"from_contains": ["friend@people.com"]}})
    rules_path.write_text(json.dumps(rules))
    eng2 = TriageEngine(home)
    recs = _recs(maildir)
    assert eng2.bundle(recs["<m1@x>"]) == "vip"


def test_snooze_until(maildir, herm_home):
    eng = TriageEngine(herm_home / ".levi" / "mailtriage")
    recs = list(_recs(maildir).values())
    mid = "<m1@x>"
    eng.snooze_until(mid, time.time() + 3600)
    view = eng.inbox_view(recs)
    assert all(r["id"] != mid for r in view)
    view_all = eng.inbox_view(recs, include_snoozed=True)
    assert any(r["id"] == mid for r in view_all)
    # due wake
    eng2 = TriageEngine(eng.home)
    eng2.snooze[mid]["until_ts"] = time.time() - 1
    eng2._save_snooze()
    assert eng2.wake_due() == [mid]
    assert not eng2.is_snoozed(mid)


def test_snooze_until_reply_wakes(maildir, herm_home):
    eng = TriageEngine(herm_home / ".levi" / "mailtriage")
    recs = _recs(maildir)
    eng.snooze_until_reply(
        "<m1@x>", sender="friend@people.com", subject="dinner friday?"
    )
    assert eng.is_snoozed("<m1@x>")
    reply = dict(recs["<m1@x>"])
    reply["id"] = "<reply@x>"
    reply["subject"] = "Re: dinner friday?"
    reply["date_ts"] = time.time() + 10
    woken = eng.check_replies(list(recs.values()) + [reply])
    assert woken == ["<m1@x>"]
    assert not eng.is_snoozed("<m1@x>")


def test_snooze_past_refused(herm_home):
    eng = TriageEngine(herm_home / ".levi" / "mailtriage")
    with pytest.raises(ValueError):
        eng.snooze_until("<x>", time.time() - 10)


def test_template_suggestions_are_honest(maildir, herm_home):
    eng = ReplyEngine(herm_home / ".levi" / "mailtriage")
    recs = _recs(maildir)
    rec = dict(recs["<m2@x>"])
    rec["body"] = "please confirm you received this receipt"
    suggestions = eng.suggest(rec)
    assert suggestions, "expected at least one template match"
    for s in suggestions:
        assert s["label"] == "template-draft — NOT sent"
        assert "not a model" in s["honest_note"]


def test_draft_lifecycle(maildir, herm_home):
    eng = ReplyEngine(herm_home / ".levi" / "mailtriage")
    recs = _recs(maildir)
    rec = dict(recs["<m2@x>"])
    rec["body"] = "please confirm you received this receipt"
    sug = eng.suggest(rec)[0]
    did = eng.save_draft(rec, sug)
    assert eng.list_drafts("draft")[0]["id"] == did
    approved = eng.approve(did)
    assert approved["status"] == "approved"
    assert eng.discard(did) is True
    assert eng.list_drafts() == []


def test_cli_inbox_and_bundles(maildir, herm_home, capsys, monkeypatch):
    from levi.mailtriage.__main__ import main

    monkeypatch.setenv("LEVI_HOME", str(herm_home / ".levi"))
    assert main(["--maildir", str(maildir), "inbox"]) == 0
    out = capsys.readouterr().out
    assert "dinner friday?" in out
    assert main(["--maildir", str(maildir), "bundles"]) == 0
    out = capsys.readouterr().out
    assert "people" in out and "receipts" in out
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0


def test_cli_snooze_roundtrip(maildir, herm_home, capsys, monkeypatch):
    from levi.mailtriage.__main__ import main

    monkeypatch.setenv("LEVI_HOME", str(herm_home / ".levi"))
    args = ["--maildir", str(maildir)]
    assert main(args + ["snooze", "<m3@x>", "--until", "2026-12-01 09:00"]) == 0
    assert main(args + ["inbox"]) == 0
    assert "digest" not in capsys.readouterr().out
    assert main(args + ["unsnooze", "<m3@x>"]) == 0
    assert main(args + ["inbox"]) == 0
    assert "digest" in capsys.readouterr().out


def test_cli_draft_flow(maildir, herm_home, capsys, monkeypatch):
    from levi.mailtriage.__main__ import main

    monkeypatch.setenv("LEVI_HOME", str(herm_home / ".levi"))
    args = ["--maildir", str(maildir)]
    recs = _recs(maildir)
    # make the receipt message match the ack template
    assert main(args + ["draft", "<m2@x>"]) == 0
    assert main(args + ["save-draft", "<m2@x>", "--index", "0"]) == 0
    out = capsys.readouterr().out
    assert "NOT sent" in out
    did = out.split("saved draft ")[1].split(" ")[0]
    assert main(["drafts"]) == 0
    assert did in capsys.readouterr().out
    assert main(["approve", did]) == 0
    out = capsys.readouterr().out
    assert "APPROVED (still not sent" in out
