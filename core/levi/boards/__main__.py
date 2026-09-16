"""CLI: python -m levi.boards <command> [options]

The community board desk: create charter-governed areas, post through
moderation, approve/reject with signed reasons, read what's new to you,
and carry areas home as offline packets.
"""

from __future__ import annotations

import argparse
import sys

from . import areas


def _cmd_create(a) -> int:
    try:
        cfg = areas.create_area(a.name, a.charter, a.moderator)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print("area %r created, moderator %s" % (cfg["name"], cfg["moderator"]))
    return 0


def _cmd_charter(a) -> int:
    try:
        print(areas.charter(a.name))
    except KeyError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


def _cmd_post(a) -> int:
    try:
        pid = areas.post(a.name, a.author, a.subject, a.body)
    except (KeyError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print("posted to queue: %s" % pid)
    return 0


def _cmd_queue(a) -> int:
    try:
        pending = areas.queue(a.name)
    except KeyError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    if not pending:
        print("queue empty")
        return 0
    for p in pending:
        print("%s  %s  %s  (%s)" % (p["id"], p["author"], p["subject"], p["ts"]))
    return 0


def _cmd_approve(a) -> int:
    try:
        msg = areas.approve(a.name, a.id, a.moderator)
    except (KeyError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print("approved %s (by %s)" % (msg["id"], msg["approved_by"]))
    return 0


def _cmd_reject(a) -> int:
    try:
        rec = areas.reject(a.name, a.id, a.moderator, a.reason)
    except (KeyError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print("rejected %s (by %s): %s" % (rec["id"], rec["rejected_by"], rec["reason"]))
    return 0


def _cmd_read(a) -> int:
    try:
        msgs = areas.read(a.name, a.reader)
    except (KeyError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    if not msgs:
        print("nothing new")
        return 0
    for m in msgs:
        print("=== %s | %s <- %s (%s)" % (m["id"], m["subject"], m["author"], m["ts"]))
        print(m["body"])
    return 0


def _cmd_export(a) -> int:
    try:
        dest = areas.export_packet(a.name, a.dest)
    except (KeyError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print("exported -> %s" % dest)
    return 0


def _cmd_import(a) -> int:
    try:
        n = areas.import_packet(a.src, a.name, a.charter)
    except (KeyError, ValueError, FileNotFoundError, OSError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print("imported %d message(s) into %r" % (n, a.name))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="levi.boards",
        description="Charter-governed local message areas with offline packets",
    )
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("create", help="create a message area (charter required)")
    c.add_argument("--name", required=True)
    c.add_argument("--charter", required=True)
    c.add_argument("--moderator", required=True)

    ch = sub.add_parser("charter", help="print an area's charter")
    ch.add_argument("--name", required=True)

    po = sub.add_parser("post", help="post to the moderation queue")
    po.add_argument("--name", required=True)
    po.add_argument("--author", required=True)
    po.add_argument("--subject", required=True)
    po.add_argument("--body", required=True)

    q = sub.add_parser("queue", help="list the moderation queue")
    q.add_argument("--name", required=True)

    ap = sub.add_parser("approve", help="approve a pending post into the area")
    ap.add_argument("--name", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--moderator", required=True)

    rj = sub.add_parser("reject", help="reject a pending post with a recorded reason")
    rj.add_argument("--name", required=True)
    rj.add_argument("--id", required=True)
    rj.add_argument("--moderator", required=True)
    rj.add_argument("--reason", required=True)

    rd = sub.add_parser("read", help="read messages unseen by this reader")
    rd.add_argument("--name", required=True)
    rd.add_argument("--reader", required=True)

    ex = sub.add_parser("export", help="export the area to an offline packet file")
    ex.add_argument("--name", required=True)
    ex.add_argument("--dest", required=True)

    im = sub.add_parser("import", help="import an offline packet file into an area")
    im.add_argument("--src", required=True)
    im.add_argument("--name", required=True)
    im.add_argument("--charter", required=True)

    a = p.parse_args(argv)
    handlers = {
        "create": _cmd_create,
        "charter": _cmd_charter,
        "post": _cmd_post,
        "queue": _cmd_queue,
        "approve": _cmd_approve,
        "reject": _cmd_reject,
        "read": _cmd_read,
        "export": _cmd_export,
        "import": _cmd_import,
    }
    return handlers[a.command](a)


if __name__ == "__main__":
    sys.exit(main())
