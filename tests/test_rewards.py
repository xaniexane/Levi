"""Hermetic tests for the rewards engine.

No HOME writes (every call takes home=tmp_path), no network, no money
layer imports beyond the event shape it returns.
"""

from pathlib import Path

import pytest

from levi.rewards import hooks, ledger, redeem, rules


def _income_event(**over):
    base = {
        "id": "evt123abc456",
        "at": "2026-09-18T10:00:00Z",
        "generator_id": "slot-7-tool",
        "kind": "sale",
        "amount": 50.0,
        "currency": "USD",
        "keeper": 35.0,
        "pool": 15.0,
        "counterparty": "client-a",
        "note": "",
    }
    base.update(over)
    return base


def _usage_report(**over):
    base = {
        "report_id": "rep-001",
        "account": "acct-1",
        "actions": 120,
        "window_days": 7,
        "at": "2026-09-18T10:00:00Z",
    }
    base.update(over)
    return base


# ---- catalog sanity --------------------------------------------------------

def test_catalog_covers_all_three_reward_types():
    types = {r["reward_type"] for r in rules.REWARDS_CATALOG}
    assert types == {"usage_grant", "tier_reduction", "badge"}


def test_catalog_triggers_valid():
    for r in rules.REWARDS_CATALOG:
        assert r["trigger"] in ("income", "usage")
        assert r["per"] in ("once", "every")


# ---- earn -> ledger -> redeem round trip -----------------------------------

def test_first_sale_earns_badge_once(tmp_path: Path):
    earned = hooks.reward_for_income_event(_income_event(), account="acct-1", home=tmp_path)
    badges = [e for e in earned if e["reward_type"] == "badge"]
    assert len(badges) == 1
    assert badges[0]["detail"]["badge"] == "first-dollar"
    # Same backing event never pays twice; "once" rule never fires again.
    again = hooks.reward_for_income_event(_income_event(), account="acct-1", home=tmp_path)
    assert [e for e in again if e["rule_id"] == "first-dollar"] == []
    other = _income_event(id="evt999zzz111", amount=10.0)
    again2 = hooks.reward_for_income_event(other, account="acct-1", home=tmp_path)
    assert [e for e in again2 if e["rule_id"] == "first-dollar"] == []


def test_recurring_income_earns_monthly_reduction(tmp_path: Path):
    earned = hooks.reward_for_income_event(
        _income_event(id="rec-1", kind="recurring", amount=20.0),
        account="acct-1",
        home=tmp_path,
    )
    reds = [e for e in earned if e["reward_type"] == "tier_reduction"]
    assert len(reds) == 1
    assert reds[0]["detail"]["month"] == "2026-09"
    assert reds[0]["detail"]["percent_off"] == 10
    assert redeem.month_reduction("acct-1", "2026-09", home=tmp_path)["percent_off"] == 10
    # A different month gets nothing.
    assert redeem.month_reduction("acct-1", "2026-10", home=tmp_path)["percent_off"] == 0


def test_usage_grant_earn_redeem_round_trip(tmp_path: Path):
    earned = hooks.reward_for_usage(_usage_report(), home=tmp_path)
    assert any(e["rule_id"] == "week-of-attention" for e in earned)
    assert redeem.usage_balance("acct-1", home=tmp_path)["units"] == 50
    out = redeem.redeem_usage("acct-1", 20, purpose="agent run", home=tmp_path)
    assert out["redeemed"] == 20
    assert out["remaining"] == 30
    assert redeem.usage_balance("acct-1", home=tmp_path)["units"] == 30
    with pytest.raises(ValueError):
        redeem.redeem_usage("acct-1", 31, home=tmp_path)


def test_big_payout_badge_and_grant(tmp_path: Path):
    earned = hooks.reward_for_income_event(
        _income_event(id="pay-1", kind="payout", amount=750.0),
        account="acct-1",
        home=tmp_path,
    )
    rule_ids = {e["rule_id"] for e in earned}
    assert "rainmaker" in rule_ids
    assert "payout-celebration" in rule_ids
    assert redeem.usage_balance("acct-1", home=tmp_path)["units"] == 200
    assert {b["badge"] for b in redeem.list_badges("acct-1", home=tmp_path)} == {"rainmaker"}


# ---- month-boundary expiry --------------------------------------------------

