"""DemandPulse CLI — `levi demandpulse`.

Top-level hook for the DemandPulse module: the standalone product surface
(status, quickstart, digest, price, gate, themes, sheet) plus the Watch —
the live tracker of everything (systems, goals, builds, open threads).

Logic lives in the product modules and in :mod:`levi.demandpulse.watch`;
this file only wires the CLI.
"""

from __future__ import annotations

import argparse


def register_demandpulse_parser(sub) -> None:
    dp = sub.add_parser(
        "demandpulse",
        help="DemandPulse engine/app/persona: product surface + the Watch",
    )
    cmds = dp.add_subparsers(dest="demandpulse_cmd")

    # -- product surface (thin, mirrors python -m levi.demandpulse) --------
    cmds.add_parser("status", help="smoke-check the product home")
    q = cmds.add_parser("quickstart", help="zero-config quickstart")
    q.add_argument("--keywords", required=True, help="comma-separated keyword set")
    q.add_argument("--exclude", default="", help="comma-separated exclusion terms")
    d = cmds.add_parser("digest", help="render the latest briefing")
    d.add_argument("--theme", default="void", help="theme pack name")
    d.add_argument("--out", action="store_true", help="write to the file outbox")
    cmds.add_parser("price", help="show the price anchor")
    cmds.add_parser("gate", help="show owner-gate status")
    cmds.add_parser("themes", help="list the bundled theme packs")
    cmds.add_parser("sheet", help="print the customer product sheet")

    # -- entitlements (owner-operated; HQ Decision 4) -----------------------
    e = cmds.add_parser("entitle", help="issue/renew a license key (owner)")
    e.add_argument("--email", required=True, help="customer email")
    e.add_argument("--months", type=int, default=1, help="months paid (default: 1)")
    e.add_argument("--payment-ref", default="",
                   help="payment reference, e.g. 'cashapp $buyer 2026-09-24'")
    e.add_argument("--note", default="", help="operator note")

    r = cmds.add_parser("revoke", help="revoke a license key (owner)")
    r.add_argument("--email", required=True, help="customer email")
    r.add_argument("--reason", default="", help="reason for the record")

    f = cmds.add_parser("refund",
                        help="refund within 7 days and revoke (owner)")
    f.add_argument("--email", required=True, help="customer email")

    c = cmds.add_parser("check", help="check a key against owner records")
    c.add_argument("--email", required=True, help="customer email")
    c.add_argument("--key", required=True, help="license key DP-XXXX-XXXX-XXXX")

    li = cmds.add_parser("list", help="list entitlements (owner)")
    li.add_argument("--status", default="all",
                    choices=["all", "active", "grace", "expired", "revoked"],
                    help="filter by state (default: all)")

    # -- the Watch ----------------------------------------------------------
    w = cmds.add_parser("watch", help="live tracker of everything")
    wcmds = w.add_subparsers(dest="watch_cmd")

    wcmds.add_parser("board", help="show the status board (default)")

    s = wcmds.add_parser("set", help="change an item's status")
    s.add_argument("id", help="watch item id")
    s.add_argument(
        "status",
        help="new status",
    )
    s.add_argument("--note", default="", help="status note")
    s.add_argument(
        "--ping",
        action="store_true",
        help="also ping Chauncey immediately via the notifier",
    )

    a = wcmds.add_parser("add", help="add a watch item")
    a.add_argument("name", help="item name")
    a.add_argument("--area", default="build",
                   help="system/goal/build/thread (default: build)")
    a.add_argument(
        "--status", default="queued", help="initial status (default: queued)"
    )
    a.add_argument("--note", default="", help="item note")
    a.add_argument(
        "--waiting-on", default="none", help="him/me/none (default: none)"
    )

    h = wcmds.add_parser("history", help="show an item's history")
    h.add_argument("id", help="watch item id")

    wcmds.add_parser("seed", help="seed the registry from the standing list")
    wcmds.add_parser("laws", help="machine-check the watch laws")


