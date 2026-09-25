"""``levi surgeon`` CLI: snapshots, cleanup, advancement proposals, sandbox gate.

Local-only code-surgery helpers. Nothing here executes code; the sandbox
``apply`` path requires an explicit ``--confirm`` human confirmation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .surgeon import (
    SnapshotManager,
    cleanup_code,
    propose_advancements,
)


def register_surgeon_parser(sub) -> None:
    sg = sub.add_parser("surgeon", help="Code surgery: snapshots, cleanup, proposals")
    cmds = sg.add_subparsers(dest="surgeon_cmd")

    snap_p = cmds.add_parser("snapshot", help="snapshot / list / revert code text")
    snap_p.add_argument("action", choices=["take", "list", "revert"])
    snap_p.add_argument("--label", default="snap", help="snapshot label")
    snap_p.add_argument("--file", default=None, help="read code from file")
    snap_p.add_argument("--id", default=None, help="snapshot id (for revert)")

    clean_p = cmds.add_parser("cleanup", help="normalize code text")
    clean_p.add_argument("--file", required=True, help="file to clean (prints result)")

    prop_p = cmds.add_parser("propose", help="propose advancements for code")
    prop_p.add_argument("--file", required=True, help="file to analyze")

    cmds.add_parser("gate", help="explain the sandbox HITL gate")


def cmd_surgeon(args: argparse.Namespace) -> int:
    cmd = getattr(args, "surgeon_cmd", None) or "gate"
    mgr = SnapshotManager()

    if cmd == "snapshot":
        action = args.action
        if action == "take":
            code = Path(args.file).read_text(encoding="utf-8") if args.file else ""
            snap_id = mgr.take(args.label, code)
            print(f"snapshot {snap_id} ({len(code)} chars)")
        elif action == "list":
            for s in mgr.list():
                print(f"{s['id']}  {s['label']}")
        else:
            code = mgr.revert(args.id or "")
            if code is None:
                print(f"unknown snapshot {args.id!r}")
                return 1
            print(code, end="" if code.endswith("\n") else "\n")
        return 0

    if cmd == "cleanup":
        text = Path(args.file).read_text(encoding="utf-8")
        cleaned, fixes = cleanup_code(text)
        print(f"fixes: {fixes}")
        print(cleaned, end="" if cleaned.endswith("\n") else "\n")
        return 0

    if cmd == "propose":
        text = Path(args.file).read_text(encoding="utf-8")
        for a in propose_advancements(text, args.file):
            print(f"{a.id} [{a.risk}] {a.title} — {a.description}")
        return 0

    # gate
    print(
        "Surgeon sandbox gate: propose → analyze → HITL → apply.\n"
        "Nothing executes code. `SandboxGate.apply` needs a clean analysis\n"
        "report AND explicit human confirmation. Demos:\n"
        "  gate = SandboxGate(); rep = gate.analyze(old, new)\n"
        "  gate.apply(new, rep, Path('out.py'), confirmed=True)  # human said yes"
    )
    return 0
