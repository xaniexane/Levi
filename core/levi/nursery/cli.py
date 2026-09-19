"""Nursery CLI — enroll, raise, examine, graduate, and work trainees.

Standalone: ``python -m levi.nursery <command> ...``
Top-level hook (pending ``cli/main.py`` availability)::

    from levi.nursery.cli import cmd_nursery, register_nursery_parser
    register_nursery_parser(sub)   # in the subparsers block
    "nursery": cmd_nursery,        # in the dispatch table
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="levi nursery", description="Agent nursery — raise the cohort")
    sub = p.add_subparsers(dest="command", required=True)

    e = sub.add_parser("enroll", help="Enroll a trainee (seeded on day one)")
    e.add_argument("name")
    e.add_argument("--track", choices=("ai", "si"), default="ai")
    e.add_argument("--no-seed", action="store_true", help="Enroll blank (no day-one seeding)")

    s = sub.add_parser("status", help="Cohort roster or one trainee's dashboard")
    s.add_argument("trainee_id", nargs="?")

    c = sub.add_parser("cycle", help="Run training cycles for a trainee")
    c.add_argument("trainee_id")
    c.add_argument("--n", type=int, default=1)

    x = sub.add_parser("exam", help="Run the 5-probe graduation exam")
    x.add_argument("trainee_id")

    g = sub.add_parser("graduate", help="Graduate a trainee (all gates + named approver)")
    g.add_argument("trainee_id")
    g.add_argument("--by", required=True, help="Approver name (e.g. chauncey)")

    a = sub.add_parser("assign", help="Assign supervised work to a graduated trainee")
    a.add_argument("trainee_id")
    a.add_argument("task_kind")
    a.add_argument("--payload", default="{}", help="JSON payload for the task")

    r = sub.add_parser("records", help="Journal / exam / ledger records")
    r.add_argument("trainee_id")
    r.add_argument("--kind", choices=("journal", "exam", "ledger"), default="journal")
    r.add_argument("--limit", type=int, default=10)

    d = sub.add_parser("drill", help="Queue a training drill card")
    d.add_argument("trainee_id")
    d.add_argument("kind")
    d.add_argument("text", nargs="+")

    sd = sub.add_parser("seed", help="Seed/re-seed a trainee from Levi's learnings")
    sd.add_argument("trainee_id")

    sy = sub.add_parser("sync", help="Sync Levi's new learnings to trainees")
    sy.add_argument("trainee_id", nargs="?", help="Omit to sync the whole cohort")

    t = sub.add_parser("tasks", help="List supervised task templates")
    return p


def register_nursery_parser(sub: Any) -> None:
    """Hook for ``cli/main.py``: adds the ``nursery`` subcommand."""
    parser = sub.add_parser("nursery", help="Agent nursery — raise the cohort")
    parser.add_argument("argv", nargs=argparse.REMAINDER, help="nursery subcommand + args")
    parser.set_defaults(_nursery_dispatch=cmd_nursery)


def cmd_nursery(args: Any) -> int:
    """Dispatch for the ``cli/main.py`` hook — passthrough to main()."""
    argv = list(getattr(args, "argv", None) or [])
    return main(argv)


def _print(obj: Any) -> None:
    if isinstance(obj, (dict, list)):
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    else:
        print(obj)


def main(argv: list[str] | None = None) -> int:
    from levi.nursery import (
        assign,
        enroll_trainee,
        evaluate_gates,
        get_trainee,
        graduate,
        list_trainees,
        run_exam,
        run_trainee_cycle,
        seed_trainee,
        sync_all_trainees,
        sync_trainee,
        trainee_stats,
    )
    from levi.nursery.exam import latest_exam
    from levi.nursery.router import read_ledger
    from levi.nursery.seed import sync_status
    from levi.nursery.tasks import TASKS
    from levi.nursery.training import queue_drill, trainee_journal

    args = build_parser().parse_args(argv)
    cmd = args.command
    try:
        if cmd == "enroll":
            t = enroll_trainee(args.name, args.track, seed=not args.no_seed)
            print("enrolled %s (%s, track=%s)" % (t.id, t.name, t.track))
        elif cmd == "status":
            if args.trainee_id:
                st = trainee_stats(args.trainee_id)
                gates = evaluate_gates(args.trainee_id)
                sync = sync_status(args.trainee_id)
                _print({"stats": st, "gates_met": gates["met_all"],
                        "unmet": [g["name"] for g in gates["gates"] if not g["met"]],
                        "sync": sync})
            else:
                for t in list_trainees():
                    print("%-28s %-10s %-8s %s" % (t.id, t.track, t.status, t.name))
                if not list_trainees():
                    print("(empty cohort)")
        elif cmd == "cycle":
            for _ in range(max(1, args.n)):
                rep = run_trainee_cycle(args.trainee_id)
            _print({k: rep[k] for k in ("trainee_id", "total_cycles", "accepted", "corroborated", "sync") if k in rep})
        elif cmd == "exam":
            _print(run_exam(args.trainee_id))
        elif cmd == "graduate":
            _print(graduate(args.trainee_id, args.by))
            print("graduated — approved by %s" % args.by)
        elif cmd == "assign":
            payload = json.loads(args.payload)
            receipt = assign(args.trainee_id, args.task_kind, payload)
            _print({k: v for k, v in receipt.items() if k != "verified_result"})
        elif cmd == "records":
            if args.kind == "journal":
                _print(trainee_journal(args.trainee_id, limit=args.limit))
            elif args.kind == "exam":
                _print(latest_exam(args.trainee_id))
            else:
                _print(read_ledger(args.trainee_id, limit=args.limit))
        elif cmd == "drill":
            card = queue_drill(args.trainee_id, args.kind, " ".join(args.text))
            print("queued drill [%s]" % card["kind"])
        elif cmd == "seed":
            _print(seed_trainee(args.trainee_id))
        elif cmd == "sync":
            if args.trainee_id:
                _print(sync_trainee(args.trainee_id))
            else:
                _print(sync_all_trainees())
        elif cmd == "tasks":
            for name, (_n, desc, _e, _v) in sorted(TASKS.items()):
                print("%-18s %s" % (name, desc))
    except (KeyError, ValueError) as exc:
        print("nursery: %s" % exc, file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — GateFailure/Refusal/VerificationFailure carry messages
        print("nursery: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 1
    return 0
