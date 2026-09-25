"""CLI: python -m levi.rag ingest <file> | ask <query> | eval [--k 5]"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _default_store_dir() -> str:
    override = os.environ.get("LEVI_RAG_HOME") or os.environ.get("LEVI_MEMORY_DIR")
    if override:
        return os.path.join(override, "memory")
    return os.path.join(os.path.expanduser("~"), ".levi", "memory")


def _make_store(data_dir: str):
    from levi.memory.store import MemoryStore

    return MemoryStore(data_dir=Path(data_dir))


def cmd_ingest(args) -> int:
    from levi.rag import ingest_file, ingest_directory

    store = _make_store(args.data_dir)
    target = Path(args.path)
    if target.is_dir():
        report = ingest_directory(
            target,
            store,
            pattern=args.pattern,
            max_chars=args.max_chars,
            overlap=args.overlap,
        )
    else:
        report = ingest_file(
            target, store, max_chars=args.max_chars, overlap=args.overlap
        )
    print(report.summary())
    for err in report.errors:
        print("  ! %s" % err, file=sys.stderr)
    return 0 if report.files_ingested else 1


def cmd_ask(args) -> int:
    from levi.rag import ask

    store = _make_store(args.data_dir)
    result = ask(args.query, store, limit=args.limit, generate=not args.no_generate)
    if result.answer:
        print(result.answer)
    elif result.context:
        print(result.context)
    if result.notice:
        print("\n[%s]" % result.notice)
    if result.citations:
        print("citations: %s" % ", ".join("[memory:%s]" % c for c in result.citations))
    return 0


def cmd_eval(args) -> int:
    from levi.rag import evaluate, print_report

    store = _make_store(args.data_dir)
    report = evaluate(store, k=args.k, method=args.method)
    print(print_report(report))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="levi.rag", description="LEVI RAG pipeline")
    ap.add_argument(
        "--data-dir", default=_default_store_dir(), help="memory store directory"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ing = sub.add_parser("ingest", help="ingest file(s) as RAG chunks")
    p_ing.add_argument("path", help="file or directory")
    p_ing.add_argument("--pattern", default="*.md")
    p_ing.add_argument("--max-chars", type=int, default=500)
    p_ing.add_argument("--overlap", type=int, default=100)
    p_ing.set_defaults(func=cmd_ingest)

    p_ask = sub.add_parser("ask", help="ask over ingested docs")
    p_ask.add_argument("query")
    p_ask.add_argument("--limit", type=int, default=5)
    p_ask.add_argument("--no-generate", action="store_true")
    p_ask.set_defaults(func=cmd_ask)

    p_eval = sub.add_parser("eval", help="run the retrieval eval harness")
    p_eval.add_argument("--k", type=int, default=5)
    p_eval.add_argument(
        "--method", default="hybrid", choices=["bm25", "vector", "hybrid", "recency"]
    )
    p_eval.set_defaults(func=cmd_eval)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
