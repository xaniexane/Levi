"""NeighborOS CLI — `levi neighboros`.

Local-first dispatch OS for LEVI product line 01. Commands: jobs
(add/list/show/assign/move/note/update), workers (add/list/
activate/deactivate), brief (generate the founder's daily operations
brief), stats. State under ``~/.levi/neighboros/``; the brief is
written to a dated file so ``levi neighboros brief`` is cron-friendly.
"""

from __future__ import annotations

import argparse

from .brief import generate_brief
from .tracker import (
    KNOWN_CATEGORIES,
    PRIORITIES,
    STATUSES,
    WORKER_STATUSES,
    NeighborTracker,
)


def register_neighboros_parser(sub) -> None:
    nb = sub.add_parser(
        "neighboros",
        help="NeighborOS dispatch OS (product line 01): jobs + daily brief",
    )
    cmds = nb.add_subparsers(dest="neighboros_cmd")

    # -- jobs ------------------------------------------------------------
    jobs_p = cmds.add_parser("jobs", help="the live Jobs project")
    jcmds = jobs_p.add_subparsers(dest="neighboros_jobs_cmd")

    add_p = jcmds.add_parser("add", help="request a new service job")
    add_p.add_argument("--title", required=True, help="job title")
    add_p.add_argument("--category", default="", help="service category")
    add_p.add_argument(
        "--priority",
        default="normal",
        choices=list(PRIORITIES),
        help="priority (default: normal)",
    )
    add_p.add_argument("--customer", default="", help="customer name")
    add_p.add_argument("--due", default="", help="due date YYYY-MM-DD")

    list_p = jcmds.add_parser("list", help="list jobs")
    list_p.add_argument(
        "--status", default=None, choices=list(STATUSES), help="filter by status"
    )
    list_p.add_argument("--category", default=None, help="filter by category")

    show_p = jcmds.add_parser("show", help="show one job with notes")
    show_p.add_argument("id", type=int, help="job id")

    assign_p = jcmds.add_parser("assign", help="dispatch: assign a worker")
    assign_p.add_argument("id", type=int, help="job id")
    assign_p.add_argument("--worker", required=True, help="worker name")

    move_p = jcmds.add_parser("move", help="move a job to a new status")
    move_p.add_argument("id", type=int, help="job id")
    move_p.add_argument("status", choices=list(STATUSES), help="new status")

    note_p = jcmds.add_parser("note", help="append a note to a job")
    note_p.add_argument("id", type=int, help="job id")
    note_p.add_argument("text", help="note text")

    upd_p = jcmds.add_parser("update", help="update a job's fields")
    upd_p.add_argument("id", type=int, help="job id")
    upd_p.add_argument("--title", default=None)
    upd_p.add_argument("--category", default=None)
    upd_p.add_argument("--priority", default=None, choices=list(PRIORITIES))
    upd_p.add_argument("--customer", default=None)
    upd_p.add_argument("--due", default=None, help="due date YYYY-MM-DD")

    # -- workers ---------------------------------------------------------
    workers_p = cmds.add_parser("workers", help="worker roster")
    wcmds = workers_p.add_subparsers(dest="neighboros_workers_cmd")

    wadd_p = wcmds.add_parser("add", help="add a worker")
    wadd_p.add_argument("--name", required=True, help="worker name")
    wadd_p.add_argument(
        "--categories",
        required=True,
        help="comma-separated categories "
        f"(e.g. {', '.join(KNOWN_CATEGORIES[:4])})",
    )

    wlist_p = wcmds.add_parser("list", help="list workers")
    wlist_p.add_argument(
        "--status",
        default=None,
        choices=list(WORKER_STATUSES),
        help="filter by status",
    )

    wact_p = wcmds.add_parser("activate", help="mark a worker active")
    wact_p.add_argument("id", type=int, help="worker id")
    wdeact_p = wcmds.add_parser("deactivate", help="mark a worker inactive")
    wdeact_p.add_argument("id", type=int, help="worker id")

    # -- brief / stats ---------------------------------------------------
    brief_p = cmds.add_parser(
        "brief", help="generate the founder's daily operations brief"
    )
    brief_p.add_argument(
        "--date",
        default=None,
        help="brief date YYYY-MM-DD (default: today)",
    )

    cmds.add_parser("stats", help="queue + roster counts")


def _fmt_job(job) -> str:
    line = f"[{job.id}] {job.title}"
    if job.category:
        line += f" [{job.category}]"
    if job.priority != "normal":
        line += f" ({job.priority})"
    line += f" — {job.status}"
    if job.worker:
        line += f" · worker: {job.worker}"
    if job.customer:
        line += f" · customer: {job.customer}"
    if job.due:
        line += f" · due {job.due}"
    return line


