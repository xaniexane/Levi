"""``levi omega`` CLI: the Omega platform's front door.

* ``levi omega gen-automation --spec JSON`` — generate automation-minion
  dicts from a declarative spec (``--spec @path`` reads a file). Prints
  the generated minions as JSON; exit 1 with the refusal reasons on an
  invalid spec.
* ``levi omega gen-skill --name X --capability Y`` — generate a LEVI
  skill scaffold; prints a human preview by default, ``--json`` dumps
  the ``{path: content}`` files map.
* ``levi omega materialize --plan JSON --dest DIR [--live] [--overwrite]``
  — dry-run by default: shows ``preview()`` plus the ``plan()`` table.
  ``--live`` lays the files down (approve gate); ``--overwrite`` allows
  replacing existing files. ``--plan`` accepts a files map or a plan
  dict; ``--plan @path`` reads a file.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict

from . import automation_gen, materialize, skill_gen

__all__ = ["register_omega_parser", "cmd_omega"]


def _read_maybe_file(text: str) -> str:
    if text.startswith("@"):
        with open(text[1:], "r", encoding="utf-8") as fh:
            return fh.read()
    return text


def _load_json(text: str, what: str) -> Any:
    try:
        return json.loads(_read_maybe_file(text))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{what} is not valid JSON: {exc}") from exc


def register_omega_parser(sub) -> None:
    op = sub.add_parser(
        "omega", help="Omega platform revival: generators + materializer"
    )
    cmds = op.add_subparsers(dest="omega_cmd")

    ga = cmds.add_parser(
        "gen-automation", help="generate automation-minion dicts from a spec"
    )
    ga.add_argument(
        "--spec",
        required=True,
        help="JSON spec (or @path to a JSON file)",
    )

    gs = cmds.add_parser("gen-skill", help="generate a LEVI skill scaffold")
    gs.add_argument("--name", required=True, help="skill slug")
    gs.add_argument("--capability", required=True, help="declared capability")
    gs.add_argument("--json", action="store_true", help="dump the files map as JSON")

    mz = cmds.add_parser(
        "materialize", help="preview/plan or live-write generated artifacts"
    )
    mz.add_argument(
        "--plan",
        required=True,
        help="JSON files-map or plan dict (or @path to a JSON file)",
    )
    mz.add_argument("--dest", required=True, help="destination directory")
    mz.add_argument(
        "--live",
        action="store_true",
        help="actually write (default is dry-run preview + plan)",
    )
    mz.add_argument(
        "--overwrite",
        action="store_true",
        help="allow replacing existing files (live only)",
    )


def _cmd_gen_automation(args: argparse.Namespace) -> int:
    spec = _load_json(args.spec, "spec")
    try:
        minions = automation_gen.generate_minions(spec)
    except ValueError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "minions": minions}, indent=2))
    return 0


def _cmd_gen_skill(args: argparse.Namespace) -> int:
    result = skill_gen.scaffold_skill(args.name, args.capability)
    if not result["ok"]:
        print("refused:", file=sys.stderr)
        for err in result["errors"]:
            print(f"  - {err}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result["files"], indent=2))
    else:
        print(materialize.preview(result["files"], max_lines=12))
        print(f"scaffold files: {sorted(result['files'])}")
    return 0


def _cmd_materialize(args: argparse.Namespace) -> int:
    payload = _load_json(args.plan, "plan")
    if not args.live:
        files: Dict[str, str] = (
            payload["files"]
            if isinstance(payload, dict) and isinstance(payload.get("entries"), list)
            else payload
        )
        print(materialize.preview(files))
        print("plan:")
        for entry in materialize.plan(files, args.dest)["entries"]:
            print(f"  [{entry['action']}] {entry['path']} — {entry['reason']}")
        print("\nDry run only. Re-run with --live to lay the files down.")
        return 0
    receipt = materialize.write(
        payload, args.dest, approve=True, overwrite=args.overwrite
    )
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["verified"] else 2


def cmd_omega(args: argparse.Namespace) -> int:
    """Dispatch ``levi omega <cmd>``; returns a process exit code."""
    cmd = getattr(args, "omega_cmd", None)
    try:
        if cmd == "gen-automation":
            return _cmd_gen_automation(args)
        if cmd == "gen-skill":
            return _cmd_gen_skill(args)
        if cmd == "materialize":
            return _cmd_materialize(args)
    except (ValueError, PermissionError, OSError) as exc:
        print(f"omega: {exc}", file=sys.stderr)
        return 1
    print("omega: choose gen-automation | gen-skill | materialize", file=sys.stderr)
    return 1
