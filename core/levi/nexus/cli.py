"""`levi nexus` — inter-organ messaging from the command line.

The CLI keeps a persistent organ registry under ``~/.levi/nexus/``
(``LEVI_HOME``-overridable): endpoints named in ``send`` are
registered on first use, so ``organs`` and ``broadcast`` see them
across invocations. Dead letters persist too — nothing is silent.
"""

from __future__ import annotations

import argparse
import json

from .bus import Nexus
from .envelope import Envelope


def _nexus() -> Nexus:
    return Nexus()  # default home: LEVI_HOME or ~/.levi


def register_nexus_parser(sub) -> None:
    np = sub.add_parser("nexus", help="Inter-organ messaging nexus (envelopes)")
    cmds = np.add_subparsers(dest="nexus_cmd")

    send_p = cmds.add_parser("send", help="send one envelope, print its receipt")
    send_p.add_argument("--from", dest="from_organ", required=True)
    send_p.add_argument("--to", dest="to_organ", required=True)
    send_p.add_argument("--kind", required=True)
    send_p.add_argument("--payload", default="{}", help="JSON object payload")
    send_p.add_argument("--ttl", type=float, default=600.0)

    bc_p = cmds.add_parser("broadcast", help="fan an envelope to all organs")
    bc_p.add_argument("--from", dest="from_organ", required=True)
    bc_p.add_argument("--kind", required=True)
    bc_p.add_argument("--payload", default="{}", help="JSON object payload")
    bc_p.add_argument("--ttl", type=float, default=600.0)

    cmds.add_parser("organs", help="list registered organs")

    dl_p = cmds.add_parser("dead-letter", help="list dead letters with reasons")
    dl_p.add_argument("--limit", type=int, default=20)


def cmd_nexus(args: argparse.Namespace) -> int:
    cmd = getattr(args, "nexus_cmd", None) or "organs"
    nexus = _nexus()

    if cmd == "send":
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError as exc:
            print("bad --payload JSON: %s" % exc)
            return 2
        # endpoints join the nexus on first use
        nexus.register_organ(args.from_organ)
        nexus.register_organ(args.to_organ)
        receipt = nexus.send(
            from_organ=args.from_organ,
            to_organ=args.to_organ,
            kind=args.kind,
            payload=payload,
            ttl=args.ttl,
        )
        print(json.dumps(receipt.to_dict(), indent=2))
        return 0 if receipt.ok() else 1

    if cmd == "broadcast":
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError as exc:
            print("bad --payload JSON: %s" % exc)
            return 2
        nexus.register_organ(args.from_organ)
        envelope = Envelope(
            from_organ=args.from_organ,
            to_organ=None,
            kind=args.kind,
            payload=payload,
            ttl=args.ttl,
        )
        receipts = nexus.broadcast(envelope, exclude=args.from_organ)
        print(json.dumps([r.to_dict() for r in receipts], indent=2))
        return 0 if all(r.ok() for r in receipts) else 1

    if cmd == "organs":
        for organ in nexus.organs():
            print(organ)
        return 0

    if cmd == "dead-letter":
        for entry in nexus.dead_letters()[-args.limit :]:
            env = entry.get("envelope", {})
            print(
                "%s -> %s [%s] %s"
                % (
                    env.get("from_organ"),
                    env.get("to_organ"),
                    env.get("kind"),
                    entry.get("reason"),
                )
            )
        return 0

    print("unknown nexus command: %s" % cmd)
    return 2
