"""LEVI job organ — GIG / FAST-CASH parallel track. Block grabbers, rules,
income.

Runs alongside the main job pipeline: gig offers (delivery blocks,
shift pickups, task gigs) get ingested, evaluated against the human's
auto-accept RULES, and only ever accepted with explicit human approval.
"Block grabbers" here draft and stage the grab — the human's tap is the
grab. Income is tracked per gig so the track stays honest about what it
earns.

Same law as Apply: nothing here accepts, claims, or books anything on
its own. Rules EVALUATE; the human DECIDES.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

from levi.automation.hitl import (
    Gate,
    GateKind,
    GateRequest,
)

from .store import Warehouse

Responder = Callable[[GateRequest], Dict[str, Any]]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_offer(
    warehouse: Warehouse,
    platform: str,
    title: str,
    pay: float = 0.0,
    pay_unit: str = "block",
    window_start: str = "",
    window_end: str = "",
    location: str = "",
    distance_mi: float = 0.0,
    expires_at: str = "",
    notes: str = "",
) -> Dict[str, Any]:
    if not platform.strip() or not title.strip():
        raise ValueError("platform and title are required")
    return warehouse.add_row(
        "gig_offers",
        {
            "platform": platform.strip(),
            "title": title.strip(),
            "pay": pay,
            "pay_unit": pay_unit,
            "window_start": window_start,
            "window_end": window_end,
            "location": location,
            "distance_mi": distance_mi,
            "expires_at": expires_at,
            "status": "open",
            "rule_verdict": "unevaluated",
            "notes": notes,
        },
    )


def evaluate_rules(offer: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate auto-accept rules against one offer. Returns a verdict,
    never an acceptance. Rules keys: min_pay, max_distance_mi,
    platforms (list), require_window (bool)."""
    reasons: List[str] = []
    ok = True

    min_pay = rules.get("min_pay")
    if min_pay is not None:
        try:
            if float(offer.get("pay") or 0) < float(min_pay):
                ok = False
                reasons.append(f"pay {offer.get('pay')} < min {min_pay}")
        except (TypeError, ValueError):
            ok = False
            reasons.append("pay unparseable")

    max_dist = rules.get("max_distance_mi")
    if max_dist is not None:
        try:
            if float(offer.get("distance_mi") or 0) > float(max_dist):
                ok = False
                reasons.append(f"distance {offer.get('distance_mi')} > max {max_dist}")
        except (TypeError, ValueError):
            pass  # unknown distance is not a veto

    platforms = rules.get("platforms") or []
    if platforms and str(offer.get("platform") or "").lower() not in [
        str(p).lower() for p in platforms
    ]:
        ok = False
        reasons.append(f"platform {offer.get('platform')} not in allowed list")

    if rules.get("require_window") and not (
        offer.get("window_start") and offer.get("window_end")
    ):
        ok = False
        reasons.append("no time window on offer")

    verdict = "would-accept" if ok else "would-skip"
    return {"verdict": verdict, "ok": ok, "reasons": reasons or ["all rules passed"]}


def evaluate_offers(
    warehouse: Warehouse, rules: Dict[str, Any], dry_run: bool = True
) -> Dict[str, Any]:
    """Run the rules over every open offer. Writes verdicts unless dry-run."""
    report = {"dry_run": dry_run, "evaluated": 0, "would_accept": 0, "items": []}
    for offer in warehouse.list_rows("gig_offers"):
        if offer.get("status") != "open":
            continue
        verdict = evaluate_rules(offer, rules)
        report["evaluated"] += 1
        if verdict["ok"]:
            report["would_accept"] += 1
        if not dry_run:
            warehouse.update_row(
                "gig_offers", offer["id"], {"rule_verdict": verdict["verdict"]}
            )
        report["items"].append(
            {
                "offer_id": offer["id"],
                "title": offer.get("title"),
                "verdict": verdict["verdict"],
                "reasons": verdict["reasons"],
            }
        )
    return report


def accept_offer(
    warehouse: Warehouse,
    offer_row_id: int,
    responder: Responder,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Stage a block grab: APPROVAL gate, human decides. On approval the
    offer is marked ``accepted-pending-grab`` — the human still taps the
    grab in the gig app. The organ never touches the gig platform."""
    offer = warehouse.get_row("gig_offers", offer_row_id)
    if offer.get("status") != "open":
        raise ValueError(
            f"offer {offer_row_id} is not open (status={offer.get('status')})"
        )
    gate = Gate(
        GateRequest(
            minion_id="jobs.gig.accept-offer",
            kind=GateKind.APPROVAL,
            prompt=(
                f"Accept gig offer? {offer.get('title')} @ {offer.get('platform')} "
                f"— pay {offer.get('pay')} ({offer.get('pay_unit')}), "
                f"window {offer.get('window_start')}–{offer.get('window_end')}"
            ),
            context={"offer_id": offer_row_id, "dry_run": dry_run},
        )
    )
    result = gate.require(responder)
    outcome: Dict[str, Any] = {
        "offer_id": offer_row_id,
        "approved": True,
        "dry_run": dry_run,
        "gate": result.to_dict(),
    }
    if not dry_run:
        warehouse.update_row(
            "gig_offers", offer_row_id, {"status": "accepted-pending-grab"}
        )
        warehouse.log_automation(
            "gig-accept",
            "Success",
            tool_used="jobs.gig",
            target_platform=str(offer.get("platform") or ""),
            job_title_processed=str(offer.get("title") or ""),
            notes=f"offer row id={offer_row_id}; human grab still required in app",
        )
    return outcome


def decline_offer(
    warehouse: Warehouse, offer_row_id: int, reason: str = ""
) -> Dict[str, Any]:
    return warehouse.update_row(
        "gig_offers", offer_row_id, {"status": "declined", "notes": reason}
    )


# -- income tracker ------------------------------------------------------


def log_income(
    warehouse: Warehouse,
    platform: str,
    description: str,
    amount: float,
    date: str = "",
    hours_worked: float = 0.0,
    notes: str = "",
) -> Dict[str, Any]:
    try:
        amount_f = float(amount)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"amount must be numeric: {amount!r}") from exc
    return warehouse.add_row(
        "gig_income",
        {
            "date": date or _utcnow()[:10],
            "platform": platform,
            "description": description,
            "amount": amount_f,
            "hours_worked": hours_worked,
            "notes": notes,
        },
    )


def income_summary(warehouse: Warehouse) -> Dict[str, Any]:
    rows = warehouse.list_rows("gig_income")
    total = sum(float(r.get("amount") or 0) for r in rows)
    hours = sum(float(r.get("hours_worked") or 0) for r in rows)
    by_platform: Dict[str, float] = {}
    for r in rows:
        key = str(r.get("platform") or "unknown")
        by_platform[key] = by_platform.get(key, 0.0) + float(r.get("amount") or 0)
    return {
        "gigs": len(rows),
        "total": round(total, 2),
        "hours": round(hours, 2),
        "per_hour": round(total / hours, 2) if hours else 0.0,
        "by_platform": {k: round(v, 2) for k, v in by_platform.items()},
    }
