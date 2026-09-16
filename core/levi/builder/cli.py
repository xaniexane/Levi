"""``levi build`` CLI: autonomous multi-agent app builder.

``levi build "<description>" [--stack static|fullstack] [--name NAME]
[--out-dir DIR] [--export] [--quality auto|council|static|off]
[--preview] [--yes]``

Safety: ``--preview`` prints the plan and changes nothing. Without
``--yes``, the plan is printed and the user is asked for explicit
confirmation before anything is written (Plan → Preview → Permission →
Execute → Verify → Receipt).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import plan_preview, run_build
from .scaffolds import list_scaffolds


def register_builder_parser(sub) -> None:
    p = sub.add_parser(
        "build",
        help="autonomous multi-agent app builder: description in, runnable app out",
    )
    p.add_argument(
        "description", help="natural-language description of the app to build"
    )
    p.add_argument(
        "--stack",
        choices=list_scaffolds(),
        default="fullstack",
        help="project stack (default: fullstack)",
    )
    p.add_argument(
        "--name", default=None, help="project name (default: slugged from description)"
    )
    p.add_argument(
        "--out-dir",
        default=None,
        help="parent directory for the project (default: ~/.levi/builds)",
    )
    p.add_argument(
        "--export",
        action="store_true",
        help="also produce a one-command export tarball",
    )
    p.add_argument(
        "--quality",
        choices=["auto", "council", "static", "off"],
        default="auto",
        help="code quality gates (default: auto — council when available, else static)",
    )
    p.add_argument(
        "--preview",
        action="store_true",
        help="print the build plan and exit without writing anything",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="skip the confirmation prompt (the command itself is permission)",
    )


def cmd_build(args: argparse.Namespace) -> int:
    description = args.description
    stack = args.stack
    name = args.name or _slugify(description)

    if args.preview:
        print(plan_preview(description, stack, name))
        print("\n(preview only — nothing was written)")
        return 0

    print(plan_preview(description, stack, name))
    if not args.yes and sys.stdin.isatty():
        try:
            answer = input("\nProceed with this build? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\naborted.")
            return 2
        if answer not in ("y", "yes"):
            print("aborted — nothing was written.")
            return 2

    out_dir = Path(args.out_dir).expanduser() if args.out_dir else None
    report = run_build(
        description,
        stack=stack,
        name=name,
        out_dir=out_dir,
        quality=args.quality,
        export=args.export,
    )
    print()
    print(report.summary())
    return 0 if report.ok else 2


def _slugify(text: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:40] or "app"
