"""python -m levi.verify — the proof desk from the command line.

Exit code 0 when the check passes, 1 when it fails, 2 on malformed input.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import (
    check_product,
    check_sum,
    crossfoot,
    elevens,
    format_sigfigs,
    nines,
    to_sigfigs,
)
from .bulla import append_record, verify_chain
from .trialbalance import trial_balance


def _report(receipts) -> int:
    failed = False
    for r in receipts:
        print(r)
        if not r.ok:
            failed = True
    return 1 if failed else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="levi.verify",
        description="Pre-digital verification rituals: proofs for numbers.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("digit-root", help="cast out nines/elevens of an int")
    p.add_argument("n", type=int)

    p = sub.add_parser("check-sum", help="prove sum(terms) == result")
    p.add_argument("terms", nargs="+", type=int)
    p.add_argument("--result", type=int, required=True)

    p = sub.add_parser("check-product", help="prove a * b == result")
    p.add_argument("a", type=int)
    p.add_argument("b", type=int)
    p.add_argument("--result", type=int, required=True)

    p = sub.add_parser("crossfoot", help="prove a ledger table from a JSON file")
    p.add_argument("path", help="JSON file holding an array of int arrays")

    p = sub.add_parser("sigfigs", help="round to n significant figures")
    p.add_argument("value", type=float)
    p.add_argument("--sig", type=int, required=True)

    p = sub.add_parser("seal", help="seal one JSON record onto a chained log")
    p.add_argument("payload", help="JSON object to seal")
    p.add_argument(
        "--prev", default="", help="previous sealed line (empty for genesis)"
    )

    p = sub.add_parser("unseal", help="verify a chained log file")
    p.add_argument("path", help="JSONL file of sealed lines")

    p = sub.add_parser("trial-balance", help="reconcile journal.json vs index.json")
    p.add_argument("journal", help="JSON object: id -> entry")
    p.add_argument("index", help="JSON object: topic -> [ids]")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "digit-root":
            print("nines: %d   elevens: %d" % (nines(args.n), elevens(args.n)))
            return 0
        if args.cmd == "check-sum":
            return _report([check_sum(args.terms, args.result)])
        if args.cmd == "check-product":
            return _report(check_product(args.a, args.b, args.result))
        if args.cmd == "crossfoot":
            with open(args.path, encoding="utf-8") as fh:
                table = json.load(fh)
            return _report([crossfoot(table)])
        if args.cmd == "sigfigs":
            print(format_sigfigs(to_sigfigs(args.value, args.sig), args.sig))
            return 0
        if args.cmd == "seal":
            payload = json.loads(args.payload)
            if not isinstance(payload, dict):
                raise ValueError("payload must be a JSON object")
            print(append_record(args.prev, payload))
            return 0
        if args.cmd == "unseal":
            with open(args.path, encoding="utf-8") as fh:
                ok, problems = verify_chain(fh)
            if ok:
                print("bulla: chain intact")
                return 0
            for prob in problems:
                print("bulla: " + prob)
            return 1
        if args.cmd == "trial-balance":
            with open(args.journal, encoding="utf-8") as fh:
                journal = json.load(fh)
            with open(args.index, encoding="utf-8") as fh:
                index = json.load(fh)
            tb = trial_balance(journal, index)
            print(tb)
            return 0 if tb.ok else 1
    except (TypeError, ValueError) as exc:
        print("malformed input: %s" % exc, file=sys.stderr)
        return 2
    raise AssertionError("unreachable")


if __name__ == "__main__":
    sys.exit(main())
