"""The Forge: Echo -> Alpha -> preview -> permission -> materialize -> Nexus.

Omega's heart was a pipeline: **Echo** turned a request into an
architecture blueprint, **Alpha** compiled the blueprint into working
products, and **Nexus** chose how the result would be served. This
module is that full journey, LEVI-native and written from scratch —
with an honest gate at every step and no step that pretends to be more
than it is.

Stages, in order:

1. ``echo``        — prompt -> product-type detection (heuristic, scored)
                     -> drafted blueprint -> structural validation.
2. ``alpha``       — pick generator(s) for the blueprint's product types,
                     compile to an in-memory ``{path: content}`` map.
                     Nothing touches disk here.
3. ``preview``     — pure render of what's coming (paths, snippets) plus
                     per-file landing verdicts at the destination.
                     No writes, ever.
4. ``permission``  — the human gate. Writing needs ``approve=True``;
                     the pipeline never default-approves, never guesses.
5. ``materialize`` — gated write + post-write byte-compare with sha256
                     per file; returns a signed receipt.
6. ``nexus``       — route the follow-through work across LEVI's lawful
                     providers and explain the choice. Routing picks a
                     provider; it does not run the artifact.
7. ``receipt``     — one combined receipt: every stage's honest account.

Every stage returns a structured result::

    {"stage", "ok", "did", "did_not", "data", "error"}

``did`` is what actually happened; ``did_not`` is what the stage
honestly does NOT claim. A stage that fails stops the run and is
recorded — never papered over.

Public surface:

- ``run_pipeline(prompt, *, dest, approve=False, ...)`` — programmatic,
  non-interactive. Raises ``ValueError`` on bad arguments; returns the
  final receipt (``ok=False`` when a stage refused).
- ``main(argv=None)`` — the ``forge`` CLI: interactive by default,
  ``--approve`` for the explicit non-interactive path.

Stdlib only. Local-first. 100% LEVI.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from . import blueprint as bp
from . import generators as gen
from . import materialize as mz
from . import nexus as nx

ORIGIN = "levi-revival-omega/forge"

# product_type -> capability tags the follow-through work needs
PRODUCT_TASK_KINDS: Dict[str, List[str]] = {
    "webpage": ["serve"],
    "cli": ["run"],
    "api": ["serve"],
    "mcp_server": ["serve", "chat"],
    "automation": ["run"],
    "skill": ["chat"],
}


# --------------------------------------------------------------------------
# default provider fleet (lawful: levi-local + levi-si-cloud only)
# --------------------------------------------------------------------------


def default_providers() -> List[nx.Provider]:
    """LEVI's own operational sources. References are never added here."""
    return [
        nx.Provider(
            name="levi-local",
            source=nx.SOURCE_LOCAL,
            kinds=frozenset({"chat", "code", "run", "serve"}),
            cost=1,
            quality=0.7,
        ),
        nx.Provider(
            name="levi-si-cloud",
            source=nx.SOURCE_CLOUD,
            kinds=frozenset({"chat", "code", "run", "serve", "vision"}),
            cost=5,
            quality=0.85,
        ),
    ]


# --------------------------------------------------------------------------
# stage bookkeeping
# --------------------------------------------------------------------------


def _stage(
    name: str,
    ok: bool,
    did: List[str],
    did_not: List[str],
    data: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "stage": name,
        "ok": ok,
        "did": did,
        "did_not": did_not,
        "data": data or {},
        "error": error,
    }


def _stop(stages: List[Dict[str, Any]], failed: Dict[str, Any]) -> Dict[str, Any]:
    stages.append(failed)
    return _receipt(stages, ok=False)


def _receipt(stages: List[Dict[str, Any]], ok: bool) -> Dict[str, Any]:
    first = next((s for s in stages if s["stage"] == "echo"), {})
    data = first.get("data", {}) if isinstance(first, dict) else {}
    return {
        "ok": ok,
        "origin": ORIGIN,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt": data.get("prompt", ""),
        "dest": data.get("dest", ""),
        "blueprint": data.get("blueprint_summary", {}),
        "stages": stages,
        "limits": [
            "detection is a keyword heuristic — scores exposed, never asserted",
            "generators emit starter scaffolds, not finished products",
            "nothing is written without explicit approval (approve=True)",
            "materialization writes files; it never executes them",
            "nexus confidence is a policy score, not measured accuracy",
            "nexus routing picks a provider; it does not run the artifact",
            "reference providers are studied, never operational — always ineligible",
        ],
    }


