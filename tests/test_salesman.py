"""Law-guard-prove tests for the salesman pipeline.

Each law from levi.salesman.__init__ gets a machine-checkable guard:
L1 condition-honesty, L2 no-fake-scarcity, L3 price-floor, L4 followup-cap,
L5 money-gate.
"""

import pytest

import random

from levi.salesman import MAX_FOLLOWUPS, Deal, Item, new_deal
from levi.salesman.closer import closing_checklist, counter, followup
from levi.salesman.listing import forge_listing
from levi.salesman.pricing import bundle_price, price_ladder
from levi.salesman.signal import score_deals, surface


def _drill() -> Item:
    return Item(
        name="DeWalt 20V Drill",
        category="tools",
        condition="used-good",
        flaws=["chuck has light wear"],
        includes=["2 batteries", "charger"],
        retail_price=149.0,
        cost_basis=18.0,
        quantity=1,
        brand="DeWalt",
    )


# L1: flaws in -> flaws disclosed; no invented claims
def test_l1_flaws_disclosed():
    pack = forge_listing(_drill(), "marketplace", 60.0)
    assert "chuck has light wear" in pack["body"]


def test_l1_no_flaws_says_checked():
    item = _drill()
    item.flaws = []
    pack = forge_listing(item, "marketplace", 60.0)
    assert "No flaws" in pack["body"]


# L2: scarcity only from real quantity
def test_l2_single_quantity_scarcity():
    pack = forge_listing(_drill(), "marketplace", 60.0)
    assert "Only 1 available" in pack["body"]


def test_l2_multi_quantity_no_fake_scarcity():
    item = _drill()
    item.quantity = 5
    pack = forge_listing(item, "marketplace", 60.0)
    assert "Only 1 available" not in pack["body"]
    assert "5 available" in pack["body"]


# L3: floor never crossed
def test_l3_ladder_ordered():
    ladder = price_ladder(_drill())
    assert ladder["floor"] <= ladder["fast"] <= ladder["max"]


def test_l3_below_floor_never_accepted():
    item = _drill()
    ladder = price_ladder(item)
    deal = new_deal(item, ask=ladder["fast"], floor=ladder["floor"])
    c = counter(deal, "would you take $5?")
    assert c.new_ask >= ladder["floor"]
    assert c.escalate_hitl is True
    assert deal.stage != "closed"


def test_l3_floor_cannot_exceed_ask():
    with pytest.raises(ValueError):
        new_deal(_drill(), ask=10.0, floor=20.0)


def test_l3_bundle_respects_floors():
    ladders = {"a": price_ladder(_drill()), "b": price_ladder(_drill())}
    b = bundle_price(ladders, discount=0.35)
    assert b["bundle"] >= b["floor"]


# L4: follow-up cap
def test_l4_max_three_touches():
    item = _drill()
    deal = new_deal(item, ask=60.0, floor=36.0)
    msgs = [followup(deal) for _ in range(MAX_FOLLOWUPS + 2)]
    assert all(m is not None for m in msgs[:MAX_FOLLOWUPS])
    assert msgs[MAX_FOLLOWUPS] is None
    assert deal.stage == "dead"


# L5: closing always needs HITL
def test_l5_closing_requires_hitl():
    item = _drill()
    deal = new_deal(item, ask=60.0, floor=36.0)
    deal.buyer_offer = 50.0
    chk = closing_checklist(deal)
    assert chk["hitl_required"] is True
    assert chk["above_floor"] is True


# Aggression works: real tactics fire
def test_closer_classifies_and_counters():
    item = _drill()
    deal = new_deal(item, ask=60.0, floor=36.0)
    c = counter(deal, "that's too expensive for me")
    assert c.close_type in ("assumptive", "takeaway", "deadline", "bundle", "judo")
    assert c.new_ask >= deal.floor
    assert len(c.reply) > 20


def test_closer_accepts_good_offer_assumptive():
    item = _drill()
    deal = new_deal(item, ask=60.0, floor=36.0)
    c = counter(deal, "I'll give you $55 cash today")
    assert c.close_type == "assumptive"
    assert deal.stage == "closing"


def test_listing_platforms_all_build():
    for plat in ("marketplace", "vinted", "x", "tiktok"):
        pack = forge_listing(_drill(), plat, 60.0)
        assert pack["title"] and pack["body"]
        # hashtags only at the bottom
        body_lines = pack["body"].strip().split("\n")
        assert body_lines[-1].startswith("#")


def test_bad_intake_rejected():
    with pytest.raises(ValueError):
        new_deal(Item(name=""), ask=10.0, floor=5.0)


# ---------------------------------------------------------------------------
# Invariant / property proof checks (law-guard-prove: machine-checkable laws)
# ---------------------------------------------------------------------------

_BANNED_WITHOUT_EVIDENCE = [
    "someone else asked",
    "someone else is circling",
    "moving to the next buyer",
    "another buyer asked",
    "checked and working",
    "below what these go for",
    "first pick of my next drop",
    "pulling the listing",
]


