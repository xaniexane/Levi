"""CLI: python -m levi.recommender <add-item|add-goal|rate|recommend|weights|list|export>

Mirrors the future ``levi recommend`` surface.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from levi.recommender.engine import (
    DEFAULT_HALF_LIFE_DAYS,
    explain,
    recommend,
)
from levi.recommender.model import (
    Goal,
    Item,
    check_rating,
    new_id,
    parse_topics,
    suggest_id,
)
from levi.recommender.store import (
    load_goals,
    load_items,
    load_ratings,
    load_weights,
    save_goals,
    save_items,
    save_ratings,
    save_weights,
    store_dir,
)
from levi.recommender.weights import (
    DEFAULT_WEIGHTS,
    SIGNALS,
    normalize_weights,
    parse_weights,
)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="levi.recommender",
        description="Goal-directed recommendations with visible math. "
                    "No engagement mining.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("add-item", help="add an item to the corpus")
    s.add_argument("--title", required=True)
    s.add_argument("--kind", required=True)
    s.add_argument("--topics", required=True,
                   help='"python:1.0,asyncio:0.6" (weight defaults to 1.0)')
    s.add_argument("--text", default="")
    s.add_argument("--id", default=None)

    s = sub.add_parser("add-goal", help="state a goal to steer recommendations")
    s.add_argument("--title", required=True)
    s.add_argument("--topics", required=True)
    s.add_argument("--kind-filter", default="",
                   help="comma-separated kinds, e.g. 'course,book'")
    s.add_argument("--notes", default="")
    s.add_argument("--id", default=None)

    s = sub.add_parser("rate", help="explicitly rate an item 1-5")
    s.add_argument("item_id")
    s.add_argument("rating")

    s = sub.add_parser("recommend", help="recommend from the corpus")
    s.add_argument("--goal", action="append", default=None, dest="goals",
                   help="only use these goal ids (repeatable)")
    s.add_argument("--top", type=int, default=10)
    s.add_argument("--explain", action="store_true")
    s.add_argument("--diverse", type=float, default=1.0, metavar="LAMBDA",
                   help="MMR lambda in [0,1]; lower = more diverse (default 1)")
    s.add_argument("--weights", default=None,
                   help='"goal=0.5,content=0.3,quality=0.2,recency=0"')
    s.add_argument("--half-life", type=float, default=DEFAULT_HALF_LIFE_DAYS)
    s.add_argument("--exclude-rated", action="store_true",
                   help="skip items you already rated")

    s = sub.add_parser("weights", help="show or set the signal weights")
    s.add_argument("action", nargs="?", choices=("show", "set"), default="show")
    s.add_argument("spec", nargs="?", help='"goal=0.5,content=0.5,..."')

    s = sub.add_parser("list", help="list stored data")
    s.add_argument("what", choices=("items", "goals", "ratings"))

    s = sub.add_parser("export", help="dump corpus+goals+ratings as JSON")
    s.add_argument("path")
    return p


def cmd_add_item(args) -> int:
    try:
        topics = parse_topics(args.topics)
    except ValueError as exc:
        print("bad topics: %s" % exc, file=sys.stderr)
        return 2
    items = load_items()
    taken = {it.id for it in items}
    item_id = args.id or suggest_id(args.title, taken)
    if item_id in taken:
        print("item id %r already exists" % item_id, file=sys.stderr)
        return 1
    try:
        item = Item(id=item_id, title=args.title, kind=args.kind,
                    topics=topics, text=args.text)
    except ValueError as exc:
        print("bad item: %s" % exc, file=sys.stderr)
        return 2
    items.append(item)
    save_items(items)
    print("added item %r (%s)" % (item.id, item.title))
    return 0


def cmd_add_goal(args) -> int:
    try:
        topics = parse_topics(args.topics)
    except ValueError as exc:
        print("bad topics: %s" % exc, file=sys.stderr)
        return 2
    goals = load_goals()
    taken = {g.id for g in goals}
    goal_id = args.id or suggest_id(args.title, taken)
    if goal_id in taken:
        print("goal id %r already exists" % goal_id, file=sys.stderr)
        return 1
    kind_filter = [k.strip() for k in args.kind_filter.split(",") if k.strip()]
    try:
        goal = Goal(id=goal_id, title=args.title, topics=topics,
                    kind_filter=kind_filter, notes=args.notes)
    except ValueError as exc:
        print("bad goal: %s" % exc, file=sys.stderr)
        return 2
    goals.append(goal)
    save_goals(goals)
    print("added goal %r (%s)" % (goal.id, goal.title))
    return 0


def cmd_rate(args) -> int:
    items = {it.id: it for it in load_items()}
    if args.item_id not in items:
        print("no such item %r" % args.item_id, file=sys.stderr)
        return 1
    try:
        value = check_rating(args.rating)
    except ValueError as exc:
        print("bad rating: %s" % exc, file=sys.stderr)
        return 2
    ratings = load_ratings()
    ratings.setdefault(args.item_id, []).append(value)
    save_ratings(ratings)
    print("rated %r %.1f/5 (explicit — this is the only taste signal)"
          % (args.item_id, value))
    return 0


def cmd_recommend(args) -> int:
    items = load_items()
    if not items:
        print("corpus is empty — add-item first")
        return 1
    goals = load_goals()
    ratings = load_ratings()
    weights = parse_weights(args.weights) if args.weights else load_weights()
    exclude = list(ratings) if args.exclude_rated else []
    try:
        recs = recommend(
            items, goals, ratings, weights=weights,
            active_goal_ids=set(args.goals) if args.goals else None,
            exclude_ids=exclude, top_k=args.top,
            half_life_days=args.half_life, mmr_lambda=args.diverse)
    except ValueError as exc:
        print("bad options: %s" % exc, file=sys.stderr)
        return 2
    print("weights: %s   goals: %s   diversity λ=%.2f" % (
        ", ".join("%s=%.2f" % kv for kv in normalize_weights(weights).items()),
        ", ".join(g.id for g in goals) if goals else "(none stated)",
        args.diverse))
    if not recs:
        print("no recommendations")
        return 1
    for i, rec in enumerate(recs, 1):
        if args.explain:
            print("--- #%d ---\n%s" % (i, explain(rec, weights)))
        else:
            print("#%d [%.4f] %s [%s]" % (i, rec.total, rec.item.title,
                                          rec.item.kind))
    return 0


def cmd_weights(args) -> int:
    if args.action == "show" or not args.spec:
        current = load_weights()
        default = normalize_weights(dict(DEFAULT_WEIGHTS))
        print("current: %s" % ", ".join("%s=%.2f" % kv
                                        for kv in current.items()))
        print("default: %s" % ", ".join("%s=%.2f" % kv
                                        for kv in default.items()))
        print("signals: %s" % ", ".join(SIGNALS))
        return 0
    try:
        cleaned = save_weights(parse_weights(args.spec))
    except ValueError as exc:
        print("bad weights: %s" % exc, file=sys.stderr)
        return 2
    print("weights set: %s" % ", ".join("%s=%.2f" % kv
                                        for kv in cleaned.items()))
    return 0


def cmd_list(args) -> int:
    if args.what == "items":
        for it in load_items():
            print("%-24s [%s] %s" % (it.id, it.kind, it.title))
    elif args.what == "goals":
        for g in load_goals():
            kinds = ",".join(g.kind_filter) or "any kind"
            print("%-24s (%s) %s" % (g.id, kinds, g.title))
    else:
        for item_id, vals in sorted(load_ratings().items()):
            print("%-24s %s" % (item_id,
                                ", ".join("%.1f" % v for v in vals)))
    return 0


def cmd_export(args) -> int:
    payload = {
        "items": [it.to_dict() for it in load_items()],
        "goals": [g.to_dict() for g in load_goals()],
        "ratings": load_ratings(),
        "weights": load_weights(),
    }
    out = Path(args.path)
    out.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print("exported %d item(s), %d goal(s) to %s (open format, no lock-in)"
          % (len(payload["items"]), len(payload["goals"]), out))
    print("store dir was %s" % store_dir())
    return 0


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    if args.cmd == "add-item":
        return cmd_add_item(args)
    if args.cmd == "add-goal":
        return cmd_add_goal(args)
    if args.cmd == "rate":
        return cmd_rate(args)
    if args.cmd == "recommend":
        return cmd_recommend(args)
    if args.cmd == "weights":
        return cmd_weights(args)
    if args.cmd == "list":
        return cmd_list(args)
    if args.cmd == "export":
        return cmd_export(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
