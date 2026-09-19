"""Site Lift tailored teams — the crew that fills the gaps the lift finds.

The lift report diagnoses; the team pack ships the crew that fixes it.
Chauncey's canon: "Site Lift must ship with TAILORED TEAMS for
businesses + other specialized packs (not just the lift report — the
crew that fills the gaps it finds)". The lift output becomes one offer:
report + crew.

This module holds the data-driven team packs. A pack is a business
type (restaurant, salon, shop, trades, generic) with named roles; each
role maps onto lift finding categories (measured check ids from
levi.services.site_lift), carries an install checklist, and declares
handoff/escalation rules.

No business names are hardcoded — packs are keyed by business TYPE,
and matching (levi.services.site_team_match) binds a pack to a specific
report.

Money is paper-only: quotes come from the founder price advisor, never
a charge, and payment still rides the Cybrus gateway only.
"""

from __future__ import annotations

from typing import Any, Dict, List

from levi.services.site_lift import FEATURE_CHECKS, FOUNDATION_CHECKS

# Every measured check id the roles may claim to cover. Attested checks
# (s-*, c-goal-*, c-showcase) are never claimed — crew members answer
# measured gaps, not attestations.
KNOWN_CHECK_IDS = frozenset(
    [cid for cid, _label, _goals, _probe in FOUNDATION_CHECKS + FEATURE_CHECKS]
)


class TeamError(ValueError):
    """Raised when a team pack is misdefined."""


def _role(
    rid: str,
    title: str,
    purpose: str,
    covers: List[str],
    checklist: List[str],
    escalation: str,
) -> Dict[str, Any]:
    return {
        "id": rid,
        "title": title,
        "purpose": purpose,
        "covers": list(covers),
        "checklist": list(checklist),
        "escalation": escalation,
    }


GREETER = lambda covers: _role(
    "greeter",
    "Greeter",
    "First contact: answers calls/chats, routes the visitor to the "
    "right crew member, never leaves a question hanging.",
    covers,
    [
        "Wire greeting to the site's contact paths (tel link / form / chat).",
        "Load the business's hours, address, and service list into answers.",
        "Define the route table: who gets booking intents, price intents, support intents.",
        "Log every unanswered question for the owner to review weekly.",
    ],
    "Unknown or angry visitor -> hand off to the human owner with the "
    "transcript; never argue, never invent policy.",
)

BOOKER = lambda covers: _role(
    "booker",
    "Reservation / appointment booker",
    "Turns booking intent into confirmed slots: answers availability, "
    "takes the booking, sends confirmation, handles changes.",
    covers,
    [
        "Connect the booking source of truth (calendar / booking tool / owner inbox).",
        "Define slot rules: lead time, buffer, cancellation window, no-show policy.",
        "Confirm every booking back to the customer in writing.",
        "Queue owner approval for anything outside the slot rules.",
    ],
    "Double-book risk, custom requests, or refunds -> hold the slot and "
    "escalate to the human owner; never confirm what the rules don't allow.",
)

FAQ_ANSWERER = lambda covers: _role(
    "faq-answerer",
    "FAQ answerer",
    "Answers the recurring questions the site never wrote down: "
    "prices, policies, what to expect, how it works.",
    covers,
    [
        "Collect the top 20 asked questions from the owner (voice memo is fine).",
        "Write answers in the owner's voice; get owner sign-off before going live.",
        "File every new question it couldn't answer into the weekly review pile.",
        "Keep a price/menu sheet current — stale prices are the #1 trust killer.",
    ],
    "Price disputes, policy exceptions, or anything it can't source -> "
    "answer honestly ('I don't know, let me get the owner') and escalate "
    "within one business day.",
)

REVIEW_RESPONDER = lambda covers: _role(
    "review-responder",
    "Review responder",
    "Watches reviews and social proof, thanks the happy, de-escalates "
    "the unhappy, and feeds patterns back to the owner.",
    covers,
    [
        "Monitor the review surfaces the business actually uses (Google, Yelp, Facebook).",
        "Reply to every new review within 48 hours in the owner's voice.",
        "Never repeat a complaint's specifics back in public — move it to a private channel.",
        "Send the owner a weekly digest: themes, repeat complaints, praise to repeat.",
    ],
    "Threats, fake-review attacks, or anything legal -> stop replying and "
    "escalate to the human owner immediately.",
)

ORDER_TRACKER = lambda covers: _role(
    "order-tracker",
    "Order tracker",
    "Answers 'where's my order' before it gets asked: order status, "
    "pickup/delivery windows, and reorder nudges.",
    covers,
    [
        "Connect the order source of truth (POS, order book, inbox).",
        "Define status vocabulary: received, in progress, ready, out for delivery.",
        "Proactive update on every status change; no silent orders.",
        "Flag stalled orders (>2x normal lead time) to the owner daily.",
    ],
    "Lost, damaged, or refunded orders -> escalate to the human owner; "
    "never promise compensation without owner approval.",
)


