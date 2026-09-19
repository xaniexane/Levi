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

    floor_max_rate = round(1.0 - floor, 10)
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
