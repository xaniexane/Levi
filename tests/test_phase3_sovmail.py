"""Acceptance suite for phase3.sovmail (C12) — T1..T7.

Own tiny socket-blocking fixture below; nothing imported from the
beginning team's synthesis/offline.py.
"""

from __future__ import annotations

import json
import random
import socket
import subprocess
import sys
from email.message import EmailMessage
from pathlib import Path

import pytest

from levi.phase3.sovmail import (
    Archive,
    Filter,
    analyze_links,
    compose,
    disposition,
    is_suspicious,
    retrain,
    score,
    search_index,
    train,
)
from levi.phase3.sovmail import stationery as stationery_mod
from levi.phase3.sovmail.bridge import baseline_bundle, intake
from levi.phase3.sovmail.stationery import default_stationery
from levi.mailtriage.store import MailStore

import mailbox

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def no_sockets(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("network attempted during offline test")

    monkeypatch.setattr(socket, "socket", blocked)
    yield


def _msg(i: int, frm: str, subject: str, body: str) -> dict:
    return {
        "id": f"<m{i}@test>",
        "from": frm,
        "to": ["me@example.com"],
        "subject": subject,
        "body": body,
        "list_unsub": False,
    }


def _filters() -> list:
    return [
        Filter(
            id="f-boss",
            predicates=({"field": "from", "domain_is": "example.com"},),
            action="file:work",
            priority=10,
        ),
        Filter(
            id="f-receipts",
            predicates=({"field": "subject", "contains_any": ["receipt", "invoice"]},),
            action="file:receipts",
            priority=20,
        ),
        Filter(
            id="f-flag",
            predicates=({"field": "subject", "contains": "urgent"},),
            action="flag",
            priority=5,
        ),
        Filter(
            id="f-drop",
            predicates=({"field": "from", "contains": "spam-blast"},),
            action="drop",
            priority=1,
        ),
    ]


# -- T1: filter determinism --------------------------------------------
def test_t1_same_message_same_filters_same_disposition():
    rng = random.Random(1234)  # seeded: deterministic corpus
    senders = [
        "boss@example.com",
        "shop@store.com",
        "spam-blast@junk.net",
        "friend@home.org",
        "news@digest.io",
    ]
    subjects = [
        "urgent: read now",
        "Your receipt #42",
        "weekly digest",
        "dinner friday",
        "invoice attached",
        "hello",
    ]
    bodies = [
        "see attached",
        "thanks for your order",
        "click here",
        "are you free",
        "payment received",
        "top stories",
    ]
    messages = [
        _msg(i, rng.choice(senders), rng.choice(subjects), rng.choice(bodies))
        for i in range(500)
    ]
    filters = _filters()
    runs = [
        json.dumps([disposition(m, filters) for m in messages], sort_keys=True)
        for _ in range(3)
    ]
    assert runs[0] == runs[1] == runs[2]
    # and every disposition explains itself
    for d in (disposition(m, filters) for m in messages):
        assert d["filter_id"]


# -- T2: autonomy (sockets disabled) ------------------------------------
def _make_maildir(base: Path) -> Path:
    md = base / "Maildir"
    box = mailbox.Maildir(str(md), create=True)

    def add(frm, subject, body, msgid):
        m = EmailMessage()
        m["From"] = frm
        m["To"] = "me@example.com"
        m["Subject"] = subject
        m["Message-ID"] = msgid
        m.set_content(body)
        box.add(m)

    add("boss@example.com", "Q3 planning", "lets meet thursday", "<a1>")
    add("shop@store.com", "Your receipt #9", "payment received", "<a2>")
    box.close()
    return md


def test_t2_full_loop_with_sockets_disabled(no_sockets, tmp_path):
    maildir = _make_maildir(tmp_path)
    store = MailStore(maildir)
    try:
        records = intake(store)
    finally:
        store.close()
    assert len(records) == 2
    archive = Archive(tmp_path / "archive")
    filters = _filters()
    for rec in records:
        disp = disposition(rec, filters)
        archive.append(disp["folder"], rec)
    for folder in ("work", "receipts"):
        index = archive.build_index(folder)
        assert isinstance(index, dict)
    assert search_index(archive.index_for("work"), "planning") == ["<a1>"]
    assert search_index(archive.index_for("receipts"), "receipt") == ["<a2>"]


# -- T3: scam defense ---------------------------------------------------
_PHISH_TEMPLATES = [
    (
        "security@paypaI-secure.com",
        "Urgent: verify your account",
        '<a href="http://xn--paypl-4ve.com/login">https://paypal.com/login</a> '
        "Your account will be suspended. Verify your account now, click here to verify.",
    ),
    (
        "alerts@bank-verify.net",
        "Unusual sign-in detected",
        "We detected an unusual sign-in. Confirm your password: "
        '<a href="http://192.168.200.44/verify">https://bank.com/verify</a>',
    ),
    (
        "support@amaz0n-help.com",
        "Your payment failed",
        "Update your payment method immediately: "
        '<a href="http://amaz0n-help.com/pay">www.amazon.com/pay</a> '
        "or your order is cancelled. Login to confirm.",
    ),
    (
        "no-reply@micros0ft-alert.com",
        "Password expired",
        "Your password expired. Click here to verify: "
        '<a href="http://xn--micrsoft-9ta.com/reset">https://microsoft.com/reset</a>',
    ),
]

_LEGIT = [
    ("friend@home.org", "dinner friday", "are you free friday night? lets cook"),
    (
        "orders@shop.com",
        "Your receipt #123",
        "thanks for your order. your receipt is attached. payment received.",
    ),
    ("news@digest.io", "weekly digest", "top stories this week in tech and science"),
    ("boss@example.com", "Q3 planning", "lets meet thursday to plan the quarter"),
    (
        "team@example.com",
        "notes from today",
        "here are the notes. see https://example.com/notes for details",
    ),
    ("library@city.gov", "book due soon", "your book is due friday, renew online"),
]


def test_t3_scam_defense():
    flagged = 0
    for i, (frm, subj, body) in enumerate(_PHISH_TEMPLATES * 50):
        analysis = analyze_links(_msg(i, frm, subj, body))
        if is_suspicious(analysis):
            flagged += 1
    assert flagged >= 190, f"only {flagged}/200 phishing flagged"

    false_flags = 0
    legit = list((_LEGIT * 34))[:200]  # exactly 200 legitimate messages
    for i, (frm, subj, body) in enumerate(legit):
        analysis = analyze_links(_msg(1000 + i, frm, subj, body))
        if is_suspicious(analysis):
            false_flags += 1
    assert false_flags <= 10, f"{false_flags} false flags on legit mail"


def test_t3_bayes_supports_local_scoring(tmp_path):
    corpus = [("free money click now winner", "spam")] * 40 + [
        ("meeting thursday planning notes", "ham")
    ] * 40
    model = train(corpus)
    assert score(model, "free money click winner") > 0.8
    assert score(model, "meeting thursday planning") < 0.2
    model_path = tmp_path / "model.json"
    corpus_path = tmp_path / "corpus.jsonl"
    corpus_path.write_text(
        "\n".join(json.dumps({"text": t, "label": lab}) for t, lab in corpus),
        encoding="utf-8",
    )
    retrained = retrain(model_path, corpus_path)  # offline housekeeping
    assert model_path.exists()
    assert score(retrained, "free money click winner") > 0.8


# -- T4: archive truth --------------------------------------------------
def test_t4_index_rebuild_identical(tmp_path):
    archive = Archive(tmp_path / "archive")
    for i in range(30):
        archive.append(
            "work",
            _msg(
                i,
                "boss@example.com",
                f"planning update {i}",
                f"quarterly planning notes number {i}",
            ),
        )
    before = search_index(archive.build_index("work"), "planning")
    assert len(before) == 30
    archive.delete_index("work")
    after = search_index(archive.index_for("work"), "planning")
    assert after == before


# -- T5: stationery -----------------------------------------------------
def test_t5_drafts_only_never_sent():
    templates = default_stationery()
    assert stationery_mod.sent_count == 0
    for i in range(20):
        draft = compose(templates[i % len(templates)], _msg(i, "a@b.com", "hi", "yo"))
        assert draft["status"] == "draft"
        assert draft["kind"] == "template-draft — NOT sent"
        assert draft["template_id"]
        assert draft["slot_fillings"]
    assert stationery_mod.sent_count == 0
    assert not hasattr(stationery_mod, "send")


# -- T6: coverage survey -------------------------------------------------
def test_t6_survey_maps_every_mailtriage_capability():
    survey = ROOT / "core" / "levi" / "phase3" / "sovmail" / "SURVEY.md"
    assert survey.exists(), "SURVEY.md missing"
    text = survey.read_text(encoding="utf-8").lower()
    for capability in ("triage", "store", "replies"):
        assert capability in text, f"survey omits {capability}"
    for verdict in ("kept", "extended", "superseded"):
        assert verdict in text, f"survey omits verdict {verdict}"


# -- T7: mailtriage untouched --------------------------------------------
def test_t7_mailtriage_tests_pass_unmodified():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_mailtriage.py",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


# -- baseline bridge sanity ----------------------------------------------
def test_bridge_intake_and_baseline_bundle(tmp_path):
    maildir = _make_maildir(tmp_path)
    store = MailStore(maildir)
    try:
        records = intake(store)
    finally:
        store.close()
    bundles = {baseline_bundle(r, tmp_path / "triage") for r in records}
    assert bundles <= {"people", "receipts", "newsletters", "notifications", "other"}
