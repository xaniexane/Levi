"""CLI: python -m levi.telegraph <command> [options]

The telegraph office counter: seal envelopes, poll the drop directory,
read the inbox, answer "who are you", and browse the Chooser directory.
"""

from __future__ import annotations

import argparse
import sys

from . import envelopes, identity, directory


def _cmd_send(a) -> int:
    env = envelopes.new_envelope(
        a.src, a.dst, a.kind, a.body, grade=a.grade, expires_in_s=a.expires_in
    )
    path = envelopes.seal(env)
    print("sealed %s grade=%d -> %s (%s)" % (env["id"], env["grade"], env["dst"], path))
    return 0


def _cmd_poll(a) -> int:
    summary = envelopes.poll(a.drop, a.node)
    print(
        "poll: carried=%d skipped_not_mine=%d refused_loop=%d "
        "refused_expired=%d"
        % (
            summary["carried"],
            summary["skipped_not_mine"],
            summary["refused_loop"],
            summary["refused_expired"],
        )
    )
    return 0


def _cmd_inbox(a) -> int:
    envs = envelopes.read_inbox(a.node)
    if not envs:
        print("inbox empty")
        return 0
    for e in envs:
        print(
            "[grade %d] %s <- %s (%s): %s"
            % (e["grade"], e["id"], e["src"], e["kind"], e["body"])
        )
        if e.get("hops"):
            print("   hops: %s" % " -> ".join(e["hops"]))
    return 0


def _cmd_ack(a) -> int:
    if envelopes.ack(a.node, a.id):
        print("acked %s" % a.id)
        return 0
    print("no such envelope in inbox: %s" % a.id, file=sys.stderr)
    return 1


def _cmd_register_card(a) -> int:
    try:
        card = identity.register_card(
            a.node, a.answerback, capabilities=a.cap, replace=a.replace
        )
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print("card registered: %s answers %r" % (card["node"], card["answerback"]))
    return 0


def _cmd_answerback(a) -> int:
    try:
        print(identity.answerback(a.node))
    except KeyError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


def _cmd_handshake(a) -> int:
    res = identity.handshake(a.me, a.peer, a.presented)
    print("%s: %s" % (res["verdict"], res["detail"]))
    return 0 if res["verdict"] == "verified" else 1


def _cmd_register(a) -> int:
    try:
        e = directory.register(a.name, a.kind, a.zone, a.node, address=a.address or "")
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print(
        "registered %s:%s@%s -> node %s" % (e["name"], e["kind"], e["zone"], e["node"])
    )
    return 0


def _cmd_names(a) -> int:
    rows = directory.browse(kind=a.kind or "", zone=a.zone or "")
    if not rows:
        print("directory empty")
        return 0
    for e in rows:
        addr = (" [%s]" % e["address"]) if e["address"] else ""
        print(
            "%s:%s@%s  node=%s%s" % (e["name"], e["kind"], e["zone"], e["node"], addr)
        )
    return 0


def _cmd_unregister(a) -> int:
    if directory.unregister(a.name, a.kind, a.zone, a.node):
        print("released %s:%s@%s" % (a.name, a.kind, a.zone))
        return 0
    print("no such registration owned by %s" % a.node, file=sys.stderr)
    return 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="levi.telegraph",
        description="The telegraph office: store-and-forward for offline nodes",
    )
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("send", help="seal an envelope into a node's outbox")
    s.add_argument("--src", required=True)
    s.add_argument("--dst", required=True)
    s.add_argument("--kind", default="note", choices=["note", "file", "echo"])
    s.add_argument("--body", required=True)
    s.add_argument("--grade", type=int, default=5)
    s.add_argument("--expires-in", type=int, default=None, help="seconds until expiry")

    po = sub.add_parser("poll", help="poll a drop dir for envelopes to me")
    po.add_argument("--drop", required=True)
    po.add_argument("--node", required=True)

    ib = sub.add_parser("inbox", help="list my inbox")
    ib.add_argument("--node", required=True)

    ak = sub.add_parser("ack", help="remove an envelope from my inbox")
    ak.add_argument("--node", required=True)
    ak.add_argument("--id", required=True)

    rc = sub.add_parser(
        "register-card", help="register this node's answerback identity"
    )
    rc.add_argument("--node", required=True)
    rc.add_argument("--answerback", required=True)
    rc.add_argument("--cap", nargs="*", default=[])
    rc.add_argument("--replace", action="store_true")

    ab = sub.add_parser("answerback", help="answer WRU for a node")
    ab.add_argument("--node", required=True)

    hs = sub.add_parser("handshake", help="verify a peer's answerback against its card")
    hs.add_argument("--me", required=True)
    hs.add_argument("--peer", required=True)
    hs.add_argument("--presented", required=True)

    r = sub.add_parser("register", help="claim a name in the Chooser directory")
    r.add_argument("--name", required=True)
    r.add_argument("--kind", required=True)
    r.add_argument("--zone", required=True)
    r.add_argument("--node", required=True)
    r.add_argument("--address", default="")

    n = sub.add_parser("names", help="browse the Chooser directory")
    n.add_argument("--kind", default="")
    n.add_argument("--zone", default="")

    u = sub.add_parser("unregister", help="release one of my names")
    u.add_argument("--name", required=True)
    u.add_argument("--kind", required=True)
    u.add_argument("--zone", required=True)
    u.add_argument("--node", required=True)

    a = p.parse_args(argv)
    handlers = {
        "send": _cmd_send,
        "poll": _cmd_poll,
        "inbox": _cmd_inbox,
        "ack": _cmd_ack,
        "register-card": _cmd_register_card,
        "answerback": _cmd_answerback,
        "handshake": _cmd_handshake,
        "register": _cmd_register,
        "names": _cmd_names,
        "unregister": _cmd_unregister,
    }
    return handlers[a.command](a)


if __name__ == "__main__":
    sys.exit(main())
