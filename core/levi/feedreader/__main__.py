"""CLI: python -m levi.feedreader — sovereign RSS/Atom reading, local only."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from levi.feedreader.reader import FeedError, FeedStore


def _store() -> FeedStore:
    return FeedStore()


def cmd_add(args) -> int:
    try:
        f = _store().add(args.url, args.title)
    except FeedError as exc:
        print("feedreader: %s" % exc, file=sys.stderr)
        return 1
    print("subscribed: %s" % f["title"])
    return 0


def cmd_remove(args) -> int:
    _store().remove(args.url)
    print("removed: %s" % args.url)
    return 0


def cmd_list(args) -> int:
    feeds = _store().list_feeds()
    if not feeds:
        print("no subscriptions — add one with: python -m levi.feedreader add URL")
    for f in feeds:
        print("%s  %s" % (f["title"], f["url"]))
    return 0


def cmd_poll(args) -> int:
    st = _store()
    try:
        reports = st.poll(force=args.force)
    except FeedError as exc:
        print("feedreader: %s" % exc, file=sys.stderr)
        return 1
    for r in reports:
        if r.get("skipped"):
            print("skip %s (%s)" % (r["url"], r["reason"]))
        elif r.get("ok"):
            if r.get("not_modified"):
                print("ok   %s (not modified)" % r["url"])
            else:
                print("ok   %s (+%d new)" % (r["url"], r["new_items"]))
        else:
            print("FAIL %s (%s)" % (r["url"], r["error"]), file=sys.stderr)
    return 0


def cmd_items(args) -> int:
    rows = _store().items(feed_url=args.feed, unread_only=args.unread,
                          limit=args.limit)
    if not rows:
        print("nothing here — poll first, or everything is read. Nice.")
    for r in rows:
        flag = " " if r["read"] else "*"
        ts = datetime.fromtimestamp(r["fetched_at"]).strftime("%m-%d %H:%M")
        print("%s [%s] %s\n    %s" % (flag, ts, r["title"], r["link"]))
    return 0


def cmd_read(args) -> int:
    n = _store().mark_read(args.link)
    print("marked read" if n else "no item with that link")
    return 0


def cmd_health(args) -> int:
    for h in _store().health():
        last = ("never" if not h["last_success"] else
                datetime.fromtimestamp(h["last_success"]).strftime("%Y-%m-%d"))
        print("%-8s %-40.40s polls=%d errs=%d streak=%d lat=%.0fms last=%s" % (
            h["status"], h["title"], h["polls"], h["errors"],
            h["fail_streak"], h["latency_ms_avg"], last))
    return 0


def cmd_opml_export(args) -> int:
    text = _store().opml_export()
    if args.out:
        open(args.out, "w", encoding="utf-8").write(text)
        print("wrote %s" % args.out)
    else:
        print(text)
    return 0


def cmd_opml_import(args) -> int:
    try:
        text = open(args.file, encoding="utf-8").read()
    except OSError as exc:
        print("feedreader: %s" % exc, file=sys.stderr)
        return 1
    try:
        n = _store().opml_import(text)
    except FeedError as exc:
        print("feedreader: %s" % exc, file=sys.stderr)
        return 1
    print("imported %d subscription(s)" % n)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.feedreader",
        description="Sovereign RSS/Atom reader (local, chronological, portable).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="subscribe to a feed")
    p.add_argument("url"); p.add_argument("--title", default=None)
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("remove", help="unsubscribe")
    p.add_argument("url")
    p.set_defaults(func=cmd_remove)

    p = sub.add_parser("list", help="list subscriptions")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("poll", help="poll feeds (conditional GET)")
    p.add_argument("--force", action="store_true",
                   help="ignore backoff/interval and poll now")
    p.set_defaults(func=cmd_poll)

    p = sub.add_parser("items", help="show items, newest first")
    p.add_argument("--feed", default=None); p.add_argument("--unread",
                   action="store_true")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_items)

    p = sub.add_parser("read", help="mark an item read by link")
    p.add_argument("link")
    p.set_defaults(func=cmd_read)

    p = sub.add_parser("health", help="per-feed health stats")
    p.set_defaults(func=cmd_health)

    p = sub.add_parser("opml-export", help="export subscriptions as OPML")
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_opml_export)

    p = sub.add_parser("opml-import", help="import subscriptions from OPML")
    p.add_argument("file")
    p.set_defaults(func=cmd_opml_import)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
