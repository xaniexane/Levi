"""CLI: python -m cybrus

The standalone customer product's command surface. Thin wrapper over the
product modules — mirrors the DemandPulse product CLI shape.

Commands:
  status      smoke-check the product home (layout, vault unlock)
  quickstart  service + username in -> vault init, password generated,
              credential stored encrypted, verified by round-trip
  sheet       print the one-page customer product sheet
  price       show the pricing status (UNDECIDED — Chauncey's call)
  broker      third-party credential broker (lands with levi.cybrus.broker)

Secrets are NEVER taken via argv: the master password comes from
CYBRUS_MASTER_PASSWORD or a getpass prompt. The generated credential
password is printed exactly once.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional


def cmd_status(args) -> int:
    from levi.cybrus.quickstart import status

    print(json.dumps(status(), indent=2))
    return 0


def cmd_quickstart(args) -> int:
    from levi.cybrus.quickstart import quickstart

    receipt = quickstart(args.service, args.username)
    print(f"Cybrus quickstart -> {receipt['home']} ({receipt['elapsed_s']}s)")
    for step in receipt["steps"]:
        print(f"  - {step['name']}: {step['detail']}")
    cred = receipt["credential"]
    print()
    print(f"  service:  {cred['service']}")
    print(f"  username: {cred['username']}")
    print(f"  password: {cred['password']}")
    print("  (shown once — it is stored encrypted; this is the only display)")
    print()
    print(receipt["price"])
    return 0


def cmd_sheet(args) -> int:
    from levi.cybrus.product import product_sheet

    print(product_sheet())
    return 0


def cmd_price(args) -> int:
    from levi.cybrus.product import price_line

    print(price_line())
    return 0


def cmd_limits(args) -> int:
    from levi.cybrus import rate_limits

    print(rate_limits.policy_summary())
    return 0


def _broker():
    """Import the broker engine (landed) — ImportError while in flight."""
    from levi.cybrus.broker import (
        BrokerApprovalRequired,
        CredentialBroker,
    )
    from levi.cybrus import rate_limits

    return CredentialBroker, BrokerApprovalRequired, rate_limits


def _broker_password() -> str:
    from levi.cybrus.quickstart import resolve_master_password

    return resolve_master_password()


def _broker_handle_denial(exc: Exception) -> int:
    from levi.cybrus.broker import BrokerApprovalRequired
    from levi.cybrus.rate_limits import RateLimitDenied

    if isinstance(exc, BrokerApprovalRequired):
        print(f"approval required: {exc}")
        print("A verified human approves it, then you retry the same command.")
        return 4
    if isinstance(exc, RateLimitDenied):
        print(f"rate limit denied: {exc}")
        if exc.reset_iso:
            print(f"retry after: {exc.reset_iso}")
        return 5
    raise exc


def cmd_broker(args) -> int:
    """Third-party credential broker (product surface over levi.cybrus.broker).

    Hookup points: while the broker module is still landing this reports the
    pending state; once landed it delegates to the real engine.
    """
    try:
        CredentialBroker, _approval_exc, _rate_limits = _broker()
    except ImportError:
        print(
            "broker module not landed yet — hookup point ready; "
            "run `python -m levi.cybrus` for the engine CLI meanwhile."
        )
        return 3

    sub = args.broker_cmd
    broker = CredentialBroker(_broker_password(), identity=args.identity)
    try:
        if sub == "provision":
            record, password = broker.provision(
                args.platform,
                args.signup_url,
                username=args.username,
            )
            print(f"provisioned {record['platform']} / {record['username']} "
                  f"(id {record['id'][:8]}, status {record['status']})")
            print(f"  password: {password}")
            print("  (shown once — stored encrypted; complete the signup on "
                  "the site, then it is tracked)")
        elif sub == "accounts":
            for acc in broker.list_accounts():
                print(f"{acc['id'][:8]} {acc['platform']} / {acc['username']} "
                      f"[{acc['status']}]")
        elif sub == "keys":
            for key in broker.list_keys():
                print(f"{key['platform']} / {key['label']} "
                      f"scopes={','.join(key.get('scopes', []))}")
        elif sub == "oauth-status":
            for flow in broker.oauth_status():
                print(f"{flow['id'][:8]} {flow['platform']} [{flow['status']}]")
        else:
            print(f"unknown broker subcommand {sub!r}")
            return 2
    except Exception as exc:  # approval + rate-limit denials handled, rest propagate
        return _broker_handle_denial(exc)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cybrus", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="smoke-check the product home")

    q = sub.add_parser("quickstart", help="init vault + store first credential")
    q.add_argument("--service", required=True, help="service name (e.g. github)")
    q.add_argument("--username", required=True, help="username on that service")

    sub.add_parser("sheet", help="print the customer product sheet")
    sub.add_parser("price", help="show the pricing status")
    sub.add_parser("limits", help="show the broker rate-limit policy")

    b = sub.add_parser("broker", help="third-party credential broker")
    b.add_argument("--identity", default=None, help="owning identity")
    bsub = b.add_subparsers(dest="broker_cmd", required=True)

    bp = bsub.add_parser("provision", help="provision a third-party account record")
    bp.add_argument("--platform", required=True)
    bp.add_argument("--signup-url", required=True)
    bp.add_argument("--username", default=None)

    bsub.add_parser("accounts", help="list provisioned third-party accounts")
    bsub.add_parser("keys", help="list recorded third-party API keys")
    bsub.add_parser("oauth-status", help="list OAuth flow states")
    return p


_COMMANDS = {
    "status": cmd_status,
    "quickstart": cmd_quickstart,
    "sheet": cmd_sheet,
    "price": cmd_price,
    "limits": cmd_limits,
    "broker": cmd_broker,
}


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return _COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
