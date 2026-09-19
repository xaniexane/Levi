"""Money-law guard: Cybrus alone handles money.

Binding law (Chauncey, 2026-09-17): Cybrus is the ONLY one ever allowed to
handle money. This test enforces it structurally:

1. No payment-SDK imports anywhere outside ``core/levi/cybrus/``.
2. Any money-verb function definition outside ``core/levi/cybrus/`` must
   be on the explicit ACCOUNTING_ALLOWLIST with a documented honest
   reason (accounting, drafts, paper simulation — never movement).
3. The finance domain stays paper-only (live trading structurally
   disabled).
4. The money gateway fails closed: plan/preview work, but execute()
   always refuses without a registered rail + Chauncey authorization.

To add a NEW money-touching module: route it through
``levi.cybrus.money.MoneyGateway``. To add an accounting-only module
whose name matches a money verb: add it here with an honest reason —
the test fails loudly until you do, which is the point.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
CORE = REPO / "core" / "levi"
CYBRUS = CORE / "cybrus"

# Payment rails must never be imported outside Cybrus.
SDK_IMPORT_RE = re.compile(
    r"^\s*(?:import|from)\s+(stripe|paypalrestsdk|paypal|squareup|braintree|plaid)\b",
    re.M,
)

# Money-verb defs. Excludes "payload" (turn_relay / capability_tokens),
# which is a false positive, not a payment.
_MONEY_VERBS = (
    "charge|refund|payout|transfer|withdraw|deposit|settle"
    "|pay_fee|execute_payment|send_money|collect_payment"
)
MONEY_DEF_RE = re.compile(r"^\s*def\s+(" + _MONEY_VERBS + r")\w*\s*\(", re.M)


def _py_files():
    for p in sorted(CORE.rglob("*.py")):
        if "__pycache__" in str(p):
            continue
        yield p


def _money_defs(path: pathlib.Path):
    try:
        src = path.read_text(encoding="utf-8")
    except OSError:
        return []
    names = []
    for m in MONEY_DEF_RE.finditer(src):
        name = m.group(1)
        if name.startswith("payl"):  # payload, not payment
            continue
        names.append(m.group(0).strip().split("(")[0])
    return names


# Every file outside cybrus/ that defines a money-verb function, with the
# honest reason it is NOT money movement. Additions require an explicit
# entry here — silent money verbs are a violation.
ACCOUNTING_ALLOWLIST = {
    # path relative to core/levi : reason
    "daemon/kernel.py": "charge() bills internal compute units, not money",
    "governor/priority.py": "refund() restores internal burst passes, not money",
    "finance/bets.py": "paper-simulation bet settlement (live structurally disabled)",
    "finance/portfolio.py": "paper-simulation portfolio deposit (live structurally disabled)",
    "graph/lwp_primitives.py": "artifact bank deposit/withdraw — versioned artifacts, not money",
    "methods/loci.py": "memory-palace loci deposit — facts, not money",
    "neighbor/pay.py": "settlement LEDGER: who owes whom; real money lives in external plug-ins (references, never core)",
    "revival/carrier_billing.py": "documented local ledger — no real payments, no network",
    "revival/carrier_micropay.py": "documented local ledger — integer minor units, no money",
    "revival/creator_economics.py": "payouts are ACCOUNTING, not money movement (documented)",
    "revival/indie_channel.py": "revenue is ledgered, not settled (documented)",
    "revival/kiosk.py": "local kiosk settlement accounting — no money movement",
    "revival/paid_community.py": "payment receipts as opaque tokens — records, not payments",
    "revival/metered_viewdata.py": "metered accounting — nothing touches money or networks",
    "revival/neighborhood_homepages.py": "homestead accounting sim — no money",
    "revival/numeric_identity.py": "transfer() looks up identity transfer RECORDS — not funds",
    "revival/quorum_chest.py": "sealed envelope deposit/withdraw — documents, not money",
    "revival/speechacts.py": "withdraw() retracts speech acts — not funds",
    "revival/tiered_disclosure.py": "tiered item deposit — content, not money",
    "revival/loci.py": "memory loci deposit — facts, not money",
    "revival/app_catalog.py": "withdraw() unlists apps — not funds",
    "bounty/payment.py": "gateway-routed settlement adapter — all movement through levi.cybrus.money.MoneyGateway; fail-closed, moves nothing itself",
    "creator/money.py": "gateway-routed charge adapter — all movement through levi.cybrus.money.MoneyGateway; fail-closed, moves nothing itself",
    "services/shield/service.py": "gateway-routed payment-stage adapter — all movement through levi.cybrus.money.MoneyGateway via bounty.payment; fail-closed, moves nothing itself",
}


def test_no_payment_sdk_imports_outside_cybrus():
    offenders = []
    for p in _py_files():
        if CYBRUS in p.parents or p == CYBRUS:
            continue
        try:
            src = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if SDK_IMPORT_RE.search(src):
            offenders.append(str(p.relative_to(REPO)))
    assert not offenders, (
        "payment-SDK imports outside core/levi/cybrus/ — "
        "money moves through Cybrus only: " + ", ".join(offenders)
    )


def test_money_verbs_declared_outside_cybrus():
    undeclared = []
    for p in _py_files():
        if CYBRUS in p.parents or p == CYBRUS:
            continue
        defs = _money_defs(p)
        if not defs:
            continue
        rel = str(p.relative_to(CORE))
        if rel not in ACCOUNTING_ALLOWLIST:
            undeclared.append(f"{rel}: {', '.join(defs)}")
    assert not undeclared, (
        "money-verb function defs outside cybrus/ without an allowlist entry — "
        "route through levi.cybrus.money.MoneyGateway or declare accounting-only: "
        + "; ".join(undeclared)
    )


def test_allowlist_entries_still_exist():
    missing = [rel for rel in ACCOUNTING_ALLOWLIST if not (CORE / rel).exists()]
    assert not missing, "stale money-law allowlist entries: " + ", ".join(missing)


def test_finance_stays_paper_only():
    sys.path.insert(0, str(REPO / "core"))
    try:
        from levi.finance import broker, brokerlink
    finally:
        sys.path.pop(0)
    assert broker.live_enabled() is False, "live trading must stay structurally disabled"
    with pytest.raises(Exception):
        brokerlink.execute_live({"order": "draft"})  # type: ignore[attr-defined]


def test_advisor_touches_no_money():
    src = (CORE / "advisor" / "pricing.py").read_text(encoding="utf-8")
    assert "import requests" not in src
    assert "stripe" not in src.lower()
    assert "socket" not in src
    # The advisor advises; it must never call the money gateway's execute.
    assert ".execute(" not in src


def test_money_gateway_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_CYBRUS_DIR", str(tmp_path))
    sys.path.insert(0, str(REPO / "core"))
    try:
        from levi.cybrus import money
    finally:
        sys.path.pop(0)

    gw = money.MoneyGateway()

    # PLAN + PREVIEW work — they move nothing.
    plan = gw.plan(money.MoneyOperation.CHARGE, 199, "usd", "nope", "test", "tester")
    assert "199" in gw.preview(plan) or "1.99" in gw.preview(plan)

    # AUTHORIZE refuses non-keeper identities.
    bad = money.MoneyAuthorization(authorized_by="mallory", plan_id=plan.plan_id,
                                   operation="charge")
    with pytest.raises(money.NotAuthorized):
        gw.authorize(plan, bad)

    # EXECUTE refuses: no rails registered (fail closed).
    good = money.MoneyAuthorization(authorized_by="chauncey", plan_id=plan.plan_id,
                                    operation="charge")
    gw.authorize(plan, good)  # permission is fine...
    with pytest.raises(money.NoRailConfigured):
        gw.execute(plan, good)  # ...but movement is not.

    # RAIL registration refuses non-keeper approvers.
    with pytest.raises(money.NotAuthorized):
        gw.register_rail("x", "y", registered_by="mallory", approved_by="mallory")

    # Audit trail records every attempt (metadata only).
    events = [e["event"] for e in gw.audit_log()]
    assert "planned" in events
    assert "authorized" in events
    assert "authorize_refused" in events
    assert "execute_refused" in events
    assert "rail_register_refused" in events

    # Receipt carries the law.
    receipt = gw.receipt(plan.plan_id)
    assert receipt["law"] == "Cybrus alone handles money."
