"""levi.shareware CLI — the honest trial engine.

Commands: issue | status | redeem | revoke | list | verify | terms
"""

from __future__ import annotations

import argparse
import json
import sys

from .grants import GrantStore, SharewareError


def _store() -> GrantStore:
    return GrantStore()


def cmd_issue(a) -> int:
    store = _store()
    try:
        g = store.issue(pack=a.pack, features=a.features, days=a.days,
                        max_uses=a.uses, note=a.note or "")
    except SharewareError as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 1
    print(g.id)
    print(g.terms_text())
    return 0


def cmd_status(a) -> int:
    store = _store()
    try:
        g = store.get(a.grant_id)
    except SharewareError as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 1
    print(json.dumps({
        "id": g.id, "pack": g.pack, "features": g.features,
        "uses": g.uses, "uses_left": g.uses_left(),
        "expires_at": g.expires_at, "expired": g.is_expired(),
        "revoked": g.revoked, "revoke_reason": g.revoke_reason,
        "note": g.note,
    }, indent=1))
    return 0


def cmd_redeem(a) -> int:
    store = _store()
    try:
        receipt = store.redeem(a.grant_id, feature=a.feature)
    except SharewareError as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 1
    print("redeemed %s" % a.grant_id)
    print(json.dumps(receipt, indent=1, sort_keys=True))
    return 0


def cmd_revoke(a) -> int:
    store = _store()
    try:
        store.revoke(a.grant_id, reason=a.reason or "")
    except SharewareError as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 1
    print("revoked %s" % a.grant_id)
    return 0


def cmd_list(a) -> int:
    store = _store()
    for g in store.list():
        state = "revoked" if g.revoked else ("expired" if g.is_expired() else "active")
        print("%s  %-18s  %-8s  uses=%s  %s" % (
            g.id, g.pack, state,
            "unlimited" if g.uses_left() is None else "%d/%d" % (g.uses, g.max_uses),
            ",".join(g.features)))
    return 0


def cmd_verify(a) -> int:
    store = _store()
    rep = store.verify()
    print(json.dumps(rep, indent=1))
    return 0 if rep["ok"] else 1


def cmd_terms(a) -> int:
    store = _store()
    try:
        g = store.get(a.grant_id)
    except SharewareError as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 1
    print(g.terms_text())
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="levi.shareware",
                                 description="The honest trial engine.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("issue", help="issue a trial grant")
    p.add_argument("--pack", required=True)
    p.add_argument("--features", nargs="+", required=True)
    p.add_argument("--days", type=float, default=None)
    p.add_argument("--uses", type=int, default=None)
    p.add_argument("--note", default="")
    p.set_defaults(fn=cmd_issue)

    p = sub.add_parser("status", help="show a grant")
    p.add_argument("grant_id")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("redeem", help="use one unit of a grant")
    p.add_argument("grant_id")
    p.add_argument("--feature", default=None)
    p.set_defaults(fn=cmd_redeem)

    p = sub.add_parser("revoke", help="revoke a grant")
    p.add_argument("grant_id")
    p.add_argument("--reason", default="")
    p.set_defaults(fn=cmd_revoke)

    p = sub.add_parser("list", help="list grants")
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("verify", help="verify the ledger hash chain")
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("terms", help="plain-language terms of a grant")
    p.add_argument("grant_id")
    p.set_defaults(fn=cmd_terms)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
