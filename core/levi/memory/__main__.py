"""CLI: python -m levi.memory — thin entry point over the local memory
store (add/get/search/list/delete, stats, hierarchy). JSON store under
~/.levi/memory (hermetic: set HOME to isolate).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from levi.memory.types import MemoryType


def _store(data_dir):
    from levi.memory.store import MemoryStore

    return MemoryStore(data_dir=Path(data_dir))


def _fmt(e) -> str:
    return (f"[{e.id}] {e.memory_type.value} importance={e.importance:.2f} "
            f"tags={','.join(e.tags)}\n  {e.content[:300]}")


def cmd_add(a) -> int:
    tags = [t.strip() for t in a.tags.split(",") if t.strip()]
    try:
        mtype = MemoryType(a.type)
    except ValueError:
        print(f"Invalid --type {a.type!r}", file=sys.stderr)
        return 2
    try:
        e = _store(a.data_dir).add(mtype, a.text, importance=a.importance,
                                   source=a.source, tags=tags or None)
    except ValueError as exc:
        print(f"add refused: {exc}", file=sys.stderr)
        return 1
    print(f"added {e.id} [{e.memory_type.value}]")
    return 0


def cmd_get(a) -> int:
    e = _store(a.data_dir).get(a.id)
    if e is None:
        print(f"no entry {a.id!r}", file=sys.stderr)
        return 1
    print(_fmt(e))
    return 0


def cmd_search(a) -> int:
    from levi.memory.retrieval import retrieve

    hits = retrieve(a.query, _store(a.data_dir), limit=a.limit, method=a.method)
    print("no matches." if not hits else "\n".join(
        _fmt(e) + f"  [score {s:.3f}]" for e, s, _w in hits))
    return 0


def cmd_list(a) -> int:

    es = _store(a.data_dir).list(
        memory_type=MemoryType(a.type) if a.type else None, limit=a.limit)
    print("store is empty." if not es else "\n".join(_fmt(e) for e in es))
    return 0


def cmd_delete(a) -> int:
    if not _store(a.data_dir).delete(a.id):
        print(f"no entry {a.id!r}", file=sys.stderr)
        return 1
    print(f"deleted {a.id}")
    return 0


def main(argv=None) -> int:

    types = [t.value for t in MemoryType]
    override = os.environ.get("LEVI_MEMORY_DIR")
    default_dir = os.path.join(override or os.path.expanduser("~/.levi"), "memory")
    ap = argparse.ArgumentParser(prog="levi.memory",
                                 description="LEVI memory store — local-first")
    ap.add_argument("--data-dir", default=default_dir)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="add a memory entry"); p.set_defaults(func=cmd_add)
    p.add_argument("text"); p.add_argument("--type", default="working", choices=types)
    p.add_argument("--tags", default=""); p.add_argument("--importance", type=float, default=0.5); p.add_argument("--source", default="user")

    p = sub.add_parser("get", help="show one entry"); p.set_defaults(func=cmd_get); p.add_argument("id")

    p = sub.add_parser("search", help="retrieve for a query"); p.set_defaults(func=cmd_search)
    p.add_argument("query"); p.add_argument("--limit", type=int, default=10)
    p.add_argument("--method", default="hybrid", choices=["bm25", "vector", "hybrid", "recency"])

    p = sub.add_parser("list", help="list entries"); p.set_defaults(func=cmd_list)
    p.add_argument("--type", default=None, choices=types); p.add_argument("--limit", type=int, default=50)

    p = sub.add_parser("delete", help="delete an entry"); p.set_defaults(func=cmd_delete); p.add_argument("id")

    def _info(a) -> int:
        if a.info == "stats":
            print(json.dumps(_store(a.data_dir).stats(), indent=2))
        elif a.info == "explain":
            from levi.memory.hierarchy import explain_belief
            print(explain_belief(a.claim))
        else:
            from levi.memory.hierarchy import hierarchy_status
            print(hierarchy_status())
        return 0

    for name, help_text in (("stats", "store stats (JSON)"),
                            ("hierarchy", "memory hierarchy map")):
        sub.add_parser(name, help=help_text).set_defaults(func=_info, info=name)
    p = sub.add_parser("explain", help="explain where a belief comes from")
    p.add_argument("claim"); p.set_defaults(func=_info, info="explain")

    args = ap.parse_args(argv)
    return args.func(args)
