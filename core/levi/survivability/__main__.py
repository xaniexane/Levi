"""CLI: python -m levi.survivability list|check [--format text|json]"""

import argparse
import json
import sys

from .catalog import check_all, catalog


def _render_list(entries, fmt) -> str:
    if fmt == "json":
        return json.dumps(entries, indent=2, ensure_ascii=False)
    lines = ["id | capability | offline_ok | degraded mode", "-" * 72]
    for e in entries:
        lines.append(
            "%s | %s | %s | %s"
            % (
                e["id"],
                e["capability"],
                "OFFLINE" if e["offline_ok"] else "ONLINE-ONLY",
                e["degraded_mode"],
            )
        )
    return "\n".join(lines)


def _render_check(results, fmt) -> str:
    if fmt == "json":
        return json.dumps(results, indent=2, ensure_ascii=False)
    lines = []
    for r in results:
        lines.append(
            "[%s] %s — %s" % ("OK " if r["ok"] else "FAIL", r["id"], r["detail"])
        )
    ok = sum(1 for r in results if r["ok"])
    lines.append("survivability check: %d/%d fallbacks present" % (ok, len(results)))
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="levi.survivability",
        description="Catalog what keeps LEVI alive offline; verify fallbacks are present.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    list_cmd = sub.add_parser("list", help="List catalog entries.")
    list_cmd.add_argument("--format", choices=("text", "json"), default="text")
    check_cmd = sub.add_parser(
        "check", help="Verify each entry's fallback is importable/present."
    )
    check_cmd.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    if args.command == "list":
        print(_render_list(catalog(), args.format))
        return 0
    if args.command == "check":
        results = check_all()
        print(_render_check(results, args.format))
        return 0 if all(r["ok"] for r in results) else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
