"""CLI: python -m levi.threads

Bridging-ranked discussion trees — threaded discussions ranked by
quality + cross-camp bridging consensus, with portable signed identity
profiles. Mirrors the future ``levi threads`` top-level command.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from levi.threads.threads import ThreadError, ThreadStore


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="levi threads",
        description="Discussion trees ranked by quality + bridging consensus — not engagement.",
    )
    sub = p.add_subparsers(dest="cmd")

    nd = sub.add_parser("new", help="start a discussion")
    nd.add_argument("--title", required=True)
    nd.add_argument("--id", default=None)
    nd.add_argument(
        "--community",
        default=None,
        help="community id (matches levi.communities by convention)",
    )

    rp = sub.add_parser("reply", help="post a comment or reply")
    rp.add_argument("discussion")
    rp.add_argument("--author", required=True)
    rp.add_argument("--text", required=True)
    rp.add_argument("--to", default=None, help="parent comment id (omit for top-level)")

    v = sub.add_parser("vote", help="vote on a comment")
    v.add_argument("discussion")
    v.add_argument("--comment", required=True)
    v.add_argument("--voter", required=True)
    v.add_argument("--value", required=True, choices=["up", "down"])

    t = sub.add_parser("tree", help="render the ranked discussion tree")
    t.add_argument("discussion")
    t.add_argument("--limit", type=int, default=50)

    e = sub.add_parser("explain", help="show score components for one comment")
    e.add_argument("discussion")
    e.add_argument("comment")

    w = sub.add_parser("rank-weight", help="edit a ranking weight")
    w.add_argument("name", choices=["quality", "bridging"])
    w.add_argument("value", type=float)

    pn = sub.add_parser("profile-new", help="create a portable identity profile")
    pn.add_argument("id")
    pn.add_argument("--name", required=True)
    pn.add_argument("--bio", default="")

    pe = sub.add_parser("profile-export", help="export a signed profile artifact")
    pe.add_argument("id")
    pe.add_argument("--out", required=True)

    pv = sub.add_parser("profile-verify", help="verify a signed profile artifact")
    pv.add_argument("--in", dest="in_path", required=True)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        store = ThreadStore()
    except Exception as exc:  # pragma: no cover - defensive
        print(f"threads: cannot open state: {exc}", file=sys.stderr)
        return 1

    try:
        if args.cmd == "new":
            d = store.new_discussion(
                args.title, discussion_id=args.id, community_id=args.community
            )
            print(f"discussion [{d.id}] {d.title}")
        elif args.cmd == "reply":
            c = store.add_comment(
                args.discussion, args.author, args.text, parent_id=args.to
            )
            print(
                f"comment [{c.id}]" + (f" reply-to [{args.to[:8]}]" if args.to else "")
            )
        elif args.cmd == "vote":
            store.vote(args.discussion, args.comment, args.voter, args.value)
            print(f"vote {args.value}: {args.voter} -> [{args.comment[:8]}]")
        elif args.cmd == "tree":
            print(store.render_tree(args.discussion, limit=args.limit))
        elif args.cmd == "explain":
            rows = store.rank(args.discussion)
            row = next(
                (
                    r
                    for r in rows
                    if r["comment"].id == args.comment
                    or r["comment"].id.startswith(args.comment)
                ),
                None,
            )
            if row is None:
                print(f"threads: unknown comment {args.comment!r}", file=sys.stderr)
                return 1
            c = row["comment"]
            print(
                f"comment [{c.id}] by {c.author_id} (depth {row['depth']}, net {c.net:+d})"
            )
            print(
                f"  quality={row['quality']:.3f} "
                f"(voteness={row['voteness']:.2f} substance={row['substance']:.2f} "
                f"depthness={row['depthness']:.2f})"
            )
            print(
                f"  bridging={row['bridging']:.3f} (cross-camp consensus, 0.5 = not enough voters)"
            )
            print(
                f"  score={row['score']:.3f} = "
                f"{store.rank_weights['quality']:.2f}*quality + "
                f"{store.rank_weights['bridging']:.2f}*bridging"
            )
        elif args.cmd == "rank-weight":
            store.set_rank_weight(args.name, args.value)
            print(f"rank weight {args.name} = {args.value}")
        elif args.cmd == "profile-new":
            pr = store.new_profile(args.id, args.name, bio=args.bio)
            print(f"profile [{pr.id}] {pr.display_name}")
        elif args.cmd == "profile-export":
            doc = store.export_profile(args.id)
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(doc, indent=2, sort_keys=True))
            print(f"exported signed profile [{args.id}] -> {out}")
            print(
                "scope: proves authorship continuity by this identity key — not personhood"
            )
        elif args.cmd == "profile-verify":
            doc = json.loads(Path(args.in_path).read_text())
            pr = store.verify_profile(doc)
            print(f"VALID: [{pr.id}] {pr.display_name} — signed by this identity key")
        else:
            build_parser().print_help()
            return 2
    except ThreadError as exc:
        print(f"threads: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
