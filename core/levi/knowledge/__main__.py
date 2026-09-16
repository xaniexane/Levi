"""CLI: python -m levi.knowledge

Thin entry point over LEVI's local knowledge base: the capability
atlas, the defensive security domain catalog, and the cached daily
news corpus. Read-only except `news-refresh`, which fetches public
feeds (offline failure is reported honestly, never fabricated).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent


def cmd_atlas(args) -> int:
    raw = json.loads((PKG / "capabilities" / "atlas.json").read_text())
    domains = raw.get("domains", [])
    print(f"capability atlas: {len(domains)} domains")
    for d in domains[: args.limit]:
        if isinstance(d, dict):
            print(f"  - {d.get('id', '?')}: {d.get('name', d.get('id', ''))}")
        else:
            print(f"  - {d}")
    return 0


def cmd_security(args) -> int:
    from levi.knowledge.security.catalog import load_catalog

    cat = load_catalog()
    if args.domain:
        d = cat.get(args.domain)
        if d is None:
            print(f"unknown domain {args.domain!r}", file=sys.stderr)
            return 1
        print(f"{d.id}: {d.name}")
        print(f"  {d.defensive_summary}")
        if d.key_concepts:
            print("  concepts: " + ", ".join(d.key_concepts[:8]))
        return 0
    print(f"security catalog: {len(cat)} defensive domains")
    for d in list(cat)[: args.limit]:
        print(f"  - {d.id}: {d.name}")
    return 0


def cmd_news(args) -> int:
    days_dir = PKG / "news" / "days"
    files = sorted(days_dir.glob("*.jsonl")) if days_dir.exists() else []
    if not files:
        print("no cached news days.")
        return 0
    print(f"cached news days: {len(files)}")
    for f in files[-args.limit :]:
        try:
            n = sum(1 for _ in f.open())
        except OSError:
            n = 0
        print(f"  {f.stem}: {n} items")
    return 0


def cmd_news_refresh(args) -> int:
    from levi.knowledge.news.refresh import main as refresh_main

    argv = []
    if args.date:
        argv.append(f"--date={args.date}")
    argv.append(f"--limit={args.limit}")
    return refresh_main(argv)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.knowledge",
        description="LEVI local knowledge base — atlas, security catalog, news",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_at = sub.add_parser("atlas", help="capability atlas summary")
    p_at.add_argument("--limit", type=int, default=50)
    p_at.set_defaults(func=cmd_atlas)

    p_sec = sub.add_parser("security", help="defensive security domain catalog")
    p_sec.add_argument("--domain", default=None, help="show one domain by id")
    p_sec.add_argument("--limit", type=int, default=81)
    p_sec.set_defaults(func=cmd_security)

    p_n = sub.add_parser("news", help="list cached daily news corpus")
    p_n.add_argument("--limit", type=int, default=10)
    p_n.set_defaults(func=cmd_news)

    p_nr = sub.add_parser(
        "news-refresh", help="fetch today's public feeds (network; honest on failure)"
    )
    p_nr.add_argument("--date", default=None)
    p_nr.add_argument("--limit", type=int, default=200)
    p_nr.set_defaults(func=cmd_news_refresh)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
