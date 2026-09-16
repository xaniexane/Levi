"""CLI: python -m levi.capproto — capability-gated service protocol.

Subcommands:
  issue       mint a capability token
  attenuate   mint a strictly narrower token from one you hold
  verify      verify a token (fail-closed; prints claims)
  serve       run the demo kvnote service on a local socket
  call        make one capability-gated call against a local endpoint
  demo        full in-process demo: issue -> attenuate -> refuse -> revoke
  ledger      show the mint/attenuation/revocation audit ledger

Home resolves at call time from --home, LEVI_HOME, or ~/.levi.
Cross-process tokens require LEVI_TELESCRIPT_SECRET to be shared.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from levi.capproto.tokens import MintLedger, attenuate, decode, default_home
from levi.revival.telescript import CapabilityError, issue, verify


def _home(a) -> Path:
    return Path(a.home) if a.home else default_home()


def cmd_issue(a) -> int:
    ledger = MintLedger(_home(a))
    try:
        token = issue(a.issuer, a.grantee, a.action, ttl_seconds=a.ttl)
    except ValueError as exc:
        print(f"issue refused: {exc}", file=sys.stderr)
        return 1
    ledger.record_issued(token)
    print(token)
    return 0


def cmd_attenuate(a) -> int:
    ledger = MintLedger(_home(a))
    try:
        child = attenuate(
            a.token,
            actions=a.action if a.action else None,
            ttl_seconds=a.ttl,
            ledger=ledger,
        )
    except Exception as exc:
        print(f"attenuate refused: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(child)
    return 0


def cmd_verify(a) -> int:
    try:
        cap = verify(a.token, expected_grantee=a.grantee or None)
    except CapabilityError as exc:
        print(f"INVALID: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    claims = decode(a.token)
    claims["verified_actions"] = list(cap.actions)
    print(json.dumps(claims, indent=2))
    return 0


def cmd_serve(a) -> int:
    from levi.capproto.demo import build_kvnote_service
    from levi.capproto.transport import CapServer

    home = _home(a)
    server = CapServer(build_kvnote_service(MintLedger(home)), home=home).start()
    print(f"capproto serving kvnote on {server.endpoint}")
    print("set LEVI_TELESCRIPT_SECRET identically for clients; Ctrl-C to stop")
    try:
        import time

        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return 0


def cmd_call(a) -> int:
    from levi.capproto.transport import CapCallError, CapClient

    try:
        args = json.loads(a.args) if a.args else {}
    except ValueError as exc:
        print(f"bad --args JSON: {exc}", file=sys.stderr)
        return 2
    client = CapClient(home=_home(a), name=a.name).connect()
    try:
        result = client.call(a.svc, a.verb, a.token, args)
    except CapCallError as exc:
        print(f"call refused/failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"transport error: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()
    print(json.dumps(result, indent=2))
    return 0


def cmd_demo(a) -> int:
    from levi.capproto.demo import run_demo

    for line in run_demo(_home(a)):
        print(line)
    return 0


def cmd_ledger(a) -> int:
    for rec in MintLedger(_home(a)).entries():
        print(json.dumps(rec, separators=(",", ":")))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.capproto",
        description="capproto/1 — capability-gated service protocol (local-first)",
    )
    ap.add_argument("--home", default=None, help="capproto home (default: ~/.levi/capproto)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("issue", help="mint a capability token")
    p.add_argument("--issuer", required=True)
    p.add_argument("--grantee", required=True)
    p.add_argument("--action", action="append", default=[], help="repeatable")
    p.add_argument("--ttl", type=float, default=3600)
    p.set_defaults(func=cmd_issue)

    p = sub.add_parser("attenuate", help="mint a strictly narrower token")
    p.add_argument("--token", required=True)
    p.add_argument("--action", action="append", default=[], help="subset of parent's; repeatable")
    p.add_argument("--ttl", type=float, default=None)
    p.set_defaults(func=cmd_attenuate)

    p = sub.add_parser("verify", help="verify a token and print its claims")
    p.add_argument("--token", required=True)
    p.add_argument("--grantee", default=None)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("serve", help="serve the demo kvnote service locally")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("call", help="call a verb on a local endpoint")
    p.add_argument("--name", default="kvnote")
    p.add_argument("--svc", default="kvnote")
    p.add_argument("--verb", required=True)
    p.add_argument("--token", required=True)
    p.add_argument("--args", default="")
    p.set_defaults(func=cmd_call)

    p = sub.add_parser("demo", help="full issue->attenuate->refuse->revoke demo")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("ledger", help="show the audit ledger")
    p.set_defaults(func=cmd_ledger)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
