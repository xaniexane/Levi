"""CLI: python -m levi.shelf <command> [options]

The Share Shelf counter: shelve with a note, star the canon, bury the
duds, and bundle the whole shelf as a portable file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .shelf import ShelfStore, ShelfError


def _store() -> ShelfStore:
    return ShelfStore()


def _cmd_add(a) -> int:
    item = _store().add(
        a.url, a.title, note=a.note or "", tags=(a.tags.split(",") if a.tags else ())
    )
    print("shelved %s" % item.id)
    return 0


def _cmd_list(a) -> int:
    store = _store()
    items = store.list(include_buried=not a.no_buried)
    for it in items:
        flags = ("*" if it.starred else " ") + ("B" if it.buried else " ")
        print("%s %s  %s" % (flags, it.id, it.title))
        print("    %s" % it.url)
        if it.note:
            print("    note: %s" % it.note)
    print("%d item(s)" % len(items))
    return 0


def _cmd_show(a) -> int:
    it = _store().get(a.item_id)
    print(json.dumps(it.to_dict(), indent=2, ensure_ascii=False))
    return 0


def _cmd_flag(a, verb) -> int:
    it = getattr(_store(), verb)(a.item_id)
    print("%s %s" % (verb, it.id))
    return 0


def _cmd_annotate(a) -> int:
    it = _store().annotate(a.item_id, a.note)
    print("annotated %s" % it.id)
    return 0


def _cmd_remove(a) -> int:
    _store().remove(a.item_id)
    print("removed %s" % a.item_id)
    return 0


def _cmd_search(a) -> int:
    for it in _store().search(a.query):
        print("%s  %s" % (it.id, it.title))
    return 0


def _cmd_stats(a) -> int:
    print(json.dumps(_store().stats()))
    return 0


def _cmd_bundle(a) -> int:
    dest = _store().bundle(Path(a.path))
    print("bundled -> %s" % dest)
    return 0


def _cmd_import(a) -> int:
    res = _store().import_bundle(Path(a.path))
    print("imported: added=%d" % res["added"])
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="levi.shelf")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add")
    p.add_argument("url")
    p.add_argument("--title", required=True)
    p.add_argument("--note", default="")
    p.add_argument("--tags", default="")

    p = sub.add_parser("list")
    p.add_argument("--no-buried", action="store_true")

    p = sub.add_parser("show")
    p.add_argument("item_id")

    for verb in ("star", "unstar", "bury", "unbury"):
        p = sub.add_parser(verb)
        p.add_argument("item_id")

    p = sub.add_parser("annotate")
    p.add_argument("item_id")
    p.add_argument("note")

    p = sub.add_parser("remove")
    p.add_argument("item_id")

    p = sub.add_parser("search")
    p.add_argument("query")

    sub.add_parser("stats")

    p = sub.add_parser("bundle")
    p.add_argument("path")

    p = sub.add_parser("import")
    p.add_argument("path")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "add":
            return _cmd_add(args)
        if args.cmd == "list":
            return _cmd_list(args)
        if args.cmd == "show":
            return _cmd_show(args)
        if args.cmd in ("star", "unstar", "bury", "unbury"):
            return _cmd_flag(args, args.cmd)
        if args.cmd == "annotate":
            return _cmd_annotate(args)
        if args.cmd == "remove":
            return _cmd_remove(args)
        if args.cmd == "search":
            return _cmd_search(args)
        if args.cmd == "stats":
            return _cmd_stats(args)
        if args.cmd == "bundle":
            return _cmd_bundle(args)
        if args.cmd == "import":
            return _cmd_import(args)
    except ShelfError as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