def test_monthly_reduction_expires_at_month_end(tmp_path: Path):
    hooks.reward_for_income_event(
        _income_event(id="rec-9", kind="recurring", amount=20.0),
        account="acct-1",
        home=tmp_path,
    )
    assert redeem.month_reduction("acct-1", "2026-09", home=tmp_path)["percent_off"] == 10
    swept = redeem.sweep_expiry("2026-10", home=tmp_path)
    assert swept["expired"] == 1
    # After expiry the September reduction no longer applies...
    assert redeem.month_reduction("acct-1", "2026-09", home=tmp_path)["percent_off"] == 0
    # ...and it never applied to October in the first place.
    assert redeem.month_reduction("acct-1", "2026-10", home=tmp_path)["percent_off"] == 0
    # Sweep is idempotent: the same earn is never expired twice.
    assert redeem.sweep_expiry("2026-10", home=tmp_path)["expired"] == 0


def test_badges_never_expire(tmp_path: Path):
    hooks.reward_for_income_event(_income_event(), account="acct-1", home=tmp_path)
    redeem.sweep_expiry("2027-01", home=tmp_path)
    assert {b["badge"] for b in redeem.list_badges("acct-1", home=tmp_path)} == {"first-dollar"}


def test_usage_grants_survive_month_sweep(tmp_path: Path):
    hooks.reward_for_usage(_usage_report(), home=tmp_path)
    redeem.sweep_expiry("2027-01", home=tmp_path)
    assert redeem.usage_balance("acct-1", home=tmp_path)["units"] == 50


# ---- badge criteria ---------------------------------------------------------

def test_deep_focus_threshold(tmp_path: Path):
    below = hooks.reward_for_usage(
        _usage_report(report_id="r-low", actions=999, window_days=30), home=tmp_path
    )
    assert [e for e in below if e["rule_id"] == "deep-focus"] == []
    at = hooks.reward_for_usage(
        _usage_report(report_id="r-high", actions=1000, window_days=30), home=tmp_path
    )
    assert [e for e in at if e["rule_id"] == "deep-focus"] != []


def test_small_payout_earns_nothing(tmp_path: Path):
    earned = hooks.reward_for_income_event(
        _income_event(id="pay-small", kind="payout", amount=10.0),
        account="acct-1",
        home=tmp_path,
    )
    assert earned == []


# ---- hash chain -------------------------------------------------------------

def test_chain_verifies_and_tamper_detected(tmp_path: Path):
    hooks.reward_for_income_event(_income_event(), account="acct-1", home=tmp_path)
    hooks.reward_for_usage(_usage_report(), home=tmp_path)
    redeem.redeem_usage("acct-1", 5, home=tmp_path)
    ok = ledger.verify(home=tmp_path)
    assert ok["ok"] and ok["entries"] >= 3
    # Tamper with one line.
    path = ledger.ledger_path(tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    import json

    rec = json.loads(lines[1])
    rec["detail"]["units"] = 99999
    lines[1] = json.dumps(rec)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    bad = ledger.verify(home=tmp_path)
    assert not bad["ok"]
    assert bad["first_bad_seq"] == 1


# ---- never invent value -----------------------------------------------------

def test_malformed_income_event_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        hooks.reward_for_income_event({"kind": "sale"}, account="acct-1", home=tmp_path)
    with pytest.raises(ValueError):
        hooks.reward_for_income_event(
            _income_event(amount=0), account="acct-1", home=tmp_path
        )
    with pytest.raises(ValueError):
        hooks.reward_for_income_event(
            _income_event(kind="expense"), account="acct-1", home=tmp_path
        )


def test_malformed_usage_report_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        hooks.reward_for_usage({"account": "acct-1"}, home=tmp_path)
    with pytest.raises(ValueError):
        hooks.reward_for_usage(_usage_report(actions=-1), home=tmp_path)


def test_zero_action_report_earns_nothing(tmp_path: Path):
    assert hooks.reward_for_usage(_usage_report(actions=0), home=tmp_path) == []


def test_earn_requires_basis_ref(tmp_path: Path):
    with pytest.raises(ValueError):
        ledger.append("earn", "acct-1", "badge", "first-dollar", {},
                      rule_id="first-dollar", home=tmp_path)


def test_chain_ok_reported_in_balances(tmp_path: Path):
    hooks.reward_for_usage(_usage_report(), home=tmp_path)
    bal = redeem.balances("acct-1", home=tmp_path)
    assert bal["chain"]["ok"] is True
    assert bal["usage"]["units"] == 50
