"""``levi alpha`` CLI: the builder seat, on demand.

Canon: ALPHA is the builder — it builds things. "Omega powered by Alpha."

* ``levi alpha build "<intent>" [--tier E3|E4|E5|E6] [--name NAME]
  [--target independent|levi] [--apply] [--force]`` — route
  natural-language build intent into an E3-E6 tiered plan (plan-first),
  and optionally apply it under the tier's gates.
* ``levi alpha reason <task...>`` — deliberate over a build plan or
  decision and print the verdict: chosen stance, the answer, which
  substrate reasoned, and the honest limits. Refuses empty tasks.
* ``levi alpha substrate`` — print the substrate report (what would
  reason, and the native-brain weights' probed status) as JSON.
* ``levi alpha brain <prompt...>`` — ask the native-brain weights to
  continue the prompt (raw continuation, labeled, never reasoning) and
  print the provenance. Refuses when the brain cannot run, honestly.
"""

from __future__ import annotations

import argparse
import json

from . import ALPHA_ROLE, probe_alpha

__all__ = ["register_alpha_parser", "cmd_alpha", "ALPHA_ROLE"]


def register_alpha_parser(sub) -> None:
    ap = sub.add_parser(
        "alpha",
        help="Alpha: the builder seat — Echo's facet that builds (Omega powered by Alpha)",
    )
    cmds = ap.add_subparsers(dest="alpha_cmd")

    bld = cmds.add_parser(
        "build",
        help="build from natural language: intent in, E3-E6 plan out",
    )
    bld.add_argument(
        "intent",
        nargs="+",
        help='build intent, e.g. "a todo list app" or "build module auth"',
    )
    bld.add_argument(
        "--tier",
        choices=["E3", "E4", "E5", "E6"],
        default="E4",
        help="E3 stabilize · E4 scaffold · E5 MVP (HITL) · E6 uplift (HITL)",
    )
    bld.add_argument("--name", default=None, help="project name (default: from intent)")
    bld.add_argument(
        "--target",
        choices=["independent", "levi"],
        default="independent",
        help="build target (default: independent)",
    )
    bld.add_argument(
        "--apply",
        action="store_true",
        help="apply the plan under the tier's gates (E5/E6 need HITL approval)",
    )
    bld.add_argument(
        "--force",
        action="store_true",
        help="bypass HITL gates — explicit and loud, use with care",
    )

    r = cmds.add_parser("reason", help="deliberate over a build plan or decision")
    r.add_argument("task", nargs="+", help="the plan/decision to deliberate over")

    cmds.add_parser("substrate", help="show the substrate report as JSON")

    b = cmds.add_parser(
        "brain", help="print a raw native-brain continuation for a prompt"
    )
    b.add_argument("prompt", nargs="+", help="the prompt for the brain to continue")
    b.add_argument("--chars", type=int, default=160, help="max continuation chars")
    b.add_argument("--seed", type=int, default=1337, help="sampling seed")
    b.add_argument(
        "--temperature",
        type=float,
        default=0.8,
        help="sampling temperature (0 = greedy)",
    )


def _require_reasoner():
    reasoner = probe_alpha()
    if reasoner is None:
        raise RuntimeError("alpha is unavailable in this build")
    return reasoner


def cmd_alpha(args: argparse.Namespace) -> int:
    """Dispatch ``levi alpha <cmd>``; returns a process exit code."""
    cmd = getattr(args, "alpha_cmd", None)
    if cmd == "build":
        from .build import (
            apply_build,
            format_plan,
            parse_build_intent,
            plan_build,
            route_summary,
        )

        intent = " ".join(getattr(args, "intent", None) or []).strip()
        try:
            parsed = parse_build_intent(intent)
            tier = getattr(args, "tier", "E4") or "E4"
            job = plan_build(
                intent,
                tier=tier,
                target=getattr(args, "target", "independent") or "independent",
                name=getattr(args, "name", None),
            )
        except ValueError as exc:
            print(f"alpha: refused: {exc}")
            return 1
        print(route_summary(parsed, job.tier))
        print(format_plan(job))
        if getattr(args, "apply", False):
            if getattr(args, "force", False):
                print("\nalpha: --force: bypassing HITL gates explicitly")
            print()
            out = apply_build(job.id, force=bool(getattr(args, "force", False)))
            print(out)
            return 0 if "Applied job" in out else 2
        if job.requires_hitl:
            print(
                f"\n(HITL required: approve request {job.hitl_id}, "
                "then re-run with --apply)"
            )
        return 0
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
    if cmd == "brain":
        from .reason import Reasoner

        reasoner = Reasoner(brain_chars=getattr(args, "chars", 160) or 160)
        brain, detail = reasoner._load_brain_inference()
        if brain is None:
            print(f"alpha: brain cannot run: {detail}")
            return 1
        desc = brain.describe()
        prompt = " ".join(args.prompt or []).strip()
        try:
            gen = brain.generate(
                prompt,
                max_new_chars=reasoner.brain_chars,
                temperature=args.temperature,
                seed=args.seed,
            )
        except Exception as exc:
            print(f"alpha: brain refused: {exc}")
            return 1
        print("--- raw brain continuation (NOT reasoning) ---")
        print(repr(gen["continuation"]))
        print("--- provenance ---")
        print(f"params: {desc['params']}")
        print(f"training steps: {desc['training_steps']}")
        print(f"sha256 match: {desc['sha256_match']}")
        print(f"unmapped prompt chars: {gen['unmapped_chars']}")
        print(f"seed: {gen['seed']} temperature: {gen['temperature']}")
        print(f"note: {desc['honest_note']}")
        return 0
    print("alpha: choose build | reason | substrate | brain")
    return 1
