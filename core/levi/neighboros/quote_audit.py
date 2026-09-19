"""Adversarial quote audit — the quote argues with itself first.

Before a quote reaches the client, it passes a second-pass
adversarial review built on the weigh engine
(:mod:`levi.engines.weigh`): the case FOR the quote (advisor band,
itemization, scope clarity) is weighed against the case AGAINST it
(over-band pricing, missing line items, rush timelines, vague scope).
The quote ships only when the engine leans "for" with calibrated
confidence >= ``PASS_CONFIDENCE``; otherwise it is flagged for human
review with the full trace.

Advisory only — the engine judges, the keeper decides. But an
unflagged quote has survived its own cross-examination.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from levi.engines import registry  # noqa: F401  (builtins self-register)

PASS_CONFIDENCE = 0.6


def _item(label: str, amount: Any) -> Dict[str, Any]:
    return {"label": str(label), "amount": float(amount)}


def audit_quote(quote: Dict[str, Any], home: Optional[object] = None) -> Dict[str, Any]:
    """Run the adversarial second pass over a quote.

    ``quote``: {"quote_id", "price_usd", "band_low", "band_high",
    "line_items": [{"label", "amount"}], "timeline_days": int,
    "scope_notes": str}. ``home`` is accepted for API symmetry and ignored.
    """
    if not isinstance(quote, dict):
        raise ValueError("quote must be a dict")
    quote_id = str(quote.get("quote_id") or "")
    if not quote_id.strip():
        raise ValueError("quote['quote_id'] must be non-empty")
    price = float(quote.get("price_usd", 0) or 0)
    band_low = float(quote.get("band_low", 0) or 0)
    band_high = float(quote.get("band_high", 0) or 0)
    if price <= 0:
        raise ValueError("quote['price_usd'] must be positive")
    items = quote.get("line_items") or []
    if not isinstance(items, list):
        raise ValueError("quote['line_items'] must be a list")
    timeline = quote.get("timeline_days")
    scope_notes = str(quote.get("scope_notes") or "").strip()

    for_evidence: List[Dict[str, Any]] = []
    against_evidence: List[Dict[str, Any]] = []

    if band_low > 0 and band_high >= band_low:
        if band_low <= price <= band_high:
            for_evidence.append({
                "point": f"price ${price:.2f} sits inside the advisor band "
                         f"${band_low:.2f}–${band_high:.2f}",
                "weight": 2.0})
        elif price > band_high:
            against_evidence.append({
                "point": f"price ${price:.2f} exceeds the advisor band top "
                         f"${band_high:.2f} — over-band risk",
                "weight": 2.5})
        else:
            against_evidence.append({
                "point": f"price ${price:.2f} undercuts the advisor band floor "
                         f"${band_low:.2f} — underpricing / scope-creep risk",
                "weight": 1.0})
    else:
        against_evidence.append({
            "point": "no advisor band supplied — price is unanchored",
            "weight": 1.5})

    if items:
        item_total = sum(float(i.get("amount", 0) or 0) for i in items
                         if isinstance(i, dict))
        for_evidence.append({
            "point": f"{len(items)} itemized line items totaling ${item_total:.2f} — "
                     "the client can see what they pay for",
            "weight": 1.5})
        if abs(item_total - price) > 0.01:
            # Objective error, not a judgment call: the math does not
            # reconcile, so the quote is flagged outright.
            return {
                "quote_id": quote_id,
                "verdict": "flagged",
                "lean": "against",
                "confidence": 1.0,
                "margin": -1.0,
                "for_points": len(for_evidence),
                "against_points": 1,
                "trace": [f"proposition: quote {quote_id} at ${price:.2f} is fair "
                          f"and shippable",
                          f"HARD FLAG: line items total ${item_total:.2f} but the "
                          f"quote says ${price:.2f} — the math does not reconcile"],
                "note": "flagged — line items do not reconcile with the quoted "
                        "price; human review required",
            }
    else:
        against_evidence.append({
            "point": "no line items — a lump sum with nothing itemized",
            "weight": 2.0})

    if scope_notes:
        for_evidence.append({
            "point": "scope notes present — the work boundary is written down",
            "weight": 1.0})
    else:
        against_evidence.append({
            "point": "no scope notes — the boundary of the work is verbal",
            "weight": 1.0})

    if isinstance(timeline, (int, float)) and timeline >= 1:
        for_evidence.append({
            "point": f"timeline of {int(timeline)} days is stated",
            "weight": 0.5})
    else:
        against_evidence.append({
            "point": "no credible timeline — delivery date is a guess",
            "weight": 1.5})

    result = registry.run("weigh", {
        "proposition": f"quote {quote_id} at ${price:.2f} is fair and shippable",
        "for_evidence": for_evidence,
        "against_evidence": against_evidence,
    })
    verdict = result.verdict
    lean = verdict.get("lean")
    # Confidence rides on the EngineResult, not inside the verdict dict.
    confidence = float(result.confidence or 0.0)
    passed = lean == "for" and confidence >= PASS_CONFIDENCE
    return {
        "quote_id": quote_id,
        "verdict": "pass" if passed else "flagged",
        "lean": lean,
        "confidence": round(confidence, 3),
        "margin": round(float(verdict.get("margin", 0.0) or 0.0), 3),
        "for_points": len(for_evidence),
        "against_points": len(against_evidence),
        "trace": result.trace,
        "note": ("survived adversarial review" if passed
                 else "flagged — human review required before this reaches the client"),
    }
