"""Quetta-Pan rebuilt CLI — keeps the v10.0 shape his muscle memory knows.

python3 -m levi.quetta_pan.cli --path .            # dry-run (default)
python3 -m levi.quetta_pan.cli --path . --apply    # per-file approval
python3 -m levi.quetta_pan.cli --path . --pi       # agent-pi fan-out/fan-in pass
python3 -m levi.quetta_pan.cli --compost           # replay failure compost
python3 -m levi.quetta_pan.cli --genome            # show learned genome
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agent_pi import run_pi
from .brain import QuettaPanDaVinci
from .engine import QuettaPanEngine


def _engine_for(args) -> QuettaPanEngine:
    brain = QuettaPanDaVinci("") if args.brain else None
    return QuettaPanEngine(
        project_root=args.path,
        brain=brain,
        test_cmd=args.test_cmd.split() if args.test_cmd else None,
    )


def cmd_scan(args) -> int:
    eng = _engine_for(args)
    stats = eng.run(dry_run=not args.apply)
    print(f"\nQuetta-Pan cycle done: {stats}")
    return 0


def cmd_pi(args) -> int:
    eng = _engine_for(args)
    stats = run_pi(eng, dry_run=not args.apply)
    print(f"\nagent-pi cycle done: {stats}")
    return 0


def cmd_compost(args) -> int:
    eng = _engine_for(args)
    entries = eng.compost.recent(args.limit)
    if not entries:
        print("Compost is empty — no failures recorded yet.")
        return 0
    for e in entries:
        print(f"[{e['ts']}] {e['rule_id']} on {e['file']}")
        print(f"  failed: {e['failed_why']}")
        print(f"  inverse: {e['inverse_lesson']}\n")
    return 0


def cmd_genome(args) -> int:
    eng = _engine_for(args)
    patterns = eng.genome.patterns()
    if not patterns:
        print("Genome is empty — no outcomes learned yet.")
        return 0
    print(json.dumps(patterns, indent=2))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Quetta-Pan rebuilt — evolution engine with REIM/RIEM loop"
    )
    parser.add_argument("--path", default=".", help="Project root to scan")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Prompt per file and apply (default: dry-run)",
    )
    parser.add_argument(
        "--pi",
        action="store_true",
        help="Run the agent-pi fan-out/fan-in pass per file "
        "instead of the standard suggest/apply cycle",
    )
    parser.add_argument(
        "--brain",
        action="store_true",
        help="Attach the QuettaPanDaVinci brain detectors",
    )
    parser.add_argument(
        "--test-cmd",
        default="",
        help="Test command run after each mutation "
        "(space-separated); failures roll back",
    )
    parser.add_argument(
        "--compost",
        action="store_true",
        help="Replay the REIM failure compost and exit",
    )
    parser.add_argument(
        "--genome", action="store_true", help="Show the RIEM genome and exit"
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="Entries to show for --compost"
    )
    args = parser.parse_args(argv)

    if not Path(args.path).is_dir():
        print(f"error: not a directory: {args.path}", file=sys.stderr)
        return 2
    if args.compost:
        return cmd_compost(args)
    if args.genome:
        return cmd_genome(args)
    if args.pi:
        return cmd_pi(args)
    return cmd_scan(args)


if __name__ == "__main__":
    raise SystemExit(main())