def _cmd_jobs(tracker: NeighborTracker, args: argparse.Namespace) -> int:
    cmd = getattr(args, "neighboros_jobs_cmd", None) or "list"

    if cmd == "add":
        try:
            job = tracker.add_job(
                title=args.title,
                category=args.category or "",
                priority=args.priority,
                customer=args.customer or "",
                due=args.due or "",
            )
        except ValueError as exc:
            print(f"neighboros jobs add failed: {exc}")
            return 2
        print(_fmt_job(job))
        return 0

    if cmd == "list":
        try:
            jobs = tracker.list_jobs(status=args.status, category=args.category)
        except ValueError as exc:
            print(f"neighboros jobs list failed: {exc}")
            return 2
        if not jobs:
            print("no jobs tracked")
            return 0
        for job in jobs:
            print(_fmt_job(job))
        return 0

    if cmd == "show":
        try:
            job = tracker.get_job(args.id)
        except (ValueError, KeyError) as exc:
            print(f"neighboros jobs show failed: {exc}")
            return 2
        print(_fmt_job(job))
        print(f"    created: {job.created_at}    updated: {job.updated_at}")
        if job.notes:
            print("    notes:")
            for n in job.notes:
                print(f"      [{n.ts}] {n.text}")
        return 0

    if cmd == "assign":
        try:
            job = tracker.assign_job(args.id, args.worker)
        except (ValueError, KeyError) as exc:
            print(f"neighboros jobs assign failed: {exc}")
            return 2
        print(f"[{job.id}] {job.title} → {job.worker} ({job.status})")
        return 0

    if cmd == "move":
        try:
            job = tracker.move_job(args.id, args.status)
        except (ValueError, KeyError) as exc:
            print(f"neighboros jobs move failed: {exc}")
            return 2
        print(f"[{job.id}] {job.title} → {job.status}")
        return 0

    if cmd == "note":
        try:
            note = tracker.note_job(args.id, args.text)
        except (ValueError, KeyError) as exc:
            print(f"neighboros jobs note failed: {exc}")
            return 2
        print(f"note added to job {args.id} @ {note.ts}")
        return 0

    if cmd == "update":
        try:
            job = tracker.update_job(
                args.id,
                title=args.title,
                category=args.category,
                priority=args.priority,
                customer=args.customer,
                due=args.due,
            )
        except (ValueError, KeyError) as exc:
            print(f"neighboros jobs update failed: {exc}")
            return 2
        print(_fmt_job(job))
        return 0

    print(f"unknown neighboros jobs command: {cmd}")
    return 2


def _cmd_workers(tracker: NeighborTracker, args: argparse.Namespace) -> int:
    cmd = getattr(args, "neighboros_workers_cmd", None) or "list"

    if cmd == "add":
        cats = [c.strip() for c in (args.categories or "").split(",")]
        cats = [c for c in cats if c]
        try:
            worker = tracker.add_worker(name=args.name, categories=cats)
        except ValueError as exc:
            print(f"neighboros workers add failed: {exc}")
            return 2
        print(
            f"[{worker.id}] {worker.name} — {worker.status} "
            f"({', '.join(worker.categories) or 'no categories'})"
        )
        return 0

    if cmd == "list":
        try:
            workers = tracker.list_workers(status=args.status)
        except ValueError as exc:
            print(f"neighboros workers list failed: {exc}")
            return 2
        if not workers:
            print("no workers tracked")
            return 0
        for w in workers:
            print(
                f"[{w.id}] {w.name} — {w.status} "
                f"({', '.join(w.categories) or 'no categories'})"
            )
        return 0

    if cmd in ("activate", "deactivate"):
        status = "active" if cmd == "activate" else "inactive"
        try:
            worker = tracker.set_worker_status(args.id, status)
        except (ValueError, KeyError) as exc:
            print(f"neighboros workers {cmd} failed: {exc}")
            return 2
        print(f"[{worker.id}] {worker.name} → {worker.status}")
        return 0

    print(f"unknown neighboros workers command: {cmd}")
    return 2


def cmd_neighboros(args: argparse.Namespace) -> int:
    tracker = NeighborTracker()
    cmd = getattr(args, "neighboros_cmd", None) or "stats"

    if cmd == "jobs":
        return _cmd_jobs(tracker, args)

    if cmd == "workers":
        return _cmd_workers(tracker, args)

    if cmd == "brief":
        try:
            text, path = generate_brief(tracker, brief_date=args.date)
        except (ValueError, OSError) as exc:
            print(f"neighboros brief failed: {exc}")
            return 2
        print(text)
        print(f"[brief written to {path}]")
        return 0

    if cmd == "stats":
        s = tracker.stats()
        print(f"jobs: {s['jobs_open']} open of {s['jobs_total']} tracked")
        for status, count in s["jobs_by_status"].items():
            if count:
                print(f"  {status}: {count}")
        print(
            f"workers: {s['workers_active']} active of {s['workers_total']}"
        )
        return 0

    print(f"unknown neighboros command: {cmd}")
    return 2
