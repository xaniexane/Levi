"""CLI: python -m levi.archive ingest|search|show|collections|stats

Run from the repo root with ``PYTHONPATH=core`` (or with the package
installed). The Archive lives at ``~/.levi/archive/``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from levi.archive.ingest import ingest_reports
from levi.archive.search import build_collections, collection_slugs, search, stats
from levi.archive.store import ArchiveStore


def _research_root() -> Path:
    # research_notes lives next to the repo in the workspace
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent.parent / "research_notes"
        if cand.is_dir():
            return cand
    # fallback: ~/workspace/research_notes
    return Path.home() / "workspace" / "research_notes"


def cmd_ingest(args) -> int:
    root = Path(args.research_root) if args.research_root else _research_root()
    if not root.is_dir():
        print("research root not found: %s" % root, file=sys.stderr)
        return 2
    records, errors = ingest_reports(root, slugs=args.slug or None)
    store = ArchiveStore()
    result = store.add_many(records)
    print("parsed=%d added=%d skipped(dup)=%d errors=%d"
          % (len(records), result["added"], result["skipped"], len(errors)))
    for err in errors:
        print("ERROR: %s" % err, file=sys.stderr)
    return 1 if errors else 0


def cmd_search(args) -> int:
    store = ArchiveStore()
    hits = search(store, args.query or "", kind=args.kind, rating=args.rating,
                  status=args.status, era=args.era, limit=args.limit)
    if args.json:
        print(json.dumps([{"id": h.record.id, "title": h.record.title,
                           "score": h.score, "why": h.why,
                           "rating": h.record.rating,
                           "status": h.record.status} for h in hits],
                         indent=2, ensure_ascii=False))
    else:
        for h in hits:
            print("[%.1f] %s  (%s · %s · %s)" %
                  (h.score, h.record.title, h.record.kind,
                   h.record.rating, h.record.status))
            print("      %s  — %s" % (h.record.id, h.why))
    return 0


def cmd_show(args) -> int:
    store = ArchiveStore()
    rec = store.get(args.id)
    if rec is None:
        print("no such record: %s" % args.id, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(rec.to_dict(), indent=2, ensure_ascii=False))
        return 0
    print(rec.placard())
    print("\n--- mechanism ---\n%s" % rec.mechanism)
    print("\n--- decline ---\n%s" % rec.decline)
    print("\n--- revival recipe ---\n%s" % rec.revival_recipe)
    print("\n--- levi application ---\n%s" % rec.levi_application)
    if rec.skepticism:
        print("\n--- skepticism ---\n%s" % rec.skepticism)
    if rec.sources:
        print("\n--- sources ---")
        for url in rec.sources:
            print("  %s" % url)
    if rec.provenance:
        print("\nprovenance: %s / %s — %s" %
              (rec.provenance.research_slug, rec.provenance.found_date,
               rec.provenance.notes))
    return 0


def cmd_collections(args) -> int:
    store = ArchiveStore()
    wings = build_collections(store.all())
    if args.wing:
        if args.wing not in wings:
            print("unknown wing (try: %s)" % ", ".join(collection_slugs()),
                  file=sys.stderr)
            return 2
        wing = wings[args.wing]
        print("%s — %s (%d records)" % (wing.name, wing.description,
                                        len(wing.record_ids)))
        for rid in sorted(wing.record_ids):
            rec = store.get(rid)
            kws = ", ".join(wing.matched_keywords.get(rid, []))
            print("  %s  [%s]" % (rec.title if rec else rid, kws))
        return 0
    for slug in collection_slugs():
        w = wings[slug]
        print("%-18s %3d  %s" % (slug, len(w.record_ids), w.name))
    return 0


def cmd_stats(args) -> int:
    print(json.dumps(stats(ArchiveStore()), indent=2, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="levi.archive",
                                 description="The LEVI Archive — the Smithsonian module.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ingest", help="parse research reports into the archive")
    p.add_argument("--research-root", default=None)
    p.add_argument("--slug", action="append", default=None,
                   help="research slug to ingest (repeatable)")
    p.set_defaults(fn=cmd_ingest)

    p = sub.add_parser("search", help="search the archive")
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--kind", default=None)
    p.add_argument("--rating", default=None)
    p.add_argument("--status", default=None)
    p.add_argument("--era", default=None)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_search)

    p = sub.add_parser("show", help="show one record in full")
    p.add_argument("id")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("collections", help="museum wings")
    p.add_argument("wing", nargs="?", default=None)
    p.set_defaults(fn=cmd_collections)

    p = sub.add_parser("stats", help="archive statistics")
    p.set_defaults(fn=cmd_stats)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
