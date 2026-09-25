"""CLI: python -m levi.generosity

charter                 print the 8 rules and what each inverts
audit                   audit an honest-by-default feature manifest
audit --manifest FILE  audit a JSON manifest (see GenerosityManifest fields)
showcase                audit the four hunted giants — all must FAIL
"""

from __future__ import annotations

import argparse
import json
import sys

from levi.generosity import (
    RULES,
    GenerosityManifest,
    audit,
    audit_giants_showcase,
)


def cmd_charter() -> int:
    print("THE HONEST GENEROSITY CHARTER")
    print("A feature that fails is not a LEVI feature.\n")
    for rule in RULES:
        print("[%s] %s" % (rule.id, rule.title))
        print("    %s\n" % rule.inversion)
    return 0


def cmd_audit(args) -> int:
    if args.manifest:
        with open(args.manifest, encoding="utf-8") as fh:
            data = json.load(fh)
        known = {f for f in GenerosityManifest.__dataclass_fields__}
        unknown = sorted(set(data) - known)
        if unknown:
            print("unknown manifest fields: %s" % ", ".join(unknown), file=sys.stderr)
            return 2
        manifest = GenerosityManifest(**{k: v for k, v in data.items() if k in known})
    else:
        manifest = GenerosityManifest(name=args.name)
    result = audit(manifest)
    print(result.report())
    return 0 if result.passed else 1


def cmd_showcase() -> int:
    results = audit_giants_showcase()
    ok = True
    for key, result in results.items():
        print(result.report())
        print()
        if result.passed:
            print("  !! toothless: %s PASSED the charter" % key)
            ok = False
    print(
        "showcase: %s"
        % ("all four giants fail as expected" if ok else "CHARTER IS TOOTHLESS")
    )
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="levi.generosity")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("charter")
    pa = sub.add_parser("audit")
    pa.add_argument(
        "--manifest", default=None, help="JSON file with GenerosityManifest fields"
    )
    pa.add_argument("--name", default="unnamed-feature")
    sub.add_parser("showcase")
    args = ap.parse_args(argv)
    if args.cmd == "charter":
        return cmd_charter()
    if args.cmd == "audit":
        return cmd_audit(args)
    return cmd_showcase()


if __name__ == "__main__":
    raise SystemExit(main())
