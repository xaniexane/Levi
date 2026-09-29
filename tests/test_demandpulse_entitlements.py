"""Tests for the DemandPulse license-key entitlement system.

Each law from entitlements.py gets its proof here:
  key-format, append-only, fail-closed, grace, refund-window, key-stability,
  money-separation, and the enforcement-default gate.
"""

from datetime import date, timedelta

import pytest

from levi.demandpulse import entitlements as E

DAY = date(2026, 9, 24)


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """Isolated entitlement store per test."""
    store = tmp_path / "dp-home"
    monkeypatch.setenv("DEMANDPULSE_HOME", str(store))
    return store


def issue(email="buyer@example.com", months=1, today=DAY, **kw):
    return E.issue(email, months=months, payment_ref="cashapp $buyer 2026-09-24",
                   today=today, **kw)


# -- key-format law ----------------------------------------------------------

def test_key_format(home):
    rec = issue()
    assert E.KEY_RE.match(rec["key"]), rec["key"]


def test_keys_unique(home):
    keys = {issue(email=f"u{i}@example.com")["key"] for i in range(25)}
    assert len(keys) == 25


def test_key_uses_unambiguous_alphabet(home):
    for _ in range(20):
        key = E.generate_key()
        assert "0" not in key and "O" not in key
        assert "1" not in key and "I" not in key


def test_bad_key_format_rejected(home):
    with pytest.raises(E.EntitlementError):
        E.validate_key_format("not-a-key")
    with pytest.raises(E.EntitlementError):
        E.validate_key_format("DP-ABC-DEF-GHI")


# -- email law ---------------------------------------------------------------

def test_email_normalized(home):
    rec = issue(email="  Buyer@Example.COM ")
    assert rec["email"] == "buyer@example.com"


def test_bad_email_rejected(home):
    for bad in ["nope", "a@b", "@example.com", "a b@example.com", "", None, 42]:
        with pytest.raises(E.EntitlementError):
            issue(email=bad)


def test_bad_months_rejected(home):
    for bad in [0, -1, "1", 1.5, True]:
        with pytest.raises(E.EntitlementError):
            issue(months=bad)


# -- issue / check happy path (fail-closed law, positive case) ---------------

def test_issue_then_check_active(home):
    rec = issue()
    res = E.check(rec["email"], rec["key"], today=DAY)
    assert res.active is True
    assert res.in_grace is False
    assert res.reason == "active"


def test_paid_through_is_30_days(home):
    rec = issue(today=DAY)
    assert rec["paid_from"] == "2026-09-24"
    assert rec["paid_through"] == "2026-10-24"


def test_issue_writes_receipt(home):
    issue()
    receipts = list((E.store_dir() / "receipts").glob("*.json"))
    assert len(receipts) == 1


# -- fail-closed law (negative cases) ----------------------------------------

def test_check_unknown_email_inactive(home):
    res = E.check("ghost@example.com", "DP-AAAA-BBBB-CCCC", today=DAY)
    assert res.active is False
    assert "no entitlement record" in res.reason


def test_check_wrong_key_inactive(home):
    rec = issue()
    other = issue(email="other@example.com")
    res = E.check(rec["email"], other["key"], today=DAY)
    assert res.active is False
    assert res.key_match is False


def test_check_expired_inactive(home):
    rec = issue(today=DAY)
    res = E.check(rec["email"], rec["key"],
                  today=DAY + timedelta(days=30 + E.GRACE_DAYS + 1))
    assert res.active is False
    assert res.in_grace is False
    assert "grace lapsed" in res.reason


# -- grace law ----------------------------------------------------------------

def test_grace_window_reports_grace_but_not_active(home):
    rec = issue(today=DAY)
    res = E.check(rec["email"], rec["key"], today=DAY + timedelta(days=33))
    assert res.active is False          # still fail-closed
    assert res.in_grace is True
    assert "grace" in res.reason


