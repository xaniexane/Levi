"""CLI: python -m levi.rendezvous <command> [options]

Declared-intent rendezvous board: declare intents, RSVP opt-in, withdraw,
cancel, list. Presence as a message, never a data stream.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import RendezvousError
from .model import IntentStore


def _cmd_declare(a) -> int:
    store = IntentStore()
    intent = store.declare(
        a.who, a.where, a.starts, a.ends, note=a.note or "",
        invites=a.invite or [],
    )
    print(json.dumps(intent.to_dict(), indent=2, ensure_ascii=False))
    return 0


def _cmd_rsvp(a) -> int:
    store = IntentStore()
    intent = store.rsvp(a.intent, a.member)
    print("rsvp recorded: %s attending %s" % (a.member, intent.id))
    return 0


def _cmd_withdraw(a) -> int:
    store = IntentStore()
    store.withdraw(a.intent, a.member)
    print("rsvp withdrawn: %s from %s" % (a.member, a.intent))
    return 0


def _cmd_cancel(a) -> int:
    store = IntentStore()
    store.cancel(a.intent)
    print("cancelled (record kept): %s" % a.intent)
    return 0


def _one_line(i) -> str:
    return "%s  [%s] %s @ %s  %s..%s  attending=%d%s" % (
        i.id,
        i.status(),
        i.who,
        i.where,
        i.starts_at,
        i.ends_at,
        len(i.rsvps),
        "  note: %s" % i.note if i.note else "",
    )


def _cmd_list(a) -> int:
    store = IntentStore()
    intents = store.list_all() if a.all else store.list_active()
    if not intents:
        print("no intents" if a.all else "no active intents")
        return 0
    for i in intents:
        print(_one_line(i))
    return 0


def _cmd_show(a) -> int:
    store = IntentStore()
    intent = store.get(a.intent)
    print(json.dumps(intent.to_dict(), indent=2, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="levi.rendezvous")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("declare", help="declare an intent (who/where/when)")
    d.add_argument("--who", required=True)
    d.add_argument("--where", required=True)
    d.add_argument("--starts", required=True, help="ISO-8601 start")
    d.add_argument("--ends", required=True, help="ISO-8601 end")
    d.add_argument("--note", default="")
    d.add_argument("--invite", action="append", default=[])
    d.set_defaults(fn=_cmd_declare)

    r = sub.add_parser("rsvp", help="opt in to an intent")
    r.add_argument("intent")
    r.add_argument("member")
    r.set_defaults(fn=_cmd_rsvp)

    w = sub.add_parser("withdraw", help="withdraw an RSVP")
    w.add_argument("intent")
    w.add_argument("member")
    w.set_defaults(fn=_cmd_withdraw)

    c = sub.add_parser("cancel", help="cancel an intent (record kept)")
    c.add_argument("intent")
    c.set_defaults(fn=_cmd_cancel)

    l = sub.add_parser("list", help="list intents")
    l.add_argument("--all", action="store_true", help="include expired/cancelled")
    l.set_defaults(fn=_cmd_list)

    s = sub.add_parser("show", help="show one intent")
    s.add_argument("intent")
    s.set_defaults(fn=_cmd_show)

    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except RendezvousError as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
