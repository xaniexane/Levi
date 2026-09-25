"""``python -m levi.snapshots`` — context snapshot CLI.

Local only: reads/writes under the LEVI home (``LEVI_HOME`` or
``~/.levi``).

Commands:
    capture NAME [--repo DIR] [--focus F] [--mode M] [--note ...]
    resume  NAME
    list
    drop    NAME
    focus   [TEXT]          # set / show the persisted current focus
"""

from __future__ import annotations

import argparse
import sys

from .store import SnapshotStore, resume_brief


def _build() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="levi.snapshots", description=__doc__.splitlines()[0]
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    cap = sub.add_parser("capture", help="capture working state into a snapshot")
    cap.add_argument("name")
    cap.add_argument("--repo", default=None, help="repo dir to summarize")
    cap.add_argument("--focus", default=None, help="active focus text")
    cap.add_argument("--mode", default=None, help="active mode (e.g. build, review)")
    cap.add_argument(
        "--note", action="append", default=[], help="capture note (repeatable)"
    )

    rs = sub.add_parser("resume", help="render the resume brief for a snapshot")
    rs.add_argument("name")

    sub.add_parser("list", help="list snapshots")

    dp = sub.add_parser("drop", help="delete a snapshot")
    dp.add_argument("name")

    fc = sub.add_parser("focus", help="set or show the persisted current focus")
    fc.add_argument("text", nargs="?", default=None)
    return p


def main(argv=None) -> int:
    args = _build().parse_args(argv)
    store = SnapshotStore()
    if args.cmd == "capture":
        snap = store.capture(
            args.name,
            repo_dir=args.repo,
            focus=args.focus,
            mode=args.mode,
            notes=args.note,
        )
        print(f"captured snapshot '{args.name}' at {snap['captured_at']}")
    elif args.cmd == "resume":
        try:
            print(resume_brief(store.resume(args.name)))
        except KeyError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    elif args.cmd == "list":
        rows = store.list_snapshots()
        if not rows:
            print("no snapshots")
        for r in rows:
            print(f"{r['name']}  (captured {r['captured_at']})")
    elif args.cmd == "drop":
        print("dropped" if store.drop(args.name) else "no such snapshot")
    elif args.cmd == "focus":
        if args.text is None:
            focus_doc = store.root / "current_focus.json"
            if focus_doc.exists():
                import json

                print(json.loads(focus_doc.read_text())["focus"])
            else:
                print("no focus set")
        else:
            store.set_focus(args.text)
            print(f"focus set: {args.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
