"""Redemption — spend granted benefits, compute monthly reductions, list badges.

  redeem_usage()        consume extra-usage credits (FIFO) -> burn entry
  month_reduction()     the account's tier pricing reduction for a month
  sweep_expiry()        expire month-scoped reductions past their month
  list_badges()         badges earned (badges never expire)
  balances()            full account standing

Honest limits: this moves ledgered BENEFITS, never money. Paper only —
applying a reduction to a real price happens in the advisor/service
layer, not here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.rewards import ledger


def _settled_map(home, account: str) -> Dict[str, int]:
    """Map earn-id -> units already consumed (burned or expired) for usage grants."""
    consumed: Dict[str, int] = {}
    for e in ledger.read(home):
        if e.get("account") != account:
            continue
        detail = e.get("detail") or {}
        if e.get("event") == "expire" and e.get("reward_type") == "usage_grant":
            ref = detail.get("settles")
            if ref:
                consumed[ref] = consumed.get(ref, 0) + int(detail.get("units", 0))
        elif e.get("event") == "burn" and e.get("reward_type") == "usage_grant":
            for ref, taken in (detail.get("takes") or {}).items():
                consumed[ref] = consumed.get(ref, 0) + int(taken)
    return consumed


def _expired_ids(home, account: str) -> set:
    """Ledger ids fully settled by burn/expire events (tier reductions, badges)."""
    settled = set()
    for e in ledger.read(home):
        if e.get("account") != account:
            continue
        if e.get("event") in ("burn", "expire") and e.get("reward_type") != "usage_grant":
            ref = (e.get("detail") or {}).get("settles")
            if ref:
                settled.add(ref)
    return settled


def _outstanding_usage_earns(account: str, home) -> List[Dict[str, Any]]:
    """Usage-grant earns with remaining units, oldest first."""
    consumed = _settled_map(home, account)
    out = []
    for e in ledger.read(home):
        if (
            e.get("account") == account
            and e.get("event") == "earn"
            and e.get("reward_type") == "usage_grant"
        ):
            total = int((e.get("detail") or {}).get("units", 0))
            left = total - consumed.get(e["id"], 0)
            if left > 0:
                out.append((e, left))
    return out


def usage_balance(account: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Available extra-usage credits for an account (earned minus burned)."""
    total = sum(left for _, left in _outstanding_usage_earns(account, home))
    return {"account": account, "units": total, "unit": "usage-credit"}


def redeem_usage(
    account: str,
    units: int,
    *,
    purpose: str = "",
    home: Optional[Path] = None,
    at: Optional[str] = None,
) -> Dict[str, Any]:
    """Burn granted usage credits. Raises if the account lacks the balance.

    Burned units settle the oldest outstanding usage grants first (FIFO).
    """
    units = int(units)
    if units <= 0:
        raise ValueError("units must be positive")
    bal = usage_balance(account, home)
    if units > bal["units"]:
        raise ValueError(
            f"account {account!r} has {bal['units']} usage credits, "
            f"cannot redeem {units}"
        )

    # FIFO: settle oldest outstanding usage-grant earns first.
    outstanding = _outstanding_usage_earns(account, home)
    remaining = units
    takes: Dict[str, int] = {}
    for earn, left in outstanding:
        if remaining <= 0:
            break
        take = min(left, remaining)
        remaining -= take
        takes[earn["id"]] = take

    burn = ledger.append(
        "burn",
        account,
        "usage_grant",
        reward_id="redeem-usage",
        detail={
            "units": units,
            "purpose": purpose,
            "takes": takes,  # earn-id -> units consumed from that earn
        },
        home=home,
        at=at,
    )
    return {
        "burn_id": burn["id"],
        "redeemed": units,
        "remaining": usage_balance(account, home)["units"],
    }


def active_reductions(
    account: str, month: str, home: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Unexpired tier-reduction earns scoped to one calendar month."""
    settled = _expired_ids(home, account)
    return [
        e
        for e in ledger.read(home)
        if e.get("account") == account
        and e.get("event") == "earn"
        and e.get("reward_type") == "tier_reduction"
        and (e.get("detail") or {}).get("month") == month
        and e.get("id") not in settled
    ]


def month_reduction(
    account: str, month: str, home: Optional[Path] = None
) -> Dict[str, Any]:
    """The account's combined tier pricing reduction for a month.

    Combination policy (documented, not stacked silently): the highest
    percentage wins; fixed-amount reductions add. Sources are listed so
    the advisor layer can show its work.
    """
    reds = active_reductions(account, month, home)
    percent = max([(r.get("detail") or {}).get("percent_off", 0) for r in reds] + [0])
    amount = round(
        sum((r.get("detail") or {}).get("amount_off_usd", 0) for r in reds), 2
    )
    return {
        "account": account,
        "month": month,
        "percent_off": percent,
        "amount_off_usd": amount,
        "sources": [r["rule_id"] for r in reds],
    }


def sweep_expiry(
    current_month: str,
    *,
    account: Optional[str] = None,
    home: Optional[Path] = None,
    at: Optional[str] = None,
) -> Dict[str, Any]:
    """Expire month-scoped reductions whose month is before current_month.

    Monthly reductions expire at month end — badges and usage grants do
    not. Returns {"expired": n}.
    """
    settled: Dict[str, set] = {}
    for se in ledger.read(home):
        if se.get("event") in ("burn", "expire") and se.get("reward_type") != "usage_grant":
            ref = (se.get("detail") or {}).get("settles")
            if ref:
                settled.setdefault(se.get("account"), set()).add(ref)
    expired = 0
    for e in ledger.read(home):
        if e.get("event") != "earn" or e.get("reward_type") != "tier_reduction":
            continue
        if account and e.get("account") != account:
            continue
        month = (e.get("detail") or {}).get("month", "")
        if not month or month >= current_month:
            continue
        if e.get("id") in settled.get(e.get("account"), set()):
            continue
        ledger.append(
            "expire",
            e["account"],
            "tier_reduction",
            reward_id=e.get("reward_id", ""),
            detail={
                "settles": e["id"],
                "month": month,
                "reason": "monthly reduction lapsed at month end",
            },
            rule_id=e.get("rule_id", ""),
            home=home,
            at=at,
        )
        expired += 1
    return {"expired": expired, "current_month": current_month}


def list_badges(
    account: str, home: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Badges the account earned. Badges never expire."""
    return [
        {
            "badge": (e.get("detail") or {}).get("badge"),
            "title": (e.get("detail") or {}).get("title"),
            "rule_id": e.get("rule_id"),
            "earned_at": e.get("at"),
            "citation": (e.get("detail") or {}).get("citation"),
            "basis_ref": e.get("basis_ref"),
        }
        for e in ledger.read(home)
        if e.get("account") == account
        and e.get("event") == "earn"
        and e.get("reward_type") == "badge"
    ]


def balances(account: str, home: Optional[Path] = None) -> Dict[str, Any]:
    """Full reward standing for an account."""
    chain = ledger.verify(home)
    return {
        "account": account,
        "usage": usage_balance(account, home),
        "badges": list_badges(account, home),
        "chain": chain,
    }
