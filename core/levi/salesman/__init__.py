"""Salesman pipeline — the closer. Ambitious, aggressive, honest.

Built on Chauncey's "Resale catalog agent" gem (photo-to-listing, ultra-sales
engine, pricing engine, HITL checkpoints) and taken further: a full pipeline
from intake to close that can sell someone the shoes they're wearing.

LAWS (law-guard-prove: declared first, enforced by tests)
--------------------------------------------------------
L1 CONDITION-HONESTY — every claim in a listing must trace to intake facts.
    Flaws in, flaws disclosed. No invented features, no polished-over damage.
L2 NO-FAKE-SCARCITY — urgency/scarcity language only from real inventory
    counts (quantity field). "Only 1 left" requires quantity == 1.
L3 PRICE-FLOOR — the pipeline never proposes or accepts below floor.
    Below-floor offers get countered or escalated to HITL, never auto-accepted.
L4 FOLLOWUP-CAP — at most 3 touches on a ghosted buyer. Aggressive is not spam.
L5 MONEY-GATE — no payment or meetup commitment without HITL confirmation.
    The pipeline drafts; Chauncey approves.

Where the aggression lives: speed (instant counters), assumptive closes,
takeaway, deadline, bundle upsell, objection judo. Never in deception —
half-truths are lies that disarm people, and this salesman doesn't lie.

Pipeline stages: intake -> listing -> pricing -> prospect -> negotiate -> followup -> close.
All stages are pure functions of their inputs: no network, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Laws as data (machine-checkable in tests)
# ---------------------------------------------------------------------------

MAX_FOLLOWUPS = 3  # L4


@dataclass
class Item:
    """Intake facts. Everything downstream must trace back to these."""

    name: str
    category: str = "general"
    condition: str = "used-good"  # new | like-new | used-good | used-fair | parts
    flaws: List[str] = field(default_factory=list)
    includes: List[str] = field(default_factory=list)
    retail_price: Optional[float] = None
    cost_basis: float = 0.0
    quantity: int = 1
    size: str = ""
    brand: str = ""

    def validate(self) -> List[str]:
        problems = []
        if not self.name.strip():
            problems.append("name is required")
        if self.cost_basis < 0:
            problems.append("cost_basis cannot be negative")
        if self.quantity < 1:
            problems.append("quantity must be >= 1")
        if self.condition not in ("new", "like-new", "used-good", "used-fair", "parts"):
            problems.append(f"unknown condition {self.condition!r}")
        return problems


@dataclass
class Deal:
    """Negotiation state for one buyer."""

    item: Item
    ask: float  # current listed/asking price
    floor: float  # L3: never go below
    buyer_offer: Optional[float] = None
    touches: int = 0  # L4: follow-up counter
    stage: str = "listed"  # listed | negotiating | ghosted | closing | closed | dead
    history: List[str] = field(default_factory=list)
    # L2 evidence gate: real signal that another buyer exists / asked.
    # Scarcity language is only emitted when this is True. Default False
    # keeps every draft honest until Chauncey records real interest.
    competing_interest: bool = False
    # L2 evidence gate: real signal that another buyer exists / asked.
    # Scarcity language is only emitted when this is True. Default False
    # keeps every draft honest until Chauncey records real interest.
    competing_interest: bool = False
    # L2 evidence gate: real signal that another buyer exists / asked.
    # Scarcity language is only emitted when this is True. Default False
    # keeps every draft honest until Chauncey records real interest.
    competing_interest: bool = False


def new_deal(item: Item, ask: float, floor: float) -> Deal:
    problems = item.validate()
    if problems:
        raise ValueError(f"bad intake: {'; '.join(problems)}")
    if ask <= 0 or floor <= 0:
        raise ValueError("ask and floor must be positive")
    if floor > ask:
        raise ValueError("floor cannot exceed ask")
    return Deal(item=item, ask=ask, floor=floor)
