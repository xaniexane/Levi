"""Cybrus FRONT-GUARD invariant tests — the law->guard->prove gate.

Honestly named: these are machine-checked invariant tests, not formal
proofs. Every FRONT law (F1-F9) is pinned here; every threat rule
(R01-R10, R99) is exercised, including a self-attack adversarial
battery standing in for the RED swarm's first pass (formal RED twin
verification is tracked separately and must still attack this work).

State is isolated per test via LEVI_HOME -> tmp_path.
"""

from __future__ import annotations

import json
import os

import pytest

from levi.cybrus import front
from levi.cybrus.identity import IdentityStore, TierError


# ---------------------------------------------------------------------------
# Fixtures


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def msg(**kw):
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


def quarantine_records(home):
    p = home / ".levi" / "cybrus" / "front_quarantine.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


# ---------------------------------------------------------------------------
# F8: laws are declared and pinned


def test_laws_declared_and_complete(home):
    ids = [lid for lid, _ in front.LAWS]
    assert ids == ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9"]
    assert len({lid for lid, _ in front.LAWS}) == 9
    # rule catalog pins every id tests reference
    assert front._RULE_IDS == {r[0] for r in front.RULES}
    assert set(front.RULES[x][0] for x in range(len(front.RULES))) >= {
        "R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08", "R09", "R10", "R99"
    }


# ---------------------------------------------------------------------------
# F1/F3: every message screened; receipt always issued


def test_clean_benign_message_passes_with_receipt(home):
    r = front.screen_message(msg())
    assert r["verdict"] == "CLEAN"
    assert r["score"] == 0
    assert r["rules"] == []
    assert r["receipt_hash"]  # signed receipt present
    # receipt hash recomputes from receipt fields (tamper-evident)
    assert r["receipt_hash"] == front._receipt_hash(r)


def test_no_receipt_no_delivery_every_input_gets_receipt(home):
    items = [
        {"id": "a", "text": "I need a plumber"},
        {"id": "b", "text": "URGENT: verify your account now http://bit.ly/x"},
        {"id": "c", "text": ""},
        {"id": "d"},  # malformed-ish: no text at all
    ]
    out = front.screen_items("text", items)
    assert len(out["receipts"]) == len(items)
    for rec in out["receipts"]:
        assert rec["verdict"] in ("CLEAN", "WARN", "QUARANTINE")
        assert rec["receipt_hash"]


# ---------------------------------------------------------------------------
# F2: suspicious = flagged + quarantined + audit-logged, never silent


def _phish(**kw):
    return msg(
        id="ph1",
        **{"from": "PayPal <billing@paypa1-secure.ru>",
           "subject": "URGENT: Your account will be suspended",
           "body": ("Dear customer, unusual activity detected. Verify your "
                    "account immediately or it will be locked within 24 hours. "
                    "Sign in here: http://bit.ly/verify-now"),
           **kw},
    )


def test_classic_phishing_quarantined(home):
    r = front.screen_message(_phish())
    assert r["verdict"] == "QUARANTINE"
    assert r["score"] >= front.QUARANTINE_AT
    # display-name spoof + urgency + cred harvest + shortener all fire
    assert {"R01", "R04", "R03", "R05"} <= set(r["rules"])
    recs = quarantine_records(home)
    assert len(recs) == 1
    assert recs[0]["msg_ref"] == r["msg_ref"]


def test_quarantined_message_never_passes_to_ingest(home):
    out = front.screen_items("email", [
        {"id": "good", "text": "I need a plumber, any recommendations?"},
        {"id": "bad", "text": "URGENT verify your account now sign in http://bit.ly/x reply with your code"},
    ])
    assert len(out["quarantined"]) == 1
    assert out["quarantined"][0]["message_id"] == "bad"
    clean_ids = [i["id"] for i in out["clean"]]
    assert "bad" not in clean_ids and "good" in clean_ids


def test_quarantine_record_is_metadata_only(home):
    secret_body = "my password is hunter2-hunter2, ssn 000-00-0000"
    r = front.screen_message(msg(
        id="q1",
        **{"from": "IRS <agent@irs-notices.ru>",
           "subject": "Final notice",
           "body": f"Legal action imminent. {secret_body}"},
    ))
    assert r["verdict"] == "QUARANTINE"
    recs = quarantine_records(home)
    assert recs
    blob = json.dumps(recs)
    assert "hunter2" not in blob and "000-00-0000" not in blob
    assert secret_body not in blob


