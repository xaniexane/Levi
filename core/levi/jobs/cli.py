"""``levi jobs`` CLI: add / list / move / note / show / restrict / stats.

Local-only job-application pipeline tracker. Tracking only — nothing here
scrapes listings or applies anywhere; applications are always your action.
"""

from __future__ import annotations

import argparse

from .tracker import STAGES, JobTracker


def register_jobs_parser(sub) -> None:
    jb = sub.add_parser(
        "jobs", help="Hybrid Search & Apply: local job-pipeline tracker"
    )
    cmds = jb.add_subparsers(dest="jobs_cmd")

    add_p = cmds.add_parser("add", help="add a job to the pipeline")
    add_p.add_argument("--title", required=True, help="job title")
    add_p.add_argument("--company", required=True, help="company name")
    add_p.add_argument("--source", default="", help="where you found it")
    add_p.add_argument(
        "--stage",
        default="review_buffer",
        choices=list(STAGES),
        help="starting stage (default: review_buffer)",
    )

    list_p = cmds.add_parser("list", help="list tracked jobs")
    list_p.add_argument(
        "--stage", default=None, choices=list(STAGES), help="filter by stage"
    )

    move_p = cmds.add_parser("move", help="move a job to a new stage")
    move_p.add_argument("id", type=int, help="job id")
    move_p.add_argument("stage", choices=list(STAGES), help="new stage")

    note_p = cmds.add_parser("note", help="append a timestamped note to a job")
    note_p.add_argument("id", type=int, help="job id")
    note_p.add_argument("text", help="note text")

    show_p = cmds.add_parser("show", help="show one job with notes")
    show_p.add_argument("id", type=int, help="job id")

    res_p = cmds.add_parser("restrict", help="manage search restrictions")
    res_p.add_argument("action", choices=["add", "remove", "list"])
    res_p.add_argument("text", nargs="?", default=None, help="restriction text")

    cmds.add_parser("stats", help="pipeline counts by stage")


def _fmt_job(job) -> str:
    return (
        f"[{job.id}] {job.title} @ {job.company}\n"
        f"    stage: {job.stage}    source: {job.source or '—'}\n"
        f"    created: {job.created_at}    updated: {job.updated_at}"
    )


def cmd_jobs(args: argparse.Namespace) -> int:
    tracker = JobTracker()
    cmd = getattr(args, "jobs_cmd", None) or "stats"

    if cmd == "add":
        try:
            job = tracker.add(
                title=args.title,
                company=args.company,
                source=args.source or "",
                stage=args.stage,
            )
        except ValueError as exc:
            print(f"jobs add failed: {exc}")
            return 2
        print(_fmt_job(job))
        return 0

    if cmd == "list":
        try:
            jobs = tracker.list(stage=args.stage)
        except ValueError as exc:
            print(f"jobs list failed: {exc}")
            return 2
        if not jobs:
            print("no jobs tracked" + (f" in {args.stage}" if args.stage else ""))
            return 0
        for job in jobs:
            print(f"[{job.id}] {job.title} @ {job.company} — {job.stage}")
        return 0

    if cmd == "move":
        try:
            job = tracker.move(args.id, args.stage)
        except (ValueError, KeyError) as exc:
            print(f"jobs move failed: {exc}")
            return 2
        print(f"[{job.id}] {job.title} → {job.stage}")
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
        for stage, count in s["by_stage"].items():
            if count:
                print(f"  {stage}: {count}")
        print(f"restrictions: {s['restrictions']}")
        return 0

    print(f"unknown jobs command: {cmd}")
    return 2
