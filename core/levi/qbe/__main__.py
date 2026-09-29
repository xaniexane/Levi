"""CLI: python -m levi.qbe records.jsonl query.json

Query a JSONL table by example. query.json holds {"skeletons": [...]} over
the table named "records", or {"tables": {...}, "skeletons": [...]}.
Prints the projected rows as JSON.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import load_jsonl, query


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="levi.qbe")
    ap.add_argument("records", help="JSONL file of records (table 'records')")
    ap.add_argument("queryfile", help="JSON file with skeletons")
    ap.add_argument("--no-dedup", action="store_true",
                    help="keep duplicate projected rows")
    args = ap.parse_args(argv)

    with open(args.queryfile, encoding="utf-8") as fh:
        spec = json.load(fh)
    tables = spec.get("tables") or {"records": load_jsonl(args.records)}
    rows = query(tables, spec["skeletons"], dedup=not args.no_dedup)
    json.dump(rows, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