def test_audit_log_carries_no_payload(home):
    body = "my one-time code is 992211, do not share"
    front.screen_message(msg(id="a1", body=body,
                             subject="URGENT verify your account now http://bit.ly/x"))
    audit_p = home / ".levi" / "cybrus" / "audit.jsonl"
    lines = [l for l in audit_p.read_text().splitlines() if "front.screen" in l]
    assert lines, "every screened message must be audit-logged"
    blob = "\n".join(lines)
    assert body not in blob and "992211" not in blob
    rec = json.loads(lines[-1])
    assert set(rec["details"]) <= {
        "msg_ref", "message_id", "channel", "verdict", "score", "rules", "receipt_hash"
    }


def test_warn_verdict_delivered_with_banner_never_silent(home):
    # urgency + shortener link = 15 + 20 = 35 -> WARN
    out = front.screen_items("text", [
        {"id": "w1", "text": "URGENT: limited time offer, click http://bit.ly/deal now"},
    ])
    assert len(out["warned"]) == 1
    flagged = out["clean"][0]
    assert "front_warning" in flagged
    assert flagged["front_warning"]["verdict"] == "WARN"


def test_urgency_alone_stays_clean(home):
    r = front.screen_message(msg(body="This is urgent, call me back asap"))
    assert r["verdict"] == "CLEAN"
    assert r["rules"] == ["R04"]


# ---------------------------------------------------------------------------
# Threat rules, one per code


def test_R02_lookalike_domain_quarantined(home):
    r = front.screen_message(msg(**{"from": "support@micros0ft-support.com",
                                    "subject": "Verify your account",
                                    "body": "Sign in to confirm: https://micros0ft-support.com/login"}))
    assert "R02" in r["rules"]


def test_R02_homoglyph_cyrillic_caught(home):
    # pаypal with cyrillic 'а' — visually identical, normalized to paypal
    r = front.screen_message(msg(**{"from": "service@pаypal.com",
                                    "subject": "Receipt",
                                    "body": "Your receipt is attached."}))
    assert "R02" in r["rules"]


def test_R02_punycode_sender(home):
    r = front.screen_message(msg(**{"from": "noreply@xn--pypal-4ve.com",
                                    "subject": "Account notice",
                                    "body": "Please review."}))
    assert "R02" in r["rules"]
    assert r["verdict"] == "WARN"  # R02 alone = 35: flagged, never silent


def test_legitimate_brand_domain_not_flagged(home):
    r = front.screen_message(msg(**{"from": "noreply@paypal.com",
                                    "subject": "Your receipt",
                                    "body": "Thanks for your purchase."}))
    assert r["verdict"] == "CLEAN"
    assert "R02" not in r["rules"] and "R01" not in r["rules"]


def test_R05_ip_host_link(home):
    r = front.screen_message(msg(body="Check this out http://192.168.1.1/login page"))
    assert "R05" in r["rules"]


def test_R05_display_href_mismatch(home):
    r = front.screen_message(msg(body="See [paypal.com/secure](http://evil.ru/login) for details"))
    assert "R05" in r["rules"]


def test_R06_risky_attachment(home):
    r = front.screen_message(msg(attachments=["invoice.pdf.exe"]))
    assert "R06" in r["rules"]
    r2 = front.screen_message(msg(attachments=["report.pdf"]))
    assert r2["verdict"] == "CLEAN"


def test_R07_secret_request_quarantined(home):
    r = front.screen_message(msg(body="Reply with your verification code to confirm"))
    assert "R07" in r["rules"]


def test_R08_authority_threat(home):
    r = front.screen_message(msg(body="IRS: arrest warrant issued, pay now to avoid legal action"))
    assert "R08" in r["rules"]


def test_R09_prize_bait(home):
    r = front.screen_message(msg(body="Congratulations! You won the lottery, claim your prize here: http://x.ru"))
    assert "R09" in r["rules"]


def test_R10_replyto_mismatch(home):
    r = front.screen_message(msg(**{"from": "boss@company.com",
                                    "reply_to": "boss@company-support.net",
                                    "subject": "Quick favor",
                                    "body": "Can you handle this today?"}))
    assert "R10" in r["rules"]


# ---------------------------------------------------------------------------
# F5: fail closed