def test_day_after_expiry_is_grace(home):
    rec = issue(today=DAY)
    res = E.check(rec["email"], rec["key"], today=DAY + timedelta(days=31))
    assert res.in_grace is True and res.active is False


# -- revoke -------------------------------------------------------------------

def test_revoke_kills_access(home):
    rec = issue()
    E.revoke(rec["email"], reason="fraud", today=DAY)
    res = E.check(rec["email"], rec["key"], today=DAY)
    assert res.active is False
    assert "revoked" in res.reason


def test_revoke_unknown_email_errors(home):
    with pytest.raises(E.EntitlementError):
        E.revoke("ghost@example.com", today=DAY)


def test_revoke_twice_errors(home):
    rec = issue()
    E.revoke(rec["email"], today=DAY)
    with pytest.raises(E.EntitlementError):
        E.revoke(rec["email"], today=DAY)


def test_reissue_after_revoke_mints_new_key(home):
    rec = issue()
    old_key = rec["key"]
    E.revoke(rec["email"], today=DAY)
    rec2 = issue(email=rec["email"], today=DAY)
    assert rec2["key"] != old_key          # revoked key never revives
    res = E.check(rec["email"], old_key, today=DAY)
    assert res.active is False


# -- renewal / key-stability law ----------------------------------------------

def test_renewal_keeps_key_and_extends(home):
    rec = issue(today=DAY)
    rec2 = issue(email=rec["email"], months=1, today=DAY + timedelta(days=10))
    assert rec2["key"] == rec["key"]
    assert rec2["event"] == "renewed"
    assert rec2["paid_through"] > rec["paid_through"]


def test_renewal_after_lapse_extends_from_today(home):
    rec = issue(today=DAY)
    later = DAY + timedelta(days=60)
    rec2 = issue(email=rec["email"], today=later)
    assert rec2["paid_through"] == (later + timedelta(days=30)).isoformat()


# -- refund-window law ----------------------------------------------------------

def test_refund_within_window_revokes(home):
    rec = issue(today=DAY)
    out = E.refund(rec["email"], today=DAY + timedelta(days=6))
    assert out["event"] == "refunded"
    assert out["status"] == "revoked"
    res = E.check(rec["email"], rec["key"], today=DAY + timedelta(days=6))
    assert res.active is False


def test_refund_past_window_refused(home):
    rec = issue(today=DAY)
    with pytest.raises(E.RefundWindowExpired):
        E.refund(rec["email"], today=DAY + timedelta(days=8))
    # still active — the refusal changed nothing
    res = E.check(rec["email"], rec["key"], today=DAY + timedelta(days=8))
    assert res.active is True


# -- append-only law ------------------------------------------------------------

def test_records_are_append_only(home):
    rec = issue()
    E.revoke(rec["email"], today=DAY)
    records = E.read_records()
    assert [r["event"] for r in records] == ["issued", "revoked"]
    assert [r["seq"] for r in records] == [1, 2]
    # every event wrote its own receipt
    assert len(list((E.store_dir() / "receipts").glob("*.json"))) == 2


def test_corrupt_record_raises(home):
    E.store_dir().mkdir(parents=True, exist_ok=True)
    E.records_path().write_text('{"seq": 1, "email": "a@b.c"}\nnot json\n')
    with pytest.raises(E.EntitlementError, match="corrupt"):
        E.read_records()


# -- list ------------------------------------------------------------------------

def test_list_states(home):
    a = issue(email="a@example.com", today=DAY)
    b = issue(email="b@example.com", today=DAY - timedelta(days=60))
    c = issue(email="c@example.com", today=DAY)
    E.revoke(c["email"], today=DAY)
    rows = {r["email"]: r["state"] for r in E.list_entitlements(today=DAY)}
    assert rows[a["email"]] == "active"
    assert rows[b["email"]] == "expired"
    assert rows[c["email"]] == "revoked"
    assert [r["email"] for r in E.list_entitlements(status="active", today=DAY)] == [a["email"]]


