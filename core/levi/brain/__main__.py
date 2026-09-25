"""CLI: python -m levi.brain

Thin entry point over LEVI's indexed second brain: the corpus
(OBSERVED/INFERENCE/... units), the brain table (domain/key/value
facts), and markdown export. Local-only, stdlib-only.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _root(brain_dir: str | None) -> Path:
    return (
        Path(brain_dir)
        if brain_dir
        else Path(
            os.environ.get("LEVI_BRAIN_DIR") or os.path.expanduser("~/.levi/brain")
        )
    )


def _corpus(d):
    from levi.brain.corpus import Corpus

    return Corpus(path=_root(d) / "corpus.json")


def _table(d):
    from levi.brain.table import BrainTable

    return BrainTable(path=_root(d) / "table.json")


def cmd(a) -> int:
    name = a.cmd.replace("-", "_")
    try:
        if name == "corpus_add":
            u = _corpus(a.brain_dir).add(a.text, kind=a.kind, source=a.source)
            print(f"added corpus unit {u.id} [{u.kind}]")
        elif name == "corpus_search":
            for u in _corpus(a.brain_dir).search(a.query, limit=a.limit):
                print(f"[{u.id}] {u.kind} {u.source}: {u.text[:160]}")
        elif name == "corpus_stats":
            units, by_kind = _corpus(a.brain_dir).list(limit=100000), {}
            for u in units:
                by_kind[u.kind] = by_kind.get(u.kind, 0) + 1
            print(f"corpus units: {len(units)}")
            for k, v in sorted(by_kind.items()):
                print(f"  {k}: {v}")
        elif name == "table_upsert":
            r = _table(a.brain_dir).upsert(a.domain, a.key, a.value, source=a.source)
            print(f"upserted [{r.domain}] {r.key}")
        elif name == "table_search":
            for r in _table(a.brain_dir).search(a.query or "", domain=a.domain)[
                : a.limit
            ]:
                print(f"[{r.domain}] {r.key}: {r.value[:160]}")
        elif name == "export":
            from levi.brain.record import export_markdown

            print(
                f"exported brain to {export_markdown(Path(a.out) if a.out else None)}"
            )
    except ValueError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.brain", description="LEVI indexed second brain"
    )
    ap.add_argument(
        "--brain-dir", default=None, help="default ~/.levi/brain or LEVI_BRAIN_DIR"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("corpus-add")
    p.set_defaults(func=cmd)
    p.add_argument("text")
    p.add_argument("--kind", default="OBSERVED")
    p.add_argument("--source", default="")

    p = sub.add_parser("corpus-search")
    p.set_defaults(func=cmd)
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=20)

    sub.add_parser("corpus-stats").set_defaults(func=cmd)

    p = sub.add_parser("table-upsert")
    p.set_defaults(func=cmd)
    p.add_argument("domain")
    p.add_argument("key")
    p.add_argument("value")
    p.add_argument("--source", default="")

    p = sub.add_parser("table-search")
    p.set_defaults(func=cmd)
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--domain", default=None)
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("export")
    p.set_defaults(func=cmd)
    p.add_argument("--out", default=None)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
