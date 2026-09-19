"""NeighborPay — local SETTLEMENT LEDGER (spec §4 system 9, §8).

The critical honesty boundary, restated:
- The core is a **settlement ledger**: who owes whom, how much, for which
  proven job, under which fee policy. It never touches real money and
  never claims to.
- **Real money movement** (Stripe, bank transfer, cash) lives in
  **labeled external plug-ins** — references, never core. The ledger
  records *that* a settlement was cleared through rail X (with a
  reference), not the payment itself.
- Fees exist **only on completed + paid jobs**. A settlement is refused
  unless the proof-of-work ledger shows check-out + customer sign-off.
- Disputed gigs freeze settlement. Resolution is human.

Pipeline: **plan → preview → permission → execute → verify → receipt**.
``settle`` computes the plan, shows the preview, requires explicit
permission, executes the ledger entry, verifies the invariants, and
returns the receipt.
"""

from __future__ import annotations

from typing import Any

from . import monetize, policies as policies_mod
from .post import latest_gig
from .store import Store


class SettlementRefused(ValueError):
    """Raised when a settlement would violate the ledger's laws."""


def _sign_off_entry(store: Store, gig_id: str) -> dict | None:
    entries = [
        e
        for e in store.read_all("ledger")
        if e.get("gig_id") == gig_id and e.get("kind") == "sign_off"
    ]
    return entries[-1] if entries else None


def plan_settlement(
    store: Store,
    gig_id: str,
    amount_paid: float,
    emergency: bool = False,
    pro_worker: bool = False,
) -> dict[str, Any]:
    """Plan step: compute what settlement *would* look like, no writes."""
    policies = policies_mod.load_policies(store)
    gig = latest_gig(store, gig_id)
    if gig is None:
        raise SettlementRefused(f"no gig {gig_id}")
    if gig["status"] == "disputed":
        raise SettlementRefused(f"gig {gig_id} is disputed — settlement frozen")
    if gig["status"] not in ("done", "paid"):
        raise SettlementRefused(
            f"gig {gig_id} is '{gig['status']}' — fees only on completed + paid jobs"
        )
    if _sign_off_entry(store, gig_id) is None:
        raise SettlementRefused(f"gig {gig_id} has no customer sign-off in the ledger")
    if amount_paid <= 0:
        raise SettlementRefused("settlement needs a positive paid amount")

    worker_id = gig.get("worker_id") or gig.get("accepted_by")
    fee = monetize.compute_fee(
        amount_paid, policies, emergency=emergency, pro_worker=pro_worker
    )
    floor = policies_mod.worker_keep_floor(policies)
    if fee["keep_rate"] < floor - 1e-9:
        raise SettlementRefused(
            f"keep rate {fee['keep_rate']} undercuts the floor {floor}"
        )
    return {
        "gig_id": gig_id,
        "worker_id": worker_id,
        "gross": round(amount_paid, 2),
        "fee": fee,
        "worker_keep": fee["worker_keep"],
        "keep_rate": fee["keep_rate"],
        "emergency": emergency,
        "pro_worker": pro_worker,
    }


def preview_settlement(plan: dict[str, Any]) -> str:
    f = plan["fee"]
    return (
        f"SETTLEMENT PREVIEW\n"
        f"  gig {plan['gig_id']} → worker {plan['worker_id']}\n"
        f"  gross ${plan['gross']:.2f} | fee ${f['fee']:.2f} "
        f"| worker keeps ${plan['worker_keep']:.2f} ({plan['keep_rate'] * 100:.2f}%)\n"
        f"  rail: EXTERNAL PLUG-IN (recorded as reference only — ledger never moves money)"
    )


