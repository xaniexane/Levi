"""CLI: python -m levi.honestsearch <add|crawl|query|weights|stats|export>

Mirrors the future ``levi search`` surface.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from levi.honestsearch.crawl import SiteCrawl, extract_links, title_of
from levi.honestsearch.model import Document, doc_id_for, now_iso
from levi.honestsearch.rank import (
    DEFAULT_WEIGHTS,
    explain,
    normalize_weights,
    parse_weights,
    search,
)
from levi.honestsearch.store import (
    append_report,
    index_path,
    load_index,
    load_weights,
    save_index,
    save_weights,
)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="levi.honestsearch",
        description="Clean-room search over a local index. No profile, no ads.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("add", help="index local files (txt/md/html)")
    s.add_argument("files", nargs="+")
    s.add_argument("--url", default=None, help="override URL for one file")
    s.add_argument("--title", default=None, help="override title for one file")

    s = sub.add_parser("crawl", help="polite crawl of seed URLs into the index")
    s.add_argument("seeds", nargs="+")
    s.add_argument("--max-pages", type=int, default=50)
    s.add_argument("--max-depth", type=int, default=2)
    s.add_argument("--scope", choices=("host", "any"), default="host")

    s = sub.add_parser("query", help="search the local index")
    s.add_argument("terms", nargs="+")
    s.add_argument("--top", type=int, default=10)
    s.add_argument("--explain", action="store_true",
                   help="show per-signal contributions")
    s.add_argument("--weights", default=None,
                   help="override, e.g. text=0.8,link=0.2")

    s = sub.add_parser("weights", help="show or set the ranking weights")
    s.add_argument("action", nargs="?", choices=("show", "set"), default="show")
    s.add_argument("spec", nargs="?", help="e.g. text=0.8,link=0.2")

    s = sub.add_parser("stats", help="index statistics")

    s = sub.add_parser("export", help="dump the index as JSON (your data)")
    s.add_argument("path")
    return p


def _read_local(path: Path):
    raw = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix in (".html", ".htm"):
        from levi.research.deepweb import extract_text
        return title_of(raw) or path.name, extract_text(raw, limit=20000), \
            extract_links(raw, "file://" + str(path))
    text = raw.decode("utf-8", "replace")
    title = path.stem.replace("_", " ").replace("-", " ")
    return title, text, []


def cmd_add(args) -> int:
    index = load_index()
    added = 0
    for name in args.files:
        path = Path(name)
        if not path.is_file():
            print("skip %s: not a file" % name, file=sys.stderr)
            continue
        title, text, outlinks = _read_local(path)
        url = args.url or ("file://" + str(path.resolve()))
        doc = Document(
            doc_id=doc_id_for(url + "|" + str(path.stat().st_mtime)),
            url=args.url or url,
            title=args.title or title,
            text=text,
            outlinks=outlinks,
            source="file",
            fetched_at=now_iso(),
        )
        index.add(doc)
        added += 1
    save_index(index)
    print("added %d file(s); index now holds %d document(s) at %s"
          % (added, len(index), index_path()))
    return 0


def cmd_crawl(args) -> int:
    crawler = SiteCrawl(max_pages=args.max_pages, max_depth=args.max_depth,
                        scope=args.scope)
    documents, report = crawler.crawl(args.seeds)
    index = load_index()
    for doc in documents:
        index.add(doc)
    save_index(index)
    append_report(report)
    print("crawled %d page(s) (%d refusals recorded, nothing fabricated)"
          % (report["pages"], len(report["refusals"])))
    for refusal in report["refusals"][:10]:
        print("  refused: %s — %s" % (refusal["url"], refusal["reason"]))
    print("index now holds %d document(s)" % len(index))
    return 0


def cmd_query(args) -> int:
    index = load_index()
    if not index.docs:
        print("index is empty — add files or crawl seeds first")
        return 1
    weights = parse_weights(args.weights) if args.weights else load_weights()
    results = search(index, " ".join(args.terms), weights=weights,
                     top_k=args.top)
    print("weights: %s   (unpersonalized: no profile enters ranking)"
          % ", ".join("%s=%.2f" % (k, v)
                      for k, v in normalize_weights(weights).items()))
    if not results:
        print("no matches")
        return 1
    for i, res in enumerate(results, 1):
        if args.explain:
            print("--- #%d ---\n%s" % (i, explain(res, weights)))
        else:
            print("#%d [%.4f] %s\n    %s" % (i, res.total,
                                             res.doc.title, res.doc.url))
    return 0


def cmd_weights(args) -> int:
    if args.action == "show" or not args.spec:
        current = load_weights()
        default = normalize_weights(dict(DEFAULT_WEIGHTS))
        print("current: %s" % ", ".join("%s=%.2f" % kv
                                        for kv in current.items()))
        print("default: %s" % ", ".join("%s=%.2f" % kv
                                        for kv in default.items()))
        return 0
    try:
        cleaned = save_weights(parse_weights(args.spec))
    except ValueError as exc:
        print("bad weights: %s" % exc, file=sys.stderr)
        return 2
    print("weights set: %s" % ", ".join("%s=%.2f" % kv
                                        for kv in cleaned.items()))
    return 0


def cmd_stats(args) -> int:
    index = load_index()
    stats = index.stats()
    print("documents: %d" % stats["documents"])
    print("terms: %d" % stats["terms"])
    for source, count in sorted(stats["sources"].items()):
        print("  %s: %d" % (source, count))
    print("index file: %s" % index_path())
    return 0


def cmd_export(args) -> int:
    index = load_index()
    payload = {
        "exported_at": now_iso(),
        "weights": load_weights(),
        "documents": [d.to_dict() for d in index.docs.values()],
    }
    out = Path(args.path)
    out.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print("exported %d document(s) to %s (open format, no lock-in)"
          % (len(index), out))
    return 0


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    if args.cmd == "add":
        return cmd_add(args)
    if args.cmd == "crawl":
        return cmd_crawl(args)
    if args.cmd == "query":
        return cmd_query(args)
    if args.cmd == "weights":
        return cmd_weights(args)
    if args.cmd == "stats":
        return cmd_stats(args)
    if args.cmd == "export":
        return cmd_export(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