def _pack(pack_id: str, title: str, blurb: str, roles: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"id": pack_id, "title": title, "blurb": blurb, "roles": list(roles)}


TEAM_PACKS: Dict[str, Dict[str, Any]] = {
    "restaurant": _pack(
        "restaurant",
        "Restaurant crew",
        "For places that seat people: greet, take the reservation, "
        "answer the menu questions, handle the reviews.",
        [
            GREETER(["f-contact", "f-cta"]),
            BOOKER(["t-booking", "f-cta"]),
            FAQ_ANSWERER(["t-faq", "t-pricing"]),
            REVIEW_RESPONDER(["t-proof"]),
        ],
    ),
    "salon": _pack(
        "salon",
        "Salon crew",
        "For appointment businesses: book the chair, answer the service "
        "questions, keep the reviews warm.",
        [
            GREETER(["f-contact", "f-cta"]),
            BOOKER(["t-booking", "f-cta"]),
            FAQ_ANSWERER(["t-faq", "t-pricing"]),
            REVIEW_RESPONDER(["t-proof"]),
        ],
    ),
    "shop": _pack(
        "shop",
        "Shop crew",
        "For retail: greet, track orders, answer product questions, "
        "keep the reviews warm.",
        [
            GREETER(["f-contact", "f-cta"]),
            ORDER_TRACKER(["t-booking"]),
            FAQ_ANSWERER(["t-faq", "t-pricing"]),
            REVIEW_RESPONDER(["t-proof"]),
        ],
    ),
    "trades": _pack(
        "trades",
        "Trades crew",
        "For contractors and field services: book the estimate, answer "
        "the scope questions, keep the reviews warm.",
        [
            GREETER(["f-contact", "f-cta"]),
            BOOKER(["t-booking", "f-cta"]),
            FAQ_ANSWERER(["t-faq", "t-pricing"]),
            REVIEW_RESPONDER(["t-proof"]),
        ],
    ),
    "generic": _pack(
        "generic",
        "Generic crew",
        "For any business type: contact, booking, FAQ, reviews — the "
        "four gaps every small site shares.",
        [
            GREETER(["f-contact", "f-cta"]),
            BOOKER(["t-booking"]),
            FAQ_ANSWERER(["t-faq", "t-pricing"]),
            REVIEW_RESPONDER(["t-proof"]),
        ],
    ),
}

# Deterministic pack preference order: ties in matching break toward
# the most specific pack first, generic last.
PACK_ORDER = ("restaurant", "salon", "shop", "trades", "generic")


def list_packs() -> List[Dict[str, Any]]:
    """All team packs in deterministic order."""
    return [TEAM_PACKS[pid] for pid in PACK_ORDER]


def get_pack(pack_id: str) -> Dict[str, Any]:
    """Fetch one pack by id; raises TeamError on unknown id."""
    try:
        return TEAM_PACKS[pack_id]
    except KeyError:
        raise TeamError(
            f"unknown team pack {pack_id!r}; known: {', '.join(PACK_ORDER)}"
        )


def validate_packs(packs: Dict[str, Dict[str, Any]] = TEAM_PACKS) -> None:
    """Validate pack definitions. Raises TeamError on the first problem."""
    seen_role_ids: Dict[str, str] = {}
    for pid, pack in packs.items():
        for key in ("id", "title", "blurb", "roles"):
            if key not in pack:
                raise TeamError(f"pack {pid!r}: missing key {key!r}")
        if pack["id"] != pid:
            raise TeamError(f"pack {pid!r}: id field {pack['id']!r} does not match key")
        if not pack["roles"]:
            raise TeamError(f"pack {pid!r}: has no roles")
        for role in pack["roles"]:
            for key in ("id", "title", "purpose", "covers", "checklist", "escalation"):
                if key not in role:
                    raise TeamError(f"pack {pid!r} role {role.get('id', '?')!r}: missing key {key!r}")
            rid = role["id"]
            if not rid or not rid.strip():
                raise TeamError(f"pack {pid!r}: role with empty id")
            if rid in seen_role_ids and seen_role_ids[rid] != pid:
                # role ids are namespaced per pack conceptually, but ids must
                # read consistently; warn-free rule: allow reuse, ids just label the seat
                pass
            seen_role_ids.setdefault(rid, pid)
            for cid in role["covers"]:
                if cid not in KNOWN_CHECK_IDS:
                    raise TeamError(
                        f"pack {pid!r} role {rid!r}: covers unknown check id {cid!r}"
                    )
            if not role["checklist"]:
                raise TeamError(f"pack {pid!r} role {rid!r}: empty install checklist")
            if not role["escalation"] or not role["escalation"].strip():
                raise TeamError(f"pack {pid!r} role {rid!r}: empty escalation rule")


# Validate the shipped packs at import: a bad definition is a build
# bug, not a runtime surprise.
validate_packs()