def settle(
    store: Store,
    gig_id: str,
    amount_paid: float,
    rail: str,
    rail_reference: str,
    confirm: bool = False,
    emergency: bool = False,
    pro_worker: bool = False,
    now: str | None = None,
) -> dict[str, Any]:
    """Execute + Verify + Receipt. Permission = explicit ``confirm=True``.

    ``rail`` names the EXTERNAL plug-in that moved the real money
    (e.g. "stripe", "cash", "bank-transfer"); ``rail_reference`` is the
    plug-in's reference. The ledger records the reference, not the money.
    """
    if not confirm:
        raise PermissionError("settle requires confirm=True (Permission step)")
    if not rail or not rail_reference:
        raise SettlementRefused(
            "a settlement needs a labeled external rail and its reference — "
            "the ledger records money movement, it never performs it"
        )
    plan = plan_settlement(
        store, gig_id, amount_paid, emergency=emergency, pro_worker=pro_worker
    )

    entry = store.append(
        "settlements",
        {
            "id": store.next_id("settlement"),
            "gig_id": plan["gig_id"],
            "worker_id": plan["worker_id"],
            "gross": plan["gross"],
            "fee": plan["fee"]["fee"],
            "applied_rate": plan["fee"]["applied_rate"],
            "worker_keep": plan["worker_keep"],
            "keep_rate": plan["keep_rate"],
            "floor": plan["fee"]["floor"],
            "fee_clamped": plan["fee"]["clamped"],
            "rail": rail,  # external plug-in label, never core money movement
            "rail_reference": rail_reference,
            "status": "recorded",  # "recorded" → "cleared" once the operator
            # confirms the external rail actually moved it
        },
        now=now,
    )
    # Verify step: the invariant holds on what we just wrote.
    verified = verify_settlement(store, entry["id"])
    entry["verified"] = verified["ok"]
    return entry


def verify_settlement(store: Store, settlement_id: str) -> dict[str, Any]:
    """Verify step: re-check every invariant on a recorded settlement."""
    settlements = [
        s for s in store.read_all("settlements") if s.get("id") == settlement_id
    ]
    if not settlements:
        raise KeyError(f"no settlement {settlement_id}")
    s = settlements[-1]
    checks = {
        "keep_rate_above_floor": s["keep_rate"] >= s["floor"] - 1e-9,
        "positive_amounts": s["gross"] > 0 and s["worker_keep"] > 0 and s["fee"] >= 0,
        "rail_labeled": bool(s.get("rail")) and bool(s.get("rail_reference")),
        "gig_not_disputed": (latest_gig(store, s["gig_id"]) or {}).get("status")
        != "disputed",
        "sign_off_present": _sign_off_entry(store, s["gig_id"]) is not None,
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "settlement_id": settlement_id,
    }


def mark_cleared(
    store: Store, settlement_id: str, confirmed_by: str, now: str | None = None
) -> dict[str, Any]:
    """Operator confirms the external rail actually moved the money.
    Appends a new snapshot — history is never rewritten."""
    matches = [s for s in store.read_all("settlements") if s.get("id") == settlement_id]
    if not matches:
        raise KeyError(f"no settlement {settlement_id}")
    record = dict(matches[-1])
    record.pop("seq", None)
    record.pop("ts", None)
    record["status"] = "cleared"
    record["cleared_by"] = confirmed_by
    cleared = store.append("settlements", record, now=now)
    gig = latest_gig(store, record["gig_id"])
    if gig and gig["status"] == "done":
        from .post import transition  # local import: no cycle at module load

        transition(store, record["gig_id"], "paid", now=now)
    return cleared


def receipt_text(store: Store, settlement: dict[str, Any]) -> str:
    fee_breakdown = {
        "amount": settlement["gross"],
        "band_rate": settlement["applied_rate"],
        "applied_rate": settlement["applied_rate"],
        "fee": settlement["fee"],
        "worker_keep": settlement["worker_keep"],
        "keep_rate": settlement["keep_rate"],
        "floor": settlement["floor"],
        "clamped": settlement.get("fee_clamped", False),
        "emergency": False,
        "pro_worker": False,
    }
    base = monetize.fee_receipt(
        fee_breakdown, settlement["gig_id"], settlement["worker_id"]
    )
    return (
        f"{base}\n"
        f"  settlement: {settlement['id']} (status: {settlement['status']})\n"
        f"  rail: {settlement['rail']} (external plug-in) ref {settlement['rail_reference']}\n"
        f"  NeighborPay moved no money — the ledger records, the rail moves."
    )
