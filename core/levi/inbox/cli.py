"""CLI for the companion inbox: user analytics + feature/request box.

``levi inbox analytics`` — today's usage (local only, nothing leaves the machine)
``levi inbox analytics week`` — last 7 days
``levi inbox analytics top`` — most-used capabilities
``levi inbox requests`` — list the request box
``levi inbox request "..."`` — drop a request in
``levi inbox request-done <n>`` — mark request #n done (or considered/building)
"""

from __future__ import annotations

import argparse

from .analytics import Analytics, render_daily, render_weekly
from .requests import STATUSES, RequestBox, RequestError, render_list


def _register_commands(sub) -> None:
    a = sub.add_parser("analytics", help="your local usage patterns")
    a.add_argument(
        "view",
        nargs="?",
        default="today",
        choices=("today", "week", "top"),
        help="today (default), week, or top",
    )
    sub.add_parser("requests", help="list the feature/request box")
    r = sub.add_parser("request", help='drop a request in: request "your idea"')
    r.add_argument("text", nargs="+", help="the request text")
    d = sub.add_parser(
        "request-status", help="move a request forward: open→considered→building→done"
    )
    d.add_argument("id", type=int, help="request number")
    d.add_argument("status", choices=STATUSES, help="new status")


def register_inbox_parser(sub) -> None:
    ib = sub.add_parser(
        "inbox", help="user analytics + the feature/request box (all local)"
    )
    cmds = ib.add_subparsers(dest="inbox_cmd")
    _register_commands(cmds)


def cmd_inbox(args) -> None:
    """Inbox: local usage analytics + the feature/request box."""
    cmd = getattr(args, "inbox_cmd", None)
    if cmd == "analytics":
        agg = Analytics()
        view = getattr(args, "view", "today")
        if view == "week":
            print(render_weekly(agg.weekly()))
        elif view == "top":
            top = agg.top()
            if not top:
                print("analytics — no events yet")
            else:
                print("analytics — top capabilities (7d):")
                for item in top:
                    print("  %s: %d" % (item["capability"], item["count"]))
        else:
            print(render_daily(agg.daily()))
        return
    if cmd == "requests":
        print(render_list(RequestBox().list()))
        return
    if cmd == "request":
        text = " ".join(getattr(args, "text", []) or [])
        try:
            req = RequestBox().add(text)
        except RequestError as exc:
            print(f"request not saved: {exc}")
            raise SystemExit(2)
        print(f"request #{req.id} saved — in the box, will be triaged")
        return
    if cmd == "request-status":
        try:
            req = RequestBox().set_status(args.id, args.status)
        except RequestError as exc:
            print(f"requests: {exc}")
            raise SystemExit(2)
        print(f"request #{req.id} → {req.status}")
        return
    print("usage: levi inbox {analytics|requests|request|request-status} ...")
    raise SystemExit(2)