# --------------------------------------------------------------------------
# stages
# --------------------------------------------------------------------------


def _run_echo(prompt: str, product_types: Optional[Sequence[str]]) -> Dict[str, Any]:
    try:
        blueprint = bp.build_blueprint(
            prompt, product_types=list(product_types) if product_types else None
        )
    except ValueError as exc:
        return _stage(
            "echo",
            False,
            ["refused to draft a blueprint"],
            ["does not guess intent from a broken or mistyped request"],
            error=str(exc),
        )
    check = bp.validate_blueprint(blueprint)
    if not check["ok"]:
        return _stage(
            "echo",
            False,
            ["drafted a blueprint that failed structural validation"],
            ["does not hand unvalidated specs to the compiler"],
            error="; ".join(check["errors"]),
        )
    types = blueprint.get("product_types", [])
    return _stage(
        "echo",
        True,
        [
            "detected product types via keyword heuristic",
            f"drafted blueprint {blueprint.get('name')!r} for {types}",
            "passed structural validation",
        ],
        [
            "detection is a keyword heuristic — it does not understand intent",
            "does not guarantee the design is good, complete, or safe to run",
        ],
        data={
            "prompt": prompt,
            "blueprint": blueprint,
            "blueprint_summary": {
                "name": blueprint.get("name"),
                "title": blueprint.get("title"),
                "product_types": types,
                "components": [c.get("name") for c in blueprint.get("components", [])],
                "artifacts": blueprint.get("artifacts", []),
            },
            "detection_scores": bp.detection_scores(prompt),
        },
    )


def _run_alpha(blueprint: Dict[str, Any], generator: Optional[str]) -> Dict[str, Any]:
    available = gen.generators_for(blueprint)
    if not available:
        return _stage(
            "alpha",
            False,
            ["matched no generators to the blueprint's product types"],
            ["does not invent a generator for a product type it cannot build"],
            data={"available_generators": gen.registered()},
            error=(
                f"no generators cover product types {blueprint.get('product_types')}"
            ),
        )
    if generator is not None:
        try:
            picked = gen.get(generator)
        except ValueError as exc:
            return _stage(
                "alpha",
                False,
                ["refused an unknown generator"],
                ["does not fall back to a different generator silently"],
                data={"available_generators": [g.name for g in available]},
                error=str(exc),
            )
        wanted = set(blueprint.get("product_types", []))
        if not wanted.intersection(picked.product_types):
            return _stage(
                "alpha",
                False,
                [
                    f"refused generator {generator!r}: it does not cover {sorted(wanted)}"
                ],
                ["does not compile a blueprint with a mismatched generator"],
                data={"available_generators": [g.name for g in available]},
                error=f"generator {generator!r} covers {picked.product_types}",
            )
        names = [picked.name]
    else:
        names = [g.name for g in available]

    files: Dict[str, str] = {}
    errors: List[str] = []
    picked_gens = [gen.get(n) for n in names]
    for g in picked_gens:
        try:
            produced = g.generate(blueprint)
        except Exception as exc:  # noqa: BLE001 - recorded, not raised
            errors.append(f"{g.name}: {exc}")
            continue
        if not isinstance(produced, dict):
            errors.append(f"{g.name}: must return dict, got {type(produced).__name__}")
            continue
        for path, content in produced.items():
            if path in files:
                errors.append(f"{g.name}: duplicate path {path!r} — first writer wins")
                continue
            files[path] = content
    if not files:
        return _stage(
            "alpha",
            False,
            ["ran the generator(s) but produced no files"],
            ["does not write empty results to disk"],
            data={"generators": names, "errors": errors},
            error="; ".join(errors) or "generators produced nothing",
        )
    return _stage(
        "alpha",
        True,
        [
            f"compiled with generator(s): {', '.join(names)}",
            f"produced {len(files)} in-memory artifact(s)",
            *([f"generator note: {e}" for e in errors] if errors else []),
        ],
        [
            "artifacts are starter scaffolds, not finished products",
            "no disk writes happened in this stage",
            "generated code was not executed or tested",
        ],
        data={
            "generators": names,
            "files": files,
            "paths": sorted(files),
            "generator_errors": errors,
        },
    )


