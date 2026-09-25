"""``levi omega`` CLI: the Omega platform's front door.

* ``levi omega gen-automation --spec JSON`` — generate automation-minion
  dicts from a declarative spec (``--spec @path`` reads a file). Prints
  the generated minions as JSON; exit 1 with the refusal reasons on an
  invalid spec.
* ``levi omega gen-skill --name X --capability Y`` — generate a LEVI
  skill scaffold; prints a human preview by default, ``--json`` dumps
  the ``{path: content}`` files map.
* ``levi omega route --task TEXT [--mode MODE] [--kinds chat,code]
  [--needs-local] [--providers JSON]`` — Alpha reasons over the task,
  Omega routes over providers (built-in demo fleet unless --providers
  JSON is given): prints the verdict, the answer, the ranked routes, the
  top provider, caveats, substrate, and honest limits. Refuses empty
  tasks.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

from . import automation_gen, materialize, reasoning, skill_gen
from .nexus import MODES, Provider, SOURCE_CLOUD, SOURCE_LOCAL, SOURCE_REFERENCE

__all__ = ["register_omega_parser", "cmd_omega"]

# The built-in demo fleet for ``levi omega route`` — representative
# lawful providers plus one reference, so the sourcing law is visible in
# the output. Qualities are operator-assessed, never asserted as fact.
_DEMO_FLEET: List[Provider] = [
    Provider(
        name="levi-local",
        source=SOURCE_LOCAL,
        kinds=frozenset({"chat", "code"}),
        cost=1,
        quality=0.6,
    ),
    Provider(
        name="levi-si-cloud",
        source=SOURCE_CLOUD,
        kinds=frozenset({"chat", "code", "vision"}),
        cost=4,
        quality=0.9,
    ),
    Provider(
        name="reference-model",
        source=SOURCE_REFERENCE,
        kinds=frozenset({"chat", "code", "vision"}),
        cost=1,
        quality=1.0,
    ),
]


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

    rt = cmds.add_parser(
        "route",
        help="Alpha reasons over a task, Omega routes it over providers",
    )
    rt.add_argument(
        "--task", required=True, help="the task text to deliberate and route"
    )
    rt.add_argument(
        "--mode",
        default="balanced",
        choices=sorted(MODES),
        help="Nexus routing mode (default: balanced)",
    )
    rt.add_argument(
        "--kinds",
        default="chat",
        help="comma-separated task kinds (default: chat; none are inferred from prose)",
    )
    rt.add_argument(
        "--needs-local",
        action="store_true",
        help="require LEVI-local providers only",
    )
    rt.add_argument(
        "--providers",
        default=None,
        help="JSON list of provider dicts (or @path); defaults to the built-in demo fleet",
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


def _cmd_route(args: argparse.Namespace) -> int:
    providers: List[Provider] = _DEMO_FLEET
    if args.providers is not None:
        raw = _load_json(args.providers, "providers")
        if not isinstance(raw, list) or not raw:
            print("omega: providers must be a non-empty JSON list", file=sys.stderr)
            return 1
        try:
            providers = [
                Provider(
                    name=str(p["name"]),
                    source=str(p.get("source", SOURCE_REFERENCE)),
                    kinds=frozenset(p.get("kinds", ())),
                    cost=int(p.get("cost", 5)),
                    quality=float(p.get("quality", 0.5)),
                )
                for p in raw
            ]
        except (ValueError, TypeError, KeyError) as exc:
            print(f"omega: bad provider entry: {exc}", file=sys.stderr)
            return 1
    kinds = frozenset(k.strip() for k in (args.kinds or "").split(",") if k.strip())
    try:
        plan = reasoning.reason_route(
            args.task,
            providers,
            mode=args.mode,
            kinds=kinds or None,
            needs_local=args.needs_local,
        )
    except (ValueError, RuntimeError) as exc:
        print(f"omega: refused: {exc}", file=sys.stderr)
        return 1
    print(reasoning.explain_plan(plan))
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
        if cmd == "route":
            return _cmd_route(args)
    except (ValueError, PermissionError, OSError) as exc:
        print(f"omega: {exc}", file=sys.stderr)
        return 1
    print(
        "omega: choose gen-automation | gen-skill | materialize | route",
        file=sys.stderr,
    )
    return 1
