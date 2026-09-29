"""CLI for levi.tasklist: ``python -m levi.tasklist --help``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from levi.tasklist import PRIORITIES, TaskError, TaskLists


def _fmt(task: dict) -> str:
    mark = "✓" if task["status"] == "done" else "○"
    due = f"  due {task['due']}" if task["due"] else ""
    done_steps = sum(1 for s in task["steps"] if s["done"])
    steps = f"  [{done_steps}/{len(task['steps'])} steps]" if task["steps"] else ""
    return f"{mark} [{task['priority']:>6}] {task['id']}  {task['title']}{due}{steps}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="levi.tasklist", description="Honest local task lists.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new", help="create a list"); p.add_argument("name")
    p = sub.add_parser("lists", help="list all lists")
    p = sub.add_parser("add", help="add a task")
    p.add_argument("list"); p.add_argument("title")
    p.add_argument("--notes", default=""); p.add_argument("--priority", default="normal",
                   choices=PRIORITIES); p.add_argument("--due", default=None)
    p.add_argument("--tag", action="append", default=[], dest="tags")
    p = sub.add_parser("show", help="show a task in full")
    p.add_argument("list"); p.add_argument("task_id")
    p = sub.add_parser("done", help="complete a task (receipt kept)")
    p.add_argument("list"); p.add_argument("task_id")
    p = sub.add_parser("reopen", help="reopen a completed task")
    p.add_argument("list"); p.add_argument("task_id")
    p = sub.add_parser("remove", help="remove a task (receipt kept)")
    p.add_argument("list"); p.add_argument("task_id")
    p = sub.add_parser("step", help="add a subtask step")
    p.add_argument("list"); p.add_argument("task_id"); p.add_argument("title")
    p = sub.add_parser("stepdone", help="toggle a step")
    p.add_argument("list"); p.add_argument("task_id"); p.add_argument("step_id")
    p.add_argument("--undo", action="store_true")
    p = sub.add_parser("open", help="open tasks"); p.add_argument("list")
    p = sub.add_parser("today", help="tasks due today"); p.add_argument("list")
    p = sub.add_parser("overdue", help="overdue open tasks"); p.add_argument("list")
    p = sub.add_parser("priority", help="open tasks, urgent first"); p.add_argument("list")
    p = sub.add_parser("search", help="search a list")
    p.add_argument("list"); p.add_argument("query")
    p = sub.add_parser("export", help="export a list to a portable share file")
    p.add_argument("list"); p.add_argument("dest")
    p = sub.add_parser("import", help="import a share file")
    p.add_argument("src")
    p = sub.add_parser("receipts", help="done/remove/reopen receipts")
    p.add_argument("--limit", type=int, default=None)

    args = ap.parse_args(argv)
    tl = TaskLists()
    try:
        if args.cmd == "new":
            tl.create_list(args.name); print(f"created {args.name!r}")
        elif args.cmd == "lists":
            for name in tl.lists(): print(name)
        elif args.cmd == "add":
            t = tl.add_task(args.list, args.title, notes=args.notes,
                            priority=args.priority, due=args.due, tags=args.tags)
            print(_fmt(t))
        elif args.cmd == "show":
            print(json.dumps(tl.get_task(args.list, args.task_id), indent=2))
        elif args.cmd == "done":
            tl.complete_task(args.list, args.task_id); print("completed (receipt kept)")
        elif args.cmd == "reopen":
            tl.reopen_task(args.list, args.task_id); print("reopened")
        elif args.cmd == "remove":
            tl.remove_task(args.list, args.task_id); print("removed (receipt kept)")
        elif args.cmd == "step":
            s = tl.add_step(args.list, args.task_id, args.title)
            print(f"step {s['id']}: {s['title']}")
        elif args.cmd == "stepdone":
            s = tl.set_step(args.list, args.task_id, args.step_id, not args.undo)
            print(("✓ " if s["done"] else "○ ") + s["title"])
        elif args.cmd == "open":
            for t in tl.open_tasks(args.list): print(_fmt(t))
        elif args.cmd == "today":
            for t in tl.due_today(args.list): print(_fmt(t))
        elif args.cmd == "overdue":
            for t in tl.overdue(args.list): print(_fmt(t))
        elif args.cmd == "priority":
            for t in tl.by_priority(args.list): print(_fmt(t))
        elif args.cmd == "search":
            for t in tl.search(args.list, args.query): print(_fmt(t))
        elif args.cmd == "export":
            print(tl.export_list(args.list, Path(args.dest)))
        elif args.cmd == "import":
            d = tl.import_list(Path(args.src)); print(f"imported {d['name']!r}")
        elif args.cmd == "receipts":
            for r in tl.receipts(args.limit):
                print(f"{r['at']}  {r['action']:>9}  {r['list']}: {r['task']['title']}")
    except TaskError as exc:
        print(f"error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