def _run_preview(files: Dict[str, str], dest: str) -> Dict[str, Any]:
    text = mz.preview(files)
    try:
        planned = mz.plan(files, dest)
    except ValueError as exc:
        return _stage(
            "preview",
            False,
            ["refused to plan against the destination"],
            ["does not plan writes into a place it cannot name"],
            error=str(exc),
        )
    return _stage(
        "preview",
        True,
        [
            "rendered the full artifact preview (paths + content snippets)",
            f"mapped {len(planned['entries'])} landing verdict(s) at {planned['dest']}",
        ],
        [
            "this stage reads nothing but destination existence checks",
            "this stage writes nothing, ever",
        ],
        data={
            "preview_text": text,
            "plan": planned,
            "entries": planned["entries"],
        },
    )


def _run_permission(files: Dict[str, str], approve: bool) -> Dict[str, Any]:
    if not approve:
        return _stage(
            "permission",
            False,
            ["held the artifacts — nothing written"],
            [
                "never default-approves",
                "never treats silence, flags, or vibes as approval",
            ],
            error=(
                "permission denied: writing needs your explicit say-so. "
                f"{len(files)} artifact(s) are staged but untouched. "
                "Re-run with approve=True (CLI: --approve)."
            ),
        )
    return _stage(
        "permission",
        True,
        ["explicit approval recorded (approve=True)"],
        ["approval covers these artifacts only — not future runs"],
    )


def _run_materialize(
    files: Dict[str, str], dest: str, approve: bool, overwrite: bool
) -> Dict[str, Any]:
    try:
        receipt = mz.write(files, dest, approve=approve, overwrite=overwrite)
    except PermissionError as exc:
        return _stage(
            "materialize",
            False,
            ["refused to touch disk without approval"],
            ["does not bypass the permission gate"],
            error=str(exc),
        )
    except (ValueError, OSError) as exc:
        return _stage(
            "materialize",
            False,
            ["attempted the write and hit a real error"],
            ["does not claim success when the disk disagrees"],
            error=f"{type(exc).__name__}: {exc}",
        )
    written = receipt.get("written", [])
    skipped = receipt.get("skipped", [])
    ok = bool(receipt.get("verified")) and not receipt.get("mismatches")
    return _stage(
        "materialize",
        ok,
        [
            f"wrote {len(written)} file(s) to {receipt.get('dest')}",
            f"skipped {len(skipped)} file(s)",
            "post-write byte-compare + sha256 "
            + ("passed" if receipt.get("verified") else "FAILED"),
        ],
        [
            "does not execute the artifacts",
            "does not verify the code runs — only that bytes match",
        ],
        data={
            "receipt": receipt,
            "written": written,
            "skipped": skipped,
            "sha256": {w["path"]: w["sha256"] for w in written},
        },
        error=None
        if ok
        else "; ".join(
            m.get("reason", "mismatch") for m in receipt.get("mismatches", [])
        ),
    )


def _run_nexus(
    product_types: Sequence[str],
    mode: str,
    providers: Optional[Sequence[nx.Provider]],
) -> Dict[str, Any]:
    kinds: List[str] = []
    for ptype in product_types:
        for kind in PRODUCT_TASK_KINDS.get(ptype, []):
            if kind not in kinds:
                kinds.append(kind)
    task = nx.Task(
        kinds=frozenset(kinds),
        label=f"carry forward the forged {sorted(product_types)} artifact(s)",
    )
    fleet = list(providers) if providers is not None else default_providers()
    try:
        routes = nx.route(task, fleet, mode=mode)
    except ValueError as exc:
        return _stage(
            "nexus",
            False,
            ["refused to route"],
            ["does not route with a broken fleet or mode"],
            error=str(exc),
        )
    chosen = next((r for r in routes if r.eligible), None)
    explanation = nx.explain(routes)
    if chosen is None:
        return _stage(
            "nexus",
            False,
            ["ranked every provider and found none eligible"],
            [
                "never leaks the task to an ineligible provider",
                "deny-closed: an empty eligible set is a refusal, not a fallback",
            ],
            data={
                "mode": mode,
                "task_kinds": sorted(kinds),
                "explanation": explanation,
            },
            error="no eligible provider for this mode/task",
        )
    return _stage(
        "nexus",
        True,
        [
            f"routed via {chosen.provider} (mode={mode})",
            "explained the ranking line-by-line",
        ],
        [
            "confidence is a policy score — it ranks options, "
            "it does not measure real-world accuracy",
            "routing selects a provider; it does not run the artifact",
            "reference providers stayed ineligible by law",
        ],
        data={
            "mode": mode,
            "task_kinds": sorted(kinds),
            "chosen": chosen.provider,
            "confidence": chosen.confidence,
            "reasons": chosen.reasons,
            "explanation": explanation,
        },
    )


