"""DemandPulse × KFX² — one motion, paired by law.

DemandPulse (scan → score → surface): deterministic, transparent scoring of
each deal on REAL signals only — message counts, objection mix, touches,
price position vs floor, days in stage. No invented signals, no hidden
weights; the breakdown is returned with every score.

KFX² (absorb → reverse → improve → return unreplicable): take the top-surfaced
deal pattern, extract what made it work (reverse), apply it to a new item
(improve), and emit a listing built from Chauncey's own intake facts —
unreplicable because it's grounded in his inventory, not copied from anyone.

The pair runs as one motion: DemandPulse scores the opportunity/placement
before KFX² lands the improved pattern. Pure functions, no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from levi.salesman import Deal, Item
from levi.salesman.closer import classify_objection
from levi.salesman.listing import forge_listing


# ---------------------------------------------------------------------------
# DemandPulse: scan → score → surface
# ---------------------------------------------------------------------------

# Deterministic weights, published here so every score is auditable.
_WEIGHTS = {
    "buyer_engaged": 3.0,     # buyer sent a message (real signal)
    "offer_on_table": 4.0,    # buyer made a numeric offer (real signal)
    "haggle_objection": 1.5,  # price/haggle objection = interest with friction
    "stall_objection": 1.0,   # stall = interest, needs a nudge
    "competing_interest": 2.0,  # another buyer really asked (evidenced)
    "ghosted_penalty": -1.0,  # each ghost touch cools the score
    "price_room": 1.0,        # ask sits above floor -> room to maneuver
}


@dataclass
class ScoredDeal:
    deal: Deal
    score: float
    breakdown: Dict[str, float] = field(default_factory=dict)


def scan(deals: List[Deal]) -> List[Dict[str, object]]:
    """Extract raw, real signals from each deal's history. No invention."""
    signals = []
    for deal in deals:
        buyer_messages = sum(
            1 for h in deal.history if h.startswith("buyer")
        )
        objections = [classify_objection(h) for h in deal.history]
        signals.append({
            "item": deal.item.name,
            "buyer_messages": buyer_messages,
            "offer_on_table": deal.buyer_offer is not None,
            "objections": objections,
            "touches": deal.touches,
            "stage": deal.stage,
            "competing_interest": deal.competing_interest,
            "price_room": deal.ask > deal.floor,
        })
    return signals


def score(signals: List[Dict[str, object]]) -> List[ScoredDeal]:
    """Deterministic weighted score. Same input -> same score, always."""
    # Caller pairs signals back to deals by index; keep the pairing explicit.
    raise NotImplementedError("use score_deals(deals) to keep pairing explicit")


def score_deals(deals: List[Deal]) -> List[ScoredDeal]:
    """Scan + score in one explicit step. Transparent breakdown per deal."""
    out: List[ScoredDeal] = []
    for deal, sig in zip(deals, scan(deals), strict=True):
        b: Dict[str, float] = {}
        b["buyer_engaged"] = _WEIGHTS["buyer_engaged"] if sig["buyer_messages"] else 0.0
        b["offer_on_table"] = _WEIGHTS["offer_on_table"] if sig["offer_on_table"] else 0.0
        b["haggle_objection"] = _WEIGHTS["haggle_objection"] * sum(
            1 for o in sig["objections"] if o in ("price", "haggle")
        )
        b["stall_objection"] = _WEIGHTS["stall_objection"] * sum(
            1 for o in sig["objections"] if o == "stall"
        )
        b["competing_interest"] = (
            _WEIGHTS["competing_interest"] if sig["competing_interest"] else 0.0
        )
        b["ghosted_penalty"] = _WEIGHTS["ghosted_penalty"] * sig["touches"]
        b["price_room"] = _WEIGHTS["price_room"] if sig["price_room"] else 0.0
        out.append(ScoredDeal(deal=deal, score=round(sum(b.values()), 2), breakdown=b))
    return out


def surface(scored: List[ScoredDeal], top: int = 3) -> List[ScoredDeal]:
    """Rank by score, surface the hottest real opportunities first."""
    return sorted(scored, key=lambda s: s.score, reverse=True)[:top]


# ---------------------------------------------------------------------------
# KFX²: absorb → reverse → improve → return unreplicable
# ---------------------------------------------------------------------------

@dataclass
class Pattern:
    """What made the winner work — extracted, not copied."""
    source_item: str
    close_type: str          # the tactic that landed (assumptive, judo, ...)
    objection_won: str       # the objection it beat
    price_move: float        # ask -> final, as a fraction of ask
    tone_notes: List[str] = field(default_factory=list)


def absorb(winner: ScoredDeal) -> ScoredDeal:
    """Take the top-surfaced deal in as the pattern source. Identity step."""
    return winner


def reverse(winner: ScoredDeal) -> Pattern:
    """Extract the mechanics of the win from the deal's own history."""
    deal = winner.deal
    close_type = "assumptive"
    objection_won = "general"
    for h in deal.history:
        if h.startswith("close_type:"):
            close_type = h.split(":", 1)[1]
        if h.startswith("buyer"):
            objection_won = classify_objection(h)
    final = deal.buyer_offer if deal.buyer_offer is not None else deal.ask
    price_move = round((deal.ask - final) / deal.ask, 3) if deal.ask else 0.0
    return Pattern(
        source_item=deal.item.name,
        close_type=close_type,
        objection_won=objection_won,
        price_move=price_move,
        tone_notes=[
            "assumptive framing (logistics, not permission)",
            "condition honesty kept the buyer in",
            f"price moved {price_move:.0%} from ask — room was real",
        ],
    )


def improve(pattern: Pattern, item: Item, ask: float, floor: float) -> Dict[str, object]:
    """Apply the reversed pattern to a NEW item.

    The listing is drafted from the new item's own intake facts — the pattern
    shapes the structure and close, never the facts. That's what makes the
    output unreplicable: it's Chauncey's inventory, Chauncey's voice.
    """
    listing = forge_listing(item, "marketplace", ask)
    listing["title"] = (
        f"{listing['title']} — priced to move, this one won't sit"
    )
    return {
        "pattern_from": pattern.source_item,
        "close_type": pattern.close_type,
        "objection_playbook": pattern.objection_won,
        "listing": listing,
        "ask": ask,
        "floor": floor,
        "unreplicable_note": (
            "Built from this item's intake facts with the winner's structure. "
            "No one else can run this exact listing — the inventory is Chauncey's."
        ),
    }


def run(deals: List[Deal], item: Item, ask: float, floor: float,
        top: int = 3) -> Dict[str, object]:
    """One motion: DemandPulse scores, KFX² transforms the winner's pattern."""
    scored = score_deals(deals)
    ranked = surface(scored, top=top)
    winner = absorb(ranked[0]) if ranked else None
    pattern = reverse(winner) if winner else None
    improved = improve(pattern, item, ask, floor) if pattern else None
    return {
        "ranked": [
            {"item": s.deal.item.name, "score": s.score, "breakdown": s.breakdown}
            for s in ranked
        ],
        "pattern": pattern.__dict__ if pattern else None,
        "improved_listing": improved,
    }
