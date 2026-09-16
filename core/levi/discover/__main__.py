"""CLI: python -m levi.discover — ritualized local discovery.

Subcommands:
  discover [--week YYYY-Www] [--source FILE] [--seed N] [--count N]
      Generate this week's digest (default: current ISO week). Fails
      closed if the week's digest already exists.
  history                    show past digests (week -> picks)
  init-sample [DEST]         write a labeled SAMPLE corpus (starter data)

The corpus is JSONL, one item per line:
  {"id","title","kind","tags","added_at","source","blurb"}

Default source: LEVI_DISCOVER_SOURCE env, else ~/.levi/discover/corpus.jsonl.
Digests land in ~/.levi/discover/digests/<week>.md — shareable plain files.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from levi.discover.digest import (
    current_week_label,
    default_home,
    generate_digest,
)
from levi.discover.items import DiscoverError, load_items

SAMPLE_ITEMS = [
    {
        "id": "sample-note-1",
        "title": "Field notes: repairing a 1987 ThinkPad keyboard",
        "kind": "note",
        "tags": ["repair", "hardware"],
        "added_at": "2026-06-01",
        "source": "sample",
        "blurb": "Forgotten method: bolt-modding buckling springs.",
    },
    {
        "id": "sample-paper-1",
        "title": "The lost art of the .plan file",
        "kind": "paper",
        "tags": ["internet-history", "finger"],
        "added_at": "2026-06-02",
        "source": "sample",
        "blurb": "Before status updates, there was finger.",
    },
    {
        "id": "sample-book-1",
        "title": "Gopher: the protocol that almost won",
        "kind": "bookmark",
        "tags": ["internet-history", "protocols"],
        "added_at": "2026-06-03",
        "source": "sample",
        "blurb": "What the web killed, and what it cost.",
    },
    {
        "id": "sample-note-2",
        "title": "Recipe: grandmother's sourdough, annotated",
        "kind": "note",
        "tags": ["food", "family"],
        "added_at": "2026-06-04",
        "source": "sample",
        "blurb": "Hydration percentages in the margins.",
    },
    {
        "id": "sample-paper-2",
        "title": "Smalltalk-80: the humane environment",
        "kind": "paper",
        "tags": ["programming", "history"],
        "added_at": "2026-06-05",
        "source": "sample",
        "blurb": "The whole system fit in your head.",
    },
    {
        "id": "sample-book-2",
        "title": "HyperCard stacks archive",
        "kind": "bookmark",
        "tags": ["programming", "history", "hypercard"],
        "added_at": "2026-06-06",
        "source": "sample",
        "blurb": "Everyone was a programmer for a while.",
    },
    {
        "id": "sample-mem-1",
        "title": "Idea: porch concerts for the block",
        "kind": "memory",
        "tags": ["community", "music"],
        "added_at": "2026-06-07",
        "source": "sample",
        "blurb": "Low-fi, high-neighbor.",
    },
    {
        "id": "sample-note-3",
        "title": "Notes on mending clothes visibly",
        "kind": "note",
        "tags": ["craft", "repair"],
        "added_at": "2026-06-08",
        "source": "sample",
        "blurb": "Sashiko as philosophy.",
    },
    {
        "id": "sample-paper-3",
        "title": "Usenet: governance without owners",
        "kind": "paper",
        "tags": ["internet-history", "governance"],
        "added_at": "2026-06-09",
        "source": "sample",
        "blurb": "The great renaming and what it taught.",
    },
    {
        "id": "sample-book-3",
        "title": "Demoscene: 64k of impossible",
        "kind": "bookmark",
        "tags": ["programming", "art", "demoscene"],
        "added_at": "2026-06-10",
        "source": "sample",
        "blurb": "Constraints as an art form.",
    },
]


def _home(a) -> Path:
    return Path(a.home) if a.home else default_home()


def _source(a) -> Path:
    import os

    if a.source:
        return Path(a.source)
    env = os.environ.get("LEVI_DISCOVER_SOURCE")
    if env:
        return Path(env)
    return _home(a) / "corpus.jsonl"


def cmd_discover(a) -> int:
    home = _home(a)
    try:
        items = load_items(_source(a))
    except DiscoverError as exc:
        print(f"discover: {exc}", file=sys.stderr)
        return 1
    week = a.week or current_week_label(date.today())
    try:
        digest, markdown = generate_digest(
            items,
            week,
            home,
            seed=a.seed,
            count=a.count,
            per_kind_cap=a.per_kind_cap,
            per_tag_cap=a.per_tag_cap,
            no_repeat_weeks=a.no_repeat_weeks,
        )
    except DiscoverError as exc:
        print(f"discover: {exc}", file=sys.stderr)
        return 1
    print(markdown)
    print(f"(saved to {home}/digests/{week}.md)", file=sys.stderr)
    return 0


def cmd_history(a) -> int:
    import json as _json

    home = _home(a)
    path = home / "history.json"
    if not path.exists():
        print("no digests yet — run `discover` to start the ritual.")
        return 0
    history = _json.loads(path.read_text(encoding="utf-8"))
    for week in sorted(history):
        picks = history[week]
        print(f"{week}: {len(picks)} picks")
        if a.verbose:
            for pid in picks:
                print(f"    - {pid}")
    return 0


def cmd_init_sample(a) -> int:
    home = _home(a)
    dest = Path(a.dest) if a.dest else home / "corpus.jsonl"
    if dest.exists() and not a.force:
        print(f"{dest} exists (pass --force to overwrite)", file=sys.stderr)
        return 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        for item in SAMPLE_ITEMS:
            fh.write(json.dumps(item, separators=(",", ":")) + "\n")
    print(f"wrote {len(SAMPLE_ITEMS)} SAMPLE items to {dest}")
    print("These are labeled starter data — replace with your own corpus.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.discover",
        description="Discover-Weekly-style ritual over your OWN corpus — no catalog, no engagement steering",
    )
    ap.add_argument("--home", default=None)
    ap.add_argument("--source", default=None, help="JSONL corpus file")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("discover", help="generate the weekly digest")
    p.add_argument("--week", default=None, help="week label like 2026-W38")
    p.add_argument(
        "--seed", type=int, default=None, help="override the week-derived seed"
    )
    p.add_argument("--count", type=int, default=7)
    p.add_argument("--per-kind-cap", type=int, default=2)
    p.add_argument("--per-tag-cap", type=int, default=3)
    p.add_argument("--no-repeat-weeks", type=int, default=8)
    p.set_defaults(func=cmd_discover)

    p = sub.add_parser("history", help="show past digests")
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("init-sample", help="write a labeled sample corpus")
    p.add_argument("dest", nargs="?", default=None)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init_sample)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