# --------------------------------------------------------------------------
# the full run
# --------------------------------------------------------------------------


def run_pipeline(
    prompt: str,
    *,
    dest: str,
    approve: bool = False,
    overwrite: bool = False,
    mode: str = "balanced",
    generator: Optional[str] = None,
    product_types: Optional[Sequence[str]] = None,
    providers: Optional[Sequence[nx.Provider]] = None,
) -> Dict[str, Any]:
    """Run Echo -> Alpha -> preview -> permission -> materialize -> Nexus.

    Returns the final receipt (``ok=False`` when any stage refused).
    Raises ``ValueError`` only on bad *arguments* (empty prompt, unknown
    dest, unknown generator/mode) — flow refusals are structured, not
    exceptions.
    """
    if not prompt or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    if not isinstance(dest, str) or not dest:
        raise ValueError(f"unknown dest: {dest!r} — give me a real directory")
    if not os.path.isdir(dest):
        raise ValueError(f"unknown dest: {dest!r} — not an existing directory")
    if mode not in nx.MODES:
        raise ValueError(f"unknown mode: {mode!r} (expected one of {sorted(nx.MODES)})")

    stages: List[Dict[str, Any]] = []

    echo = _run_echo(prompt, product_types)
    if not echo["ok"]:
        return _stop(stages, echo)
    stages.append(echo)
    blueprint: Dict[str, Any] = echo["data"]["blueprint"]
    # the destination is fixed from here on — it becomes part of the story
    echo["data"]["dest"] = os.path.realpath(dest)

    alpha = _run_alpha(blueprint, generator)
    if not alpha["ok"]:
        return _stop(stages, alpha)
    stages.append(alpha)
    files: Dict[str, str] = alpha["data"]["files"]

    preview = _run_preview(files, dest)
    if not preview["ok"]:
        return _stop(stages, preview)
    stages.append(preview)

    permission = _run_permission(files, approve)
    if not permission["ok"]:
        return _stop(stages, permission)
    stages.append(permission)

    material = _run_materialize(files, dest, approve=approve, overwrite=overwrite)
    if not material["ok"]:
        return _stop(stages, material)
    stages.append(material)

    nexus = _run_nexus(blueprint.get("product_types", []), mode, providers)
    if not nexus["ok"]:
        return _stop(stages, nexus)
    stages.append(nexus)

    return _receipt(stages, ok=True)


# --------------------------------------------------------------------------
# forge CLI
# --------------------------------------------------------------------------


def _blueprint_summary(blueprint: Dict[str, Any], scores: Dict[str, int]) -> str:
    lines = [
        "── Echo's blueprint ──",
        f"  name   : {blueprint.get('name')}",
        f"  types  : {', '.join(blueprint.get('product_types', []))}",
        f"  scores : {scores or 'none (fallback)'}",
        "  parts  :",
    ]
    for comp in blueprint.get("components", []):
        lines.append(f"    ▸ {comp.get('name')}  [{comp.get('kind')}]")
    lines.append(f"  layers : {', '.join(blueprint.get('layers', []))}")
    return "\n".join(lines)


