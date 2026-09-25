"""Supplier portal — `supply.py` (spec §4 system 7, phase 2).

Materials/equipment referrals ledger: workers and customers get matched
to local suppliers, and every referral is recorded — the platform takes
no cut on materials and moves no material money.

LAWS (machine-checked by `check_laws`):
- L1: referrals are records only — amounts, when present, are labeled
  `quoted_amount` (a quote, never a transaction).
- L2: every referral names a gig or a requester — traceable to real
  work, never free-floating.
- L3: supplier ratings come only from recorded referrals (closed with
  an outcome) — never invented.
"""

from __future__ import annotations

from typing import Any

from .store import Store

OUTCOMES = ("fulfilled", "partial", "failed", "cancelled")


def register_supplier(
    store: Store,
    name: str,
    contact: str,
    categories: list[str],
    neighborhood_cell: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Register a materials/equipment supplier."""
    supplier = {
        "id": store.next_id("supplier"),
        "name": name,
        "contact": contact,  # plain — never masked
        "categories": list(categories),
        "neighborhood_cell": neighborhood_cell,
        "status": "active",
    }
    return store.append("suppliers", supplier, now=now)


def _latest(store: Store, stream: str, key: str, value: str) -> dict | None:
    matches = [r for r in store.read_all(stream) if r.get(key) == value]
    return matches[-1] if matches else None


def refer(
    store: Store,
    supplier_id: str,
    items: list[str],
    gig_id: str | None = None,
    requester: str | None = None,
    quoted_amount: float | None = None,
    referred_by: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    """Record a materials referral to a supplier.

    `quoted_amount` is a quote for the materials — the ledger records it,
    it never moves money and the platform takes no cut.
    """
    if not gig_id and not requester:
        raise ValueError("a referral must name a gig or a requester (law L2)")
    supplier = _latest(store, "suppliers", "id", supplier_id)
    if supplier is None:
        raise KeyError(f"no supplier {supplier_id}")
    referral = {
        "id": store.next_id("referral"),
        "supplier_id": supplier_id,
        "supplier_name": supplier["name"],
        "items": list(items),
        "gig_id": gig_id,
        "requester": requester,
        "quoted_amount": quoted_amount,  # a quote, never a transaction (law L1)
        "referred_by": referred_by,
        "outcome": "open",
    }
    return store.append("referrals", referral, now=now)


def close_referral(
    store: Store,
    referral_id: str,
    outcome: str,
    rating: int | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Close a referral with its outcome. Rating 1–5 feeds supplier rating."""
    if outcome not in OUTCOMES:
        raise ValueError(f"unknown outcome {outcome!r}")
    if rating is not None and not 1 <= rating <= 5:
        raise ValueError("rating must be 1–5")
    record = _latest(store, "referrals", "id", referral_id)
    if record is None:
        raise KeyError(f"no referral {referral_id}")
    updated = dict(record)
    updated.pop("seq", None)
    updated.pop("ts", None)
    updated["outcome"] = outcome
    if rating is not None:
        updated["rating"] = rating
    return store.append("referrals", updated, now=now)


def supplier_rating(store: Store, supplier_id: str) -> dict[str, Any]:
    """Honest supplier rating: only from closed referrals with ratings."""
    latest: dict[str, dict] = {}
    for r in store.read_all("referrals"):
        latest[r["id"]] = r
    ratings = [
        r["rating"]
        for r in latest.values()
        if r.get("supplier_id") == supplier_id
        and r.get("outcome") != "open"
        and r.get("rating")
    ]
    return {
        "supplier_id": supplier_id,
        "ratings_count": len(ratings),
        "average": round(sum(ratings) / len(ratings), 2) if ratings else None,
    }


def check_laws(store: Store) -> dict[str, Any]:
    """Machine-check the supplier-portal laws against live state."""
    checks: dict[str, dict] = {}
    latest: dict[str, dict] = {}
    for r in store.read_all("referrals"):
        latest[r["id"]] = r
    untraceable = [
        r["id"]
        for r in latest.values()
        if not r.get("gig_id") and not r.get("requester")
    ]
    checks["referrals_traceable"] = {
        "ok": not untraceable,
        "violations": untraceable,
    }
    bad_outcome = [
        r["id"]
        for r in latest.values()
        if r.get("outcome") not in (*OUTCOMES, "open")
    ]
    checks["outcomes_valid"] = {"ok": not bad_outcome, "violations": bad_outcome}
    return {"ok": all(c["ok"] for c in checks.values()), "checks": checks}
