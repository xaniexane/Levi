"""CLI: python -m levi.demandpulse

The standalone customer product's command surface. Thin wrapper over the
product modules — no network calls, no installation, no payments.

Commands:
  status      smoke-check the product home (layout, filters, alert store)
  quickstart  keywords in -> filters + watch alerts installed (offline)
  digest      render the latest briefing to stdout / --out to the outbox
  price       show the $6/mo anchor and what it covers
  gate        show the owner-gate status (payments, channels, release)
  themes      list the bundled theme packs
  sheet       print the one-page customer product sheet
  activate    activate with your license email + key (stored on this machine)
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional


def cmd_status(args) -> int:
    from levi.demandpulse.quickstart import status

    print(json.dumps(status(), indent=2))
    return 0


def cmd_quickstart(args) -> int:
    from levi.demandpulse.quickstart import quickstart

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    exclude = [e.strip() for e in (args.exclude or "").split(",") if e.strip()]
    receipt = quickstart(keywords, exclude=exclude)
    print(f"DemandPulse quickstart -> {receipt['home']} ({receipt['elapsed_s']}s)")
    for step in receipt["steps"]:
        print(f"  - {step['name']}: {step['detail']}")
    print(receipt["price"])
    return 0


def cmd_digest(args) -> int:
    from levi.demandpulse.briefing import render_latest, write_briefing

    text = render_latest(theme=args.theme)
    if text is None:
        print("no stored digest yet — run quickstart, then feed a scan")
        return 1
    if args.out:
        path = write_briefing(text)
        print(f"briefing written to {path}")
    else:
        print(text)
    return 0


def cmd_price(args) -> int:
    from levi.demandpulse.product import (
        COMPETITOR_PRICE_CAVEAT,
        PLATFORM_CUT,
        monthly_price_line,
    )

    print(monthly_price_line())
    print(f"platform cut on on-platform digital products: {PLATFORM_CUT:.0%}")
    print()
    print(COMPETITOR_PRICE_CAVEAT)
    return 0


def cmd_gate(args) -> int:
    from levi.demandpulse.payments import activation_checklist

    print(json.dumps(activation_checklist(), indent=2))
    return 0


def cmd_themes(args) -> int:
    from levi.demandpulse.themes import list_themes

    for name in list_themes():
        print(name)
    return 0


def cmd_sheet(args) -> int:
    from levi.demandpulse.product import product_sheet

    print(product_sheet())
    return 0


def cmd_activate(args) -> int:
    from levi.demandpulse import entitlements as E

    try:
        record = E.validate_activation(args.email, args.key)
    except E.EntitlementError as exc:
        print(f"activation failed: {exc}")
        print("check the email and key from your license email and try again.")
        return 2
    print(f"activated for {record['email']} — key recorded on this machine.")
    print("note: license checks are informational until the owner enables "
          "enforcement; the product runs fully ungated meanwhile.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="demandpulse", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="smoke-check the product home")

    q = sub.add_parser("quickstart", help="zero-config quickstart")
    q.add_argument("--keywords", required=True, help="comma-separated keyword set")
    q.add_argument("--exclude", default="", help="comma-separated exclusion terms")

    d = sub.add_parser("digest", help="render the latest briefing")
    d.add_argument("--theme", default="void", help="theme pack name")
    d.add_argument("--out", action="store_true", help="write to the file outbox")

    sub.add_parser("price", help="show the price anchor")
    sub.add_parser("gate", help="show owner-gate status")
    sub.add_parser("themes", help="list theme packs")
    sub.add_parser("sheet", help="print the customer product sheet")

    a = sub.add_parser("activate", help="activate with your license email + key")
    a.add_argument("--email", required=True, help="the email on your license")
    a.add_argument("--key", required=True, help="license key DP-XXXX-XXXX-XXXX")
    return p


_COMMANDS = {
    "status": cmd_status,
    "quickstart": cmd_quickstart,
    "digest": cmd_digest,
    "price": cmd_price,
    "gate": cmd_gate,
    "themes": cmd_themes,
    "sheet": cmd_sheet,
    "activate": cmd_activate,
}


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return _COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