def _all_copy(deal: Deal) -> list:
    """Every buyer-facing string the pipeline can emit for this deal."""
    out = []
    for msg in [
        "too expensive", "best price?", "let me think about it",
        "what's the condition", "where can we meet", "I'll offer $30",
        "I'll offer $100", "hello",
    ]:
        d = Deal(item=deal.item, ask=deal.ask, floor=deal.floor,
                 competing_interest=deal.competing_interest)
        try:
            out.append(counter(d, msg).reply)
        except Exception:
            pass
    d2 = Deal(item=deal.item, ask=deal.ask, floor=deal.floor,
              competing_interest=deal.competing_interest)
    for _ in range(MAX_FOLLOWUPS):
        m = followup(d2)
        if m:
            out.append(m)
    pack = forge_listing(deal.item, "marketplace", deal.ask)
    out.append(pack["body"])
    out.append(pack["title"])
    return out


def test_truth_no_banned_claims_without_evidence():
    """Property: with competing_interest=False, no banned scarcity/claim
    phrase may appear in ANY emitted copy."""
    rng = random.Random(20260922)
    for _ in range(25):
        item = _drill()
        item.quantity = rng.choice([1, 2, 5])
        ask = round(rng.uniform(40, 120), 2)
        floor = round(ask * rng.uniform(0.5, 0.9), 2)
        deal = new_deal(item, ask=ask, floor=floor)  # competing=False default
        for text in _all_copy(deal):
            for banned in _BANNED_WITHOUT_EVIDENCE:
                assert banned.lower() not in text.lower(), (
                    f"banned phrase {banned!r} leaked without evidence: {text[:80]!r}"
                )


def test_truth_evidence_gates_scarcity_language():
    """With competing_interest=True the evidence-gated lines may appear;
    the gate bit itself is what differs."""
    deal_plain = new_deal(_drill(), ask=60.0, floor=36.0)
    deal_ev = new_deal(_drill(), ask=60.0, floor=36.0)
    deal_ev.competing_interest = True
    plain = counter(deal_plain, "let me think about it").reply
    ev = counter(deal_ev, "let me think about it").reply
    assert "another buyer" not in plain.lower()
    assert "another buyer" in ev.lower()


def test_floor_never_crossed_property():
    """Property: over random offers/messages, counter().new_ask >= floor."""
    rng = random.Random(7)
    messages = [
        "would you take $%d?" % n for n in range(1, 200, 7)
    ] + ["too expensive", "best price", "let me think", "hello", "$0", "$999999"]
    for _ in range(60):
        ask = round(rng.uniform(30, 150), 2)
        floor = round(ask * rng.uniform(0.4, 0.95), 2)
        deal = new_deal(_drill(), ask=ask, floor=floor)
        c = counter(deal, rng.choice(messages))
        assert c.new_ask >= deal.floor, (
            f"floor crossed: new_ask={c.new_ask} floor={deal.floor}"
        )


def test_followup_cap_invariant():
    """Property: from any valid state, touches never exceeds MAX_FOLLOWUPS;
    over-cap deals return None without further increments."""
    for start in range(0, MAX_FOLLOWUPS + 1):
        deal = new_deal(_drill(), ask=60.0, floor=36.0)
        deal.touches = start
        for _ in range(5):
            followup(deal)
        assert deal.touches <= MAX_FOLLOWUPS
        assert followup(deal) is None
        assert deal.stage == "dead"
    # pre-violated state: no new touch is ever added
    deal = new_deal(_drill(), ask=60.0, floor=36.0)
    deal.touches = MAX_FOLLOWUPS + 5
    assert followup(deal) is None
    assert deal.touches == MAX_FOLLOWUPS + 5
    assert deal.stage == "dead"


def test_hitl_always_required_property():
    """Property: closing_checklist always demands HITL, any deal state."""
    rng = random.Random(11)
    for _ in range(30):
        ask = round(rng.uniform(20, 200), 2)
        floor = round(ask * rng.uniform(0.4, 0.95), 2)
        deal = new_deal(_drill(), ask=ask, floor=floor)
        deal.buyer_offer = rng.choice([None, floor - 1, floor, ask, ask + 10])
        deal.stage = rng.choice(["listed", "negotiating", "ghosted", "closing"])
        chk = closing_checklist(deal)
        assert chk["hitl_required"] is True
        assert chk["above_floor"] == ((deal.buyer_offer or ask) >= floor)


def test_demandpulse_deterministic_and_transparent():
    """DemandPulse: same deals in -> same scores; breakdown sums to score."""
    def _mk():
        d1 = new_deal(_drill(), ask=60.0, floor=36.0)
        d1.history.append("buyer: too expensive, offer $40")
        d1.buyer_offer = 40.0
        d2 = new_deal(_drill(), ask=80.0, floor=50.0)
        d2.touches = 2
        d2.history.append("buyer: let me think about it")
        return [d1, d2]

    s1 = score_deals(_mk())
    s2 = score_deals(_mk())
    assert [s.score for s in s1] == [s.score for s in s2]
    for s in s1:
        assert abs(sum(s.breakdown.values()) - s.score) < 1e-9
    ranked = surface(s1, top=2)
    assert ranked[0].score >= ranked[1].score
