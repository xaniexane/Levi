"""The closer — aggressive negotiation engine.

This is the "sell someone the shoes they're wearing" module. It reads a
buyer's message, classifies the objection, and fires back an aggressive but
honest counter. The aggression is in the tactics — assumptive close, takeaway,
deadline, bundle upsell, objection judo — never in deception (L1/L2 hold here
too: no fake competing buyers, no invented deadlines).

Close types:
  assumptive  — act like the sale is decided, only logistics remain
  takeaway    — threaten to pull the deal (only when real: another buyer or floor)
  deadline    — real time-boxed offer (explicit hours, never "today only" twice)
  bundle      — upsell a second item at bundle discount
  judo        — turn the objection into the reason to buy

L3: never counter below floor. L4: ghost follow-ups capped at 3 touches.
L5: closing (meetup/payment) always returns a draft for HITL approval.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional

from levi.salesman import MAX_FOLLOWUPS, Deal, Item

_CLOSE_TYPES = ("assumptive", "takeaway", "deadline", "bundle", "judo")


@dataclass
class Counter:
    reply: str
    new_ask: float
    close_type: str
    escalate_hitl: bool = False


_MONEY = re.compile(r"\$?\s*(\d+(?:\.\d{1,2})?)")

_OBJECTION_PATTERNS = [
    (re.compile(r"\b(too (expensive|much|high)|overpriced|pricey)\b", re.I), "price"),
    (re.compile(r"\b(lower|discount|deal|best price|firm)\b", re.I), "haggle"),
    (re.compile(r"\b(think|consider|let me|maybe|later|get back)\b", re.I), "stall"),
    (re.compile(r"\b(condition|flaw|damage|scratch|work|broken|test)\b", re.I), "condition"),
    (re.compile(r"\b(pickup|meet|deliver|ship|location|where)\b", re.I), "logistics"),
]


def classify_objection(message: str) -> str:
    for pat, label in _OBJECTION_PATTERNS:
        if pat.search(message):
            return label
    return "general"


def parse_offer(message: str) -> Optional[float]:
    m = _MONEY.search(message)
    return float(m.group(1)) if m else None


def _fmt(n: float) -> str:
    return f"${n:.2f}"


def counter(deal: Deal, buyer_message: str, bundle_item: Optional[Item] = None) -> Counter:
    """One aggressive counter. Pure function of (deal, message)."""
    objection = classify_objection(buyer_message)
    offer = parse_offer(buyer_message)
    item = deal.item

    # --- L3: below-floor offer -> never accept, counter at floor or escalate
    if offer is not None and offer < deal.floor:
        deal.buyer_offer = offer
        deal.history.append(f"buyer offered {_fmt(offer)} (below floor {_fmt(deal.floor)})")
        reply = (
            f"I hear you, but {_fmt(offer)} doesn't work — {_fmt(deal.floor)} is the "
            f"absolute lowest I can go on the {item.name}, and honestly it's worth "
            f"every penny at that. Want me to hold it for you at {_fmt(deal.floor)}?"
        )
        return Counter(reply=reply, new_ask=deal.floor, close_type="takeaway",
                       escalate_hitl=True)

    # --- at/above floor offer -> assumptive close, lock it in
    if offer is not None and offer >= deal.floor:
        deal.buyer_offer = offer
        deal.history.append(f"buyer offered {_fmt(offer)}")
        if offer >= deal.ask:
            reply = (
                f"Deal. {_fmt(offer)} for the {item.name} — when can you pick up? "
                f"I'm in Springfield, IL."
            )
        else:
            reply = (
                f"You've got a deal at {_fmt(offer)}. The {item.name} is yours — "
                f"I'll hold it for you. When works for pickup?"
            )
        deal.stage = "closing"
        return Counter(reply=reply, new_ask=offer, close_type="assumptive")

    # --- no number: judo the objection into a close
    if objection == "price":
        mid = round((deal.ask + deal.floor) / 2, 2)
        reply = (
            f"Totally get watching the budget — that's exactly why this one's priced "
            f"to move at {_fmt(deal.ask)}. Tell you what: I can do {_fmt(mid)} — "
            f"that's my move on price. Deal?"
        )
        return Counter(reply=reply, new_ask=mid, close_type="judo")
    if objection == "haggle":
        reply = (
            f"My best price is on the listing: {_fmt(deal.ask)}. That's firm, and "
            f"it's fair for the condition. You in?"
        )
        return Counter(reply=reply, new_ask=deal.ask, close_type="takeaway")
    if objection == "stall":
        # L2: competing-buyer language only when real interest is recorded.
        if deal.competing_interest:
            reply = (
                f"No pressure — but fair warning, I've got {_fmt(deal.ask)} on it and "
                f"another buyer asked about it. I can hold it for you until tonight "
                f"at {_fmt(deal.ask)} — after that it's first come, first served. "
                f"Want me to hold it?"
            )
        else:
            reply = (
                f"No pressure — I've got {_fmt(deal.ask)} on it. I can hold it for "
                f"you until tonight at {_fmt(deal.ask)} — after that it stays listed "
                f"and it's first come, first served. Want me to hold it?"
            )
        return Counter(reply=reply, new_ask=deal.ask, close_type="deadline")
    if objection == "condition":
        flaws = "; ".join(item.flaws) if item.flaws else "none on record"
        reply = (
            f"Good question — full honesty: {flaws}. That's why it's {_fmt(deal.ask)} "
            f"instead of full retail. You're getting the real condition and a real "
            f"price, no surprises at pickup. Still interested?"
        )
        return Counter(reply=reply, new_ask=deal.ask, close_type="judo")
    if objection == "logistics":
        reply = (
            f"Easy — I'm in Springfield, IL. The {item.name} at {_fmt(deal.ask)} — "
            f"want to lock in a pickup time?"
        )
        return Counter(reply=reply, new_ask=deal.ask, close_type="assumptive")
    if objection == "general" and bundle_item is not None:
        reply = (
            f"The {item.name} is {_fmt(deal.ask)} — and since you're looking, I've "
            f"also got a {bundle_item.name}. Take both and I'll knock 20% off the "
            f"pair. Two problems solved in one pickup. Want the bundle?"
        )
        return Counter(reply=reply, new_ask=deal.ask, close_type="bundle")
    # fallback: assumptive
    reply = (
        f"The {item.name} is {_fmt(deal.ask)} and ready to go. "
        f"When do you want to pick it up?"
    )
    return Counter(reply=reply, new_ask=deal.ask, close_type="assumptive")


def followup(deal: Deal) -> Optional[str]:
    """Ghost nudge. L4: None after MAX_FOLLOWUPS touches — then it's dead.

    L2: competing-buyer language is evidence-gated on
    ``deal.competing_interest`` — never invented.
    """
    if deal.touches >= MAX_FOLLOWUPS:
        deal.stage = "dead"
        return None
    deal.touches += 1
    deal.stage = "ghosted"
    if deal.competing_interest:
        nudges = [
            f"Hey — still interested in the {deal.item.name} at {_fmt(deal.ask)}? "
            f"Happy to answer any questions.",
            f"Quick check-in: the {deal.item.name} is still available at {_fmt(deal.ask)}. "
            f"Another buyer asked about it, so let me know today if you want it.",
            f"Last call on the {deal.item.name} — {_fmt(deal.ask)} and it's yours. "
            f"Otherwise I'm moving to the next buyer.",
        ]
    else:
        nudges = [
            f"Hey — still interested in the {deal.item.name} at {_fmt(deal.ask)}? "
            f"Happy to answer any questions.",
            f"Quick check-in: the {deal.item.name} is still available at {_fmt(deal.ask)}. "
            f"Let me know today if you want it — happy to hold it for a few hours.",
            f"Last call on the {deal.item.name} — {_fmt(deal.ask)} and it's yours. "
            f"Otherwise I'm leaving it on the listing.",
        ]
    msg = nudges[min(deal.touches - 1, len(nudges) - 1)]
    deal.history.append(f"followup #{deal.touches}")
    return msg


def closing_checklist(deal: Deal) -> Dict[str, object]:
    """L5: the draft Chauncey approves before money moves. Never auto-sends."""
    return {
        "hitl_required": True,  # L5
        "item": deal.item.name,
        "agreed_price": deal.buyer_offer if deal.buyer_offer is not None else deal.ask,
        "floor": deal.floor,
        "above_floor": (deal.buyer_offer or deal.ask) >= deal.floor,
        "meetup": "Springfield, IL — public spot, daylight",
        "payment": "cash or verified digital on pickup",
        "history": list(deal.history),
    }
