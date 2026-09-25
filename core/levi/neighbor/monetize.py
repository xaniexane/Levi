"""Fee math for NeighborOS — `monetize.py` (spec §4 system 10, §11).

Corpus bands: standard 8–12%, emergency 12–18%, dynamic by job size
(<$100: 12%; $100–500: 10%; $500–2,000: 8%; >$2,000: 6%).

The floor overrides the bands: **worker_keep_floor = 0.90** is a law,
not a target. Wherever a band rate would leave the worker with less than
the floor, the fee is clamped and ``clamped: True`` is reported — the
platform eats the difference, never the worker. Fee math is inspectable
by both sides (spec §14): every computation returns its full breakdown.
"""

from __future__ import annotations

import math
from typing import Any

from . import policies as policies_mod


def compute_fee(
    amount: float,
    policies: dict[str, Any] | None = None,
    emergency: bool = False,
    pro_worker: bool = False,
) -> dict[str, Any]:
    """Compute the platform fee for a completed + paid job.

    Returns the full breakdown: applied rate, fee, worker keep, keep
    rate, and whether the floor clamp fired. The floor clamp means the
    corpus 12%/18% top bands can never actually take more than the floor
    allows — the band is the ask, the floor is the law.
    """
    if amount <= 0:
        raise ValueError("fee math needs a positive amount")
    policies = policies or {}
    floor = policies_mod.worker_keep_floor(policies)

    rate = policies_mod.fee_rate_for(amount, policies)
    if emergency:
        rate = max(rate, float(policies.get("emergency_rate", 0.15)))
    if pro_worker:
        rate = max(
            0.0, rate - float(policies.get("pro_worker_commission_reduction", 0.02))
        )

    round(1.0 - floor, 10)
    applied_rate = rate
    fee = round(amount * applied_rate, 2)
    worker_keep = round(amount - fee, 2)
    keep_rate = round(worker_keep / amount, 6)
    # The clamp fires on the ROUNDED outcome, not the raw rate: a band
    # rate that merely equals the floor max can still undercut it once
    # the fee is rounded to cents (e.g. $499.99 @ 10%).
    clamped = keep_rate < floor - 1e-9
    if clamped:
        # The floor is a law, not a target: round the WORKER'S keep UP to
        # the cent so cent-rounding can never leave them a hair under.
        # The platform eats the difference, never the worker.
        keep_cents = math.ceil(amount * floor * 100 - 1e-6)
        worker_keep = keep_cents / 100
        fee = round(amount - worker_keep, 2)
        applied_rate = round(fee / amount, 6)
        keep_rate = round(worker_keep / amount, 6)

    return {
        "amount": round(amount, 2),
        "band_rate": round(rate, 4),
        "applied_rate": round(applied_rate, 4),
        "fee": fee,
        "worker_keep": worker_keep,
        "keep_rate": keep_rate,
        "floor": floor,
        "clamped": clamped,
        "emergency": emergency,
        "pro_worker": pro_worker,
    }


def fee_receipt(fee_breakdown: dict[str, Any], gig_id: str, worker_id: str) -> str:
    f = fee_breakdown
    clamp_note = (
        " (floor clamp applied — platform ate the difference)" if f["clamped"] else ""
    )
    return (
        f"FEE RECEIPT — gig {gig_id} / worker {worker_id}\n"
        f"  gross:        ${f['amount']:.2f}\n"
        f"  platform fee: ${f['fee']:.2f} ({f['applied_rate'] * 100:.1f}%){clamp_note}\n"
        f"  worker keeps: ${f['worker_keep']:.2f} ({f['keep_rate'] * 100:.2f}% ≥ {f['floor'] * 100:.0f}% floor)\n"
        f"  band rate was {f['band_rate'] * 100:.1f}%"
        + (" (emergency)" if f["emergency"] else "")
        + (" (pro worker)" if f["pro_worker"] else "")
    )


# -- subscription tiers + revenue report (spec §4 system 10, §11) ----------
def tiers(policies: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Paid-layer subscription tiers from operator config (corpus bands).

    Free core forever (spec §3 law 2): tiers buy convenience (hosting,
    feeds, packs), never access to work itself.
    """
    if policies is None:
        policies = {}
    return list(policies.get("subscription_tiers", []))


def tier_by_id(policies: dict[str, Any], tier_id: str) -> dict[str, Any]:
    for t in tiers(policies):
        if t.get("id") == tier_id:
            return t
    raise KeyError(f"unknown tier {tier_id!r}")


def subscribe(
    store, tier_id: str, subscriber: str, operator: str, now: str | None = None
) -> dict[str, Any]:
    """Record a paid-layer subscription.

    Honesty boundary: this is a ledger record of an agreement, not a
    charge — real billing lives in external plug-ins like all money
    movement (spec §8).
    """
    from . import policies as policies_mod

    policies = policies_mod.load_policies(store)
    tier = tier_by_id(policies, tier_id)
    return store.append(
        "subscriptions",
        {
            "id": store.next_id("subscription"),
            "tier_id": tier_id,
            "tier_name": tier.get("name"),
            "monthly_price": tier.get("monthly_price"),
            "subscriber": subscriber,
            "recorded_by": operator,
            "status": "active",
        },
        now=now,
    )


def cancel_subscription(
    store, subscription_id: str, now: str | None = None
) -> dict[str, Any]:
    """Cancel — appends a new snapshot (history never rewritten)."""
    matches = [
        s for s in store.read_all("subscriptions") if s.get("id") == subscription_id
    ]
    if not matches:
        raise KeyError(f"no subscription {subscription_id}")
    record = dict(matches[-1])
    record.pop("seq", None)
    record.pop("ts", None)
    record["status"] = "cancelled"
    return store.append("subscriptions", record, now=now)


def revenue_report(store) -> dict[str, Any]:
    """Revenue report across streams + the concentration guardrail.

    Corpus long-term guardrail (spec §11): no single revenue stream
    >30–40% of total. Warning at >35%, hard flag at >40%.
    Streams: platform fees (from settlements), subscriptions (monthly,
    active only). All figures are ledger records, not bank balances.
    """
    from . import policies as policies_mod

    policies = policies_mod.load_policies(store)
    latest_settlements: dict[str, dict] = {}
    for s in store.read_all("settlements"):
        latest_settlements[s["id"]] = s
    fee_total = round(
        sum(float(s.get("fee", 0)) for s in latest_settlements.values()), 2
    )
    latest_subs: dict[str, dict] = {}
    for s in store.read_all("subscriptions"):
        latest_subs[s["id"]] = s
    sub_total = round(
        sum(
            float(s.get("monthly_price", 0))
            for s in latest_subs.values()
            if s.get("status") == "active"
        ),
        2,
    )
    streams = {"platform_fees": fee_total, "subscriptions": sub_total}
    total = round(fee_total + sub_total, 2)
    concentrations = {
        name: round(amount / total, 3) if total else 0.0
        for name, amount in streams.items()
    }
    flags = [
        name
        for name, c in concentrations.items()
        if c > float(policies.get("revenue_concentration_flag", 0.40))
    ]
    warnings = [
        name
        for name, c in concentrations.items()
        if float(policies.get("revenue_concentration_warn", 0.35)) < c
        <= float(policies.get("revenue_concentration_flag", 0.40))
    ]
    return {
        "streams": streams,
        "total": total,
        "concentrations": concentrations,
        "warnings": warnings,
        "flags": flags,
        "note": "ledger records, not bank balances — real money moves in external rails",
    }
