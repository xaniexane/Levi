"""CLI: python -m levi.circles <command> [options]

Dunbar-bounded trust circles: add/remove/move members with hard caps,
circle-scoped share receipts, and an owner-only cap audit.
"""

from __future__ import annotations

import argparse
import sys

from . import CircleError
from .model import CircleStore, layer_names


def _cmd_add(a) -> int:
    store = CircleStore()
    m = store.add(a.id, name=a.name or "", layer=a.layer)
    print("added %s (%s) to %s" % (m.id, m.name, m.layer))
    return 0


def _cmd_remove(a) -> int:
    store = CircleStore()
    store.remove(a.id)
    print("removed %s" % a.id)
    return 0


def _cmd_move(a) -> int:
    store = CircleStore()
    m = store.move(a.id, a.layer)
    print("moved %s -> %s" % (m.id, m.layer))
    return 0


def _cmd_list(a) -> int:
    store = CircleStore()
    members = store.members(layer=a.layer)
    if not members:
        print("no members" + (" in %s" % a.layer if a.layer else ""))
        return 0
    for m in members:
        print("%s  [%s]  %s" % (m.id, m.layer, m.name))
    return 0


def _cmd_audit(a) -> int:
    store = CircleStore()
    for row in store.audit():
        status = "FULL" if row["full"] else "%d free" % row["headroom"]
        print("%-8s %3d/%-3d  %s" % (row["layer"], row["used"], row["cap"], status))
    return 0


def _cmd_share(a) -> int:
    store = CircleStore()
    r = store.share(a.title, a.body or "", a.layer)
    print(
        "shared %s to %s (%d members saw it): %s"
        % (r.id, r.layer, len(r.member_ids), r.title)
    )
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="levi.circles")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="add a member to a layer (cap enforced)")
    a.add_argument("id")
    a.add_argument("--name", default="")
    a.add_argument("--layer", default="friends", choices=layer_names())
    a.set_defaults(fn=_cmd_add)

    r = sub.add_parser("remove", help="remove a member")
    r.add_argument("id")
    r.set_defaults(fn=_cmd_remove)

    m = sub.add_parser("move", help="move a member to another layer")
    m.add_argument("id")
    m.add_argument("layer", choices=layer_names())
    m.set_defaults(fn=_cmd_move)

    li = sub.add_parser("list", help="list members (optionally one layer)")
    li.add_argument("--layer", default=None, choices=layer_names())
    li.set_defaults(fn=_cmd_list)

    au = sub.add_parser("audit", help="owner-only cap headroom")
    au.set_defaults(fn=_cmd_audit)

    s = sub.add_parser("share", help="share to exactly one circle")
    s.add_argument("title")
    s.add_argument("--body", default="")
    s.add_argument("--layer", default="friends", choices=layer_names())
    s.set_defaults(fn=_cmd_share)

    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except CircleError as exc:
        print("circles: refused: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
