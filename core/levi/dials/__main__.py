"""CLI: python -m levi.dials

Sovereign attention dials — inspect and edit your own ranking weights,
manage the local item stream, and see exactly why each item ranks where
it does. Mirrors the future ``levi dials`` top-level command.
"""

from __future__ import annotations

import argparse
import sys

from levi.dials.dials import AttentionDials, DialError, FEATURES


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="levi dials",
        description="Sovereign attention dials: your weights, your feed, fully explainable.",
    )
    sub = p.add_subparsers(dest="cmd")

    a = sub.add_parser("add", help="add an item to the local stream")
    a.add_argument("--author", required=True)
    a.add_argument("--text", required=True)
    a.add_argument("--tags", default="", help="comma-separated tags")

    sub.add_parser("feed", help="show the feed (chronological default)").add_argument(
        "--limit", type=int, default=20
    )

    sub.add_parser(
        "rank", help="show the feed scored with current weights"
    ).add_argument("--limit", type=int, default=20)

    sub.add_parser("weights", help="show the weight vector and dials")

    s = sub.add_parser("set-weight", help="edit one weight")
    s.add_argument("name", choices=sorted(FEATURES))
    s.add_argument("value", type=float)

    m = sub.add_parser("mode", help="set ranking mode")
    m.add_argument("mode", choices=["chronological", "weighted"])

    af = sub.add_parser("affinity-add", help="opt an author IN to affinity (explicit)")
    af.add_argument("author")
    ar = sub.add_parser("affinity-remove", help="opt an author OUT of affinity")
    ar.add_argument("author")

    pt = sub.add_parser("pin-tag", help="pin a tag for tag_match scoring")
    pt.add_argument("tag")

    hl = sub.add_parser("half-life", help="set recency half-life in hours")
    hl.add_argument("hours", type=float)

    e = sub.add_parser("explain", help="show per-weight contributions for one item")
    e.add_argument("item_id")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        d = AttentionDials()
    except Exception as exc:  # pragma: no cover - defensive
        print(f"dials: cannot open state: {exc}", file=sys.stderr)
        return 1

    try:
        if args.cmd == "add":
            tags = [t.strip() for t in args.tags.split(",") if t.strip()]
            item = d.add_item(args.author, args.text, tags=tags)
            print(f"added [{item.id}] by {item.author}")
        elif args.cmd == "feed":
            print(d.format_feed(limit=args.limit))
        elif args.cmd == "rank":
            d.set_mode("weighted")
            print(d.format_feed(limit=args.limit))
            d.set_mode(
                "chronological"
            )  # rank is a preview; do not move the sticky dial
        elif args.cmd == "weights":
            print(d.format_weights())
        elif args.cmd == "set-weight":
            d.set_weight(args.name, args.value)
            print(f"{args.name} = {args.value}")
        elif args.cmd == "mode":
            d.set_mode(args.mode)
            print(f"mode = {args.mode}")
        elif args.cmd == "affinity-add":
            d.add_affinity(args.author)
            print(f"affinity +{args.author} (explicit opt-in)")
        elif args.cmd == "affinity-remove":
            d.remove_affinity(args.author)
            print(f"affinity -{args.author}")
        elif args.cmd == "pin-tag":
            d.pin_tag(args.tag)
            print(f"pinned tag: {args.tag}")
        elif args.cmd == "half-life":
            if args.hours <= 0:
                print("half-life must be positive", file=sys.stderr)
                return 2
            d.recency_halflife_s = args.hours * 3600.0
            d._save()
            print(f"recency half-life = {args.hours}h")
        elif args.cmd == "explain":
            info = d.explain(args.item_id)
            print(f"item [{info['id']}] by {info['author']}  mode={info['mode']}")
            print(
                f"score={info['score']:.4f}  (weights sum to {info['total_weight']:.2f})"
            )
            for name in FEATURES:
                print(
                    f"  {name:10s} feature={info['features'][name]:.3f} "
                    f"weight={info['weights'][name]:.2f} contrib={info['contributions'][name]:.4f}"
                )
        else:
            build_parser().print_help()
            return 2
    except DialError as exc:
        print(f"dials: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
