"""CLI: python -m levi.mailtriage — sovereign mail triage, local only.

Subcommands:
  inbox       show the inbox (snoozed hidden unless --include-snoozed)
  bundles     show bundle counts / list one bundle
  snooze      snooze a message: --until 'YYYY-MM-DD HH:MM' or --until-reply
  unsnooze    lift a snooze
  wake        list + clear due snoozes; check for replies
  draft       show template smart-reply suggestions for a message
  save-draft  save a suggestion as a draft
  drafts      list drafts
  approve     approve a draft (marks approved + prints it; never sends)
  discard     delete a draft

Read-only against the user's real mail: --maildir/--mbox pick the store
(default: ~/Maildir, ~/Mail, ~/.mail, ~/mail). Triage state lives in
--home / LEVI_HOME / ~/.levi/mailtriage. Times in --until parse in the
local timezone.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from levi.mailtriage.replies import ReplyEngine
from levi.mailtriage.store import MailStore
from levi.mailtriage.triage import TriageEngine, default_home


def _home(a) -> Path:
    return Path(a.home) if a.home else default_home()


def _store(a) -> MailStore:
    try:
        if a.maildir:
            return MailStore(Path(a.maildir))
        if a.mbox:
            return MailStore(Path(a.mbox))
        return MailStore()
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)


def _records(a):
    store = _store(a)
    try:
        return list(store.iter_messages())
    finally:
        store.close()


def _fmt(rec) -> str:
    subj = rec.get("subject", "")[:70]
    return (
        f"[{rec['bundle'] if 'bundle' in rec else '?':12}] "
        f"{rec.get('date', '?')[:16]:16} {rec.get('from', '?')[:28]:28} {subj}\n"
        f"  id={rec['id']}"
    )


def cmd_inbox(a) -> int:
    eng = TriageEngine(_home(a))
    due = eng.wake_due()
    for mid in due:
        print(f"(woke: {mid})")
    view = eng.inbox_view(
        _records(a), bundle=a.bundle, include_snoozed=a.include_snoozed
    )[: a.limit]
    if not view:
        print("inbox is clear.")
        return 0
    for rec in view:
        print(_fmt(rec))
    return 0


def cmd_bundles(a) -> int:
    eng = TriageEngine(_home(a))
    grouped = eng.bundle_all(eng.inbox_view(_records(a), include_snoozed=True))
    order = ["people", "receipts", "newsletters", "notifications", "other"]
    names = sorted(grouped, key=lambda n: order.index(n) if n in order else 99)
    if a.name:
        for rec in grouped.get(a.name, [])[: a.limit]:
            print(_fmt(rec))
        return 0
    for name in names:
        print(f"{name:14} {len(grouped[name])}")
    return 0


def _parse_until(text: str) -> float:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).astimezone().timestamp()
        except ValueError:
            continue
    raise SystemExit(f"cannot parse --until {text!r}; use 'YYYY-MM-DD HH:MM'")


def cmd_snooze(a) -> int:
    eng = TriageEngine(_home(a))
    if a.until_reply:
        rec = next((r for r in _records(a) if r["id"] == a.id), None)
        eng.snooze_until_reply(
            a.id,
            sender=rec["from"] if rec else "",
            subject=rec["subject"] if rec else "",
        )
        print(f"snoozed {a.id} until a reply arrives")
    elif a.until:
        ts = _parse_until(a.until)
        eng.snooze_until(a.id, ts, note=a.note or "")
        print(f"snoozed {a.id} until {a.until}")
    else:
        print("need --until 'YYYY-MM-DD HH:MM' or --until-reply", file=sys.stderr)
        return 2
    return 0


def cmd_unsnooze(a) -> int:
    eng = TriageEngine(_home(a))
    print("unsnoozed" if eng.unsnooze(a.id) else f"not snoozed: {a.id}")
    return 0


def cmd_wake(a) -> int:
    eng = TriageEngine(_home(a))
    records = _records(a)
    due = eng.wake_due()
    woken = eng.check_replies(records)
    for mid in due:
        print(f"due: {mid}")
    for mid in woken:
        print(f"reply arrived, woke: {mid}")
    if not due and not woken:
        print("nothing to wake.")
    return 0


def cmd_draft(a) -> int:
    eng = ReplyEngine(_home(a))
    rec = next((r for r in _records(a) if r["id"] == a.id), None)
    if rec is None:
        print(f"no message {a.id!r}", file=sys.stderr)
        return 1
    suggestions = eng.suggest(rec)
    if not suggestions:
        print("no template matched this message.")
        return 0
    for i, s in enumerate(suggestions):
        print(f"--- suggestion {i} [{s['template']}] ({s['label']}) ---")
        print(f"To: {s['to']}\nSubject: {s['subject']}\n\n{s['body']}\n")
        print(f"honest note: {s['honest_note']}\n")
    return 0


def cmd_save_draft(a) -> int:
    eng = ReplyEngine(_home(a))
    rec = next((r for r in _records(a) if r["id"] == a.id), None)
    if rec is None:
        print(f"no message {a.id!r}", file=sys.stderr)
        return 1
    suggestions = eng.suggest(rec)
    if a.index >= len(suggestions):
        print(
            f"only {len(suggestions)} suggestion(s); --index out of range",
            file=sys.stderr,
        )
        return 1
    draft_id = eng.save_draft(rec, suggestions[a.index])
    print(
        f"saved draft {draft_id} (template: {suggestions[a.index]['template']}) — NOT sent"
    )
    return 0


def cmd_drafts(a) -> int:
    eng = ReplyEngine(_home(a))
    drafts = eng.list_drafts(status=a.status)
    if not drafts:
        print("no drafts.")
        return 0
    for d in drafts:
        print(
            f"[{d['status']:8}] {d['id']} template={d['template']} to={d['to']}\n"
            f"  subject={d['subject']}"
        )
    return 0


def cmd_approve(a) -> int:
    eng = ReplyEngine(_home(a))
    try:
        draft = eng.approve(a.id)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        f"APPROVED (still not sent — copy into your mail client):\n"
        f"To: {draft['to']}\nSubject: {draft['subject']}\n\n{draft['body']}"
    )
    return 0


def cmd_discard(a) -> int:
    eng = ReplyEngine(_home(a))
    print("discarded" if eng.discard(a.id) else f"no draft {a.id!r}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.mailtriage",
        description="sovereign mail triage — local maildir/mbox, read-only, no network",
    )
    ap.add_argument("--home", default=None, help="triage state dir")
    ap.add_argument("--maildir", default=None, help="maildir to read")
    ap.add_argument("--mbox", default=None, help="mbox file to read")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("inbox", help="show the inbox (snoozed hidden)")
    p.add_argument("--bundle", default=None)
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--include-snoozed", action="store_true")
    p.set_defaults(func=cmd_inbox)

    p = sub.add_parser("bundles", help="bundle counts or one bundle's mail")
    p.add_argument("name", nargs="?", default=None)
    p.add_argument("--limit", type=int, default=30)
    p.set_defaults(func=cmd_bundles)

    p = sub.add_parser("snooze", help="snooze a message")
    p.add_argument("id")
    p.add_argument("--until", default=None, help="'YYYY-MM-DD HH:MM'")
    p.add_argument("--until-reply", action="store_true")
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_snooze)

    p = sub.add_parser("unsnooze", help="lift a snooze")
    p.add_argument("id")
    p.set_defaults(func=cmd_unsnooze)

    p = sub.add_parser("wake", help="wake due snoozes; check for replies")
    p.set_defaults(func=cmd_wake)

    p = sub.add_parser("draft", help="template smart-reply suggestions")
    p.add_argument("id")
    p.set_defaults(func=cmd_draft)

    p = sub.add_parser("save-draft", help="save a suggestion as a draft")
    p.add_argument("id")
    p.add_argument("--index", type=int, default=0)
    p.set_defaults(func=cmd_save_draft)

    p = sub.add_parser("drafts", help="list drafts")
    p.add_argument("--status", default=None, choices=["draft", "approved"])
    p.set_defaults(func=cmd_drafts)

    p = sub.add_parser("approve", help="approve a draft (never sends)")
    p.add_argument("id")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("discard", help="delete a draft")
    p.add_argument("id")
    p.set_defaults(func=cmd_discard)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
