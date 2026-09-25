"""CLI for the Agent Workshop.

Thin hook; the real work lives in the workshop package. Registered from
core/levi/cli/main.py via register_workshop_parser(sub) and dispatched
as cmd_workshop — the same minimal-hook pattern as the other modules.
"""

from __future__ import annotations

import json
from typing import Optional

from .blueprint import (
    compose_blueprint,
    list_blueprints,
    load_blueprint,
    save_blueprint,
)
from .dryrun import dry_run
from .inventory import inventory
from .validate import ValidationError, validate_blueprint


def register_workshop_parser(sub) -> None:
    ws = sub.add_parser(
        "workshop",
        help="Agent Workshop: inventory parts, compose/validate/dry-run blueprints",
    )
    cmd = ws.add_subparsers(dest="workshop_cmd")

    cmd.add_parser(
        "inventory",
        help="list the real parts (agents, specialists, substrates, organs, "
        "Legion roles, nanobit, the eleven originals)",
    )

    comp = cmd.add_parser("compose", help="compose a deterministic blueprint")
    comp.add_argument("--name", required=True, help="blueprint name")
    comp.add_argument("--agent", required=True, help="agent id from the registry")
    comp.add_argument("--specialist", required=True, help="specialist id")
    comp.add_argument("--substrate", required=True, help="mind substrate id")
    comp.add_argument("--organ", required=True, help="organ name")
    comp.add_argument("--role", required=True, help="Legion crew role")
    comp.add_argument(
        "--nanobit",
        default="",
        help="nanobit format (optional; the canonical micro-companion format)",
    )
    comp.add_argument(
        "--original",
        default="",
        help="original lineage (optional; one of the eleven originals)",
    )
    comp.add_argument(
        "--claim",
        action="append",
        default=[],
        help="capability/semantic claim (repeatable)",
    )
    comp.add_argument(
        "--twin-note", default="", help="free-text twin note (no semantics attached)"
    )
    comp.add_argument(
        "--auth", action="append", default=[], help="authorized substrate (repeatable)"
    )
    comp.add_argument(
        "--save", action="store_true", help="save the blueprint after composing"
    )

    val = cmd.add_parser("validate", help="fail-closed validation of a blueprint")
    val.add_argument("--name", required=True, help="saved blueprint name")
    val.add_argument(
        "--auth", action="append", default=[], help="authorized substrate (repeatable)"
    )

    dry = cmd.add_parser(
        "dry-run", help="local-only simulated assembly (honestly labeled)"
    )
    dry.add_argument("--name", required=True, help="saved blueprint name")
    dry.add_argument(
        "--auth", action="append", default=[], help="authorized substrate (repeatable)"
    )

    cmd.add_parser("save", help="save is done via: compose --save")
    cmd.add_parser("list", help="list saved blueprints")
    ld = cmd.add_parser("load", help="load and show a saved blueprint")
    ld.add_argument("--name", required=True, help="saved blueprint name")


def cmd_workshop(args) -> Optional[int]:
    """Agent Workshop commands."""
    cmd = getattr(args, "workshop_cmd", None) or "inventory"
    if cmd == "inventory":
        return _cmd_inventory(args)
    if cmd == "compose":
        return _cmd_compose(args)
    if cmd == "validate":
        return _cmd_validate(args)
    if cmd == "dry-run":
        return _cmd_dry_run(args)
    if cmd == "list":
        names = list_blueprints()
        print("\n".join(names) if names else "(no saved blueprints)")
        return 0
    if cmd == "load":
        try:
            bp = load_blueprint(args.name)
        except (FileNotFoundError, ValueError) as exc:
            print(f"load refused: {exc}")
            return 1
        print(json.dumps(bp.to_dict(), indent=2, sort_keys=True))
        return 0
    print(f"unknown workshop command: {cmd}")
    return 1


def _cmd_inventory(args) -> int:
    inv = inventory()
    print(json.dumps(inv["counts"], indent=2, sort_keys=True))
    for section in (
        "agents",
        "specialists",
        "substrates",
        "organs",
        "legion_roles",
        "nanobit",
        "originals",
    ):
        items = inv[section]
        key = {
            "agents": "agent_id",
            "specialists": "specialist_id",
            "substrates": "substrate_id",
            "organs": "name",
            "legion_roles": "role",
            "nanobit": "id",
            "originals": "id",
        }[section]
        ids = [i[key] for i in items]
        shown = ", ".join(ids[:12]) + (" ..." if len(ids) > 12 else "")
        print(f"{section} ({len(ids)}): {shown}")
    return 0


def _cmd_compose(args) -> int:
    bp = compose_blueprint(
        name=args.name,
        agent=args.agent,
        specialist=args.specialist,
        substrate=args.substrate,
        organ=args.organ,
        legion_role=args.role,
        nanobit=args.nanobit,
        original=args.original,
        claims=args.claim,
        twin_note=args.twin_note,
    )
    try:
        checks = validate_blueprint(bp, set(args.auth))
    except ValidationError as exc:
        print(f"compose refused: {exc}")
        return 1
    for c in checks:
        print("ok:", c)
    print("fingerprint:", bp.fingerprint)
    if args.save:
        path = save_blueprint(bp)
        print("saved:", path)
    return 0


def _cmd_validate(args) -> int:
    try:
        bp = load_blueprint(args.name)
    except (FileNotFoundError, ValueError) as exc:
        print(f"validate refused: {exc}")
        return 1
    try:
        checks = validate_blueprint(bp, set(args.auth))
    except ValidationError as exc:
        print(f"validate refused: {exc}")
        return 1
    for c in checks:
        print("ok:", c)
    return 0


def _cmd_dry_run(args) -> int:
    try:
        bp = load_blueprint(args.name)
    except (FileNotFoundError, ValueError) as exc:
        print(f"dry-run refused: {exc}")
        return 1
    try:
        report = dry_run(bp, set(args.auth))
    except ValidationError as exc:
        print(f"dry-run refused: {exc}")
        return 1
    print(report["label"])
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "label"},
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0