def test_screening_error_quarantines_never_passes(home, monkeypatch):
    def boom(message):
        raise RuntimeError("parser exploded")
    monkeypatch.setattr(front, "_screen_inner", boom)
    r = front.screen_message(msg())
    assert r["verdict"] == "QUARANTINE"
    assert r["rules"] == ["R99"]
    assert r["score"] == 100
    assert len(quarantine_records(home)) == 1


def test_release_of_quarantine_escape_attempt_refused(home):
    store = IdentityStore()
    store.create("mallory", tier="starter")
    r = front.screen_message(_phish())
    with pytest.raises(TierError):
        front.release(r["msg_ref"], identity_store=store, authorizer="mallory")


# ---------------------------------------------------------------------------
# F6: quarantine append-only; founder-only release


def test_release_requires_founder_and_is_logged(home):
    from levi.cybrus.factory import hash_password

    store = IdentityStore()
    store.create("chauncey", tier="founder")
    store.set_credential("chauncey", hash_password("correct-horse"))
    r = front.screen_message(_phish())
    with pytest.raises(KeyError):
        front.release("no-such-ref", identity_store=store,
                      authorizer="chauncey", credential="correct-horse")
    rel = front.release(r["msg_ref"], identity_store=store,
                        authorizer="chauncey", credential="correct-horse")
    assert rel["released_by"] == "chauncey"
    assert rel["msg_ref"] == r["msg_ref"]
    # quarantine record itself untouched (append-only), release logged separately
    assert len(quarantine_records(home)) == 1
    rel_p = home / ".levi" / "cybrus" / "front_releases.jsonl"
    assert rel_p.exists()
    assert json.loads(rel_p.read_text().splitlines()[0])["msg_ref"] == r["msg_ref"]


def test_release_rejects_bare_name_and_wrong_credential(home):
    """F6: a bare founder name — or the wrong credential — releases nothing."""
    from levi.cybrus.factory import hash_password

    store = IdentityStore()
    store.create("chauncey", tier="founder")
    store.set_credential("chauncey", hash_password("correct-horse"))
    r = front.screen_message(_phish())
    with pytest.raises(TierError):
        front.release(r["msg_ref"], identity_store=store, authorizer="chauncey")
    with pytest.raises(TierError):
        front.release(r["msg_ref"], identity_store=store,
                      authorizer="chauncey", credential="wrong-horse")
    # still quarantined — nothing escaped
    assert len(quarantine_records(home)) == 1


# ---------------------------------------------------------------------------
# F9: deterministic scoring


def test_deterministic_scoring(home):
    m = _phish()
    r1 = front.screen_message(dict(m))
    r2 = front.screen_message(dict(m))
    assert r1["score"] == r2["score"] == r1["score"]
    assert r1["rules"] == r2["rules"]
    assert r1["verdict"] == r2["verdict"]
    assert r1["msg_ref"] == r2["msg_ref"]


# ---------------------------------------------------------------------------
# F7: no egress — module performs no network calls


def test_no_network_egress(home, monkeypatch):
    import socket
    def no_connect(*a, **k):
        raise AssertionError("FRONT attempted network egress")
    monkeypatch.setattr(socket, "socket", no_connect)
    monkeypatch.setattr(socket, "create_connection", no_connect)
    front.screen_message(_phish())
    front.screen_items("email", [{"id": "x", "text": "hello http://example.com"}])
    front.describe_posture()


# ---------------------------------------------------------------------------
# Self-attack battery (RED-swarm first pass, adversarial samples)


def test_selfattack_zero_width_urgency_still_caught(home):
    # "URGENT" with zero-width joiners between letters
    zw = "URG\u200bENT: verify your account now or it will be locked http://bit.ly/x"
    r = front.screen_message(msg(body=zw))
    assert r["verdict"] == "QUARANTINE"
    assert "R04" in r["rules"]


def test_selfattack_leet_lookalike(home):
    r = front.screen_message(msg(**{"from": "security@g00gle-verify.com",
                                    "subject": "Security alert",
                                    "body": "Unusual sign in. Confirm: https://g00gle-verify.com/login"}))
    assert "R02" in r["rules"]


def test_selfattack_credential_link_no_phrase_is_warn_not_quarantine(home):
    # cred phrase + link triggers R03 (30) -> WARN: flagged, not silently delivered
    r = front.screen_message(msg(body="Sign in to verify your account: https://evil.ru/login"))
    assert r["verdict"] == "WARN"
    assert "R03" in r["rules"]


