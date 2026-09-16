"""CLI: python -m levi.bounty

Thin entry point over the bug-bounty recon pipeline. Mirrors
``levi bounty`` (levi.cli.main.cmd_bounty): scoped, polite,
recon-only. Domain scope is always enforced; recon outside enrolled
scope is refused.
"""

from __future__ import annotations

import argparse
import sys


def _parse_ports(raw: str) -> list[int]:
    try:
        ports = [int(p) for p in raw.split(",") if p.strip()]
    except ValueError:
        raise ValueError("expected comma-separated ints, e.g. --ports 80,443")
    bad = [p for p in ports if not 1 <= p <= 65535]
    if bad or not ports:
        raise ValueError(f"ports must be 1-65535, got {bad or 'empty'}")
    return ports


def cmd_scope(a) -> int:
    from levi.bounty.scope import ScopeStore

    store, scmd = ScopeStore(), a.scope_cmd or "list"
    if scmd in ("add", "remove"):
        if not a.domain:
            print(f"Usage: python -m levi.bounty scope {scmd} <domain>",
                  file=sys.stderr)
            return 2
        try:
            res = store.add(a.domain) if scmd == "add" else store.remove(a.domain)
        except ValueError as exc:
            print(f"scope {scmd} refused: {exc}", file=sys.stderr)
            return 1
        print(f"Scope {'enrolled' if scmd == 'add' else 'removed'}: {res or a.domain}")
        return 0
    doms = store.list()
    print("No scopes enrolled. Use: python -m levi.bounty scope add <domain>"
          if not doms else "Enrolled scopes (domain + subdomains):")
    for d in doms:
        print(f"  {d}")
    return 0


def cmd_findings(a) -> int:
    from levi.bounty.store import FindingStore

    store = FindingStore()
    items = store.new_since_last_run() if a.new else store.list()
    if not items:
        print("No findings stored yet.")
        return 0
    print(f"══ {len(items)} {'new ' if a.new else ''}findings ══")
    for f in items:
        print(f"  [{f.kind:16s}] {f.target}: {f.detail[:110]}")
    return 0


def cmd_recon(a) -> int:
    from levi.bounty.pipeline import run_recon
    from levi.bounty.scope import ScopeError

    if not a.domain:
        print("Usage: python -m levi.bounty recon <domain> [--ports 80,443]",
              file=sys.stderr)
        return 2
    try:
        ports = _parse_ports(a.ports) if a.ports else None
    except ValueError as exc:
        print(f"Invalid --ports: {exc}", file=sys.stderr)
        return 2
    try:
        rep = run_recon(a.domain, ports=ports)
    except ScopeError as exc:
        print(f"SCOPE REFUSED: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid target: {exc}", file=sys.stderr)
        return 1
    print(f"══ recon {rep['domain']} [scope: {rep['scope']}] ══")
    print(f"  subdomains alive : {len(rep['subdomains'])}")
    print(f"  hosts probed     : {rep['hosts_probed']}")
    print(f"  findings new     : {rep['findings_new']}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="levi.bounty",
                                 description="LEVI bug-bounty recon — scoped, "
                                 "polite, recon-only (mirrors `levi bounty`)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("scope", help="manage enrolled scopes")
    p.add_argument("scope_cmd", nargs="?", choices=["add", "remove", "list"],
                   default="list")
    p.add_argument("domain", nargs="?", default=None)
    p.set_defaults(func=cmd_scope)

    p = sub.add_parser("findings", help="list stored findings")
    p.add_argument("--new", action="store_true")
    p.set_defaults(func=cmd_findings)

    p = sub.add_parser("recon", help="enum -> probe -> content -> store")
    p.add_argument("domain", help="must be enrolled in scope")
    p.add_argument("--ports", default=None)
    p.set_defaults(func=cmd_recon)

    args = ap.parse_args(argv)
    return args.func(args)
