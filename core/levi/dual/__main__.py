"""CLI for dual-reality files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from levi.dual import create, read, seal, verify, verify_seal


def _show(report: dict) -> None:
    print(json.dumps(report, indent=2))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="levi-dual")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create", help="Write a new dual-reality file")
    c.add_argument("--path", required=True)
    c.add_argument("--title", required=True)
    c.add_argument("--physical", required=True, help="SIDE A content")
    c.add_argument("--canon", required=True, help="SIDE B content")

    r = sub.add_parser("read", help="Print both sides of a dual file")
    r.add_argument("--path", required=True)

    v = sub.add_parser("verify", help="Check the two sides are in sync")
    v.add_argument("--path", required=True)

    s = sub.add_parser("seal", help="Identity-lock a synced dual file")
    s.add_argument("--path", required=True)

    vs = sub.add_parser("verify-seal", help="Check for drift since sealing")
    vs.add_argument("--path", required=True)

    args = ap.parse_args(argv)
    try:
        if args.cmd == "create":
            df = create(Path(args.path), args.title, args.physical, args.canon)
            print(f"created {df.path} — two sides, one file")
        elif args.cmd == "read":
            df = read(Path(args.path))
            print(f"# {df.title}\n\n{SIDE_A}:\n{df.physical}\n\n{SIDE_B}:\n{df.canon}")
        elif args.cmd == "verify":
            _show(verify(Path(args.path)))
        elif args.cmd == "seal":
            _show(seal(Path(args.path)))
        elif args.cmd == "verify-seal":
            _show(verify_seal(Path(args.path)))
    except (ValueError, OSError) as e:
        print(f"error: {e}")
        return 1
    return 0


SIDE_A = "SIDE A (PHYSICAL)"
SIDE_B = "SIDE B (CANON)"

if __name__ == "__main__":
    raise SystemExit(main())