def test_selfattack_multi_signal_stacking(home):
    r = front.screen_message(msg(
        **{"from": "IRS Agent <agent@micros0ft.com>",
           "reply_to": "agent@other-domain.net",
           "subject": "FINAL NOTICE: arrest warrant",
           "body": ("Legal action imminent. Confirm your identity now: "
                    "http://bit.ly/irs-form. Reply with your SSN.")},
    ))
    assert r["verdict"] == "QUARANTINE"
    assert {"R02", "R08", "R10", "R05", "R07"} <= set(r["rules"])


def test_selfattack_benign_newsletter_not_quarantined(home):
    r = front.screen_message(msg(
        **{"from": "news@newsletter.example.com",
           "subject": "This week's deals",
           "body": "Limited time offer! Shop now: https://example.com/deals"},
    ))
    # "limited time" fires R04 only -> CLEAN (no false quarantine)
    assert r["verdict"] == "CLEAN"


def test_screen_items_rejects_unknown_channel(home):
    with pytest.raises(ValueError):
        front.screen_items("smoke-signal", [])


def test_describe_posture_is_honest(home):
    p = front.describe_posture()
    assert p["egress"] == "none — stdlib-only, zero network"
    assert set(p["thresholds"]) == {"quarantine_at", "warn_at"}
    assert "screen_items() between watcher fetch and ingest" in p["integration"]


# ---------------------------------------------------------------------------
# RED-3 twin-verification fixes (2026-09-22): regression proofs


def test_red3_html_anchor_display_href_mismatch(home):
    r = front.screen_message(msg(body=(
        'Please review: <a href="http://evil-login.example/verify">'
        "https://paypal.com/signin</a>")))
    assert "R05" in r["rules"]


def test_red3_bare_domain_feeds_r03(home):
    r = front.screen_message(msg(body=(
        "Your account will be suspended. "
        "Sign in at evil-login.example to verify your account.")))
    assert "R03" in r["rules"]


def test_red3_userinfo_url_smuggling(home):
    # RED's finding was rule evasion (score 0, R05 silent); the fix is that
    # R05 fires. A lone userinfo URL with no lure still scores below WARN —
    # consistent with the rest of the threshold design.
    r = front.screen_message(msg(body="verify at http://paypal.com@evil.example/ now"))
    assert "R05" in r["rules"]


def test_red3_decimal_and_hex_ip_hosts(home):
    assert "R05" in front.screen_message(msg(body="see http://2130706433/phish now"))["rules"]
    assert "R05" in front.screen_message(msg(body="see http://0x7f000001/phish now"))["rules"]
    assert "R05" in front.screen_message(msg(body="see http://192.168.0.1/phish now"))["rules"]


def test_red3_macro_office_attachments(home):
    for name in ("invoice.docm", "budget.xlsm", "deck.pptm"):
        r = front.screen_message(msg(attachments=[name]))
        assert "R06" in r["rules"], name


def test_red3_smish_bare_brand_sender_id(home):
    r = front.screen_message(msg(
        channel="text", **{"from": "PayPal"},
        body="ALERT: your account locked. Call 1-800-555-0199 immediately to unlock."))
    assert r["verdict"] in ("WARN", "QUARANTINE")
    assert "R01" in r["rules"]


def test_red3_audit_failure_raises_not_silent(home, monkeypatch):
    from levi.cybrus import audit as audit_mod

    def dead(self, *a, **k):
        raise RuntimeError("audit store unwritable")

    monkeypatch.setattr(audit_mod.AuditEngine, "append", dead)
    with pytest.raises(RuntimeError):
        front.screen_message(_phish())


def test_red3_r99_returns_verdict_when_quarantine_store_dead(home, monkeypatch):
    def dead(name):
        raise OSError("quarantine store unwritable")

    monkeypatch.setattr(front, "_store_path", dead)
    r = front.screen_message(_phish())
    assert r["verdict"] == "QUARANTINE"
    assert "R99" in r["rules"]
    assert r.get("quarantine_write") == "failed"


def test_red3_quarantine_subject_redacted(home):
    r = front.screen_message({
        "id": "s1", "channel": "email", "from": "x@y.z", "reply_to": "",
        "subject": "code 984211 inside",
        "body": ("verify your account now: sign in at http://evil.example - "
                 "act now or lose access. your verification code please")})
    assert r["verdict"] == "QUARANTINE"
    recs = quarantine_records(home)
    assert recs
    assert "984211" not in json.dumps(recs)
