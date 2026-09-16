"""CLI: python -m levi.digest <command> [options]

The list owner's counter: create lists, double-opt-in subscriptions,
post with moderation holds, and compile plain-text digests.
"""

from __future__ import annotations

import argparse
import sys

from . import lists


def _cmd_create(a) -> int:
    try:
        cfg = lists.create_list(a.name, a.owner, a.description, a.moderated)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print(
        "list created: %s owner=%s moderated=%s" % (cfg["name"], cfg["owner"],
                                                   cfg["moderated"])
    )
    return 0


def _cmd_sub(a) -> int:
    try:
        token = lists.subscribe(a.list, a.email)
    except (ValueError, KeyError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print("confirmation required for %s" % a.email)
    print("token: %s" % token)
    return 0


def _cmd_confirm(a) -> int:
    try:
        email = lists.confirm(a.list, a.token)
    except (ValueError, KeyError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print("subscribed: %s" % email)
    return 0


def _cmd_unsub(a) -> int:
    try:
        removed = lists.unsubscribe(a.list, a.email)
    except KeyError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print("unsubscribed %s" % a.email if removed else "not subscribed: %s" % a.email)
    return 0


def _cmd_post(a) -> int:
    try:
        msg_id, status = lists.post(a.list, a.sender, a.subject, a.body)
    except (ValueError, KeyError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print("message %s: %s" % (status, msg_id))
    return 0


def _cmd_approve(a) -> int:
    try:
        msg = lists.approve(a.list, a.id, a.moderator)
    except (ValueError, KeyError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print("approved %s (%s)" % (msg["id"], msg["subject"]))
    return 0


def _cmd_reject(a) -> int:
    try:
        lists.reject(a.list, a.id, a.moderator, a.reason)
    except (ValueError, KeyError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print("rejected %s" % a.id)
    return 0


def _cmd_digest(a) -> int:
    try:
        print(lists.compile_digest(a.list, a.period))
    except (ValueError, KeyError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


def _cmd_archive(a) -> int:
    try:
        hits = lists.archive_search(a.list, a.query)
    except (ValueError, KeyError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    if not hits:
        print("no matches")
        return 0
    for m in hits:
        print("[%s] %s <- %s" % (m["ts"], m["subject"], m["sender"]))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="levi.digest",
        description="Local-first mailing lists: own the list, batch the attention",
    )
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("create", help="create a list")
    c.add_argument("--name", required=True)
    c.add_argument("--owner", required=True)
    c.add_argument("--description", default="")
    c.add_argument("--moderated", action="store_true")

    s = sub.add_parser("sub", help="request a subscription (double-opt-in)")
    s.add_argument("--list", required=True)
    s.add_argument("--email", required=True)

    cf = sub.add_parser("confirm", help="confirm a subscription token")
    cf.add_argument("--list", required=True)
    cf.add_argument("--token", required=True)

    u = sub.add_parser("unsub", help="remove a subscriber")
    u.add_argument("--list", required=True)
    u.add_argument("--email", required=True)

    po = sub.add_parser("post", help="post a message to a list")
    po.add_argument("--list", required=True)
    po.add_argument("--sender", required=True)
    po.add_argument("--subject", required=True)
    po.add_argument("--body", required=True)

    ap = sub.add_parser("approve", help="release a held message")
    ap.add_argument("--list", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--moderator", required=True)

    rj = sub.add_parser("reject", help="reject a held message with a reason")
    rj.add_argument("--list", required=True)
    rj.add_argument("--id", required=True)
    rj.add_argument("--moderator", required=True)
    rj.add_argument("--reason", default="")

    dg = sub.add_parser("digest", help="compile a plain-text digest")
    dg.add_argument("--list", required=True)
    dg.add_argument("--period", default="daily", choices=["daily", "weekly"])

    ar = sub.add_parser("archive", help="search the list archive")
    ar.add_argument("--list", required=True)
    ar.add_argument("--query", required=True)

    a = p.parse_args(argv)
    handlers = {
        "create": _cmd_create,
        "sub": _cmd_sub,
        "confirm": _cmd_confirm,
        "unsub": _cmd_unsub,
        "post": _cmd_post,
        "approve": _cmd_approve,
        "reject": _cmd_reject,
        "digest": _cmd_digest,
        "archive": _cmd_archive,
    }
    return handlers[a.command](a)


if __name__ == "__main__":
    sys.exit(main())
