"""CLI: python -m levi.charters

Community charters — versioned founder-signed governance, mod action
log with appeals, checksummed export/import, attach to communities.
Mirrors the future ``levi charters`` top-level command.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from levi.charters.charters import CharterError, CharterStore


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="levi charters",
        description="Community charters: governance as a portable, signed artifact.",
    )
    sub = p.add_subparsers(dest="cmd")

    nw = sub.add_parser("new", help="found a charter (generates the founder key)")
    nw.add_argument("id")
    nw.add_argument("--community", required=True)
    nw.add_argument("--founder", required=True)
    nw.add_argument("--rules", nargs="*", default=[])

    sub.add_parser("list", help="list charters")

    sh = sub.add_parser("show", help="show a charter")
    sh.add_argument("id")

    vf = sub.add_parser("verify", help="verify a charter's founder signature")
    vf.add_argument("id")

    ar = sub.add_parser("add-rule", help="add a rule (re-signs the charter)")
    ar.add_argument("id")
    ar.add_argument("--text", required=True)

    rr = sub.add_parser("retire-rule", help="retire a rule")
    rr.add_argument("id")
    rr.add_argument("rule")

    rl = sub.add_parser("add-role", help="add a governance role")
    rl.add_argument("id")
    rl.add_argument("role")
    rl.add_argument("--name", default="")
    rl.add_argument("--permissions", default="")

    sc = sub.add_parser("set-succession", help="set succession plan")
    sc.add_argument("id")
    sc.add_argument("--successors", default="")
    sc.add_argument("--trigger", default="")

    sa = sub.add_parser("set-amendment", help="set amendment procedure + quorum")
    sa.add_argument("id")
    sa.add_argument("--procedure", required=True)
    sa.add_argument("--quorum", type=int, required=True)

    am = sub.add_parser("amend", help="bump charter version with claimed approvals")
    am.add_argument("id")
    am.add_argument("--changes", nargs="+", required=True)
    am.add_argument(
        "--approvals",
        nargs="+",
        required=True,
        help="claimed approvers (recorded, not cryptographically proven)",
    )

    rk = sub.add_parser("rotate-key", help="rotate the founder key")
    rk.add_argument("id")

    ma = sub.add_parser("mod", help="record a mod action (reason required)")
    ma.add_argument("id")
    ma.add_argument("--moderator", required=True)
    ma.add_argument(
        "--action",
        required=True,
        choices=["warn", "remove", "ban", "unban", "note", "appeal-decision"],
    )
    ma.add_argument("--target", required=True)
    ma.add_argument("--reason", required=True)

    ap = sub.add_parser("appeal", help="file an appeal against a mod action")
    ap.add_argument("id")
    ap.add_argument("--action-id", required=True)
    ap.add_argument("--appellant", required=True)
    ap.add_argument("--text", required=True)

    da = sub.add_parser("decide-appeal", help="decide an appeal")
    da.add_argument("id")
    da.add_argument("--appeal-id", required=True)
    da.add_argument("--by", required=True)
    da.add_argument("--decision", required=True, choices=["upheld", "overturned"])
    da.add_argument("--note", default="")

    ml = sub.add_parser("modlog", help="show mod actions and appeals")
    ml.add_argument("id")

    at = sub.add_parser(
        "attach", help="link charter into a community's governance block"
    )
    at.add_argument("id")
    at.add_argument("--community", required=True)

    ex = sub.add_parser(
        "export", help="export charter + mod log + appeals (checksummed)"
    )
    ex.add_argument("id")
    ex.add_argument("--out", required=True)

    im = sub.add_parser(
        "import", help="import a verified charter export (fails closed)"
    )
    im.add_argument("--in", dest="in_path", required=True)
    im.add_argument("--as", dest="as_id", default=None)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        store = CharterStore()
    except Exception as exc:  # pragma: no cover - defensive
        print(f"charters: cannot open state: {exc}", file=sys.stderr)
        return 1

    try:
        if args.cmd == "new":
            doc = store.new(args.id, args.community, args.founder, rules=args.rules)
            print(
                f"charter [{doc['id']}] v1 for community '{doc['community_id']}' — founder key generated"
            )
        elif args.cmd == "list":
            ids = store.list()
            print("\n".join(f"  {i}" for i in ids) or "  (none)")
        elif args.cmd == "show":
            print(store.format_charter(args.id))
        elif args.cmd == "verify":
            print("VALID signature" if store.verify(args.id) else "INVALID signature")
            return 0 if store.verify(args.id) else 1
        elif args.cmd == "add-rule":
            doc = store.add_rule(args.id, args.text)
            print(f"rule added (charter v{doc['version']}, re-signed)")
        elif args.cmd == "retire-rule":
            store.retire_rule(args.id, args.rule)
            print(f"rule {args.rule} retired")
        elif args.cmd == "add-role":
            perms = [x.strip() for x in args.permissions.split(",") if x.strip()]
            store.add_role(args.id, args.role, args.name, permissions=perms)
            print(f"role {args.role} added")
        elif args.cmd == "set-succession":
            succ = [s.strip() for s in args.successors.split(",") if s.strip()]
            store.set_succession(args.id, succ, trigger=args.trigger or None)
            print("succession updated")
        elif args.cmd == "set-amendment":
            store.set_amendment(args.id, args.procedure, args.quorum)
            print("amendment procedure updated")
        elif args.cmd == "amend":
            doc = store.amend(args.id, args.changes, args.approvals)
            print(
                f"amended -> v{doc['version']} "
                f"(approvals recorded as claimed: {', '.join(sorted(set(args.approvals)))})"
            )
        elif args.cmd == "rotate-key":
            store.rotate_key(args.id)
            print(
                "founder key rotated; charter re-signed; rotation recorded in history"
            )
        elif args.cmd == "mod":
            a = store.mod_action(
                args.id, args.moderator, args.action, args.target, args.reason
            )
            print(
                f"mod action [{a['id'][:8]}] {args.action} {args.target} — reason recorded"
            )
        elif args.cmd == "appeal":
            ap = store.appeal(args.id, args.action_id, args.appellant, args.text)
            print(f"appeal [{ap['id'][:8]}] filed against [{args.action_id[:8]}]")
        elif args.cmd == "decide-appeal":
            ap = store.decide_appeal(
                args.id, args.appeal_id, args.by, args.decision, note=args.note
            )
            print(f"appeal [{ap['id'][:8]}] {args.decision} by {args.by}")
        elif args.cmd == "modlog":
            print(store.format_modlog(args.id))
        elif args.cmd == "attach":
            ref = store.attach(args.id, args.community)
            print(
                f"attached charter [{ref['id']}] v{ref['version']} to community '{args.community}'"
            )
        elif args.cmd == "export":
            out = store.export(args.id, Path(args.out))
            print(f"exported [{args.id}] -> {out}")
            print("format: levi-charter-export/1, per-section SHA-256 + manifest")
        elif args.cmd == "import":
            cid = store.import_charter(Path(args.in_path), as_id=args.as_id)
            print(
                f"imported [{cid}] — checksums verified; re-keyed locally (see history)"
            )
        else:
            build_parser().print_help()
            return 2
    except CharterError as exc:
        print(f"charters: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