def _cmd_watch(args: argparse.Namespace) -> int:
    from levi.demandpulse import watch as W

    cmd = getattr(args, "watch_cmd", None) or "board"
    reg = W.WatchRegistry()

    if cmd == "board":
        print(W.render_board(reg.board()))
        return 0

    if cmd == "set":
        try:
            item = reg.set_status(args.id, args.status, note=args.note,
                                  ping=args.ping)
        except W.WatchError as exc:
            print(f"watch set failed: {exc}")
            return 2
        print(f"{item['id']}: {item['name']} → {item['status']}")
        return 0

    if cmd == "add":
        try:
            item = reg.add(args.name, args.area, status=args.status,
                           note=args.note, waiting_on=args.waiting_on)
        except W.WatchError as exc:
            print(f"watch add failed: {exc}")
            return 2
        print(f"added {item['id']}: {item['name']} [{item['status']}]")
        return 0

    if cmd == "history":
        try:
            events = reg.history_for(args.id)
        except W.WatchError as exc:
            print(f"watch history failed: {exc}")
            return 2
        if not events:
            print(f"{args.id}: no history")
            return 0
        for ev in events:
            frm = ev.get("from", "—")
            print(f"  #{ev['seq']} {ev['ts']} {ev['event']}: {frm} → {ev.get('to')}"
                  + (f" — {ev['note']}" if ev.get("note") else ""))
        return 0

    if cmd == "seed":
        before = len(reg.items())
        W.seed(reg)
        print(f"seeded {len(reg.items()) - before} items "
              f"({len(reg.items())} total)")
        return 0

    if cmd == "laws":
        import json

        report = reg.check_laws()
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1

    print(f"unknown demandpulse watch command: {cmd}")
    return 2


def _cmd_entitlements(args: argparse.Namespace) -> int:
    from levi.demandpulse import entitlements as E

    cmd = args.demandpulse_cmd
    try:
        if cmd == "entitle":
            rec = E.issue(args.email, months=args.months,
                          payment_ref=args.payment_ref, note=args.note)
            print(f"{rec['event']}: {rec['email']} -> {rec['key']} "
                  f"(paid through {rec['paid_through']})")
            return 0
        if cmd == "revoke":
            rec = E.revoke(args.email, reason=args.reason)
            print(f"revoked: {rec['email']} (key {rec['key']} is dead)")
            return 0
        if cmd == "refund":
            rec = E.refund(args.email)
            print(f"refunded: {rec['email']} — return $6 same rail within "
                  f"3 days, then close the receipt")
            return 0
        if cmd == "check":
            res = E.check(args.email, args.key)
            state = "ACTIVE" if res.active else (
                "GRACE" if res.in_grace else "INACTIVE")
            print(f"{state}: {res.email} — {res.reason}")
            return 0 if res.active else 1
        if cmd == "list":
            rows = E.list_entitlements(status=args.status)
            if not rows:
                print("no entitlements on record")
                return 0
            for row in rows:
                print(f"{row['state']:8} {row['email']:40} {row['key']} "
                      f"through {row['paid_through']}")
            return 0
    except E.EntitlementError as exc:
        print(f"entitlement {cmd} failed: {exc}")
        return 2
    print(f"unknown demandpulse command: {cmd}")
    return 2


def cmd_demandpulse(args: argparse.Namespace) -> int:
    from levi.demandpulse import __main__ as mod

    cmd = getattr(args, "demandpulse_cmd", None) or "watch"

    if cmd == "watch":
        return _cmd_watch(args)

    if cmd in ("entitle", "revoke", "refund", "check", "list"):
        return _cmd_entitlements(args)

    # product surface: delegate to the module's own command functions
    handlers = {
        "status": mod.cmd_status,
        "quickstart": mod.cmd_quickstart,
        "digest": mod.cmd_digest,
        "price": mod.cmd_price,
        "gate": mod.cmd_gate,
        "themes": mod.cmd_themes,
        "sheet": mod.cmd_sheet,
    }
    fn = handlers.get(cmd)
    if fn is None:
        print(f"unknown demandpulse command: {cmd}")
        return 2
    return fn(args)
