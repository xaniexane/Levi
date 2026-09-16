"""CLI: python -m levi.communities

Portable communities — create, populate, export to the open checksummed
format, and import with integrity verification. Mirrors the future
``levi communities`` top-level command.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from levi.communities.model import CommunityError, CommunityStore


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="levi communities",
        description="Portable communities: own the data, leave any platform.",
    )
    sub = p.add_subparsers(dest="cmd")

    c = sub.add_parser("create", help="create a community")
    c.add_argument("id")
    c.add_argument("--name", required=True)

    sub.add_parser("list", help="list local communities")

    s = sub.add_parser("status", help="show a community")
    s.add_argument("id")

    ch = sub.add_parser("add-channel", help="add a channel/room")
    ch.add_argument("community")
    ch.add_argument("channel")
    ch.add_argument("--name", default="")
    ch.add_argument("--kind", default="text")
    ch.add_argument("--topic", default="")

    mb = sub.add_parser("add-member", help="add a member")
    mb.add_argument("community")
    mb.add_argument("member")
    mb.add_argument("--name", default="")

    rl = sub.add_parser("add-role", help="add a role")
    rl.add_argument("community")
    rl.add_argument("role")
    rl.add_argument("--name", default="")
    rl.add_argument("--permissions", default="", help="comma-separated permissions")

    gr = sub.add_parser("grant-role", help="grant a role to a member")
    gr.add_argument("community")
    gr.add_argument("role")
    gr.add_argument("member")

    po = sub.add_parser("post", help="post a message")
    po.add_argument("community")
    po.add_argument("--channel", required=True)
    po.add_argument("--author", required=True)
    po.add_argument("--text", required=True)

    ru = sub.add_parser("set-rules", help="replace governance rules")
    ru.add_argument("community")
    ru.add_argument("rules", nargs="+")

    ex = sub.add_parser("export", help="export to the open checksummed format")
    ex.add_argument("community")
    ex.add_argument("--out", required=True)

    im = sub.add_parser(
        "import", help="import a verified export (fails closed on tampering)"
    )
    im.add_argument("--in", dest="in_path", required=True)
    im.add_argument("--as", dest="as_id", default=None)

    v = sub.add_parser("verify", help="verify an export file without importing")
    v.add_argument("--in", dest="in_path", required=True)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        store = CommunityStore()
    except Exception as exc:  # pragma: no cover - defensive
        print(f"communities: cannot open state: {exc}", file=sys.stderr)
        return 1

    try:
        if args.cmd == "create":
            c = store.create(args.id, args.name)
            print(f"community [{c.id}] {c.name}")
        elif args.cmd == "list":
            comms = store.list()
            for c in comms:
                print(
                    f"  [{c.id}] {c.name} "
                    f"({len(c.members)} members, {len(c.messages)} messages)"
                )
            if not comms:
                print("  (none)")
        elif args.cmd == "status":
            print(store.format_status(args.id))
        elif args.cmd == "add-channel":
            ch = store.add_channel(
                args.community,
                args.channel,
                args.name,
                kind=args.kind,
                topic=args.topic,
            )
            print(f"channel #{ch.name} [{ch.id}]")
        elif args.cmd == "add-member":
            m = store.add_member(args.community, args.member, args.name)
            print(f"member {m.name} [{m.id}]")
        elif args.cmd == "add-role":
            perms = [x.strip() for x in args.permissions.split(",") if x.strip()]
            r = store.add_role(args.community, args.role, args.name, permissions=perms)
            print(f"role {r.name} [{r.id}] perms={','.join(r.permissions) or '(none)'}")
        elif args.cmd == "grant-role":
            store.grant_role(args.community, args.role, args.member)
            print(f"granted {args.role} to {args.member}")
        elif args.cmd == "post":
            m = store.post(args.community, args.channel, args.author, args.text)
            print(f"message [{m.id}] in #{args.channel}")
        elif args.cmd == "set-rules":
            store.set_rules(args.community, args.rules)
            print(f"rules updated ({len(args.rules)})")
        elif args.cmd == "export":
            out = store.export(args.community, Path(args.out))
            print(f"exported [{args.community}] -> {out}")
            print("format: levi-community-export/1, per-section SHA-256 + manifest")
        elif args.cmd == "import":
            c = store.import_community(Path(args.in_path), as_id=args.as_id)
            print(f"imported [{c.id}] {c.name} — checksums verified")
        elif args.cmd == "verify":
            from levi.communities.model import verify_export
            import json

            community = verify_export(json.loads(Path(args.in_path).read_text()))
            print(
                f"VALID export: [{community.id}] {community.name} — "
                f"all section checksums + manifest verified"
            )
        else:
            build_parser().print_help()
            return 2
    except CommunityError as exc:
        print(f"communities: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
