"""CLI: python -m levi.reveal FILE [--json] [--exorcise]

The Reveal-Codes inspector: open the second screen on a document and
show the codes editors hide — structure (headings, emphasis, links,
lists, tables) and invisible characters (zero-width, trailing whitespace,
BOM). With --exorcise, strip the invisibles and report every removal.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import exorcise, reveal


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="levi.reveal", description="Reveal the codes editors hide."
    )
    ap.add_argument("file", help="text/markdown file to inspect")
    ap.add_argument("--json", action="store_true", help="emit the token list as JSON")
    ap.add_argument(
        "--exorcise",
        action="store_true",
        help="strip invisible characters; cleaned text to stdout, "
        "removal receipt to stderr",
    )
    args = ap.parse_args(argv)

    path = Path(args.file)
    if not path.is_file():
        print("no such file: %s" % args.file, file=sys.stderr)
        return 2
    text = path.read_text(encoding="utf-8", errors="replace")

    if args.exorcise:
        cleaned, removed = exorcise(text)
        sys.stdout.write(cleaned)
        print("exorcised %d invisible codes" % len(removed), file=sys.stderr)
        for t in removed:
            print(
                "  L%d c%d [%s] %s" % (t.line, t.col, t.label, t.detail),
                file=sys.stderr,
            )
        return 0

    report = reveal(text)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(report.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
