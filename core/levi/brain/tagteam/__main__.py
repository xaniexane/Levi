"""CLI for the tag-team teacher loop.

Usage:
    python -m levi.brain.tagteam run --round 1 --drops drops/ \\
        --workdir work/tagteam --ledger work/tagteam/ledger.jsonl
    python -m levi.brain.tagteam run --round 2 --drops drops/ \\
        --workdir work/tagteam --ledger work/tagteam/ledger.jsonl \\
        --mode bpe --live --steps 600
    python -m levi.brain.tagteam status --ledger work/tagteam/ledger.jsonl

Dry-run is the default: intake + eval + requests run, training does not.
Pass --live to let LEVI's trainer (continue.py) update the weights.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from levi.brain.tagteam import ledger as ledger_mod
from levi.brain.tagteam import personas as personas_mod
from levi.brain.tagteam.loop import RoundConfig, run_round


def _load_conditions(path_str: str) -> tuple:
    """Load persona_condition dicts from a JSON file; validate each."""
    if not path_str:
        return ()
    raw = json.loads(Path(path_str).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit("--conditions file must hold a JSON list")
    return tuple(personas_mod.validate_condition(c) for c in raw)


def cmd_run(args: argparse.Namespace) -> int:
    cfg = RoundConfig(
        round_n=args.round,
        drops_dir=Path(args.drops),
        workdir=Path(args.workdir),
        ledger_path=Path(args.ledger),
        mode=args.mode,
        ckpt=Path(args.ckpt) if args.ckpt else None,
        max_steps=args.steps,
        live=args.live,
        conditions=_load_conditions(args.conditions),
    )
    result = run_round(cfg)
    print(json.dumps(_summarize(result), indent=2))
    return 0 if not result["aborted"] else 1


def _summarize(result: dict) -> dict:
    stages = result["stages"]
    entry = result["entry"]
    return {
        "round": result["round"],
        "aborted": result["aborted"],
        "stages": stages,
        "gaps": (stages.get("gaps") or {}).get("gaps", []),
        "requests_issued": (stages.get("gaps") or {}).get("requests_issued", []),
        "teacher_mix": entry.get("teacher_mix", {}),
        "staged_pending_roster": entry.get("staged_pending_roster", {}),
        "conditions": [c["persona_id"] for c in entry.get("conditions", [])],
    }


def cmd_status(args: argparse.Namespace) -> int:
    entries = ledger_mod.read_entries(Path(args.ledger))
    if not entries:
        print("no tag-team rounds logged yet")
        return 0
    last = entries[-1]
    print(f"rounds logged: {len(entries)}")
    print(f"last round: {last['round']} @ {last['ts']}"
          + (f" — ABORTED: {last['aborted']}" if last.get("aborted") else ""))
    stages = last.get("stages", {})
    for name, st in stages.items():
        if isinstance(st, dict):
            print(f"  {name}: ran={st.get('ran')} "
                  f"{st.get('reason', '')}".rstrip())
    gaps = (stages.get("gaps") or {}).get("gaps", [])
    if gaps:
        print("  gaps:")
        for g in gaps:
            print(f"    {g['topic']}/{g['prompt_id']}: {g['severity']} "
                  f"(score {g['cur_score']:.2f}, delta {g['delta']:+.2f})")
    reqs = (stages.get("gaps") or {}).get("requests_issued", [])
    if reqs:
        print(f"  requests issued: {len(reqs)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Tag-team teacher loop for LEVI's brain.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="run one tag-team round")
    run.add_argument("--round", type=int, required=True)
    run.add_argument("--drops", required=True, help="teacher drop dir (JSONL files)")
    run.add_argument("--workdir", required=True, help="round outputs go here")
    run.add_argument("--ledger", required=True, help="append-only round ledger JSONL")
    run.add_argument("--mode", choices=("char", "bpe"), default="char")
    run.add_argument("--ckpt", default="", help="checkpoint .pt (vocab for char mode)")
    run.add_argument("--steps", type=int, default=600)
    run.add_argument(
        "--live",
        action="store_true",
        help="actually train with LEVI's trainer (default: dry-run)",
    )
    run.add_argument(
        "--conditions",
        default="",
        help="JSON file with a list of persona_condition dicts "
        "(persona/trait/tone/role frames for this round's "
        "teacher requests)",
    )

    status = sub.add_parser("status", help="show ledger status")
    status.add_argument("--ledger", required=True)

    args = ap.parse_args(argv)
    if args.cmd == "run":
        return cmd_run(args)
    return cmd_status(args)


if __name__ == "__main__":
    raise SystemExit(main())
