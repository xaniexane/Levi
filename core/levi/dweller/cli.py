"""``levi dweller`` CLI: tend LEVI's purgatory.

``purgatory`` renders the Dweller's ledger of the waiting — dead
letters, compost, denied gates, fog verdicts, unborn concepts.
``tend`` performs the tending rites: compost review, dead-letter
re-drive (gated) or release (receipted), and the unborn watch.
``grind`` queues tending-labor jobs and runs them; ``jobs`` lists the
queue; ``receipt`` shows a finished job's receipt.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from levi.automation.hitl import auto_approve

from .jobs import new_job
from .purgatory import gather_purgatory, render_ledger
from .queue import enqueue, list_jobs, load_receipt
from .runners import RUNNER_KINDS
from .si import grind
from .si.grind import default_steps, grind_job_id
from .tend import (
    compost_review,
    redrive_dead_letter,
    release_dead_letter,
    unborn_watch,
)


def _console_responder(request):
    """Interactive yes/no gate responder. Non-tty stdin denies (fail-closed)."""
    try:
        if not sys.stdin.isatty():
            return {"decision": "denied", "note": "non-interactive stdin"}
        answer = input("[dweller gate] %s — approve? [y/N] " % request.prompt)
    except (EOFError, KeyboardInterrupt):
        return {"decision": "denied", "note": "no answer"}
    if answer.strip().lower() in ("y", "yes"):
        return {"decision": "approved", "note": "approved at the console"}
    return {"decision": "denied", "note": "declined at the console"}


def _add_subcommands(cmds) -> None:
    """Attach grind/jobs/receipt under an existing argparse subparsers object."""
    grind_p = cmds.add_parser("grind", help="queue and grind a job")
    grind_p.add_argument(
        "--kind",
        required=True,
        choices=list(RUNNER_KINDS),
        help="grind kind",
    )
    grind_p.add_argument("--root", default="", help="repo-sweep: root to sweep")
    grind_p.add_argument(
        "--set-a",
        action="append",
        default=[],
        help="crossref: file in set A (repeatable)",
    )
    grind_p.add_argument(
        "--set-b",
        action="append",
        default=[],
        help="crossref: file in set B (repeatable)",
    )
    grind_p.add_argument("--probe-path", default="", help="watch: file to probe")
    grind_p.add_argument(
        "--probe-contains", default="", help="watch: substring that satisfies the watch"
    )
    grind_p.add_argument(
        "--times", type=int, default=3, help="watch: max attempts (default 3)"
    )
    grind_p.add_argument(
        "--sandbox",
        default="",
        help="sandbox root the job may not leave (default: the grind root / cwd)",
    )
    grind_p.add_argument(
        "--dry-run",
        action="store_true",
        help="queue the job and preview it without executing",
    )
    grind_p.add_argument(
        "--yes",
        action="store_true",
        help="approve the permission gate (only for grinds you fully trust)",
    )
    grind_p.add_argument(
        "--resume",
        action="store_true",
        help="with --job-id: resume a failed job instead of queueing new",
    )
    grind_p.add_argument(
        "--job-id", default="", help="grind an already-queued job by id"
    )

    cmds.add_parser("jobs", help="list queued jobs")

    receipt_p = cmds.add_parser("receipt", help="show a job's final receipt")
    receipt_p.add_argument("job_id", help="job id (see `jobs`)")

    purg_p = cmds.add_parser(
        "purgatory",
        help="the Dweller's ledger of the waiting (dead letters, compost, "
        "denied gates, fog verdicts, unborn)",
    )
    purg_p.add_argument(
        "--json", action="store_true", help="emit the raw ledger as JSON"
    )
    purg_p.add_argument(
        "--no-fog", action="store_true", help="skip the fresh fog sweep"
    )

    tend_p = cmds.add_parser(
        "tend",
        help="perform a tending rite for the waiting",
    )
    tend_p.add_argument(
        "rite",
        choices=["compost-review", "re-drive", "release", "unborn-watch"],
        help="which rite to perform",
    )
    tend_p.add_argument(
        "--failures",
        default="",
        help="compost-review: JSON file with a list of failure records",
    )
    tend_p.add_argument(
        "--index",
        type=int,
        default=-1,
        help="re-drive/release: dead-letter index (see `purgatory`)",
    )
    tend_p.add_argument(
        "--reason", default="", help="release: why the letter is released"
    )
    tend_p.add_argument(
        "--yes",
        action="store_true",
        help="approve the permission gate (only for rites you fully trust)",
    )


def register_dweller_parser(sub) -> None:
    """Attach the ``levi dweller`` parser under ``sub`` (argparse subparsers)."""
    dp = sub.add_parser(
        "dweller",
        help="Dweller: purgatory-dweller, Leviathan-class — it tends LEVI's in-between",
    )
    cmds = dp.add_subparsers(dest="dweller_cmd", required=True)
    _add_subcommands(cmds)


def _build_job(args: argparse.Namespace):
    kind = args.kind
    if kind == "repo-sweep":
        if not args.root:
            raise ValueError("repo-sweep needs --root")
        root = os.path.abspath(args.root)
        params = {"root": root}
        sandbox = os.path.abspath(args.sandbox) if args.sandbox else root
    elif kind == "crossref":
        if not args.set_a or not args.set_b:
            raise ValueError("crossref needs --set-a and --set-b")
        params = {
            "set_a": [os.path.abspath(p) for p in args.set_a],
            "set_b": [os.path.abspath(p) for p in args.set_b],
        }
        sandbox = os.path.abspath(args.sandbox) if args.sandbox else os.getcwd()
    elif kind == "watch":
        if not args.probe_path or not args.probe_contains:
            raise ValueError("watch needs --probe-path and --probe-contains")
        probe = os.path.abspath(args.probe_path)
        params = {
            "probe_path": probe,
            "probe_contains": args.probe_contains,
            "times": args.times,
        }
        sandbox = (
            os.path.abspath(args.sandbox) if args.sandbox else os.path.dirname(probe)
        )
    else:  # pragma: no cover — argparse choices guard this
        raise ValueError("unknown kind: %r" % kind)
    job = new_job(
        kind, params=params, sandbox_root=sandbox, steps=default_steps(kind, params)
    )
    return job


def _print_receipt_summary(receipt) -> None:
    print("job:      %s" % receipt["job_id"])
    print("kind:     %s" % receipt["kind"])
    print("decision: %s" % receipt["decision"])
    print("state:    %s" % receipt["state"])
    print("note:     %s" % receipt["note"])
    for s in receipt["steps"]:
        extra = (" (%s)" % s["error"]) if s.get("error") else ""
        print("  [%s] %s%s" % (s["state"], s["label"], extra))


def _cmd_grind(args: argparse.Namespace) -> int:
    responder = auto_approve if args.yes else _console_responder
    if args.job_id:
        try:
            receipt = grind_job_id(
                args.job_id,
                responder=responder,
                dry_run=args.dry_run,
                resume=args.resume,
            )
        except (KeyError, ValueError) as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 1
        _print_receipt_summary(receipt)
        return 0 if receipt["decision"] in ("dry-run", "executed") else 1
    try:
        job = _build_job(args)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    enqueue(job)
    print("queued %s (%s)" % (job.id, job.kind))
    receipt = grind(job, responder=responder, dry_run=args.dry_run)
    _print_receipt_summary(receipt)
    return 0 if receipt["decision"] in ("dry-run", "executed") else 1


def _cmd_jobs(args: argparse.Namespace) -> int:
    jobs = list_jobs()
    if not jobs:
        print("no jobs queued")
        return 0
    for job in jobs:
        print(
            "%s | %s | %s | %d step(s) | %s"
            % (job.id, job.kind, job.state, len(job.steps), job.created_ts)
        )
    print("%d job(s)" % len(jobs))
    return 0


def _cmd_receipt(args: argparse.Namespace) -> int:
    try:
        receipt = load_receipt(args.job_id)
    except KeyError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


def _cmd_purgatory(args: argparse.Namespace) -> int:
    ledger = gather_purgatory(include_fog=not args.no_fog)
    if args.json:
        print(json.dumps(ledger, indent=2, sort_keys=True))
    else:
        print(render_ledger(ledger))
    return 0


def _cmd_tend(args: argparse.Namespace) -> int:
    responder = auto_approve if args.yes else _console_responder
    if args.rite == "compost-review":
        if not args.failures:
            print("error: compost-review needs --failures <json-file>", file=sys.stderr)
            return 2
        try:
            records = json.loads(Path(args.failures).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print("error: cannot read failures file: %s" % exc, file=sys.stderr)
            return 2
        if not isinstance(records, list):
            print("error: failures file must hold a JSON list", file=sys.stderr)
            return 2
        receipt = compost_review(records)
    elif args.rite == "re-drive":
        if args.index < 0:
            print(
                "error: re-drive needs --index (see `levi dweller purgatory`)",
                file=sys.stderr,
            )
            return 2
        try:
            receipt = redrive_dead_letter(args.index, responder=responder)
        except KeyError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 1
    elif args.rite == "release":
        if args.index < 0 or not args.reason:
            print("error: release needs --index and --reason", file=sys.stderr)
            return 2
        try:
            receipt = release_dead_letter(args.index, args.reason)
        except KeyError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 1
    else:  # unborn-watch
        receipt = unborn_watch()
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if isinstance(receipt, dict) and receipt.get("decision") == "denied":
        return 1
    return 0


def cmd_dweller(args: argparse.Namespace) -> int:
    """Dispatch ``levi dweller`` subcommands."""
    handlers = {
        "grind": _cmd_grind,
        "jobs": _cmd_jobs,
        "receipt": _cmd_receipt,
        "purgatory": _cmd_purgatory,
        "tend": _cmd_tend,
    }
    handler = handlers.get(args.dweller_cmd)
    if handler is None:
        print("error: unknown dweller command", file=sys.stderr)
        return 2
    return handler(args)
