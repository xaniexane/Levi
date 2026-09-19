"""CLI: python -m levi.eula lint --file terms.txt [--format text|json]"""

import argparse
import json
import sys

from .linter import lint_file, summarize


def _render_text(findings) -> str:
    if not findings:
        return "No hostile clauses detected. Nothing above info level found."
    lines = []
    counts = summarize(findings)
    lines.append(
        "EULA scan: %d hostile, %d caution, %d info"
        % (counts["hostile"], counts["caution"], counts["info"])
    )
    for f in findings:
        lines.append("")
        lines.append("[%s] %s" % (f["severity"].upper(), f["title"]))
        lines.append("  Clause: %s" % f["clause_excerpt"])
        lines.append("  Plain language: %s" % f["plain_language_flag"])
        if f["why_it_matters"]:
            lines.append("  Why it matters: %s" % f["why_it_matters"])
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="levi.eula",
        description="Lint EULA/terms-of-service text for hostile clauses.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    lint_cmd = sub.add_parser("lint", help="Scan a terms file.")
    lint_cmd.add_argument("--file", required=True, help="Path to the terms text file.")
    lint_cmd.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    if args.command == "lint":
        try:
            findings = lint_file(args.file)
        except OSError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 1
        if args.format == "json":
            print(json.dumps(findings, indent=2, ensure_ascii=False))
        else:
            print(_render_text(findings))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
