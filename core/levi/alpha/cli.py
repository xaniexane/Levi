"""``levi alpha`` CLI: the SI team's first mind, on demand.

* ``levi alpha reason <task...>`` — deliberate over the task and print
  the verdict: chosen stance, the answer, which substrate reasoned, and
  the honest limits. Refuses empty tasks.
* ``levi alpha substrate`` — print the substrate report (what would
  reason, and the native-brain weights' probed status) as JSON.
"""

from __future__ import annotations

import argparse
import json

from . import ALPHA_ROLE, probe_alpha

__all__ = ["register_alpha_parser", "cmd_alpha", "ALPHA_ROLE"]


def register_alpha_parser(sub) -> None:
    ap = sub.add_parser(
        "alpha",
        help="Alpha: the SI team's first mind — reasoning (propose/critique/verdict)",
    )
    cmds = ap.add_subparsers(dest="alpha_cmd")

    r = cmds.add_parser("reason", help="deliberate over a task")
    r.add_argument("task", nargs="+", help="the task to reason about")

    cmds.add_parser("substrate", help="show the substrate report as JSON")


def _require_reasoner():
    reasoner = probe_alpha()
    if reasoner is None:
        raise RuntimeError("alpha is unavailable in this build")
    return reasoner


def cmd_alpha(args: argparse.Namespace) -> int:
    """Dispatch ``levi alpha <cmd>``; returns a process exit code."""
    cmd = getattr(args, "alpha_cmd", None)
    if cmd == "substrate":
        print(json.dumps(_require_reasoner().substrate_report(), indent=2))
        return 0
    if cmd == "reason":
        task = " ".join(args.task or []).strip()
        try:
            result = _require_reasoner().reason(task)
        except ValueError as exc:
            print(f"alpha: refused: {exc}")
            return 1
        v = result["verdict"]
        print(f"verdict: {v['chosen']} (score {v['score']})")
        print()
        print(v["answer"])
        print()
        print(f"survived: {v['survived_weakness']}")
        print(f"open question: {v['open_question']}")
        print(f"substrate: {result['substrate']}")
        print(f"limits: {result['limits']}")
        return 0
    print("alpha: choose reason | substrate")
    return 1
