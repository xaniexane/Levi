"""CLI for the universe architecture: the park's map, door, star, and groupings.

Thin hook; the real work lives in the universe package. Registered from
core/levi/cli/main.py via register_universe_parser(sub) and dispatched
as cmd_universe — the same minimal-hook pattern as the other modules.

- ``levi universe map`` — print the canon -> module map.
- ``levi universe enter --task ... [--mode] [--kinds a,b] [--needs-local]``
  — admit one task through the entrance (Omega platform, Alpha builder).
- ``levi universe star`` — show the star: the role and its sealed filling.
- ``levi universe groupings [list]`` — the forms, the sealed law, proposals.
- ``levi universe propose-grouping --name X --form hive [--essence ...] [--domain ...] [--by ...]``
  — propose a grouping. Proposed only — never canon; only Chauncey's word
  declares one, and this CLI offers no declare path.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import PARK_MAP, entrance, groupings, star

__all__ = ["register_universe_parser", "cmd_universe"]


def _home() -> Path:
    base = os.environ.get("LEVI_HOME") or str(Path.home() / ".levi")
    return Path(base).expanduser()


def _registry() -> groupings.GroupingRegistry:
    d = _home() / "universe"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    reg = groupings.GroupingRegistry(d / "groupings.jsonl")
    return reg


def _save_registry(reg: groupings.GroupingRegistry) -> None:
    p = reg.save()
    os.chmod(p, 0o600)


# ---------------------------------------------------------------------------
# parser registration (the minimal hook in main.py)
# ---------------------------------------------------------------------------


def register_universe_parser(sub) -> None:
    uv = sub.add_parser(
        "universe",
        help="the universe architecture: map, entrance, star, groupings",
    )
    cmds = uv.add_subparsers(dest="universe_cmd")

    mp = cmds.add_parser("map", help="print the canon -> module map of the park")
    mp.set_defaults()

    en = cmds.add_parser(
        "enter", help="admit one task through the entrance (Omega platform)"
    )
    en.add_argument("--task", required=True, help="the task to admit")
    en.add_argument(
        "--mode",
        default="balanced",
        choices=["fast", "balanced", "deep", "offline"],
        help="Omega routing mode",
    )
    en.add_argument(
        "--kinds",
        default="",
        help="comma-separated routing kinds (explicit facts only)",
    )
    en.add_argument("--needs-local", action="store_true", help="deny remote providers")

    cmds.add_parser("star", help="show the star: the role and its sealed filling")

    cmds.add_parser(
        "groupings", help="list the grouping forms, the sealed law, and proposals"
    )

    pg = cmds.add_parser(
        "propose-grouping",
        help="propose a Legion grouping (proposed only — never canon)",
    )
    pg.add_argument("--name", required=True, help="the proposer's grouping name")
    pg.add_argument(
        "--form",
        required=True,
        choices=list(groupings.GROUPING_FORMS),
        help="the mass-grouping form",
    )
    pg.add_argument(
        "--essence", default="", help="the grouping's essence (essences only)"
    )
    pg.add_argument("--domain", default="", help="the grouping's domain")
    pg.add_argument("--by", default="", dest="proposed_by", help="who proposes it")


# ---------------------------------------------------------------------------
# command
# ---------------------------------------------------------------------------


def cmd_universe(args) -> int:
    cmd = getattr(args, "universe_cmd", None)
    if cmd == "map":
        print("the park — canon -> module map (docs/LEXICON.md, 'The ultimate goal'):")
        for node, module in PARK_MAP.items():
            print(f"  {node:10} -> {module}")
        return 0

    if cmd == "enter":
        kinds = (
            frozenset(k.strip() for k in args.kinds.split(",") if k.strip())
            if args.kinds
            else None
        )
        try:
            session = entrance.enter(
                args.task,
                mode=args.mode,
                kinds=kinds,
                needs_local=args.needs_local,
            )
        except entrance.EntranceError as exc:
            print(f"universe: refused: {exc}")
            return 1
        s = session.summary()
        print(f"admitted through: {s['entrance']} (built by {s['built_by']})")
        print(f"task type: {s['task_type']}  |  mode: {s['mode']}")
        print(f"verdict: {s['verdict_choice']} ({s['verdict_confidence']})")
        print(f"answer: {s['answer']}")
        print(f"substrate: {s['substrate']}")
        print(f"limits: {s['limits']}")
        print("routing:")
        for r in s["routes"]:
            mark = "[OK]" if r["eligible"] else "[SKIP]"
            print(f"  {mark} {r['provider']} conf={r['confidence']}")
            for reason in r["reasons"]:
                print(f"       - {reason}")
        print(f"top provider: {s['top_provider']}")
        if s["caveats"]:
            print("caveats:")
            for c in s["caveats"]:
                print(f"  ! {c}")
        if s["brain_voice"] is not None:
            # The evidence trail, labeled verbatim: what the brain said is
            # reported exactly; it was heard in deliberation, never obeyed
            # in the verdict. Quoted with !r so it reads as quoted speech —
            # the same convention as reasoning.explain_plan.
            print("brain-voice (heard, never obeyed):")
            print(f"  raw continuation, not reasoning: {s['brain_voice']!r}")
        return 0

    if cmd == "star":
        print(json.dumps(star.current_star().describe(), indent=2))
        return 0

    if cmd == "groupings":
        print(json.dumps(_registry().describe(), indent=2))
        return 0

    if cmd == "propose-grouping":
        reg = _registry()
        try:
            g = reg.propose(
                name=args.name,
                form=args.form,
                essence=args.essence,
                domain=args.domain,
                proposed_by=args.proposed_by,
            )
        except groupings.GroupingError as exc:
            print(f"universe: refused: {exc}")
            return 1
        _save_registry(reg)
        print(json.dumps(g.to_dict(), indent=2))
        print("recorded as PROPOSED — not canon. Only Chauncey's word declares one.")
        return 0

    print("universe: map | enter | star | groupings | propose-grouping")
    return 1
