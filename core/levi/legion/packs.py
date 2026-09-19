"""Specialist add-on packs: restaurant, salon, shop, generic.

Data-driven: each pack is a plain Python dict (JSON-shaped) with domain
vocabulary, FAQs/tasks, and escalation rules. No hardcoded business
names — packs describe *patterns* for a trade, and the white-label
config supplies the specific business.

A pack's extra needs extend the tailored team (see team.py).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from .product import LegionError


def _pack(
    name: str,
    blurb: str,
    *,
    vocabulary: List[str],
    extra_needs: List[str],
    faqs: List[Dict[str, str]],
    tasks: List[Dict[str, str]],
    escalations: List[Dict[str, str]],
) -> Dict[str, Any]:
    return {
        "name": name,
        "blurb": blurb,
        "vocabulary": vocabulary,
        "extra_needs": extra_needs,
        "faqs": faqs,      # {"q", "a"} — a is a template, owner words it
        "tasks": tasks,    # {"task", "owner_role", "notes"}
        "escalations": escalations,  # {"trigger", "to", "note"}
    }


PACKS: Dict[str, Dict[str, Any]] = {
    "restaurant": _pack(
        "restaurant",
        "Front-of-house crew for eateries: reservations, menu questions, "
        "hours, takeout notes.",
        vocabulary=[
            "reservation", "party size", "table", "wait time", "menu",
            "daily special", "takeout", "delivery", "allergen", "vegan",
            "gluten-free", "happy hour", "patio", "private dining",
        ],
        extra_needs=["booking", "pricing", "hours", "reviews"],
        faqs=[
            {"q": "do you take reservations?",
             "a": "Yes — tell me the date, time, and party size and I'll book it."},
            {"q": "do you have vegetarian / vegan / gluten-free options?",
             "a": "We do — say the word and I'll point you at the right dishes."},
            {"q": "what's the wait right now?",
             "a": "I don't track live waits — call us and the host stand will tell you."},
            {"q": "do you do takeout?",
             "a": "Yes. Order ahead and it's ready when you arrive."},
        ],
        tasks=[
            {"task": "take a reservation", "owner_role": "booker",
             "notes": "date, time, party size, name, phone; confirm back"},
            {"task": "answer menu questions", "owner_role": "cashier",
             "notes": "quote the menu as written; never invent prices or dishes"},
            {"task": "note an allergy", "owner_role": "receptionist",
             "notes": "record it on the booking; advise the kitchen is told on arrival"},
        ],
        escalations=[
            {"trigger": "allergy emergency or food-safety complaint", "to": "owner",
             "note": "immediately, with the booking details"},
            {"trigger": "guest is angry or demands a refund", "to": "owner",
             "note": "crew apologizes, owner decides"},
            {"trigger": "large party or private event", "to": "owner",
             "note": "owner confirms availability"},
        ],
    ),
    "salon": _pack(
        "salon",
        "Booking-desk crew for salons and barbers: appointments, service "
        "menu, stylist notes, gallery.",
        vocabulary=[
            "appointment", "cut", "color", "balayage", "highlights",
            "fade", "beard trim", "manicure", "pedicure", "facial",
            "stylist", "barber", "consultation", "patch test",
            "deposit", "cancellation policy",
        ],
        extra_needs=["booking", "pricing", "gallery", "reminders"],
        faqs=[
            {"q": "how much is a cut and color?",
             "a": "Prices are on our service menu — tell me which service and I'll quote it."},
            {"q": "can I book with a specific stylist?",
             "a": "Of course — name them and I'll check their chair."},
            {"q": "what's your cancellation policy?",
             "a": "Life happens — just give us notice and we'll move it."},
            {"q": "do I need a consultation first?",
             "a": "For color, yes — it's free and quick."},
        ],
        tasks=[
            {"task": "book an appointment", "owner_role": "booker",
             "notes": "service, stylist preference, date/time, phone; confirm back"},
            {"task": "send a reminder", "owner_role": "booker",
             "notes": "day-before reminder for confirmed bookings"},
            {"task": "show the portfolio", "owner_role": "marketer",
             "notes": "point at the gallery; never promise a result"},
        ],
        escalations=[
            {"trigger": "chemical reaction or injury", "to": "owner",
             "note": "immediately; advise the client to seek care"},
            {"trigger": "client unhappy with a result", "to": "owner",
             "note": "crew apologizes, owner handles the fix"},
            {"trigger": "no-show / late cancellation dispute", "to": "owner",
             "note": "owner applies the policy"},
        ],
    ),
    "shop": _pack(
        "shop",
        "Counter crew for retail: catalog questions, ordering, pickup, "
        "returns policy.",
        vocabulary=[
            "in stock", "size", "color", "price", "sale", "clearance",
            "return", "exchange", "warranty", "pickup", "shipping",
            "gift wrap", "loyalty", "new arrival",
        ],
        extra_needs=["catalog", "ordering", "contact", "pricing"],
        faqs=[
            {"q": "is this in stock?",
             "a": "I can check the shelf list — what item and size?"},
            {"q": "what's your return policy?",
             "a": "Standard policy applies — I'll read you the terms."},
            {"q": "can I order for pickup?",
             "a": "Yes — tell me what you want and when you'll swing by."},
            {"q": "do you ship?",
             "a": "We do — give me the address and I'll quote it."},
        ],
        tasks=[
            {"task": "check stock", "owner_role": "merchandiser",
             "notes": "quote the stock list as written; never invent counts"},
            {"task": "take a pickup order", "owner_role": "cashier",
             "notes": "items, name, phone, pickup time; confirm back"},
            {"task": "quote a return", "owner_role": "cashier",
             "notes": "read the policy; owner approves exceptions"},
        ],
        escalations=[
            {"trigger": "defective or dangerous product", "to": "owner",
             "note": "immediately; do not advise continued use"},
            {"trigger": "refund or charge dispute", "to": "owner",
             "note": "owner decides; crew never promises money back"},
            {"trigger": "suspected theft or fraud", "to": "owner",
             "note": "crew stays polite, owner handles"},
        ],
    ),
    "generic": _pack(
        "generic",
        "Baseline crew for any small business: contact, hours, FAQ, "
        "simple lead capture.",
        vocabulary=[
            "hours", "location", "contact", "quote", "appointment",
            "services", "pricing", "about",
        ],
        extra_needs=["contact", "faq"],
        faqs=[
            {"q": "what are your hours?",
             "a": "I'll read you the hours as listed."},
            {"q": "where are you located?",
             "a": "I'll give you the address and directions."},
            {"q": "how do I get a quote?",
             "a": "Tell me what you need and I'll take the details for the owner."},
        ],
        tasks=[
            {"task": "capture a lead", "owner_role": "receptionist",
             "notes": "name, contact, what they need; confirm back"},
            {"task": "answer hours/location", "owner_role": "receptionist",
             "notes": "quote the listing as written"},
        ],
        escalations=[
            {"trigger": "anything the crew can't answer", "to": "owner",
             "note": "take a message, promise a callback"},
            {"trigger": "angry visitor", "to": "owner",
             "note": "crew stays calm, owner decides"},
        ],
    ),
}


def list_packs() -> List[Dict[str, str]]:
    """Pack menu: name + blurb, for CLI and quotes."""
    return [{"name": n, "blurb": p["blurb"]} for n, p in PACKS.items()]


def get_pack(name: str) -> Dict[str, Any]:
    """Fetch one pack by name. Raises LegionError on unknown names."""
    key = (name or "").lower()
    if key not in PACKS:
        raise LegionError(
            f"unknown pack {name!r} — choose one of {sorted(PACKS)}"
        )
    return PACKS[key]


def pack_names() -> List[str]:
    return sorted(PACKS)


def merge_pack_into_profile(
    profile: Mapping[str, Any], pack_name: str
) -> Dict[str, Any]:
    """Return a copy of the business-profile dict with the pack's extra
    needs merged into its needs list (deduplicated, order-preserved).

    The pack never edits the caller's profile in place.
    """
    pack = get_pack(pack_name)
    data = dict(profile)
    needs = list(data.get("needs") or [])
    for need in pack["extra_needs"]:
        if need not in needs:
            needs.append(need)
    data["needs"] = needs
    return data
