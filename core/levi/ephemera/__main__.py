"""CLI: python -m levi.ephemera

True-delete ephemeral channels. The passphrase is the channel key — LEVI
never stores it; lose it and messages are unreadable (that's the point).
"""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import datetime

from levi.ephemera.store import EphemeraError, EphemeraStore


def _store() -> EphemeraStore:
    return EphemeraStore()


def _passphrase(args) -> str:
    if args.passphrase:
        return args.passphrase
    return getpass.getpass("Channel passphrase: ")


def cmd_create(args) -> int:
    st = _store()
    try:
        m = st.create_channel(args.name, args.ttl, _passphrase(args))
    except EphemeraError as exc:
        print("ephemera: %s" % exc, file=sys.stderr)
        return 1
    print("channel '%s' created — TTL %ds (messages expire %ds after posting)"
          % (m["name"], m["ttl_seconds"], m["ttl_seconds"]))
    return 0


def cmd_post(args) -> int:
    st = _store()
    try:
        r = st.post(args.channel, args.author, args.body, _passphrase(args),
                    forwarding_discouraged=args.no_forward)
    except EphemeraError as exc:
        print("ephemera: %s" % exc, file=sys.stderr)
        return 1
    exp = datetime.fromtimestamp(r["expires_at"]).strftime("%Y-%m-%d %H:%M")
    print("posted %s — expires %s%s" % (
        r["id"], exp,
        " [forwarding discouraged]" if args.no_forward else ""))
    return 0


def cmd_read(args) -> int:
    st = _store()
    try:
        msg = st.read_message(args.channel, args.msg_id, _passphrase(args),
                              reader=args.reader)
    except EphemeraError as exc:
        print("ephemera: %s" % exc, file=sys.stderr)
        return 1
    except ValueError as exc:
        print("ephemera: cannot decrypt: %s" % exc, file=sys.stderr)
        return 1
    print("[%s] %s" % (msg["author"],
                       datetime.fromtimestamp(msg["created_at"]).strftime("%H:%M")))
    if msg["forwarding_discouraged"]:
        print("(the author asked that this message not be forwarded "
              "or screenshotted — honor it)")
    print(msg["body"])
    return 0


def cmd_sweep(args) -> int:
    st = _store()
    deleted = st.sweep(args.channel)
    if not deleted:
        print("nothing expired — no deletions")
    for d in deleted:
        print("deleted %s/%s — receipt %s" % (d["channel"], d["id"], d["receipt"]))
    return 0


def cmd_receipts(args) -> int:
    st = _store()
    try:
        v = st.verify_receipts(args.channel)
    except EphemeraError as exc:
        print("ephemera: %s" % exc, file=sys.stderr)
        return 1
    if v["ok"]:
        print("receipt chain OK — %d deletion receipts verified" % v["count"])
        return 0
    print("RECEIPT CHAIN BROKEN: %s" % v["error"], file=sys.stderr)
    return 1


def cmd_channels(args) -> int:
    for name in _store().list_channels():
        print(name)
    return 0


def cmd_access(args) -> int:
    st = _store()
    try:
        rows = st.access_log(args.channel)
    except EphemeraError as exc:
        print("ephemera: %s" % exc, file=sys.stderr)
        return 1
    if not rows:
        print("no recorded reads")
    for r in rows:
        print("%s  %s read %s (%s)" % (
            datetime.fromtimestamp(r["ts"]).strftime("%Y-%m-%d %H:%M"),
            r["reader"], r["msg_id"], r["note"]))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.ephemera",
        description="True-delete ephemeral channels (local, encrypted at rest).")
    ap.add_argument("--passphrase", default=None,
                    help="channel passphrase (else prompted, never stored)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("create", help="create a channel")
    p.add_argument("name"); p.add_argument("--ttl", type=int, default=86400,
                                          help="seconds until messages expire")
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("post", help="post a message")
    p.add_argument("channel"); p.add_argument("--author", required=True)
    p.add_argument("--body", required=True)
    p.add_argument("--no-forward", action="store_true",
                   help="mark forwarding/screenshotting as discouraged")
    p.set_defaults(func=cmd_post)

    p = sub.add_parser("read", help="read a message (access-logged)")
    p.add_argument("channel"); p.add_argument("msg_id")
    p.add_argument("--reader", default="owner")
    p.set_defaults(func=cmd_read)

    p = sub.add_parser("sweep", help="delete expired messages (secure overwrite)")
    p.add_argument("channel", nargs="?", default=None)
    p.set_defaults(func=cmd_sweep)

    p = sub.add_parser("receipts", help="verify deletion-receipt chain")
    p.add_argument("channel")
    p.set_defaults(func=cmd_receipts)

    p = sub.add_parser("channels", help="list channels")
    p.set_defaults(func=cmd_channels)

    p = sub.add_parser("access", help="show access log")
    p.add_argument("channel")
    p.set_defaults(func=cmd_access)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
