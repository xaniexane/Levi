"""CLI: ``levi salesman <stage>`` — thin layer over the pipeline."""

from __future__ import annotations

import argparse
import json
import sys

from levi.salesman import Item, new_deal
from levi.salesman.closer import classify_objection, closing_checklist, counter, followup
from levi.salesman.listing import forge_listing
from levi.salesman.pricing import price_ladder
from levi.salesman.prospect import pitch_openers, prospect
from levi.salesman.signal import run as signal_run


def _item_from(args) -> Item:
    flaws = [f.strip() for f in (getattr(args, "flaws", "") or "").split(";") if f.strip()]
    includes = [i.strip() for i in (getattr(args, "includes", "") or "").split(";") if i.strip()]
    return Item(
        name=args.name,
        category=getattr(args, "category", "general") or "general",
        condition=getattr(args, "condition", "used-good") or "used-good",
        flaws=flaws,
        includes=includes,
        retail_price=getattr(args, "retail", None),
        cost_basis=getattr(args, "cost", 0.0) or 0.0,
        quantity=getattr(args, "qty", 1) or 1,
        size=getattr(args, "size", "") or "",
        brand=getattr(args, "brand", "") or "",
    )


def _item_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--name", required=True)
    p.add_argument("--category", default="general")
    p.add_argument("--condition", default="used-good",
                   choices=["new", "like-new", "used-good", "used-fair", "parts"])
    p.add_argument("--flaws", default="", help="semicolon-separated")
    p.add_argument("--includes", default="", help="semicolon-separated")
    p.add_argument("--retail", type=float, default=None)
    p.add_argument("--cost", type=float, default=0.0)
    p.add_argument("--qty", type=int, default=1)
    p.add_argument("--size", default="")
    p.add_argument("--brand", default="")


def _deal_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--ask", type=float, required=True)
    p.add_argument("--floor", type=float, required=True)
    # L2 evidence gate: only pass when another buyer REALLY asked.
    p.add_argument("--competing", action="store_true",
                   help="real competing interest recorded (evidence-gated scarcity)")


def _add_subcommands(sub) -> None:
    """Attach all salesman subcommands to a subparsers object.

    Shared by the standalone ``build_parser()`` and by
    ``register_salesman_parser()`` for the root ``levi`` parser.
    """
    lp = sub.add_parser("price", help="Price ladder: max / fast / floor")
    _item_args(lp)

    ll = sub.add_parser("listing", help="Forge a listing for a platform")
    _item_args(ll)
    ll.add_argument("--platform", default="marketplace",
                    choices=["marketplace", "vinted", "x", "tiktok"])
    ll.add_argument("--at", type=float, default=None, help="list price (default: fast)")

    pr = sub.add_parser("prospect", help="Buyer intel for a category")
    pr.add_argument("--category", default="general")
    pr.add_argument("--openers", action="store_true")

    ng = sub.add_parser("counter", help="Generate an aggressive counter to a buyer message")
    _item_args(ng)
    _deal_args(ng)
    ng.add_argument("--message", required=True, help="buyer's message")

    fu = sub.add_parser("followup", help="Ghost nudge (max 3 touches)")
    _item_args(fu)
    _deal_args(fu)
    fu.add_argument("--touches", type=int, default=0)

    cl = sub.add_parser("close", help="Closing checklist draft (HITL required)")
    _item_args(cl)
    _deal_args(cl)
    cl.add_argument("--offer", type=float, default=None)

    dm = sub.add_parser("demand",
                        help="DemandPulse x KFX²: score deals, improve the winner's pattern")
    dm.add_argument("--top", type=int, default=3)
    dm.add_argument("--deals", default="",
                    help="semicolon-separated ask:floor pairs for scoring demo, "
                         "e.g. '45:30;60:40'")


def register_salesman_parser(sub) -> argparse.ArgumentParser:
    """Attach ``levi salesman`` to the root parser.

    Called from ``levi/cli/main.py`` during parser construction (before
    ``parse_args``). This is the fix for the missing root registration:
    dispatch alone (``cmds["salesman"]``) can never work because argparse
    rejects the command first.
    """
    p = sub.add_parser("salesman", help="Salesman pipeline: intake to close.")
    _add_subcommands(p.add_subparsers(dest="salesman_cmd"))
    return p


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="levi salesman",
                                description="Salesman pipeline: intake to close.")
    _add_subcommands(p.add_subparsers(dest="salesman_cmd"))
    return p


def cmd_salesman(args) -> int:
    cmd = getattr(args, "salesman_cmd", None) or "price"
    if cmd == "prospect":
        data = prospect(args.category)
        if getattr(args, "openers", False):
            data["openers"] = pitch_openers(args.category)
        print(json.dumps(data, indent=2))
        return 0
    if cmd == "demand":
        # DemandPulse x KFX² one motion. Deals come from --deals as
        # ask:floor pairs; a real store would load live deals here.
        pairs = [p for p in (args.deals or "").split(";") if p.strip()]
        deals = []
        for i, pair in enumerate(pairs):
            ask_s, floor_s = pair.split(":")
            it = Item(name=f"deal-{i + 1}")
            d = new_deal(it, float(ask_s), float(floor_s))
            deals.append(d)
        item = Item(name="next-item")
        print(json.dumps(signal_run(deals, item, ask=0.0, floor=0.0,
                                    top=args.top), indent=2, default=str))
        return 0
    item = _item_from(args)
    if cmd == "price":
        print(json.dumps(price_ladder(item), indent=2))
        return 0
    if cmd == "listing":
        ladder = price_ladder(item)
        at = args.at if args.at is not None else ladder["fast"]
        print(json.dumps(forge_listing(item, args.platform, at), indent=2))
        return 0
    deal = new_deal(item, args.ask, args.floor)
    # L2 evidence gate: scarcity language only when real interest recorded.
    deal.competing_interest = bool(getattr(args, "competing", False))
    if cmd == "counter":
        c = counter(deal, args.message)
        deal.history.append(f"close_type:{c.close_type}")
        print(json.dumps({
            "objection": classify_objection(args.message),
            "close_type": c.close_type,
            "new_ask": c.new_ask,
            "escalate_hitl": c.escalate_hitl,
            "reply": c.reply,
        }, indent=2))
        return 0
    if cmd == "followup":
        deal.touches = args.touches
        msg = followup(deal)
        print(json.dumps({"nudge": msg, "touches": deal.touches,
                          "stage": deal.stage}, indent=2))
        return 0
    if cmd == "close":
        deal.buyer_offer = args.offer
        print(json.dumps(closing_checklist(deal), indent=2))
        return 0
    print(f"unknown salesman command {cmd!r}", file=sys.stderr)
    return 2