def _ask(question: str, default: str = "") -> str:
    try:
        answer = input(f"{question} ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""
    return answer or default


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="forge",
        description=(
            "The Forge: prompt -> Echo blueprint -> Alpha compile -> preview -> "
            "your explicit yes -> safe materialization -> Nexus routing -> receipt."
        ),
    )
    parser.add_argument("prompt", nargs="?", help="what to build (asked if omitted)")
    parser.add_argument(
        "--dest",
        default="forge-out",
        help="directory the artifacts land in (created if missing)",
    )
    parser.add_argument(
        "--mode",
        default="balanced",
        choices=sorted(nx.MODES),
        help="Nexus routing mode (default: balanced)",
    )
    parser.add_argument(
        "--generator",
        default=None,
        help=f"pin one generator (default: all matching; known: {', '.join(gen.registered())})",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="allow replacing existing files at the destination",
    )
    parser.add_argument(
        "--approve",
        action="store_true",
        help="NON-INTERACTIVE approval: you say the files may land. "
        "Never on by default — the gate only opens when you open it.",
    )
    parser.add_argument(
        "--product-type",
        action="append",
        default=None,
        dest="product_types",
        help="pin a product type (repeatable); default: Echo detects",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def _run_interactive(args: argparse.Namespace) -> int:
    prompt = args.prompt or _ask("What should the Forge build?")
    if not prompt.strip():
        print("No prompt — the Forge stands down.", file=sys.stderr)
        return 2

    os.makedirs(args.dest, exist_ok=True)

    # Echo — show the blueprint, let them bail
    blueprint = bp.build_blueprint(prompt, product_types=args.product_types or None)
    print()
    print(_blueprint_summary(blueprint, bp.detection_scores(prompt)))
    print()
    if _ask("Does this blueprint look right? [yes/no]").lower() not in {"yes", "y"}:
        print("Standing down — no blueprint, no build.")
        return 1

    # Alpha — generator pick
    available = gen.generators_for(blueprint)
    if args.generator:
        pick = args.generator
    elif len(available) == 1:
        pick = available[0].name
        print(f"One generator fits: {pick} — taking it.")
    else:
        print("Generators that fit this blueprint:")
        for i, g in enumerate(available, 1):
            print(f"  {i}. {g.name} — {g.title}")
        choice = _ask(f"Pick one [1-{len(available)}], or 'all':", default="1")
        if choice.lower() == "all":
            pick = None
        else:
            try:
                pick = available[int(choice) - 1].name
            except (ValueError, IndexError):
                print("That's not a pick — standing down.", file=sys.stderr)
                return 2

    print()
    print("Compiling with Alpha…")
    result = run_pipeline(
        prompt,
        dest=args.dest,
        approve=False,  # preview first, ask after
        overwrite=args.overwrite,
        mode=args.mode,
        generator=pick,
        product_types=args.product_types,
    )
    alpha_stage = next(s for s in result["stages"] if s["stage"] == "alpha")
    print(mz.preview(alpha_stage["data"]["files"]))
    plan = next(s for s in result["stages"] if s["stage"] == "preview")["data"]["plan"]
    for entry in plan["entries"]:
        print(f"  [{entry['action']:>13}] {entry['path']} — {entry['reason']}")
    print()

    # the gate: explicit yes, nothing else counts
    if _ask("Write these files? Type YES to approve:") != "YES":
        print("No approval — nothing was written. The Forge stands down.")
        return 1

    print("Approval recorded. Materializing…")
    result = run_pipeline(
        prompt,
        dest=args.dest,
        approve=True,
        overwrite=args.overwrite,
        mode=args.mode,
        generator=pick,
        product_types=args.product_types,
    )
    return _print_receipt(result)


def _print_receipt(result: Dict[str, Any]) -> int:
    print()
    print("── Forge receipt ──")
    print(f"  ok      : {result['ok']}")
    print(f"  origin  : {result['origin']}")
    print(f"  when    : {result['timestamp']}")
    for stage in result["stages"]:
        mark = "✓" if stage["ok"] else "✗"
        print(f"  {mark} {stage['stage']}")
        for done in stage["did"]:
            print(f"      did     : {done}")
        if stage["error"]:
            print(f"      stopped : {stage['error']}")
    if result["ok"]:
        nexus_data = next(s for s in result["stages"] if s["stage"] == "nexus")["data"]
        print(
            f"  routed  : {nexus_data['chosen']} "
            f"(confidence {nexus_data['confidence']:.3f} — a policy score, "
            f"not measured accuracy)"
        )
        mat = next(s for s in result["stages"] if s["stage"] == "materialize")["data"]
        print(f"  landed  : {len(mat['written'])} file(s) at {result['dest']}")
    else:
        print("  The Forge stopped where the ✗ is — nothing after it happened.")
    return 0 if result["ok"] else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        if args.approve:
            os.makedirs(args.dest, exist_ok=True)
            result = run_pipeline(
                args.prompt or "",
                dest=args.dest,
                approve=True,
                overwrite=args.overwrite,
                mode=args.mode,
                generator=args.generator,
                product_types=args.product_types,
            )
            return _print_receipt(result)
        return _run_interactive(args)
    except ValueError as exc:
        print(f"forge: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
