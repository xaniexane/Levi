"""CLI: python -m levi.echoverse <dream|lenses|status|run> ..."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from levi.echoverse import (
    EchoverseEngine,
    all_lenses,
    apply_lens,
    pipeline,
    seed_from_mandella,
)
from levi.echoverse.branches import BranchStore


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="levi.echoverse", description="Echoverse — Echo in engine form")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("dream", help="multi-cycle REIM expansion")
    p.add_argument("seed")
    p.add_argument("--cycles", type=int, default=3)

    p = sub.add_parser("lenses", help="all six lens views of a seed")
    p.add_argument("seed")
    p.add_argument("--lens", default=None, help="one lens, or all six")

    p = sub.add_parser("run", help="bounded multi-path simulation (taken/not_taken/wild)")
    p.add_argument("seed")
    p.add_argument("--cycles", type=int, default=3)

    p = sub.add_parser("status", help="vault / success memory / rounds")

    p = sub.add_parser("mandella-seed", help="seed a run from a Mandella option label")
    p.add_argument("label")
    p.add_argument("--key", default="A")

    args = ap.parse_args(argv)
    eng = EchoverseEngine()

    if args.cmd == "dream":
        print(json.dumps(eng.dream(args.seed, args.cycles), indent=2, ensure_ascii=True))
    elif args.cmd == "lenses":
        if args.lens:
            print(json.dumps(apply_lens(args.seed, args.lens), indent=2, ensure_ascii=True))
        else:
            print(json.dumps(all_lenses(args.seed), indent=2, ensure_ascii=True))
    elif args.cmd == "run":
        run = BranchStore().simulate(args.seed, args.cycles)
        print(run.format())
    elif args.cmd == "status":
        print(json.dumps(eng.status(), indent=2, ensure_ascii=True))
    elif args.cmd == "mandella-seed":
        run = seed_from_mandella({"key": args.key, "label": args.label})
        print(run.format())
    print("pipeline:", pipeline.doctrine(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
