"""LEVI jobs tracker — local-first opportunity / deal pipeline.

Commands: add / list / move / note / show / update / restrict / stats /
import-demand. Local only: state under ``~/.levi/jobs/`` with owner-only
permissions. Tracking only — nothing here scrapes listings or acts on
anything; applications and outreach are always your action.
"""

from __future__ import annotations

import argparse

from .tracker import STATUSES, JobTracker, import_demand
from .organ_cli import cmd_organ, register_organ_parser


def register_jobs_parser(sub) -> None:
    jb = sub.add_parser("jobs", help="local opportunity pipeline tracker")
    cmds = jb.add_subparsers(dest="jobs_cmd")

    add_p = cmds.add_parser("add", help="add a job to the pipeline")
    add_p.add_argument("--title", required=True, help="job title")
    add_p.add_argument("--company", default="", help="company / counterpart")
    add_p.add_argument(
        "--source",
        default="manual",
        help="where it came from (e.g. demand-pipeline, manual)",
    )
    add_p.add_argument(
        "--status",
        default="new",
        choices=list(STATUSES),
        help="starting status (default: new)",
    )

    list_p = cmds.add_parser("list", help="list tracked jobs")
    list_p.add_argument(
        "--status", default=None, choices=list(STATUSES), help="filter by status"
    )

    move_p = cmds.add_parser("move", help="move a job to a new pipeline status")
    move_p.add_argument("id", type=int, help="job id")
    move_p.add_argument("status", choices=list(STATUSES), help="new status")

    note_p = cmds.add_parser("note", help="append a timestamped note to a job")
    note_p.add_argument("id", type=int, help="job id")
    note_p.add_argument("text", help="note text")

    show_p = cmds.add_parser("show", help="show one job with notes")
    show_p.add_argument("id", type=int, help="job id")

    upd_p = cmds.add_parser("update", help="update a job's fields")
    upd_p.add_argument("id", type=int, help="job id")
    upd_p.add_argument("--title", default=None, help="new title")
    upd_p.add_argument("--company", default=None, help="new company")
    upd_p.add_argument("--source", default=None, help="new source")
    upd_p.add_argument(
        "--status",
        default=None,
        choices=list(STATUSES),
        help="new status (validated transition)",
    )

    res_p = cmds.add_parser("restrict", help="manage pipeline restrictions")
    res_p.add_argument("action", choices=["add", "remove", "list"])
    res_p.add_argument("text", nargs="?", default=None, help="restriction text")

    cmds.add_parser("stats", help="pipeline counts by status")

    imp_p = cmds.add_parser(
        "import-demand",
        help="track DemandPulse opportunities/score cards as jobs (idempotent)",
    )
    imp_p.add_argument(
        "--min-worth",
        type=float,
        default=0.0,
        help="only import opportunities with worth >= this (0-1)",
    )
    imp_p.add_argument(
        "--min-score",
        type=float,
        default=0.0,
        help="only import five-factor cards with composite >= this (0-100)",
    )
    imp_p.add_argument(
        "--limit", type=int, default=0, help="max items to import (0 = no limit)"
    )
    imp_p.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be imported without writing",
    )

    register_organ_parser(cmds)


def _fmt_job(job) -> str:
    return (
        f"[{job.id}] {job.title}"
        + (f" @ {job.company}" if job.company else "")
        + f"\n    status: {job.status}    source: {job.source}\n"
        f"    created: {job.created_at}    updated: {job.updated_at}"
    )


def cmd_jobs(args: argparse.Namespace) -> int:
    if getattr(args, "jobs_cmd", None) == "organ":
        return cmd_organ(args)
    tracker = JobTracker()
    cmd = getattr(args, "jobs_cmd", None) or "stats"

    if cmd == "add":
        try:
            job = tracker.add(
                title=args.title,
                company=args.company or "",
                source=args.source or "manual",
                status=args.status,
            )
        except ValueError as exc:
            print(f"jobs add failed: {exc}")
            return 2
        print(_fmt_job(job))
        return 0

    if cmd == "list":
        try:
            jobs = tracker.list(status=args.status)
        except ValueError as exc:
            print(f"jobs list failed: {exc}")
            return 2
        if not jobs:
            print(
                "no jobs tracked"
                + (f" with status {args.status}" if args.status else "")
            )
            return 0
        for job in jobs:
            line = f"[{job.id}] {job.title}"
            if job.company:
                line += f" @ {job.company}"
            print(f"{line} — {job.status} (source: {job.source})")
        return 0

    if cmd == "move":
        try:
            job = tracker.move(args.id, args.status)
        except (ValueError, KeyError) as exc:
            print(f"jobs move failed: {exc}")
            return 2
        print(f"[{job.id}] {job.title} → {job.status}")
        return 0

    if cmd == "update":
        try:
            job = tracker.update(
                args.id,
                title=args.title,
                company=args.company,
                source=args.source,
                status=args.status,
            )
        except (ValueError, KeyError) as exc:
            print(f"jobs update failed: {exc}")
            return 2
        print(_fmt_job(job))
        return 0

    if cmd == "note":
        try:
            note = tracker.note(args.id, args.text)
        except (ValueError, KeyError) as exc:
            print(f"jobs note failed: {exc}")
            return 2
        print(f"note added to job {args.id} @ {note.ts}")
        return 0

    if cmd == "show":
        try:
            job = tracker.get(args.id)
        except (ValueError, KeyError) as exc:
            print(f"jobs show failed: {exc}")
            return 2
        print(_fmt_job(job))
        if job.notes:
            print("    notes:")
            for n in job.notes:
                print(f"      [{n.ts}] {n.text}")
        return 0

    if cmd == "restrict":
        if args.action == "list" or args.text is None:
            current = tracker.restrictions()
            if not current:
                print("no restrictions set")
            else:
                for r in current:
                    print(f"  - {r}")
            return 0
        try:
            if args.action == "add":
                updated = tracker.add_restriction(args.text)
            else:
                updated = tracker.remove_restriction(args.text)
        except ValueError as exc:
            print(f"jobs restrict failed: {exc}")
            return 2
        print(f"restrictions ({len(updated)}):")
        for r in updated:
            print(f"  - {r}")
        return 0

    if cmd == "stats":
        s = tracker.stats()
        print(f"total: {s['total']}   active: {s['active']}")
        for status, count in s["by_status"].items():
            if count:
                print(f"  {status}: {count}")
        print(f"restrictions: {s['restrictions']}")
        return 0

    if cmd == "import-demand":
        try:
            result = import_demand(
                tracker,
                min_worth=args.min_worth,
                min_score=args.min_score,
                limit=args.limit or 0,
                dry_run=args.dry_run,
            )
        except (ValueError, OSError) as exc:
            print(f"jobs import-demand failed: {exc}")
            return 2
        tag = "would import" if result["dry_run"] else "imported"
        print(
            f"{tag}: created={result['created']} refreshed={result['refreshed']} "
            f"skipped={result['skipped']}"
        )
        for item in result["imported"]:
            print(f"  - {item['title']}")
        return 0

    print(f"unknown jobs command: {cmd}")
    return 2