def test_list_bad_filter_errors(home):
    with pytest.raises(E.EntitlementError):
        E.list_entitlements(status="bogus")


# -- enforcement-default law -------------------------------------------------------

def test_enforcement_off_by_default():
    assert E.ENFORCEMENT_ENABLED is False


def test_require_active_refuses_while_gated(home):
    rec = issue()
    # even with a VALID entitlement, the enforcing path refuses while gated
    with pytest.raises(E.EntitlementError, match="not enabled"):
        E.require_active_entitlement(rec["email"], rec["key"], today=DAY)


# -- customer activation -------------------------------------------------------------

def test_activation_stores_claim(home):
    rec = E.validate_activation("buyer@example.com", "dp-aaaa-bbbb-cccc")
    assert rec["email"] == "buyer@example.com"
    assert rec["key"] == "DP-AAAA-BBBB-CCCC"
    stored = E.read_activation()
    assert stored["email"] == "buyer@example.com"


def test_activation_rejects_bad_input(home):
    with pytest.raises(E.EntitlementError):
        E.validate_activation("nope", "DP-AAAA-BBBB-CCCC")
    with pytest.raises(E.EntitlementError):
        E.validate_activation("buyer@example.com", "bad-key")
    assert E.read_activation() is None

# --------------------------------------- wave 6: entitlements hardening
import json


def _write_raw_record(home, rec):
    path = E.records_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


def test_read_records_rejects_non_int_seq(home):
    _write_raw_record(home, {"email": "a@b.c", "seq": "1"})
    with pytest.raises(E.EntitlementError, match="seq must be an int"):
        E.read_records(home)


def test_check_malformed_date_is_fail_closed_not_crash(home):
    rec = issue(today=DAY)
    path = E.records_path(home)
    lines = path.read_text(encoding="utf-8").splitlines()
    bad = json.loads(lines[-1])
    bad["paid_through"] = "not-a-date"
    path.write_text("\n".join(lines[:-1] + [json.dumps(bad)]) + "\n",
                    encoding="utf-8")
    verdict = E.check("buyer@example.com", rec["key"], home=home, today=DAY)
    assert verdict.active is False
    assert "malformed" in verdict.reason


def test_issue_renewal_refuses_keyless_active_record(home):
    _write_raw_record(home, {
        "seq": 1, "event": "issued", "email": "buyer@example.com",
        "key": "", "paid_from": DAY.isoformat(),
        "paid_through": (DAY + timedelta(days=30)).isoformat(),
        "payment_ref": "x", "status": "active", "note": "",
        "ts": "2026-09-24T00:00:00+00:00",
    })
    with pytest.raises(E.EntitlementError, match="has no key"):
        E.issue("buyer@example.com", today=DAY, home=home)


def test_list_entitlements_tolerates_keyless_record(home):
    _write_raw_record(home, {
        "seq": 1, "event": "issued", "email": "ghost@example.com",
        "paid_from": DAY.isoformat(),
        "paid_through": (DAY + timedelta(days=30)).isoformat(),
        "payment_ref": "x", "status": "active", "note": "",
        "ts": "2026-09-24T00:00:00+00:00",
    })
    rows = E.list_entitlements(home=home, today=DAY)
    assert rows[0]["state"] == "expired"  # fail-closed, no crash
    assert rows[0]["key"] == ""


def test_store_dir_blank_env_falls_back(monkeypatch, tmp_path):
    from pathlib import Path

    monkeypatch.setenv("DEMANDPULSE_HOME", "  ")
    assert E.store_dir().parent == Path.home() / ".demandpulse"


def test_read_activation_bad_bytes_is_none(home):
    E.validate_activation("buyer@example.com",
                          E.generate_key(), home=home)
    E.activation_path(home).write_bytes(b"\xff\xfe not json \x00")
    assert E.read_activation(home) is None
