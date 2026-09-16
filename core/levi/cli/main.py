#!/usr/bin/env python3
"""
LEVI × L.W.P. CLI — Companion + constructive DNA + retention surface
Power complexity is soft by default; use --verbose for internals.
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import types
from pathlib import Path

# Only touch sys.path when the package isn't already importable (e.g. a fresh
# checkout without `pip install -e .`). When installed, the `levi` console
# script and plain `import levi` work without any path mutation.
try:
    import levi  # noqa: F401
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from levi import __version__
from levi.orchestration.loop import Orchestrator
from levi.persona.lattice import PersonaLattice
from levi.skill.registry import SkillRegistry
from levi.agent.specialists import SpecialistRegistry
from levi.memory.store import MemoryStore
from levi.memory.types import MemoryType
from levi.policy.gates import PolicyEngine
from levi.model.abstraction import ModelRouter
from levi.graph.interpenetration import InterpenetrationEngine
from levi.graph.genres import GenreRegistry
from levi.factory.pipeline import SoftwareFactory
from levi.daemon.automation import AutomationRegistry
from levi.identity.profile import ProfileStore
from levi.identity.shelf import collect_shelf, format_shelf, latest_item
from levi.identity.export_life import export_life_pack, import_life_pack
from levi.identity.templates import list_templates, apply_template

# >>> LEVI backup module — minimal hook (backup coordinator); logic in levi/backup/
from levi.backup.cli import cmd_backup, register_backup_parser
from levi.jobs.cli import cmd_jobs, register_jobs_parser

# >>> LEVI teach module — minimal hook (teach worker); logic in levi/teach/
from levi.teach.cli import cmd_teach, register_teach_parser
# <<< LEVI teach module

# <<< LEVI backup module
# >>> LEVI Stage-1 lineage — minimal hooks (source-sync entry `levi-ai`)
from levi.surgeon.cli import cmd_surgeon, register_surgeon_parser
from levi.automation.cli import cmd_automation, register_automation_parser
# <<< LEVI Stage-1 lineage


def banner():
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  LEVI × L.W.P.  —  Local-First Super-System                  ║
║  v{__version__}  ·  Companion · Structure · Factory DNA         ║
║  Friend · Mentor · Challenger · Protector                    ║
╚══════════════════════════════════════════════════════════════╝
""")


def _verbose(args) -> bool:
    if getattr(args, "verbose", False):
        return True
    return ProfileStore().load().verbose


def cmd_init(args):
    store = ProfileStore()
    p = store.load()
    print("══ LEVI first-run (local only) ══\n")
    name = args.name or input("What should I call you? ").strip() or "friend"
    goal = args.goal or input("One goal for this week (optional): ").strip()
    print("\nPreferred daily loop:")
    print("  1) companion  2) writing  3) building")
    loop = args.loop or input("Choice [1/2/3]: ").strip()
    loop_map = {
        "1": "companion",
        "2": "writing",
        "3": "building",
        "companion": "companion",
        "writing": "writing",
        "building": "building",
    }
    preferred = loop_map.get(loop, "companion")
    p.name = name
    p.goal_this_week = goal
    p.preferred_loop = preferred
    p.onboarded = True
    p.confirm_constructive = not args.yes
    store.save(p)

    # Seed memory
    mem = MemoryStore()
    mem.add(
        MemoryType.SEMANTIC,
        content=f"User name: {name}",
        importance=0.9,
        source="init",
        tags=["profile"],
    )
    if goal:
        mem.add(
            MemoryType.SEMANTIC,
            content=f"Goal this week: {goal}",
            importance=0.85,
            source="init",
            tags=["goal"],
        )

    router = ModelRouter()
    local = router.status().get("local_available")
    print(f"\nWelcome, {name}.")
    if goal:
        print(f"I'll hold this goal with you: {goal}")
    print(f"Daily loop bias: {preferred}")
    if not local:
        print("\nNo local model detected yet. Core still works offline.")
        print("  For full conversation:  ollama serve && ollama pull llama3.2")
    print("\n5-minute win:")
    print("  levi home          — your shelf + continue")
    print("  levi morning       — daily goal + next move")
    print("  levi nervous       — affect + persona matrix")
    print('  levi ask "..."       — talk to me')
    if preferred == "writing":
        print("  levi templates     — try systems_horror_seed")
    elif preferred == "building":
        print("  levi templates     — try checklist_cli")
    else:
        print('  levi ask "Who are you?"')
    print("\nYou're onboarded. Data stays in ~/.levi/")


def cmd_home(args):
    store = ProfileStore()
    p = store.load()
    if not p.onboarded:
        print("Not onboarded yet. Run:  levi init")
        return
    print(f"══ Home — {p.name or 'friend'} ══\n")
    if p.goal_this_week:
        print(f"This week: {p.goal_this_week}")
    if p.preferred_loop:
        print(f"Loop: {p.preferred_loop}")
    router = ModelRouter()
    st = router.status()
    print(
        f"Model: {'local ready' if st.get('local_available') else 'offline fallback (ollama optional)'}"
    )
    print()
    print(format_shelf(limit=8))
    latest = latest_item()
    if latest:
        print("\nSuggested: levi continue")
    store.save(p)


def cmd_continue(args):
    try:
        from levi.runtime.continuity import ContinuityShelf

        print(ContinuityShelf().resume_card())
        print("")
    except Exception:
        pass
    item = latest_item()
    if not item:
        print(
            'Nothing on the shelf yet. Try: levi templates  or  levi ask "Build me..."'
        )
        return
    print(f"Continuing [{item.kind}] {item.title} ({item.id})\n")
    orch = Orchestrator(persona_id=args.personality)
    if item.kind == "story":
        r = orch.turn(f"expand story {item.id}")
        print(r.response if not _verbose(args) else r.response)
        try:
            from levi.runtime.continuity import ContinuityShelf

            ContinuityShelf().snapshot(
                last_ask=getattr(args, "text", "") or "",
                last_reply=str(r.response)[:200],
            )
        except Exception:
            pass
    elif item.kind == "factory":
        from levi.factory.pipeline import SoftwareFactory

        p = SoftwareFactory().advance(item.id, summary="Continued from home/continue")
        print(f"Advanced to stage={p.stage.value} iteration={p.iteration}")
        if p.metadata.get("sandbox_path"):
            print(f"Sandbox: {p.metadata['sandbox_path']}")
    elif item.kind == "automation":
        print(f"Automation {item.id} — run: use skill path or levi automations")
        from levi.daemon.automation import AutomationRegistry

        reg = AutomationRegistry()
        a = reg.get(item.id)
        if a:
            print(reg.run_manual(item.id, SkillRegistry())[:500])
    ProfileStore().save(ProfileStore().load())


def cmd_templates(args):
    if args.use:
        print(apply_template(args.use))
        return
    print("══ Free templates (asset flywheel seeds) ══\n")
    for t in list_templates():
        print(f"  {t.get('id'):22} [{t.get('kind'):11}] {t.get('name')}")
        print(f"    {t.get('description', '')[:70]}")
    print("\nUse:  levi templates --use checklist_cli")


def cmd_export(args):
    path = export_life_pack(Path(args.out) if args.out else None)
    print(f"Life pack written: {path}")
    print("Contains profile, memory, stories, factory, automations, graph composites.")
    print("Your data. Portable. Free core.")


def cmd_import(args):
    src = Path(args.path)
    try:
        report = import_life_pack(src, merge=not args.replace)
    except FileNotFoundError as e:
        print(str(e))
        return
    print("Life pack imported.")
    print(f"  format: {report.get('format')}")
    if report.get("imported"):
        print("  wrote:")
        for n in report["imported"][:20]:
            print(f"    - {n}")
    if report.get("skipped"):
        print("  missing in pack (kept local if present):")
        for n in report["skipped"][:12]:
            print(f"    - {n}")
    print("Try: levi home")


def cmd_morning(args):
    """Daily pull: goal + shelf continue + one clear next move."""
    from levi.identity.profile import ProfileStore

    p = ProfileStore().load()
    name = (p.name if p else "") or "friend"
    goal = (p.goal_this_week if p else "") or ""
    print(banner())
    print(f"Morning, {name}.")
    if goal:
        print(f"This week's goal: {goal}")
    else:
        print("No weekly goal set. Use: levi init --goal YOUR_GOAL")
    print()
    shelf = collect_shelf()
    if shelf:
        top = shelf[0]
        print("Continue from shelf:")
        print(f"  [{top.kind}] {top.title}")
        print(f"  {top.summary}")
        print("  -> levi continue")
    else:
        print("Shelf is empty. A small story or local tool would fill it.")
        print("  -> levi templates")
        print('  -> levi ask "Build me a local offline notes CLI"')
    print()
    try:
        from levi.model.abstraction import ModelRouter

        r = ModelRouter()
        local = getattr(r, "local_available", None)
        if callable(local):
            ok = local()
        else:
            ok = bool(local)
        if not ok:
            print(
                "Voice: local model not detected. Structural path still works offline."
            )
    except Exception:
        pass
    print("One honest move today beats a perfect plan.")


def cmd_status(args):
    memory = MemoryStore()
    router = ModelRouter()
    policy = PolicyEngine()
    skills = SkillRegistry()
    agents = SpecialistRegistry()
    p = ProfileStore().load()

    if not _verbose(args):
        print("══ LEVI status ══\n")
        print(f"Version: {__version__}")
        print(f"User: {p.name or '(run levi init)'} · onboarded={p.onboarded}")
        print("Companion: Friend · Mentor · Challenger · Protector")
        print(
            f"Model: {'local' if router.status().get('local_available') else 'offline fallback'}"
        )
        print(f"Memory entries: {memory.stats().get('total', 0)}")
        print(f"Skills: {len(skills.list())} · Specialists: {len(agents.list())}")
        print(f"Shelf items: {len(collect_shelf())}")
        if not router.status().get("local_available"):
            print("\nTip: ollama serve && ollama pull llama3.2")
        return

    print("=== LEVI System Status (verbose) ===\n")
    print(
        json.dumps(
            {
                "profile": p.to_dict(),
                "memory": memory.stats(),
                "model": router.status(),
                "policy": policy.status(),
            },
            indent=2,
        )
    )


def cmd_ask(args):
    if getattr(args, "ultimate", False):
        from levi.ei.ultimate_path import ultimate_reply

        q = (
            (getattr(args, "question", None) or "")
            + " "
            + " ".join(getattr(args, "extra", None) or [])
        )
        q = q.strip() or "What is the real constraint?"
        print(ultimate_reply(q))
        return

    question = args.question or " ".join(args.extra)
    if not question:
        print("Usage: levi ask [--personality NAME] <question>")
        return
    orch = Orchestrator(persona_id=args.personality, soft_power=not _verbose(args))
    result = orch.turn(question)
    if _verbose(args):
        print(f"[Intent]     {result.intent}")
        print(f"[Companion]  {result.companion_summary}")
        print(f"[Persona]    {result.persona_id}")
        print(f"[Specialists] {', '.join(result.specialists)}")
        if result.skills_considered:
            print(f"[Skills]     {', '.join(result.skills_considered)}")
        print()
    print(result.response)
    if result.is_special_behavior:
        p = orch.lattice.current()
        if p and p.requires_explicit_answer_request:
            print('\n(Say "give the answer" when you want the full answer.)')
        elif p and getattr(p, "no_hero_mode", False):
            print('\n(Say "more detail" for the next layer.)')


def cmd_turn(args):
    """One bloodstream turn: companion + 5D EI → persona lens → L.W.P.
    governor → factory / organ / model → policy gate → memory → trace.

    Prints the reply and a one-line receipt summary. Consequential acts
    (risk >= 2) are HITL-gated: without --yes, LEVI asks on stdin and
    refuses on EOF/denial (fail-closed).
    """
    from levi.bloodstream import TurnContext, run_turn

    text = ((args.text or "") + " " + " ".join(args.extra)).strip()
    if not text:
        print(
            "Usage: levi turn [--persona NAME] [--provider NAME] [--session ID] "
            '[--composite NAME] [--yes] [--dry-run] "your text"'
        )
        return

    if getattr(args, "yes", False):
        confirm = lambda proposal: True  # noqa: E731
    else:

        def confirm(proposal):
            try:
                ans = (
                    input(
                        f"Approve '{proposal.description}' "
                        f"(risk {int(proposal.risk_level)})? [y/N] "
                    )
                    .strip()
                    .lower()
                )
            except EOFError:
                return False
            return ans in ("y", "yes")

    ctx = TurnContext(
        session_id=getattr(args, "session", "default") or "default",
        persona_id=getattr(args, "persona", None),
        provider=getattr(args, "provider", None),
        confirm=confirm,
        composite_name=getattr(args, "composite", None),
        dry_run=getattr(args, "dry_run", False),
    )
    result = run_turn(text, ctx)
    print(result.reply)
    print()
    print(f"[{result.route.value}] {result.receipt_summary}")
    if result.awaiting_permission:
        print("(Awaiting permission — rerun with --yes to approve.)")


def cmd_nervous(args):
    """Show LEVI affect state + persona activation matrix."""
    from levi.persona.nervous_system import NervousSystem

    ns = NervousSystem(persona_ids=PersonaLattice().keys())
    if getattr(args, "unlock", False):
        ns.unlock()
        print("Persona lock cleared. Matrix selection resumed.")
    if getattr(args, "reset", False):
        from levi.persona.nervous_system import AffectState

        ns.affect = AffectState()
        for a in ns.affinities.values():
            a.uses = 0
            a.last_used_at = None
        ns._last_selected = None
        ns._incumbent_turns = 0
        ns._last_blend = None
        ns._persist()
        print("Nervous system affect + usage reset.")
    print(ns.format_status())
    if args.verbose or getattr(args, "verbose", False):
        import json

        print(json.dumps(ns.status(), indent=2))


def cmd_daemon(args):
    """Control daemon: steer personas, wit styles, alchemy (no-pure-negative)."""
    action = getattr(args, "action", None) or "status"
    if action == "services":
        # Unified supervisor (axis 4) — branch before ControlDaemon import.
        return cmd_daemon_services(args)
    from levi.daemon.control import ControlDaemon

    d = ControlDaemon()
    action = getattr(args, "action", None) or "status"
    if action == "status":
        print(d.format_status())
        return
    if action == "clear":
        d.issue("clear", reason="cli clear")
        print("All locks/boosts/suppress cleared.")
        print(d.format_status())
        return
    if action == "alchemy":
        on = not getattr(args, "off", False)
        intensity = float(getattr(args, "intensity", 0.55) or 0.55)
        d.set_alchemy(enabled=on, intensity=intensity)
        print(f"Alchemy set enabled={on} intensity={intensity}")
        print(d.alchemy.system_block()[:600])
        return
    if action in ("life-equation", "xyz"):
        on = not getattr(args, "off", False)
        intensity = float(getattr(args, "intensity", 0.55) or 0.55)
        d.set_life_equation(enabled=on, intensity=intensity)
        print(f"Life equation (x+y=z) set enabled={on} intensity={intensity}")
        print(d.life_equation.system_block()[:700])
        return
    if action in ("life-chess", "chess"):
        on = not getattr(args, "off", False)
        intensity = float(getattr(args, "intensity", 0.55) or 0.55)
        d.set_life_chess(enabled=on, intensity=intensity)
        print(f"Life chess set enabled={on} intensity={intensity}")
        print(d.life_chess.system_block()[:700])
        return
    if action in ("ugly-truth", "ugly", "director"):
        on = not getattr(args, "off", False)
        intensity = float(getattr(args, "intensity", 0.55) or 0.55)
        d.set_ugly_truth(enabled=on, intensity=intensity)
        print(f"Ugly truth set enabled={on} intensity={intensity}")
        print(d.ugly_truth.system_block()[:700])
        return
    if action in ("leverage", "mountain", "root"):
        on = not getattr(args, "off", False)
        intensity = float(getattr(args, "intensity", 0.55) or 0.55)
        d.set_leverage(enabled=on, intensity=intensity)
        print(f"Leverage (problem mountain) set enabled={on} intensity={intensity}")
        print(d.leverage.system_block()[:700])
        return
    if action in ("game-tester", "tester", "bug-hunt", "qa"):
        on = not getattr(args, "off", False)
        intensity = float(getattr(args, "intensity", 0.50) or 0.50)
        d.set_game_tester(enabled=on, intensity=intensity)
        print(f"Game-tester set enabled={on} intensity={intensity}")
        print(d.game_tester.system_block()[:700])
        return
    if action in ("capability-mod", "mod", "cheat", "cheat-code"):
        on = not getattr(args, "off", False)
        intensity = float(getattr(args, "intensity", 0.50) or 0.50)
        d.set_capability_mod(enabled=on, intensity=intensity)
        print(f"Capability/mod set enabled={on} intensity={intensity}")
        print(d.capability_mod.system_block()[:700])
        return
    if action in ("chisel", "sculpt", "iterate"):
        on = not getattr(args, "off", False)
        intensity = float(getattr(args, "intensity", 0.55) or 0.55)
        d.set_chisel(enabled=on, intensity=intensity)
        print(f"Chisel set enabled={on} intensity={intensity}")
        print(d.chisel.system_block()[:700])
        return
    if action == "lock-persona":
        target = getattr(args, "target", None)
        if not target:
            print("Need --target PERSONA_ID")
            return
        d.issue(
            "lock_persona",
            target=target,
            turns=int(getattr(args, "turns", 12) or 12),
            reason="cli lock-persona",
        )
        print(d.format_status())
        return
    if action == "boost-persona":
        target = getattr(args, "target", None)
        if not target:
            print("Need --target PERSONA_ID")
            return
        d.issue(
            "boost_persona",
            target=target,
            strength=float(getattr(args, "strength", 0.6) or 0.6),
            turns=int(getattr(args, "turns", 10) or 10),
            reason="cli boost",
        )
        print(d.format_status())
        return
    if action == "lock-wit":
        target = getattr(args, "target", None)
        if not target:
            print("Need --target STYLE_ID (e.g. precision_deadpan)")
            return
        d.issue(
            "lock_wit",
            target=target,
            turns=int(getattr(args, "turns", 10) or 10),
            reason="cli lock-wit",
        )
        print(d.format_status())
        return
    if action == "force-alchemy":
        d.issue("force_alchemy", strength=0.85, turns=15, reason="cli force-alchemy")
        print(d.format_status())
        return
    if action == "force-life-equation" or action == "force-xyz":
        d.issue("force_life_equation", strength=0.85, turns=15, reason="cli force-xyz")
        print(d.format_status())
        return
    if action in ("force-life-chess", "force-chess"):
        d.issue("force_life_chess", strength=0.85, turns=15, reason="cli force-chess")
        print(d.format_status())
        return
    if action in ("force-ugly-truth", "force-ugly"):
        d.issue("force_ugly_truth", strength=0.85, turns=15, reason="cli force-ugly")
        print(d.format_status())
        return
    print(d.format_status())


def cmd_rail(args):
    from levi.lwp.opportunity_rail import OpportunityRail

    rail = OpportunityRail()
    if getattr(args, "start", None):
        car = rail.start(args.start, title=getattr(args, "title", "") or "")
        print(f"Started car {car.id} at gate {car.gate}")
        print(rail.advance(car.id))
        return
    if getattr(args, "advance", None):
        print(
            rail.advance(
                args.advance, hitl_approved=bool(getattr(args, "approved", False))
            )
        )
        return
    print(rail.format_status())


def cmd_mirror(args):
    from levi.lwp.mirror_cascade import reverse_crosscheck

    print(
        reverse_crosscheck(
            getattr(args, "seed", None) or "empty", getattr(args, "context", "") or ""
        )
    )


def cmd_lwp_model(args):
    from levi.lwp.model_engine import LWPModelEngine

    eng = LWPModelEngine()
    if getattr(args, "direction", None):
        eng.configure(direction=args.direction)
    if getattr(args, "pov", None):
        eng.configure(pov=args.pov)
    if getattr(args, "genres", None):
        eng.configure(genres=args.genres)
    if getattr(args, "seed", None):
        eng.configure(seed=args.seed)
    if getattr(args, "expand", False) or getattr(args, "n", None):
        n = int(getattr(args, "n", None) or 1)
        print(eng.expand(n=n, seed=getattr(args, "seed", None)))
        return
    if getattr(args, "reim", False):
        print(
            eng.reim_forks(
                seed=getattr(args, "seed", None),
                tracks=int(getattr(args, "tracks", None) or 3),
            )
        )
        return
    if getattr(args, "deny", False):
        print(eng.deny_last())
        return
    if getattr(args, "approve", False):
        print(eng.approve_last())
        return
    if getattr(args, "rupture", False):
        print(eng.wyrd_rupture(lens=getattr(args, "lens", None) or "mccarthy"))
        return
    print(eng.status())


def cmd_characters(args):
    from levi.lwp.character_graph import CharacterGraph

    g = CharacterGraph()
    if getattr(args, "weave", False):
        print(g.weave(n_chars=int(getattr(args, "n", None) or 4)))
        return
    if getattr(args, "mint", False):
        c = g.mint(seed=getattr(args, "seed", None))
        print(c.blurb())
        print("id=", c.id)
        return
    print(g.format_status())


def cmd_watch(args):
    from levi.runtime.standing_watch import run_watch

    print(run_watch())


def cmd_crucible(args):
    from levi.runtime.crucible import Crucible

    c = Crucible()
    if getattr(args, "syntax", None):
        print(c.format_result(c.syntax_probe(args.syntax)))
        return
    if getattr(args, "eval", None):
        print(c.format_result(c.restricted_eval(args.eval)))
        return
    if getattr(args, "file", None) and getattr(args, "content", None):
        print(c.format_result(c.file_smoke(args.file, args.content)))
        return
    print("Crucible: --syntax CODE | --eval LITERAL | --file name --content …")


def cmd_services(args):
    from levi.runtime.service_mesh import ServiceMesh

    print(ServiceMesh().format(getattr(args, "query", None) or None))


def cmd_serve_ui(args):
    from levi.ops.serve_ui import serve

    port = int(getattr(args, "port", None) or 8765)
    serve(port=port, open_browser=not getattr(args, "no_browser", False))


def cmd_provenance(args):
    from levi.identity.provenance import (
        provenance_report,
        scan_tree_for_foreign_branding,
    )

    print(provenance_report())
    print("")
    root = __file__
    from pathlib import Path

    print(scan_tree_for_foreign_branding(str(Path(root).resolve().parents[1])))


def cmd_perfection(args):
    from levi.ops.perfection import perfection_report

    print(perfection_report())


def cmd_free(args):
    from levi.integrations.free_graph import build_free_graph
    from levi.integrations.free_lattice import format_catalog, interpenetration_matrix

    if getattr(args, "path", None):
        import json

        a, b = args.path
        route = build_free_graph().shortest_path(a, b)
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "schema": "levi.free_graph.path/v1",
                        "from": a,
                        "to": b,
                        "path": route,
                    },
                    indent=2,
                )
            )
        elif route is None:
            print(f"no path: {a} !-> {b} (unknown asset id or disconnected)")
        else:
            print(" -> ".join(route))
        return
    if getattr(args, "neighborhood", None):
        import json

        nid = args.neighborhood
        depth = getattr(args, "depth", 1) or 1
        layers = build_free_graph().neighborhood(nid, depth=depth)
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "schema": "levi.free_graph.neighborhood/v1",
                        "id": nid,
                        "depth": depth,
                        "layers": {str(k): v for k, v in layers.items()},
                    },
                    indent=2,
                )
            )
        elif not layers:
            print(f"unknown asset id (or no neighbors within depth {depth}): {nid}")
        else:
            print(f"neighborhood of {nid} (depth {depth}):")
            for d in sorted(layers):
                print(f"  hop {d}: {', '.join(layers[d])}")
        return
    if getattr(args, "matrix", False):
        if getattr(args, "json", False):
            print(build_free_graph().to_json_str())
        else:
            print(interpenetration_matrix())
        return
    print(format_catalog())
    print("")
    print(interpenetration_matrix())


def cmd_production(args):
    from levi.ops.production_table import production_table

    print(production_table())


def cmd_go(args):
    """Fast operator path: integrate → ladder → ops in one shot."""
    try:
        from levi.brain.corpus import Corpus
        from levi.brain.seed_atlas import seed_corpus

        units = Corpus().list() if hasattr(Corpus(), "list") else []
        if len(units) < 20:
            print(seed_corpus())
            print("")
    except Exception:
        pass
    from levi.ops.integration import run_integration_audit

    print(run_integration_audit())
    print("")
    from levi.meta.ladder import format_ladder

    try:
        print(format_ladder())
    except Exception:
        import levi.meta.ladder as lad

        if hasattr(lad, "run_ladder"):
            print(lad.run_ladder())
        else:
            from levi.cli.main import cmd_ladder

            cmd_ladder(types.SimpleNamespace())
    print("")
    from levi.ops.layer import OperationalLayer

    print(OperationalLayer().format_status())
    print("")
    try:
        from levi.runtime.standing_watch import run_watch

        print(run_watch())
    except Exception:
        pass


def cmd_integrate(args):
    from levi.ops.integration import run_integration_audit

    print(run_integration_audit())


def cmd_ops(args):
    from levi.ops.layer import OperationalLayer

    ops = OperationalLayer()
    if getattr(args, "estop", False):
        print(ops.estop(getattr(args, "reason", None) or "operator"))
        return
    if getattr(args, "clear_estop", False):
        print(ops.clear_estop())
        return
    if getattr(args, "cycle", None):
        print(ops.run_cycle(args.cycle, execute=bool(getattr(args, "execute", False))))
        return
    if getattr(args, "rail_dry", None):
        print(ops.rail_dry_run(args.rail_dry))
        return
    print(ops.format_status())


def cmd_ladder(args):
    from levi.meta.ladder import format_ladder, readiness_pct

    print(format_ladder())
    if getattr(args, "json", False):
        import json

        print(json.dumps(readiness_pct(), indent=2))


def cmd_organism(args):
    from levi.graph.organism import format_organism, register_into_graph

    if getattr(args, "register", False):
        print(register_into_graph())
    print(format_organism())


def cmd_charter(args):
    from levi.identity.charter import Charter

    c = Charter.load()
    print(c.format())


def cmd_symbiosis(args):
    from levi.graph.symbiosis import format_symbiosis, value_check, orphans
    from levi.plugins.catalog import PluginCatalog

    if getattr(args, "value", None):
        print(value_check(args.value))
        return
    if getattr(args, "orphans", False):
        ids = [p.id for p in PluginCatalog().list()]
        o = orphans(ids)
        print("Assets without explicit pair entry:")
        for x in o:
            print(f"  · {x}")
        if not o:
            print("  (none from catalog ids — check aliases)")
        return
    print(format_symbiosis(getattr(args, "asset", None) or None))


def cmd_sandbox(args):
    from levi.factory.sandbox import run_smoke
    from pathlib import Path

    root = Path(getattr(args, "path", None) or ".")
    print(run_smoke(root))


def cmd_plugins(args):
    from levi.plugins.catalog import PluginCatalog

    print(PluginCatalog().format(category=getattr(args, "category", None) or None))


def cmd_reference(args):
    from levi.plugins.cli import cmd_reference as _cmd

    _cmd(args)


def cmd_doc(args):
    from levi.docs.cli import cmd_doc as _cmd

    _cmd(args)


def cmd_plugin(args):
    """Plugin connectors (blueprint §3): list registered connectors or
    execute one operation. Writes require --yes (HITL gate); without a
    credential the connector reports exactly what is missing and sends
    nothing."""
    import json as _json
    from levi.plugins.registry import describe, get_connector, list_connectors
    import levi.plugins.github  # noqa: F401  (registers the GitHub connector)

    action = getattr(args, "plugin_action", None) or "list"
    if action == "list":
        conns = list_connectors()
        if not conns:
            print("No plugin connectors registered.")
            return
        for i, conn in enumerate(conns):
            if i:
                print()
            print(describe(conn))
        return

    conn = get_connector(getattr(args, "connector", None) or "")
    if conn is None:
        print(
            f"Unknown connector {getattr(args, 'connector', None)!r}. Try: levi plugin list"
        )
        raise SystemExit(2)
    params = {}
    for item in getattr(args, "param", None) or []:
        if "=" not in item:
            print(f"Ignoring malformed --param {item!r} (want k=v)")
            continue
        key, value = item.split("=", 1)
        params[key.strip()] = value
    result = conn.execute(
        getattr(args, "operation", None) or "",
        params,
        confirm=bool(getattr(args, "yes", False)),
    )
    if getattr(args, "json", False):
        print(
            _json.dumps(
                {
                    "connector": result.connector,
                    "operation": result.operation,
                    "ok": result.ok,
                    "status": result.status,
                    "message": result.message,
                    "data": result.data,
                    "request_made": result.request_made,
                },
                indent=2,
            )
        )
    else:
        verdict = "OK" if result.ok else "FAILED"
        print(f"[{result.connector}/{result.operation}] {verdict} ({result.status})")
        print(result.message)
        if result.data:
            print(_json.dumps(result.data, indent=2))
    if not result.ok:
        raise SystemExit(2)


def cmd_finance(args):
    """Paper-only finance domain (blueprint §5.4/5.5): quotes, indicator
    snapshots, advisory signals, a paper portfolio ledger, and paper
    orders behind an explicit HITL gate.

    Nothing here can reach a live account. The only broker reachable
    from this command is ``PaperBroker``; ``AlpacaConnector`` is never
    imported, and live trading is structurally disabled in this build.
    Market-data failures are reported honestly (exit 1) — numbers are
    never fabricated.
    """
    import os as _os
    import json as _json
    from levi.finance import market as _market
    from levi.finance import indicators as _indicators
    from levi.finance import signals as _signals
    from levi.finance import portfolio as _portfolio
    from levi.finance import broker as _broker

    # --- WSB finance expansion modules (all paper-only) ---
    from levi.finance import crypto as _crypto
    from levi.finance import synth as _synth
    from levi.finance import wsb as _wsb
    from levi.finance import bets as _bets
    from levi.finance import leaderboard as _leaderboard
    from levi.finance import copytrade as _copytrade
    from levi.finance import brokerlink as _brokerlink

    ADVISORY_BANNER = "══ ADVISORY ONLY — paper only, not financial advice ══"

    def _signed_money(value: float) -> str:
        sign = "+" if value >= 0 else "-"
        return f"{sign}${abs(value):,.2f}"

    def _load_link_config():
        """Load the broker-link config, warning loudly on corruption.

        Returns (config, config_state). A corrupt config is never
        silently treated as unconfigured — the caller sees the warning.
        """
        try:
            data = _json.loads(
                _brokerlink.DEFAULT_LINK_PATH.read_text(encoding="utf-8")
            )
            cfg = _brokerlink.BrokerLinkConfig.from_dict(data)
            return cfg, "ok"
        except FileNotFoundError:
            return _brokerlink.BrokerLinkConfig(platform=None), "missing"
        except Exception:
            return _brokerlink.BrokerLinkConfig(platform=None), "corrupt"

    def _warn_link_corrupt(config_state: str) -> None:
        if config_state == "corrupt":
            print(
                "  ⚠️  WARNING: the broker-link config file is corrupt — "
                "treating as unconfigured. Back it up or delete it to "
                "silence this warning."
            )

    def _provider_for(source: str):
        """Return (provider, source_label) for a --source name.

        Unknown names are a usage error (exit 2), not a silent default.
        """
        name = str(source or "stooq").strip().lower()
        if name == "stooq":
            return _market.StooqProvider(), "Stooq daily bars (keyless)"
        if name == "binance":
            return _crypto.BinanceProvider(), "Binance public klines (keyless)"
        if name == "synth":
            return _synth.SyntheticProvider(), "seeded synthetic bars (SIMULATED)"
        print(f"Unknown data source {source!r}: expected stooq|binance|synth.")
        raise SystemExit(2)

    def _source_name(source: str) -> str:
        return str(source or "stooq").strip().lower()

    def _bars_for(symbol: str, days: int = 120, source: str = "stooq") -> list:
        provider, _label = _provider_for(source)
        try:
            return provider.daily_bars(symbol, days=days)
        except _market.MarketDataError as exc:
            # Honest failure: name what happened, print no numbers, exit 1.
            # Add a routing hint when the symbol smells like another source.
            hint = ""
            if _crypto.looks_like_crypto(symbol) and _source_name(source) != "binance":
                hint = " (hint: crypto pairs like BTCUSDT need --source binance)"
            elif _synth.is_synth_symbol(symbol) and _source_name(source) != "synth":
                hint = " (hint: SYNTH* symbols need --source synth)"
            print(f"Market data unavailable for {symbol}{hint}: {exc}")
            raise SystemExit(1) from None

    def _fmt(value, need: int, have: int, decimals: int = 4) -> str:
        if value is None:
            return f"n/a (needs {need} bars, have {have})"
        return f"{value:.{decimals}f}"

    action = getattr(args, "finance_action", None)

    # -- quote -----------------------------------------------------------
    if action == "quote":
        symbol = str(getattr(args, "sym", "") or "").upper()
        source = getattr(args, "source", "stooq")
        bars = _bars_for(symbol, days=10, source=source)
        last = bars[-1]
        _provider, source_label = _provider_for(source)
        if getattr(args, "wsb", False):
            print(_wsb.wsb_quote(symbol, last.close, last.date, source_label))
            return
        payload = {
            "symbol": symbol,
            "date": last.date,
            "close": last.close,
            "day_high": last.high,
            "day_low": last.low,
            "volume": last.volume,
        }
        if getattr(args, "json", False):
            print(_json.dumps(payload, indent=2))
        else:
            print(f"{symbol}  close ${last.close:,.2f}  ({last.date})")
            print(
                f"  day range ${last.low:,.2f} – ${last.high:,.2f}  "
                f"volume {last.volume:,.0f}"
            )
            print(f"  source: {source_label}")
        return

    # -- indicators -------------------------------------------------------
    if action == "indicators":
        symbol = str(getattr(args, "sym", "") or "").upper()
        source = getattr(args, "source", "stooq")
        bars = _bars_for(symbol, source=source)
        closes = [b.close for b in bars]
        last = bars[-1]
        n = len(closes)
        sma20 = _indicators.sma(closes, 20)[-1]
        ema12 = _indicators.ema(closes, 12)[-1]
        ema26 = _indicators.ema(closes, 26)[-1]
        rsi14 = _indicators.rsi(closes, 14)[-1]
        macd_res = _indicators.macd(closes)
        macd_line = macd_res["macd_line"][-1]
        macd_signal = macd_res["signal_line"][-1]
        macd_hist = macd_res["histogram"][-1]
        bands = _indicators.bollinger(closes, 20, 2.0)
        bb_upper = bands["upper"][-1]
        bb_middle = bands["middle"][-1]
        bb_lower = bands["lower"][-1]
        atr14 = _indicators.atr(bars, 14)[-1]
        stoch = _indicators.stochastic(bars)
        stoch_k = stoch["k"][-1]
        stoch_d = stoch["d"][-1]
        obv_val = _indicators.obv(bars)[-1]
        adx_res = _indicators.adx(bars)
        adx14 = adx_res["adx"][-1]
        plus_di14 = adx_res["plus_di"][-1]
        minus_di14 = adx_res["minus_di"][-1]
        vwap_val = _indicators.vwap(bars)[-1]
        regime = _indicators.classify_regime(bars)
        print(
            f"══ {symbol} indicators — latest bar {last.date}, "
            f"close ${last.close:,.2f} ══"
        )
        print(f"  SMA20            {_fmt(sma20, 20, n)}")
        print(f"  EMA12            {_fmt(ema12, 12, n)}")
        print(f"  EMA26            {_fmt(ema26, 26, n)}")
        print(f"  RSI14            {_fmt(rsi14, 15, n, decimals=1)}")
        print(f"  MACD line        {_fmt(macd_line, 26, n)}")
        print(f"  MACD signal      {_fmt(macd_signal, 34, n)}")
        print(f"  MACD histogram   {_fmt(macd_hist, 34, n)}")
        print(
            f"  Bollinger 20     upper {_fmt(bb_upper, 20, n)}  "
            f"middle {_fmt(bb_middle, 20, n)}  lower {_fmt(bb_lower, 20, n)}"
        )
        print(f"  ATR14            {_fmt(atr14, 14, n)}")
        print(
            f"  Stoch %K/%D      {_fmt(stoch_k, 14, n, decimals=1)} / "
            f"{_fmt(stoch_d, 16, n, decimals=1)}"
        )
        print(f"  OBV              {obv_val:,.0f}")
        print(f"  ADX14            {_fmt(adx14, 28, n, decimals=1)}")
        print(
            f"  +DI14/-DI14      {_fmt(plus_di14, 15, n, decimals=1)} / "
            f"{_fmt(minus_di14, 15, n, decimals=1)}"
        )
        print(f"  VWAP             {_fmt(vwap_val, 1, n)}")
        if regime["regime"] == "unknown":
            print(f"  Regime           n/a (needs 28 bars, have {n})")
        else:
            print(
                f"  Regime           {regime['regime']} "
                f"(ADX14 {regime['adx']:.1f}, ATR% {regime['atr_pct']:.2f})"
            )
        return

    # -- signal ------------------------------------------------------------
    if action == "signal":
        symbol = str(getattr(args, "sym", "") or "").upper()
        source = getattr(args, "source", "stooq")
        provider, _label = _provider_for(source)
        try:
            signal = _signals.generate_signal(symbol, provider=provider)
        except _market.MarketDataError as exc:
            # Never fabricate a signal from a failed fetch.
            print(f"Market data unavailable for {symbol}: {exc}")
            raise SystemExit(1) from None
        if getattr(args, "wsb", False):
            # WSB skin: the same Signal, rendered as a DD post.
            print(_wsb.dd_post(signal))
            return
        narrative = _signals.narrate(signal)
        if getattr(args, "json", False):
            print(
                _json.dumps(
                    {
                        "symbol": signal.symbol,
                        "direction": signal.direction,
                        "confidence": signal.confidence,
                        "rationale": signal.rationale,
                        "indicator_snapshot": signal.indicator_snapshot,
                        "generated_at": signal.generated_at,
                        "advisory": signal.advisory,
                        "narrative": narrative,
                    },
                    indent=2,
                )
            )
            return
        print(ADVISORY_BANNER)
        print(
            f"Signal for {signal.symbol}: {signal.direction.upper()}  "
            f"(confidence {signal.confidence:.2f})"
        )
        print("\nRationale:")
        for line in signal.rationale:
            print(f"  • {line}")
        print("\nIndicator snapshot:")
        for key, value in signal.indicator_snapshot.items():
            print(f"  {key}: {value}")
        print("\nNarrated:")
        for line in narrative.splitlines():
            print(f"  {line}")
        print("\n" + ADVISORY_BANNER)
        return

    # -- portfolio ----------------------------------------------------------
    if action == "portfolio":
        portfolio = _portfolio.load(_portfolio.DEFAULT_PATH)
        source = getattr(args, "source", "stooq")
        # Portfolio is deliberately resilient: a per-symbol fetch failure
        # values the position at average cost with a warning, never zeroed
        # and never a hard crash.  So this action uses the provider
        # directly instead of the hard-exiting _bars_for() helper.
        provider, _source_label = _provider_for(source)
        prices: dict[str, float] = {}
        fetch_failures: list[str] = []
        for symbol, pos in portfolio.positions.items():
            if pos.qty <= 0:
                continue
            try:
                bars = provider.daily_bars(symbol, days=10)
            except _market.MarketDataError:
                # Unknown symbols are valued at average cost downstream,
                # never zeroed; record the failure instead.
                fetch_failures.append(symbol)
                continue
            prices[symbol] = bars[-1].close
        summary = portfolio.summary(prices)
        positions = summary.get("positions", {})
        missing = [
            s
            for s in summary.get("warnings", [])
            if positions.get(s, {}).get("qty", 0) > 0
        ]
        if getattr(args, "json", False):
            if fetch_failures:
                summary["fetch_failures"] = fetch_failures
            print(_json.dumps(summary, indent=2))
            return
        if getattr(args, "wsb", False):
            # WSB skin: positions-or-ban ledger + gain/loss porn.
            print(_wsb.positions_or_ban(summary))
            print()
            print(_wsb.gain_loss_porn(summary))
            if missing:
                print(
                    "  warnings: could not fetch latest prices for "
                    + ", ".join(missing)
                    + " — valued at average cost, not zeroed"
                )
            return
        print("══ Paper portfolio (SIMULATED — no real money) ══")
        print(f"  cash: ${summary['cash']:,.2f}")
        for symbol, pos in positions.items():
            if pos.get("qty", 0) > 0:
                line = f"  {symbol}: qty {pos['qty']:g} @ avg ${pos['avg_cost']:,.2f}"
                if "unrealized_pnl" in pos:
                    line += f"  unrealized ${pos['unrealized_pnl']:+,.2f}"
                print(line)
        if not any(pos.get("qty", 0) > 0 for pos in positions.values()):
            print("  (no open positions — deposit and place paper orders to start)")
        print(f"  realized P&L:   ${summary.get('realized_pnl', 0.0):+,.2f}")
        print(f"  unrealized P&L: ${summary.get('unrealized_pnl', 0.0):+,.2f}")
        print(f"  market value:   ${summary.get('market_value', 0.0):,.2f}")
        print(f"  total P&L:      ${summary.get('total_pnl', 0.0):+,.2f}")
        if missing:
            print(
                "  warnings: could not fetch latest prices for "
                + ", ".join(missing)
                + " — valued at average cost, not zeroed"
            )
        return

    # -- order ---------------------------------------------------------------
    if action == "order":
        symbol = str(getattr(args, "sym", "") or "").upper()
        # Live trading is structurally impossible in this build. Refuse any
        # live-shaped request first — never let it fall through to a broker
        # silently, and never reach AlpacaConnector from this command.
        if getattr(args, "live", False) or _os.environ.get("LEVI_BROKER_LIVE"):
            print(
                "Live trading is NOT enabled in this build. The order was NOT placed."
            )
            print("This command can only ever place paper orders.")
            print("Enabling live trading would require (none of it is wired here):")
            print(
                "  1. a deliberate dependency decision with sign-off (blueprint §1.1)"
            )
            print(
                "  2. a wired AlpacaConnector transport (stdlib urllib or an approved SDK)"
            )
            print("  3. LEVI_ALPACA_KEY and LEVI_ALPACA_SECRET in the environment")
            print("  4. LEVI_BROKER_LIVE=1 (explicit opt-in)")
            print("  5. per-order human confirmation")
            print("Until all five hold, AlpacaConnector reports transport_not_wired:")
            print("live trading is structurally impossible in this build.")
            raise SystemExit(2)
        side = str(getattr(args, "side", "") or "").lower()
        try:
            qty = float(getattr(args, "qty", 0) or 0)
        except (TypeError, ValueError):
            qty = 0.0
        # HITL gate (blueprint §1.5): a paper order is still a consequential
        # action — without explicit --yes this command refuses to place it.
        if not getattr(args, "yes", False):
            print(
                "Order NOT placed: paper orders require an explicit --yes "
                "(HITL gate, blueprint §1.5)."
            )
            print(
                f"  Would have placed: {side or '?'} {qty:g} {symbol} "
                "@ latest Stooq close (paper)."
            )
            print("  Nothing was placed and nothing was saved.")
            print("  Re-run with --yes to confirm this paper order.")
            raise SystemExit(2) from None
        # Validate before touching anything.
        try:
            order = _broker.Order(symbol=symbol, qty=qty, side=side)
        except _broker.InvalidOrder as exc:
            print(f"Order NOT placed: {exc}")
            raise SystemExit(2) from None
        # Reference price comes from real market data — never invented.
        bars = _bars_for(symbol, days=10)
        ref_price = bars[-1].close
        # Paper only. AlpacaConnector is never reachable from this command.
        broker = _broker.PaperBroker()
        try:
            fill = broker.place_order(order, confirm=True, reference_price=ref_price)
        except (
            _broker.InvalidOrder,
            _broker.OrderNotConfirmed,
            _broker.NoReferencePrice,
        ) as exc:
            print(f"Order NOT placed: {exc}")
            raise SystemExit(2) from None
        portfolio = _portfolio.load(_portfolio.DEFAULT_PATH)
        try:
            portfolio.apply_fill(fill.symbol, fill.side, fill.qty, fill.fill_price)
        except ValueError as exc:
            print(f"Paper ledger rejected the fill: {exc}")
            print("Nothing was saved.")
            raise SystemExit(2) from None
        saved_path = portfolio.save(_portfolio.DEFAULT_PATH)
        print(fill)  # Fill.__str__ always says SIMULATED
        print(f"Applied to the paper ledger and saved: {saved_path}")
        print(f"Paper cash is now ${portfolio.cash:,.2f} (SIMULATED — no real money)")
        return

    # -- deposit --------------------------------------------------------------
    if action == "deposit":
        try:
            amount = float(getattr(args, "amount", 0) or 0)
        except (TypeError, ValueError):
            amount = 0.0
        portfolio = _portfolio.load(_portfolio.DEFAULT_PATH)
        try:
            portfolio.deposit(amount)
        except ValueError as exc:
            print(f"Deposit refused: {exc}")
            raise SystemExit(2) from None
        saved_path = portfolio.save(_portfolio.DEFAULT_PATH)
        print(
            f"Deposited ${amount:,.2f} into the PAPER portfolio "
            "(SIMULATED — no real money)."
        )
        print(f"Paper cash is now ${portfolio.cash:,.2f}  (saved: {saved_path})")
        return

    # --- WSB finance expansion actions (all paper-only) ---------------------

    # -- bet -----------------------------------------------------------------
    if action == "bet":
        symbol = str(getattr(args, "sym", "") or "").upper()
        source = getattr(args, "source", "stooq")
        side = str(getattr(args, "side", "") or "").lower()
        trader = str(getattr(args, "trader", "anon") or "anon")
        try:
            qty = float(getattr(args, "qty", 0) or 0)
        except (TypeError, ValueError):
            qty = 0.0
        try:
            horizon = int(getattr(args, "horizon", 30) or 0)
        except (TypeError, ValueError):
            horizon = 0
        # HITL gate (blueprint §1.5): a paper bet is still a consequential
        # action — without explicit --yes this command refuses to place it.
        if not getattr(args, "yes", False):
            print(
                "Bet NOT placed: paper bets require an explicit --yes "
                "(HITL gate, blueprint §1.5)."
            )
            print(
                f"  Would have placed: {side or '?'} {qty:g} {symbol} "
                f"for {trader} (paper)."
            )
            print("  Nothing was placed and nothing was saved.")
            print("  Re-run with --yes to confirm this paper bet.")
            raise SystemExit(2) from None
        # Entry price comes from real market data (or seeded synthetic
        # bars) — never invented.
        bars = _bars_for(symbol, days=10, source=source)
        entry_price = bars[-1].close
        ledger = _bets.BetLedger.load(_bets.DEFAULT_BETS_PATH)
        try:
            bet = ledger.place(
                trader=trader,
                symbol=symbol,
                side=side,
                qty=qty,
                entry_price=entry_price,
                horizon_days=horizon,
                source=_source_name(source),
            )
        except _bets.InvalidBet as exc:
            print(f"Bet NOT placed: {exc}")
            raise SystemExit(2) from None
        saved_path = ledger.save(_bets.DEFAULT_BETS_PATH)
        print(_bets.BetLedger.ticket(bet))
        print(f"Recorded in the paper bet ledger (saved: {saved_path})")
        return

    # -- bets ----------------------------------------------------------------
    if action == "bets":
        trader = getattr(args, "trader", None)
        ledger = _bets.BetLedger.load(_bets.DEFAULT_BETS_PATH)
        open_bets = ledger.open_bets(trader)
        settled = ledger.settled_bets(trader)
        score = ledger.win_rate(trader)
        hands = ledger.hands_stats()
        if getattr(args, "json", False):
            print(
                _json.dumps(
                    {
                        "trader": trader,
                        "open": [b.to_dict() for b in open_bets],
                        "settled": [b.to_dict() for b in settled],
                        "win_rate": score,
                        "hands": hands,
                        "paper_only": True,
                    },
                    indent=2,
                )
            )
            return
        who = f" for {trader}" if trader else ""
        print(f"🎰 PAPER BETS{who} (SIMULATED — no real money)")
        for bet in open_bets:
            print(
                f"  OPEN   {bet.id}  {bet.trader}  {bet.side} {bet.qty:g} "
                f"{bet.symbol} @ ${bet.entry_price:,.2f}  ({bet.horizon_days}d)"
            )
        for bet in settled:
            hands_tag = "💎" if not bet.early_exit else "🧻"
            print(
                f"  SETTLD {bet.id}  {bet.trader}  {bet.side} {bet.qty:g} "
                f"{bet.symbol}  P&L {_signed_money(bet.pnl or 0)} {hands_tag}"
            )
        if not open_bets and not settled:
            print("  (no paper bets yet — place one with `levi finance bet`)")
        wr = score["win_rate"]
        print(
            f"  win rate: {wr:.1%} ({score['wins']}/{score['bets']})"
            if wr is not None
            else "  win rate: n/a (no settled bets)"
        )
        dh, ph = hands["diamond_hands"], hands["paper_hands"]
        dh_wr = "n/a" if dh["win_rate"] is None else f"{dh['win_rate']:.0%}"
        ph_wr = "n/a" if ph["win_rate"] is None else f"{ph['win_rate']:.0%}"
        print(f"  💎 diamond hands: {dh['bets']} bets, {dh_wr} win")
        print(f"  🧻 paper hands:   {ph['bets']} bets, {ph_wr} win")
        return

    # -- settle ---------------------------------------------------------------
    if action == "settle":
        bet_id = str(getattr(args, "bet_id", "") or "")
        try:
            exit_price = float(getattr(args, "price", 0) or 0)
        except (TypeError, ValueError):
            exit_price = 0.0
        early = bool(getattr(args, "paper_hands", False))
        ledger = _bets.BetLedger.load(_bets.DEFAULT_BETS_PATH)
        try:
            bet = ledger.settle(bet_id, exit_price, early=early)
        except (_bets.BetNotFound, _bets.BetAlreadySettled, _bets.InvalidBet) as exc:
            print(f"Bet NOT settled: {exc}")
            raise SystemExit(2) from None
        saved_path = ledger.save(_bets.DEFAULT_BETS_PATH)
        print(_bets.BetLedger.ticket(bet))
        print(f"Settled in the paper bet ledger (saved: {saved_path})")
        return

    # -- leaderboard -----------------------------------------------------------
    if action == "leaderboard":
        ledger = _bets.BetLedger.load(_bets.DEFAULT_BETS_PATH)
        rows = _leaderboard.build_leaderboard(ledger.bets)
        if getattr(args, "json", False):
            print(
                _json.dumps(
                    {
                        "rows": _leaderboard.ranked_leaderboard(rows),
                        "paper_only": True,
                    },
                    indent=2,
                )
            )
            return
        print(_leaderboard.render_leaderboard(rows))
        return

    # -- copytrade ---------------------------------------------------------------
    if action == "copytrade":
        follow = str(getattr(args, "follow", "") or "")
        try:
            capital = float(getattr(args, "capital", 10000.0) or 0)
        except (TypeError, ValueError):
            capital = 0.0
        ledger = _bets.BetLedger.load(_bets.DEFAULT_BETS_PATH)
        if getattr(args, "all", False):
            reports = _copytrade.compare_traders(ledger.bets, capital=capital)
            if getattr(args, "json", False):
                print(_json.dumps({"reports": reports, "paper_only": True}, indent=2))
                return
            if not reports:
                print(
                    "No paper trader has enough settled bets to rank "
                    "(need 3+). Paper only."
                )
                return
            for report in reports:
                print(_copytrade.render_copy_report(report))
                print()
            return
        try:
            report = _copytrade.mirror_report(ledger.bets, follow, capital=capital)
        except (_copytrade.NoSettledBets, ValueError) as exc:
            print(f"Copy simulation NOT run: {exc}")
            raise SystemExit(2) from None
        if getattr(args, "json", False):
            print(_json.dumps({**report, "paper_only": True}, indent=2))
            return
        print(_copytrade.render_copy_report(report))
        return

    # -- broker-link --------------------------------------------------------------
    if action == "broker-link":
        bl_action = getattr(args, "broker_link_action", None)
        if bl_action == "status":
            st = _brokerlink.broker_link_status(
                link_path=_brokerlink.DEFAULT_LINK_PATH,
                drafts_path=_brokerlink.DEFAULT_DRAFTS_PATH,
            )
            print("🔌 BROKER LINK — DRAFT ONLY (live structurally refused)")
            print(f"  platform: {st['platform'] or '(not configured)'}")
            _warn_link_corrupt(st["config_state"])
            if st["platform_label"]:
                print(f"  label:    {st['platform_label']}")
            print(f"  mode:     {st['mode']}")
            print(f"  live:     {st['live_execution']}")
            print(f"  keys:     {st['credentials_requested']}")
            print(
                f"  drafts:   {st['drafts_pending']} pending / "
                f"{st['drafts_total']} total"
            )
            return
        if bl_action == "configure":
            platform = str(getattr(args, "platform", "") or "")
            try:
                cfg = _brokerlink.configure_broker_link(
                    platform, path=_brokerlink.DEFAULT_LINK_PATH
                )
            except _brokerlink.InvalidDraft as exc:
                print(f"Broker link NOT configured: {exc}")
                raise SystemExit(2) from None
            print(
                f"Broker link configured for {cfg.platform} "
                f"({_brokerlink.SUPPORTED_PLATFORMS[cfg.platform]}) — "
                "draft-only. No keys requested, nothing connected."
            )
            return
        if bl_action == "draft":
            symbol = str(getattr(args, "sym", "") or "").upper()
            side = str(getattr(args, "side", "") or "").lower()
            try:
                qty = float(getattr(args, "qty", 0) or 0)
            except (TypeError, ValueError):
                qty = 0.0
            source = getattr(args, "source", "stooq")
            price = getattr(args, "price", None)
            if price is None:
                # Reference price from market data — never invented.
                bars = _bars_for(symbol, days=10, source=source)
                price = bars[-1].close
                print(f"  reference price ${price:,.2f} (latest {source} bar)")
            cfg, link_state = _load_link_config()
            _warn_link_corrupt(link_state)
            try:
                drafts = _brokerlink.prepare_drafts(
                    [
                        {
                            "symbol": symbol,
                            "side": side,
                            "qty": qty,
                            "reference_price": float(price),
                        }
                    ],
                    cfg,
                    path=_brokerlink.DEFAULT_DRAFTS_PATH,
                )
            except (_brokerlink.InvalidDraft, ValueError) as exc:
                print(f"Draft NOT prepared: {exc}")
                raise SystemExit(2) from None
            for draft in drafts:
                print(draft.render())
            return
        print("Usage: levi finance broker-link <status|configure|draft>")
        print("  live execution is structurally refused — drafts are review-only.")
        raise SystemExit(2)

    if action is None:
        print(
            "Usage: levi finance "
            "<quote|indicators|signal|portfolio|order|deposit|bet|bets|settle|"
            "leaderboard|copytrade|broker-link>"
        )
        print(
            "  levi finance quote <SYM> [--source stooq|binance|synth] [--wsb]  — latest close + day range"
        )
        print(
            "  levi finance indicators <SYM> [--source ...]  — SMA/EMA/RSI/MACD/Bollinger/ATR/Stoch/OBV/ADX/VWAP + regime snapshot"
        )
        print(
            "  levi finance signal <SYM> [--source ...] [--wsb]  — advisory signal, or --wsb for a DD post (paper-only, not financial advice)"
        )
        print(
            "  levi finance portfolio [--json] [--source ...] [--wsb]  — paper ledger: cash, positions, P&L"
        )
        print(
            "  levi finance order <SYM> <QTY> --side buy|sell [--yes]  — paper order (needs --yes)"
        )
        print(
            "  levi finance deposit <AMOUNT>               — fund the paper portfolio"
        )
        print(
            "  levi finance bet <SYM> <QTY> --side buy|sell [--trader NAME] [--horizon D] [--source ...] [--yes]  — paper YOLO bet (needs --yes)"
        )
        print(
            "  levi finance bets [--trader NAME] [--json]  — paper bets, win rate, diamond vs paper hands"
        )
        print(
            "  levi finance settle <BETID> --price <PX> [--paper-hands]  — settle an open paper bet"
        )
        print(
            "  levi finance leaderboard [--json]           — paper-trader leaderboard (SIMULATED)"
        )
        print(
            "  levi finance copytrade --follow <TRADER> [--capital X] [--all]  — simulated copy-trade forecast (paper-only)"
        )
        print(
            "  levi finance broker-link <status|configure|draft>  — draft-only broker link (live structurally refused)"
        )
        return

    print(f"Unknown finance action {action!r}")
    raise SystemExit(2)


def cmd_forge(args):
    """LEVI Forge — local-first code home. Pass-through to levi.forge CLI."""
    from levi.forge.__main__ import main as forge_main

    return forge_main(getattr(args, "forge_args", None) or [])


def _record_agent_ledger(task, transcript, provider) -> None:
    """Write one ``levi agent run`` into the decision ledger (phase 2).

    Telemetry only — never fatal to the agent run.
    """
    try:
        import uuid as _uuid
        from levi.control.ledger import LedgerWriter
        from levi.control.routing import classify_complexity

        task_id = _uuid.uuid4().hex[:12]
        complexity, _ = classify_complexity(task or "")
        ledger = LedgerWriter()
        ledger.record_task(task_id, objective=(task or "")[:2000], status="running")
        tools_used: list = []
        for step in getattr(transcript, "steps", []) or []:
            for call in getattr(step, "tool_calls", []) or []:
                name = call.get("name") if isinstance(call, dict) else None
                if name:
                    tools_used.append(name)
        ledger.record_step(
            task_id,
            agent="agent_cli",
            category="agent_run",
            task_class=complexity,
            model=str(
                getattr(provider, "name", None)
                or getattr(transcript, "provider_name", "")
            ),
            decision_summary=(
                "agent run via `levi agent run`; per-step rationales "
                "live in the transcript, not stored here"
            ),
            action=(task or "")[:2000],
            actual_result=str(
                getattr(transcript, "final", "") or getattr(transcript, "error", "")
            )[:2000],
            error=str(getattr(transcript, "error", "") or "")[:1000],
            outcome="ok" if getattr(transcript, "ok", False) else "failed",
            cost_units=float(len(tools_used)),
        )
        ledger.set_task_status(
            task_id,
            "ok" if getattr(transcript, "ok", False) else "failed",
            cost_units=float(len(tools_used)),
        )
    except Exception:
        pass  # ledger is telemetry, never load-bearing


def cmd_agent(args):
    """Agent runtime (blueprint §7): run a task through the step-level tool
    loop, list tools, or serve the agent over HTTP. Agent modules are
    imported lazily here so `levi` startup stays fast."""
    import sys as _sys

    action = getattr(args, "agent_action", None)

    def _levi_register_system() -> tuple[str | None, str | None]:
        """Validate --register and return (variant_id, system_prompt).

        Returns (None, None) when no --register was given. Exits 2 with the
        valid id list on an unknown id.
        """
        variant_id = getattr(args, "register", None) or ""
        variant_id = variant_id.strip()
        if not variant_id:
            return None, None
        from levi.persona.levi import get as _levi_get, all_variants, system_for

        variant = _levi_get(variant_id)
        if variant is None:
            valid = ", ".join(v.id for v in all_variants())
            print(f"Unknown LEVI register {variant_id!r}. Valid ids: {valid}")
            raise SystemExit(2)
        return variant.id, system_for(variant.id)

    def _attach_mcp(registry):
        """Merge configured external MCP servers' tools (never breaks startup)."""
        try:
            from levi.mcp.client import attach_mcp_tools as _attach

            attached = _attach(registry)
            if attached:
                print(f"MCP client: attached {', '.join(attached)}\n")
        except Exception as e:
            print(f"[levi:mcp] client attach failed: {e}")

    if action == "serve":
        from levi.agent.server import serve

        serve(
            host=getattr(args, "host", None) or "127.0.0.1",
            port=int(getattr(args, "port", None) or 8765),
        )
        return

    if action == "tools":
        from levi.agent.tools import build_default_registry

        registry = build_default_registry()
        print("══ Agent tools ══\n")
        for tool in registry.list():
            gate = " [requires confirmation]" if tool.requires_confirmation else ""
            print(f"  {tool.name}{gate}")
            print(f"    {tool.description[:110]}")
        print("\nGated tools need --yes on `levi agent run`, or an interactive yes.")
        return

    if action == "chat":
        from levi.agent.chat import run_chat_repl
        from levi.agent.providers import select_provider
        from levi.agent.tools import build_default_registry

        consent = bool(getattr(args, "yes", False))
        provider = select_provider(getattr(args, "provider", None) or None)
        registry = build_default_registry(
            workspace_root=getattr(args, "workspace", None) or None,
            consent=consent,
        )
        _attach_mcp(registry)
        register_id, register_system = _levi_register_system()
        if register_id:
            print(f"LEVI register: {register_id}\n")
        use_affect = bool(getattr(args, "affect", False))
        affect_session = None
        if use_affect:
            from levi.affect import SessionEI

            affect_session = SessionEI(
                register_id=(getattr(args, "register", None) or "levi")
            )
            print("Affect engine: ON (5D EI modulation, docs/AFFECT.md)\n")
            # Rebuild the registry so the affect_state tool shares the live tracker.
            from levi.agent.tools import build_default_registry as _bdr

            registry = _bdr(
                workspace_root=getattr(args, "workspace", None) or None,
                consent=consent,
                affect_tracker=affect_session,
            )
        run_chat_repl(
            getattr(args, "session", None) or "default",
            provider=provider,
            registry=registry,
            max_steps=int(getattr(args, "max_steps", None) or 10),
            consent=consent,
            workspace_root=getattr(args, "workspace", None) or None,
            system_prompt=register_system,
            affect=use_affect,
            affect_session=affect_session,
        )
        return

    if action == "model":
        from levi.agent import local_model, model_family

        maction = getattr(args, "agent_model_action", None)

        def _print_family(active_name):
            print(
                "== LEVI model family ==  (LEVI is the model; everything else is a selectable source)\n"
            )
            for info in model_family.entries():
                st = info["status"]
                mark = "*" if info["name"] == active_name else " "
                if st["downloaded"]:
                    state = "DOWNLOADED"
                    if info["kind"] == "remix" and not st["runner_present"]:
                        state = "downloaded, no runner"
                else:
                    state = "missing"
                extra = ", base %s" % info["base"] if info["kind"] == "remix" else ""
                mb = info["approx_bytes"] / 1e6
                print(
                    f" {mark} {info['name']:<10} [{info['kind']:<6}]  {state:<22} (~{mb:.0f}MB{extra})"
                )
                print(f"      {info['blurb']}")
            print("\n  * = active default (what the agent uses with no --provider)")

        def _print_other_sources():
            from levi.agent import providers as _pv

            oai = _pv.OpenAICompatibleProvider()
            ant = _pv.AnthropicProvider()
            print("== Other selectable sources ==\n")
            print(
                f"  openai     {'available' if oai.is_available() else 'not configured'}   (LEVI_OPENAI_API_KEY, or LEVI_OPENAI_BASE_URL for Ollama/vLLM)"
            )
            print(
                f"  anthropic  {'available' if ant.is_available() else 'not configured'}   (LEVI_ANTHROPIC_API_KEY)"
            )
            print(
                "  local      always available   (deterministic rules planner — the honest fallback)"
            )

        if maction == "list":
            resolved = model_family.resolve_family()
            _print_family(resolved["entry"] if resolved else None)
            print()
            _print_other_sources()
            print(
                "\nPick a source per run with --provider, or persist a LEVI weight with: levi agent model use <name>"
            )
            return
        if maction == "use":
            name = (getattr(args, "name", None) or "").strip()
            try:
                model_family.set_choice(name)
            except ValueError as exc:
                print(f"error: {exc}")
                raise SystemExit(2) from None
            print(f"Default LEVI weight set to '{name}'.")
            print("It takes effect once downloaded; until then the best available")
            print("LEVI weight is used (see `levi agent model status`).")
            return
        if maction == "status":
            from levi.agent import brain_provider

            resolved = model_family.resolve_family()
            active_name = resolved["entry"] if resolved else None
            print("== Active model ==\n")
            if resolved:
                print(f"  {resolved['entry']}  — {resolved['reason']}")
            else:
                print(
                    "  (no LEVI weight available — the deterministic rules planner fills in)"
                )
            print()
            _print_family(active_name)
            print()
            brain = brain_provider.NativeBrainProvider().status()
            print("-- levi-tiny: native brain detail --\n")
            if brain["weights_present"]:
                print(f"  Weights   : PRESENT  {Path(brain['weights']).name}")
                if brain["params"]:
                    print(f"  Params    : {brain['params']:,}")
                if brain["steps"]:
                    lf = f"{brain['loss_first']:.4f} -> " if brain["loss_first"] else ""
                    ll = f"{brain['loss_last']:.4f}" if brain["loss_last"] else "?"
                    print(f"  Training  : {brain['steps']} steps, loss {lf}{ll}")
            else:
                print("  Weights   : MISSING — no trained native brain yet")
                print("              Fix: train one — see docs/BRAIN_TRAINING.md")
            print(
                f"  torch     : {'AVAILABLE' if brain['torch_available'] else 'MISSING (pip install torch to run the brain)'}"
            )
            print(
                "  Limits    : prose continuations only — no tool calls; at tiny scale the"
            )
            print(
                "              output is fluent-ish gibberish with corpus flavor (docs/BRAIN_TRAINING.md)."
            )
            print(
                "              It earns the loop's default slot by growing, not by branding."
            )
            print()
            print("-- levi-* remixes: runner detail --\n")
            report = local_model.status_report()
            print(f"  Model dir : {report['model_dir']}")
            if report["weights"]:
                mb = (report["weights_bytes"] or 0) / 1e6
                sha = (report["weights_sha256"] or "")[:16]
                print(
                    f"  Weights   : PRESENT  {Path(report['weights']).name} "
                    f"({mb:.0f}MB{', sha256 ' + sha + '...' if sha else ''})"
                )
                native = report.get("weights_native_ctx")
                print(
                    f"  Context   : {report['ctx_size']} tokens"
                    f"{' (model native: %d; set LEVI_LOCAL_CTX_SIZE to change)' % native if native else ''}"
                )
            else:
                print("  Weights   : MISSING — no .gguf file in the model dir")
                print("              Pull one: levi agent model pull levi-0.6b")
            if report["runner"]:
                print(f"  Runner    : PRESENT  {report['runner']}")
            else:
                print(
                    "  Runner    : MISSING — llama-server not found (pull fetches it best-effort)"
                )
            print()
            _print_other_sources()
            return
        if maction == "pull":
            fam_name = (getattr(args, "name", None) or "").strip() or None
            legacy_key = getattr(args, "model", None)
            if fam_name:
                entry = model_family.get_entry(fam_name)
                if entry is None:
                    print(
                        f"Unknown model {fam_name!r} (known: {', '.join(model_family.family_names())})"
                    )
                    raise SystemExit(2)
                if entry["kind"] == "native":
                    print(
                        "levi-tiny is LEVI's native brain — it is trained, not downloaded."
                    )
                    print(
                        "See docs/BRAIN_TRAINING.md to train it; check status with: levi agent model status"
                    )
                    return
                model_key = entry["local_key"]
            else:
                model_key = legacy_key or local_model.DEFAULT_MODEL_KEY
            force = bool(getattr(args, "force", False))

            def _progress(done, total):
                if total:
                    pct = 100.0 * done / total
                    print(
                        f"\r  {done / 1e6:7.1f}MB / {total / 1e6:.1f}MB ({pct:5.1f}%)",
                        end="",
                        flush=True,
                    )
                else:
                    print(f"\r  {done / 1e6:7.1f}MB downloaded", end="", flush=True)

            spec = local_model.MODELS.get(model_key)
            if spec is None:
                print(
                    f"Unknown model {model_key!r} (known: {', '.join(sorted(local_model.MODELS))})"
                )
                raise SystemExit(2)
            if fam_name is None and legacy_key is None:
                print(
                    "LEVI family remixes (intelligence-per-RAM tradeoff — bigger is smarter, not magic):"
                )
                for info in model_family.entries():
                    if info["kind"] != "remix":
                        continue
                    key = info["local_key"]
                    s = local_model.MODELS[key]
                    mark = "  [default]" if key == local_model.DEFAULT_MODEL_KEY else ""
                    print(
                        f"  {info['name']}{mark}: {s['display']} (~{s['approx_bytes'] / 1e6:.0f}MB, base {info['base']})"
                    )
                    print(f"      {s['blurb']}")
                    print(f"      {s['ram_note']}")
                print()
            dest = Path(local_model.model_dir()) / spec["file"]
            if dest.is_file() and not force:
                print(f"Weights already present: {dest}")
                print("Use --force to re-download.")
            else:
                print(
                    f"Downloading {spec['display']} (~{spec['approx_bytes'] / 1e6:.0f}MB)..."
                )
                print(f"  {spec['ram_note']}")
                print(f"  {spec['url']}")
                try:
                    dest = local_model.download_weights(
                        model_key, force=force, progress=_progress
                    )
                except local_model.PullError as exc:
                    print(f"\npull failed: {exc}")
                    print(
                        "Partial files were cleaned up. Check your connection and retry; "
                        "nothing half-installed was left behind."
                    )
                    raise SystemExit(1) from None
                print(f"\nDownloaded: {dest}")
            print("\nRunner (llama-server):")
            runner, err = local_model.ensure_runner(progress=_progress)
            if runner:
                print(f"  OK: {runner}")
            else:
                print(f"  Could not fetch automatically.\n{err}")
            print("\nVerify with: levi agent model status")
            return
        print("Usage: levi agent model <list|status|pull|use>")
        print("  levi agent model list")
        print("  levi agent model status")
        print("  levi agent model pull [name] [--force]   (name: levi-0.6b | levi-4b)")
        print(
            "  levi agent model use <name>              (persist the default LEVI weight)"
        )
        return

    if action == "run":
        from levi.agent.loop import run_subtask
        from levi.agent.providers import select_provider
        from levi.agent.tools import build_default_registry

        task = getattr(args, "task", None) or ""
        if not task.strip():
            print(
                'Usage: levi agent run "<task>" [--provider local|levi-local|openai|anthropic] [--yes] [--max-steps N]'
            )
            raise SystemExit(2)
        consent = bool(getattr(args, "yes", False))

        def _confirm(preview: str) -> bool:
            # Interactive gate: prompt ONLY on a TTY; otherwise deny honestly.
            if not _sys.stdin.isatty():
                return False
            answer = input(f"{preview}\nApprove? [y/N]: ").strip().lower()
            return answer in ("y", "yes")

        provider = select_provider(getattr(args, "provider", None) or None)
        use_affect = bool(getattr(args, "affect", False))
        affect_session = None
        if use_affect:
            from levi.affect import SessionEI

            affect_session = SessionEI(
                register_id=(getattr(args, "register", None) or "levi")
            )
            print("Affect engine: ON (5D EI modulation, docs/AFFECT.md)\n")
        registry = build_default_registry(
            workspace_root=getattr(args, "workspace", None) or None,
            consent=consent,
            confirm=None if consent else _confirm,
            affect_tracker=affect_session,
        )
        print(
            f"Running with provider={getattr(provider, 'name', '?')} "
            f"consent={'yes (--yes)' if consent else 'no (gates will prompt/deny)'} ...\n"
        )
        _attach_mcp(registry)
        register_id, register_system = _levi_register_system()
        if register_id:
            print(f"LEVI register: {register_id}\n")
        transcript = run_subtask(
            task,
            provider=provider,
            registry=registry,
            consent=consent,
            confirm=None if consent else _confirm,
            max_steps=int(getattr(args, "max_steps", None) or 10),
            workspace_root=getattr(args, "workspace", None) or None,
            system_prompt=register_system,
            affect=use_affect,
            affect_session=affect_session,
        )
        _record_agent_ledger(task, transcript, provider)
        if getattr(args, "json", False):
            import json as _json

            print(_json.dumps(transcript.to_dict(), indent=2))
        else:
            for step in transcript.steps:
                print(f"── step {step.index + 1} ──")
                if step.provider_text:
                    print(f"  agent: {step.provider_text[:300]}")
                for call, result in zip(step.tool_calls, step.results, strict=False):
                    args_preview = {
                        k: (str(v)[:80]) for k, v in (call.get("args") or {}).items()
                    }
                    verdict = "ok" if result.get("ok") else "FAILED"
                    print(f"  tool {call.get('name')} {args_preview} → {verdict}")
                    if result.get("output"):
                        print(f"    out: {result['output'][:400]}")
                    if result.get("error"):
                        print(f"    err: {result['error'][:400]}")
            print(f"\n══ final ({'ok' if transcript.ok else 'FAILED'}) ══")
            print(transcript.final)
        if not transcript.ok:
            raise SystemExit(1)
        return

    print("Usage: levi agent <run|chat|tools|serve|model>")
    print(
        '  levi agent run "<task>" [--provider local|levi-local|openai|anthropic] [--yes] [--max-steps N] [--workspace DIR]'
    )
    print(
        "  levi agent chat [--session NAME] [--provider ...] [--yes] [--workspace DIR]"
    )
    print("  levi agent tools")
    print(
        "  levi agent serve [--host 127.0.0.1] [--port 8765]   (requires LEVI_AGENT_TOKEN)"
    )
    print("  levi agent model <list|status|pull|use>   (the LEVI model family)")
    raise SystemExit(2)


def cmd_builder(args):
    from levi.builder.emergency import EmergencyBuilder

    b = EmergencyBuilder()
    if getattr(args, "plan", None):
        job = b.plan(
            goal=args.plan,
            tier=getattr(args, "tier", None) or "E4",
            target=getattr(args, "target", None) or "independent",
            project_name=getattr(args, "name", None) or "new_project",
        )
        print(b.format_job(job))
        return
    if getattr(args, "apply", None):
        print(b.apply(args.apply, force=bool(getattr(args, "force", False))))
        return
    print(b.format_status())


def cmd_unified(args):
    """Unified LEVI Daemon Core — operating layer cycle."""
    from levi.daemon.unified import UnifiedDaemon

    d = UnifiedDaemon()
    if getattr(args, "clear_estop", False):
        d.kernel.clear_estop()
        print("E-stop cleared")
        return
    if getattr(args, "estop", False):
        d.kernel.emergency_stop(getattr(args, "reason", "") or "cli")
        print("EMERGENCY STOP engaged")
        return
    if getattr(args, "cycle", None):
        print(d.run_cycle(args.cycle, execute=bool(getattr(args, "execute", False))))
        return
    print(d.status())


def cmd_demand(args):
    from levi.demand.pulse import DemandPulse

    dp = DemandPulse()
    if getattr(args, "scan", None):
        s = dp.scan_seed(args.scan, segment=getattr(args, "segment", None) or "general")
        print(f"Signal [{s.id}] kind={s.kind}: {s.need[:80]}")
        if getattr(args, "title", None):
            if getattr(args, "five_factor", False):
                _cmd_demand_five_factor(dp, s.id, args)
            else:
                try:
                    o = dp.score_opportunity(
                        s.id,
                        args.title,
                        demand_score=float(getattr(args, "demand_score", 0.6) or 0.6),
                        serviceability=float(
                            getattr(args, "serviceability", 0.6) or 0.6
                        ),
                        startup_cost=float(getattr(args, "cost", 0.2) or 0.2),
                    )
                except ValueError as exc:
                    print(f"Opportunity scoring rejected: {exc}")
                    return
                print(f"Opportunity worth={o.worth:.2f}: {o.title}")
    elif getattr(args, "five_factor", False):
        print(
            'Five-factor scoring needs --scan "..." --title "..." plus the --ff-* factors.'
        )
    print(dp.format_status())


def _cmd_demand_five_factor(dp, demand_id, args):
    """Score one opportunity on the five-factor model from CLI flags."""
    from levi.demand.scoring import FACTORS, parse_weights

    flag_for = {
        "demand": "ff_demand",
        "market_size": "ff_market",
        "competition_gap": "ff_gap",
        "trend_velocity": "ff_velocity",
        "entry_feasibility": "ff_feasibility",
    }
    missing = [f for f in FACTORS if getattr(args, flag_for[f], None) is None]
    if missing:
        print(
            f"Five-factor scoring needs values for: {', '.join(missing)} "
            f"(flags --ff-demand/--ff-market/--ff-gap/--ff-velocity/--ff-feasibility, 0-100)."
        )
        return
    basis = getattr(args, "ff_basis", None)
    if not basis or not basis.strip():
        print(
            "Five-factor scoring needs --ff-basis: a note on why these scores were assigned."
        )
        return
    weights = None
    if getattr(args, "ff_weights", None):
        try:
            weights = parse_weights(args.ff_weights)
        except ValueError as e:
            print(f"Bad --ff-weights: {e}")
            return
    try:
        factor_vals = {}
        for f in FACTORS:
            raw = getattr(args, flag_for[f])
            try:
                val = float(raw)
            except (TypeError, ValueError):
                raise ValueError(
                    f"--ff-{f.replace('_', '-')} must be a number 0-100, got {raw!r}"
                )
            factor_vals[f] = (val, basis)
        try:
            threshold = float(getattr(args, "ff_threshold", 75.0) or 75.0)
        except (TypeError, ValueError):
            raise ValueError(
                f"--ff-threshold must be numeric, got {args.ff_threshold!r}"
            )
        card = dp.score_five_factor(
            demand_id,
            args.title,
            factor_vals,
            weights=weights,
            threshold=threshold,
        )
    except ValueError as e:
        print(f"Five-factor scoring rejected: {e}")
        return
    print(card.explain())


def cmd_income(args):
    from levi.income.factory import IncomeFactory

    fac = IncomeFactory()
    if getattr(args, "compose", None):
        plan = fac.compose(
            args.compose,
            service=getattr(args, "service", None) or "service modernization",
        )
        print(fac.format_plan(plan))
        return
    print(fac.format_status())


def cmd_memory_hierarchy(args):
    from levi.memory.hierarchy import hierarchy_status, explain_belief

    if getattr(args, "why", None):
        print(explain_belief(args.why))
        return
    print(hierarchy_status())


def cmd_brain(args):
    """Corpus, indexed table, recording export."""
    from levi.brain.corpus import Corpus
    from levi.brain.table import BrainTable
    from levi.brain.record import export_markdown

    action = getattr(args, "brain_action", "table") or "table"
    if getattr(args, "seed_expand", False):
        from levi.brain.seed_expand import expand_corpus, format_expand_info

        lim = int(getattr(args, "expand_limit", None) or 25000)
        print(format_expand_info(lim))
        print(expand_corpus(limit=lim))
        return
    if getattr(args, "seed_hyperdrive", False):
        from levi.brain.seed_hyperdrive import seed as seed_hd

        n = seed_hd()
        print(f"Hyperdrive corpus seed: {n} high-signal units.")
        return
    if getattr(args, "seed_knowledge", False):
        from levi.brain.seed_knowledge import seed as seed_k, format_index

        print(format_index())
        n = seed_k()
        print(f"Knowledge corpus seed: {n} units (A–Z, events, inventors, stars, X).")
        return
    # >>> LEVI Stage-1 lineage — seed path (source-sync entry `levi-ai`)
    if getattr(args, "seed_stage1", False):
        from levi.brain.seed_stage1 import format_index as fmt_s1
        from levi.brain.seed_stage1 import seed as seed_s1

        print(fmt_s1())
        n = seed_s1()
        print(f"Stage-1 corpus seed: {n} nano literacy units.")
        return
    # <<< LEVI Stage-1 lineage
    if getattr(args, "seed_knowledge_heavy", False):
        from levi.brain.seed_knowledge_heavy import (
            seed as seed_h,
            format_index as fmt_h,
        )

        print(fmt_h())
        n = seed_h()
        print(
            f"Heavy knowledge seed: {n} additional units (depth A–Z, cognition, wit rules)."
        )
        return
    if getattr(args, "seed_x100", False):
        from levi.brain.seed_knowledge_x100 import seed as seed_x, format_index as fmt_x

        print(fmt_x())
        n = seed_x()
        print(f"×100 knowledge seed: {n} units.")
        return
    if getattr(args, "seed_max", False):
        from levi.brain.seed_knowledge_max import seed as seed_m, format_index as fmt_m

        print(fmt_m())
        n = seed_m()
        print(f"MAX knowledge seed: {n} units.")
        return
    if getattr(args, "seed_expand2", False):
        from levi.brain.seed_expand2 import seed as seed_e2, format_index as fmt_e2

        print(fmt_e2())
        n = seed_e2()
        print(f"Expansion pack II: {n} units.")
        return
    if action == "atlas" or getattr(args, "seed_atlas", False):
        from levi.brain.seed_atlas import seed_corpus, format_atlas_index

        print(format_atlas_index())
        print(seed_corpus())
        return
    if action == "corpus":
        c = Corpus()
        q = getattr(args, "query", "") or ""
        if q:
            hits = c.search(q) if hasattr(c, "search") else []
            if hits:
                for h in hits[:12]:
                    print(
                        getattr(h, "text", h)[:200]
                        if not isinstance(h, str)
                        else h[:200]
                    )
                    print("---")
            else:
                print(c.format())
            return
        if getattr(args, "add", None):
            u = c.add(
                args.add,
                kind=getattr(args, "kind", None) or "OBSERVED",
                source=getattr(args, "source", "") or "",
            )
            print(f"Added [{u.id}] {u.kind}")
        print(c.format())
        return
    if action == "set":
        r = BrainTable().upsert(
            domain=getattr(args, "domain", None) or "general",
            key=getattr(args, "key", None) or "note",
            value=getattr(args, "value", None) or "",
            source=getattr(args, "source", "") or "",
        )
        print(f"Upserted [{r.id}] {r.domain}/{r.key}")
        return
    if action == "export":
        path = export_markdown()
        print(f"Exported: {path}")
        return
    print(BrainTable().format(query=getattr(args, "query", "") or ""))


def cmd_growth(args):
    """Raising baby Levi: the developmental learning loop.

    status (default) — growth dashboard: stage, cycles, learnings, pending
    cycle [--dry-run] [--no-model] — run one harvest→reflect→consolidate cycle
    journal [--limit N] — read the growth journal (baby book)
    learnings [--kind KIND] — list Levi's self-taught learnings
    forget (--id ID | --tag TAG) — remove learnings (parental control)
    curriculum [load|list] — ingest or list the founders' seed curriculum
    study [run|trend] — study hall: full cycle + self-quiz, or quiz trend
    pack [--build] [--ingest FILE] [--sync] [--pack-list] — learning-pack
        distribution: build versioned packs, ingest files, or sync from cloud
    export-corpus --out FILE [--min-confidence X] — export redacted,
        deduped learning texts as JSONL for the curriculum builder
    """
    from levi.growth import cycle as _cycle
    from levi.growth import journal as _journal
    from levi.growth import study as _study

    action = getattr(args, "growth_action", "status") or "status"

    if action == "status":
        s = _cycle.status()
        print("=== LEVI growth ===")
        print(f"stage: {s['stage']} — {s['stage_blurb']}")
        nxt = s.get("next_stage")
        if nxt:
            parts = ", ".join(
                f"{counter} {int(req['current'])}/{req['threshold']}"
                for counter, req in nxt["requirements"].items()
            )
            print(f"progress to {nxt['name']}: {parts}")
        else:
            print("progress: top stage reached — fully mature")
        print(f"cycles completed: {s['cycles_completed']}")
        print(f"learnings consolidated: {s['learnings_consolidated']}")
        if s["learnings_by_kind"]:
            kinds = ", ".join(
                f"{k}={v}" for k, v in sorted(s["learnings_by_kind"].items())
            )
            print(f"by kind: {kinds}")
        print(f"recent learnings (7d): {s.get('recent_learnings_7d', 0)}")
        jbytes = int(s.get("journal_bytes", 0) or 0)
        print(f"journal: {s.get('journal_records', 0)} records, {jbytes / 1024:.1f} KB")
        print(f"experiences pending: {s['experiences_pending']}")
        pending = s.get("pending_by_source") or {}
        by_origin = pending.get("by_origin") or {}
        if by_origin:
            parts = ", ".join(f"{k}={v}" for k, v in sorted(by_origin.items()))
            print(f"pending by source: {parts}")
        providers = pending.get("cloud_providers") or {}
        if providers:
            parts = ", ".join(f"{k}={v}" for k, v in sorted(providers.items()))
            print(f"cloud providers pending: {parts}")
        last = s["last_cycle"]
        if last:
            print(
                f"last cycle: {last['id']} at {last['ts']} "
                f"(mode={last['mode']}, accepted={last['accepted']})"
            )
        else:
            print("last cycle: none yet — run `levi growth cycle` to begin")
        print(f"growth dir: {s['growth_dir']}")
        return

    if action == "cycle":
        dry = bool(getattr(args, "dry_run", False))
        use_model = not bool(getattr(args, "no_model", False))
        print(
            "Running growth cycle"
            + (" (dry run — nothing will be written)" if dry else "")
            + (" (rules only)" if not use_model else "")
            + " …"
        )
        report = _cycle.run_cycle(use_model=use_model, dry_run=dry)
        print(
            f"cycle {report['cycle_id']}: "
            f"{report['experiences']} experiences, "
            f"mode={report['mode']}, "
            f"{report['learnings_proposed']} proposed → "
            f"{report['consolidation']['accepted']} accepted, "
            f"{report['consolidation']['corroborated']} corroborated, "
            f"{report['consolidation']['skipped']} skipped"
        )
        for learning in report["learnings"]:
            print(
                f"  [{learning['kind']}] ({learning['confidence']:.2f}) {learning['content'][:160]}"
            )
        if report["quiet"]:
            print("(quiet cycle — nothing new to learn from)")
        return

    if action == "journal":
        limit = int(getattr(args, "limit", 10) or 10)
        entries = _journal.read_entries(limit=limit)
        if not entries:
            print("The baby book is empty — no growth cycles yet.")
            return
        for e in entries:
            if e.get("kind") == "cycle":
                print(
                    f"{e.get('ts')} {e.get('id')}: "
                    f"{e.get('experiences', 0)} exp, mode={e.get('mode')}, "
                    f"accepted={e.get('accepted', 0)}, "
                    f"corroborated={e.get('corroborated', 0)}"
                    + (" (quiet)" if e.get("quiet") else "")
                )
            else:
                print(f"{e.get('ts')} {e.get('id')}: {e.get('kind')}")
        return

    if action == "learnings":
        from levi.memory.store import MemoryStore

        kind = (getattr(args, "kind", "") or "").strip().lower()
        entries = [e for e in MemoryStore().list(limit=5000) if "growth" in e.tags]
        if kind:
            entries = [e for e in entries if kind in e.tags]
        if not entries:
            print("No learnings consolidated yet.")
            return
        for e in entries[:50]:
            kinds = [
                t
                for t in e.tags
                if t in ("fact", "preference", "procedural", "correction")
            ]
            conf = (e.metadata or {}).get("confidence", e.importance)
            print(f"- [{e.id[:8]}] ({'/'.join(kinds) or 'learning'}, conf={conf})")
            print(f"  {e.content[:220]}")
        if len(entries) > 50:
            print(f"… and {len(entries) - 50} more")
        return

    if action == "forget":
        from levi.memory.store import MemoryStore

        store = MemoryStore()
        target_id = (getattr(args, "forget_id", "") or "").strip()
        tag = (getattr(args, "tag", "") or "").strip().lower()
        removed = 0
        if target_id:
            entries = [
                e
                for e in store.list(limit=5000)
                if "growth" in e.tags and e.id.startswith(target_id)
            ]
            for e in entries:
                if store.delete(e.id):
                    removed += 1
        elif tag:
            entries = [
                e
                for e in store.list(limit=5000)
                if "growth" in e.tags and tag in e.tags
            ]
            for e in entries:
                if store.delete(e.id):
                    removed += 1
        else:
            print("Specify --id <id> or --tag <tag> to forget.")
            return
        _journal.append_entry(
            {
                "kind": "forget",
                "removed": removed,
                "by_id": bool(target_id),
                "tag": tag or None,
            }
        )
        print(f"Forgot {removed} learning(s).")
        return

    if action == "curriculum":
        from levi.growth import curriculum as _curriculum

        sub = (getattr(args, "curriculum_action", "load") or "load").strip()
        if sub == "load":
            report = _curriculum.load_curriculum()
            print(
                f"curriculum: {report['total']} lessons — "
                f"{report['accepted']} accepted, "
                f"{report['corroborated']} already present, "
                f"{report['skipped']} skipped"
            )
            return
        if sub == "list":
            topics = _curriculum.curriculum_topics()
            total = sum(topics.values())
            print(f"curriculum: {total} seed lessons loaded")
            for topic, count in sorted(topics.items()):
                print(f"  {topic}: {count}")
            return
        print(f"Unknown curriculum action: {sub}")
        return

    if action == "study":
        # the study sub-action shares the curriculum_action positional slot
        sub = (getattr(args, "curriculum_action", "load") or "load").strip()
        if sub not in ("run", "trend"):
            sub = "run"  # bare `levi growth study`
        if sub == "run":
            use_model = bool(getattr(args, "study_model", False))
            dry = bool(getattr(args, "dry_run", False))
            print(
                "Running study hall"
                + (" (dry run — nothing will be written)" if dry else "")
                + (" (model reflection)" if use_model else " (rules only)")
                + " …"
            )
            report = _study.run_study(use_model=use_model, dry_run=dry)
            print(_study.format_study_report(report))
            return
        if sub == "trend":
            limit = int(getattr(args, "limit", 10) or 10)
            print(_study.format_trend(_study.study_trend(limit=limit)))
            return
        print(f"Unknown study action: {sub}")
        return

    if action == "pack":
        from levi.growth import sync as _sync

        if getattr(args, "build", False):
            min_corr = int(getattr(args, "min_corroboration", 0) or 0)
            report = _sync.build_pack(min_corroboration=min_corr)
            print(
                f"pack v{report['version']}: {report['entries']} technique(s), "
                f"{len(report['excluded'])} excluded"
            )
            print(f"  file: {report['path']}")
            print(f"  sha256: {report['manifest']['sha256'][:16]}…")
            for ex in report["excluded"][:10]:
                print(f"  excluded [{ex['id'][:8]}]: {ex['reason']}")
            if len(report["excluded"]) > 10:
                print(f"  … and {len(report['excluded']) - 10} more excluded")
            return

        if getattr(args, "ingest", ""):
            try:
                report = _sync.ingest_pack_file(args.ingest)
            except _sync.PackError as exc:
                print(f"ingest refused: {exc}")
                return
            print(
                f"ingested pack v{report['version']}: "
                f"{report['accepted']} new, {report['corroborated']} corroborated"
            )
            return

        if getattr(args, "sync", False):
            server = (
                (getattr(args, "server", "") or "").strip()
                or os.environ.get("LEVI_CLOUD_SERVER", "").strip()
                or "http://127.0.0.1:8765"
            )
            api_key = (
                (getattr(args, "api_key", "") or "").strip()
                or os.environ.get("LEVI_API_KEY", "").strip()
                or os.environ.get("LEVI_AGENT_TOKEN", "").strip()
            )
            if not api_key:
                print(
                    "sync needs an API key: --api-key, LEVI_API_KEY, or LEVI_AGENT_TOKEN"
                )
                return
            try:
                report = _sync.sync_from_server(server, api_key)
            except _sync.PackError as exc:
                print(f"sync failed: {exc}")
                return
            if report["status"] == "no-packs":
                print("server has published no learning packs yet")
            else:
                print(
                    f"synced pack v{report['version']}: "
                    f"{report['accepted']} new, {report['corroborated']} corroborated"
                )
            return

        # default: list installed packs
        installed = _sync.installed_packs()
        if not installed:
            print("No learning packs installed yet.")
            return
        for rec in installed:
            print(
                f"v{rec['version']}: {rec['entry_count']} technique(s), "
                f"ingested {rec['ingested_at']}, sha {rec['sha256'][:16]}…"
            )
        return

    if action == "export-corpus":
        from levi.growth import corpus_export as _export

        out = (getattr(args, "out", "") or "").strip()
        if not out:
            print("export-corpus needs --out FILE")
            return
        try:
            min_conf = float(getattr(args, "min_confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            print("--min-confidence must be a number between 0 and 1")
            return
        try:
            summary = _export.export_corpus(out, min_confidence=min_conf)
        except ValueError as exc:
            print(f"export-corpus refused: {exc}")
            return
        print(
            f"exported {summary['records']} learning(s) "
            f"(min_confidence={summary['min_confidence']}) → {summary['path']}"
        )
        return

    print(f"Unknown growth action: {action}")


def cmd_echo(args):
    from levi.organs.echo import run_echo, format_echo

    print(format_echo(run_echo(getattr(args, "seed", None) or "silence")))


def cmd_mandella(args):
    from levi.organs.mandella import run_mandella, format_mandella

    print(
        format_mandella(
            run_mandella(
                getattr(args, "domain", None) or "build",
                getattr(args, "seed", "") or "",
            )
        )
    )


def cmd_pulse(args):
    from levi.pulse.check import run_pulse

    print(run_pulse())


def cmd_relay(args):
    from levi.model.relay import ModelRelay

    r = ModelRelay()
    if getattr(args, "test", False):
        print(r.test())
        return
    print(r.status())


def cmd_news(args):
    """Current-events ingest: refresh / latest / search (dated recall)."""
    import json
    import subprocess
    import sys
    from pathlib import Path

    base = Path(__file__).resolve().parent.parent / "knowledge" / "news"
    action = getattr(args, "news_action", None) or "latest"

    if action == "refresh":
        script = base / "refresh.py"
        subprocess.run([sys.executable, str(script)])
        return

    days = base / "days"
    items: list[dict] = []
    if days.is_dir():
        for fp in sorted(days.glob("*.jsonl")):
            try:
                for line in fp.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        items.append(json.loads(line))
            except (OSError, ValueError):
                continue
    if not items:
        print("No ingested news yet — run: levi news refresh")
        return

    def fmt(it: dict) -> str:
        return (
            f"[{it.get('date', '?')}] ({it.get('source', '?')}) {it.get('title', '')}\n"
            f"    {it.get('summary', '')}\n    {it.get('url', '')}"
        )

    if action == "search":
        q = (getattr(args, "news_arg", None) or "").strip().lower()
        if not q:
            print("Usage: levi news search <query>")
            return
        terms = [t for t in q.split() if len(t) > 2]
        hits = [
            it
            for it in items
            if any(
                t in f"{it.get('title', '')} {it.get('summary', '')}".lower()
                for t in terms
            )
        ]
        hits.sort(key=lambda it: it.get("date", ""), reverse=True)
        print(f"{len(hits)} match(es) for {q!r} (dates shown — dated recall):")
        for it in hits[:20]:
            print(fmt(it))
        return

    # latest
    limit = getattr(args, "limit", 10) or 10
    items.sort(key=lambda it: it.get("date", ""), reverse=True)
    print(
        f"Latest ingested headlines (newest date: {items[0].get('date', '?')} — dated recall):"
    )
    for it in items[:limit]:
        print(fmt(it))


def cmd_capabilities(args):
    """Print the honest capability atlas (all or one domain)."""
    import json
    from pathlib import Path

    path = (
        Path(__file__).resolve().parent.parent
        / "knowledge"
        / "capabilities"
        / "atlas.json"
    )
    atlas = json.loads(path.read_text(encoding="utf-8"))
    domain = getattr(args, "domain", None)
    domains = atlas["domains"]
    if domain:
        domains = [d for d in domains if d["id"] == domain]
        if not domains:
            print(
                f"Unknown domain {domain!r}. Known: {', '.join(d['id'] for d in atlas['domains'])}"
            )
            return
    for d in domains:
        print(f"## {d['name']} [{d['id']}]")
        print(d["description"])
        print(f"Tools: {', '.join(d['tools'])}")
        print(f"Limits: {'; '.join(d['known_limits'])}\n")
    print(
        "Honesty rule: if it is not in this atlas or the tool list, the agent says so."
    )


def cmd_affect(args):
    """5D emotional-intelligence engine: detect affect or show the spec."""
    action = getattr(args, "affect_action", None) or "status"
    if action == "detect":
        from levi.affect import detect, evaluate, suggest_register

        text = getattr(args, "affect_arg", None) or ""
        if not text:
            print('Usage: levi affect detect "some text"')
            return
        r = detect(text)
        d = evaluate(text, r)
        s = suggest_register(text, r, d)
        print(
            f"dominant : {r.dominant} (valence {r.valence:+.2f}, "
            f"arousal {r.arousal:.2f}, confidence {r.confidence:.2f})"
        )
        print(f"stress   : {', '.join(r.stress_signals) or 'none'}")
        print(f"policy   : {d.reason}")
        print(f"register : {s.register_id} — {s.rationale}")
        print("Note: pattern-based heuristic, not felt emotion.")
        return
    # status — the honest spec summary
    print("══ LEVI affect engine — Goleman's 5 dimensions ══\n")
    print("  1. self_awareness  — LEVI tracks its own operating state")
    print("                       (register, confidence, stated limits).")
    print("  2. self_regulation — de-escalation policy: never mirrors")
    print("                       hostility; crisis routes to Care register.")
    print("  3. motivation      — frustration/repair signals feed the")
    print("                       growth loop as a drive to improve.")
    print("  4. empathy         — lexicon/heuristic affect perception")
    print("                       (valence, arousal, 6 emotion categories).")
    print("  5. social_skills   — affect-aware register selection across")
    print("                       the 14 LEVI registers + repair/rapport.")
    print("\nHonesty rule: this is pattern-based affect modeling, not felt")
    print("emotion. No sentience or subjective-experience claims — ever.")
    print("Full spec: docs/AFFECT.md")


# --- LEVI Boot Camp: 30-day 24/7 program (academy-owned block) ---
def cmd_academy(args):
    """LEVI Boot Camp: 30-day x 4-block training program status and sessions."""
    from levi.academy import run_session as rs

    action = getattr(args, "academy_action", None) or "status"
    if action == "status":
        syllabus = rs.load_syllabus()
        progress = rs.load_progress()
        done = progress.get("completed", [])
        per_track = {"A": 0, "B": 0, "C": 0, "S": 0}
        for sid in done:
            try:
                n = (int(sid[1:].split("b")[0]) - 1) * 4 + int(sid.split("b")[1])
                per_track[{1: "A", 2: "B", 3: "C", 0: "S"}[n % 4]] += 1
            except Exception:
                continue
        day = min(len(done) // 4 + 1, 30)
        phase = rs.week_phase_for(syllabus, day)
        try:
            from levi.academy import corpus_ingest as aci

            cstats = aci.corpus_stats()
        except Exception:
            cstats = {"records": 0, "chars": 0}
        try:
            from levi.academy import concepts as acon

            rstats = acon.retention_stats()
        except Exception:
            rstats = {}
        streaks = rs.get_streaks(progress)
        print("LEVI Boot Camp — 30-day 24/7 program")
        print(f"  day: {day}/30 ({phase})")
        print(f"  sessions completed: {len(done)}/120")
        for t in ("A", "B", "C", "S"):
            n = per_track[t]
            bar = "#" * (n * 30 // 30) + "-" * (30 - n * 30 // 30)
            name = syllabus["track_names"][t]
            print(f"  [{t}] {name:38s} [{bar}] {n}/30")
        print(
            "  pass streaks (current/best): "
            + "  ".join(
                f"{t} {streaks[t]['current']}/{streaks[t]['best']}"
                for t in ("A", "B", "C", "S")
            )
        )
        if rstats:
            print(
                "  retention — review drill hit rate "
                "(completion without retention is failure):"
            )
            for t in ("A", "B", "C", "S"):
                r = rstats.get(t, {})
                hr = r.get("hit_rate", 0.0)
                bar = "#" * int(hr * 20) + "-" * (20 - int(hr * 20))
                print(
                    f"    [{t}] [{bar}] {hr:.0%} "
                    f"({r.get('concepts', 0)} concepts, "
                    f"{r.get('reviewed', 0)} reviewed)"
                )
        pending = progress.get("pending_remedial")
        if pending:
            print(
                f"  ! pending remediation: day {pending['day']} block "
                f"{pending['block']} (attempt {pending.get('attempts', 0) + 1}) "
                f"— next run remediates before any new session"
            )
        print(
            f"  brain corpus: {cstats['records']} academy records, "
            f"{cstats['chars']:,} chars (post-mastery knowledge only)"
        )
        if progress.get("graduated"):
            print("  status: GRADUATED")
        return 0
    if action == "session":
        day = getattr(args, "day", None)
        block = getattr(args, "block", None)
        if day is None or block is None:
            print("Usage: levi academy session --day N --block M")
            return 2
        return rs.main(["--day", str(day), "--block", str(block)])
    print(f"Unknown academy action: {action}")
    return 2


# --- end academy-owned block ---


def cmd_lab(args):
    """LEVI Lab: on-device agentic AI demos, fixtures, footprint math."""
    from levi.lab import scenarios as lab_scen
    from levi.lab.footprint import footprint as lab_footprint_fn
    from levi.lab.footprint import format_footprint as lab_format_fp
    from levi.lab import models as lab_models
    from levi.lab import live as lab_live

    action = getattr(args, "lab_action", None) or "scenarios"
    arg = getattr(args, "lab_arg", None)

    if action == "scenarios":
        print("══ LEVI Lab scenarios ══\n")
        for sc in lab_scen.list_scenarios():
            fx = "captured" if lab_scen.load_fixture(sc.id) else "not captured"
            print(f"  {sc.id:15s} {sc.title}  [{fx}]")
        print("\n`levi lab run <id>` plays back the captured transcript;")
        print("add --live to execute the loop for real.")
        return

    if action == "run":
        if not arg:
            print("Usage: levi lab run <scenario-id> [--live]")
            return
        if getattr(args, "live", False):
            import tempfile

            workdir = tempfile.mkdtemp(prefix="levi-lab-")
            print(f"Running scenario {arg!r} live (workdir {workdir}) …")
            try:
                lab_scen.capture(arg, Path(workdir), live=True)
            except ValueError as exc:
                print(f"lab: {exc}")
                return
            print("Captured. Playback:\n")
        print(lab_scen.playback(arg))
        return

    if action == "footprint":
        try:
            fp = lab_footprint_fn(
                getattr(args, "params", "0.6B"),
                quant=getattr(args, "quant", "int4"),
                ctx=getattr(args, "ctx", "32k"),
            )
        except ValueError as exc:
            print(f"lab: {exc}")
            return
        print(lab_format_fp(fp))
        return

    if action == "card":
        if not arg:
            print("LEVI Lab model cards (models LEVI actually supports):")
            for key in lab_models.MODEL_CARDS:
                print(f"  {key}")
            print("Usage: levi lab card <model>")
            return
        card = lab_models.get_card(arg)
        if card is None:
            print(f"lab: no card for {arg!r} — LEVI doesn't support that model.")
            print("Known:", ", ".join(lab_models.MODEL_CARDS))
            return
        print(lab_models.format_card(arg.strip().lower(), card))
        return

    if action == "chat":
        endpoint = lab_live.resolve_endpoint(getattr(args, "endpoint", None))
        if not endpoint:
            print("lab: no endpoint. Pass --endpoint URL or set LEVI_LAB_ENDPOINT.")
            print(
                "Example: levi lab chat --endpoint http://localhost:8080 --model qwen3-0.6b"
            )
            print(
                "(Serve one with: levi agent model pull, then llama-server on :8080.)"
            )
            return
        model = getattr(args, "model", None) or "qwen3-0.6b"
        probe = lab_live.probe(endpoint)
        print(lab_live.format_probe(probe))
        if not probe["ok"]:
            return
        print(f"Chatting with {model} — empty line quits.\n")
        messages = [
            {
                "role": "system",
                "content": "You are LEVI, a local-first synthetic-intelligence assistant.",
            }
        ]
        while True:
            try:
                user = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not user:
                break
            messages.append({"role": "user", "content": user})
            res = lab_live.chat(endpoint, model, messages)
            if not res["ok"]:
                print(f"levi> [error] {res['error']}")
                messages.pop()
                continue
            print(f"levi> {res['text']}\n")
            messages.append({"role": "assistant", "content": res["text"]})
        return

    print(f"lab: unknown action {action!r}")


def cmd_vault(args):
    """Encrypt/decrypt local notes (passphrase required)."""
    from levi.vault.seal import VaultSeal
    import getpass

    pw = getattr(args, "passphrase", None) or ""
    if not pw:
        # Non-echoing prompt; avoids leaving the passphrase in shell history.
        pw = getpass.getpass("Vault passphrase: ")
    v = VaultSeal(pw)
    if getattr(args, "put", None) and getattr(args, "text", None) is not None:
        path = v.put(args.put, args.text)
        print(f"Sealed {path}")
        return
    if getattr(args, "get", None):
        print(v.get(args.get))
        return
    print("Vault names:", v.list_names())


def _cmd_cloud_keys(args):
    """`levi cloud keys create <name> [--no-learn]|list|revoke <name|prefix>|learn <name|prefix> on|off`."""
    from levi.cloud import apikeys

    rest = list(getattr(args, "cloud_args", None) or [])
    keys_action = rest[0].lower() if rest else ""
    flags = {a for a in rest if a.startswith("--")}
    positionals = [a for a in rest[1:] if not a.startswith("--")]
    target = positionals[0] if positionals else None
    if keys_action == "create":
        if not target:
            print("Usage: levi cloud keys create <name> [--no-learn]")
            raise SystemExit(2)
        learn = "--no-learn" not in flags and not bool(
            getattr(args, "cloud_no_learn", False)
        )
        try:
            raw, record = apikeys.create_key(target, learn=learn)
        except apikeys.KeyError as exc:
            print(f"Error: {exc}")
            raise SystemExit(1) from None
        # The raw key is printed ONCE and never stored. Warn loudly.
        print(raw)
        print()
        print(
            "API key created for %r (prefix %s)." % (record["name"], record["prefix"])
        )
        print("This is the ONLY time the full key is shown — copy it now.")
        print("It is stored as a SHA-256 hash only; it cannot be recovered.")
        print(
            "Growth learning: %s (change with `levi cloud keys learn %s off|on`)."
            % ("enabled" if record.get("learn", True) else "disabled", record["name"])
        )
        return
    if keys_action == "list":
        keys = apikeys.list_keys()
        if not keys:
            print("No API keys.")
            return
        for k in keys:
            status = "REVOKED" if k.get("revoked") else "active"
            learn = "learn" if k.get("learn", True) else "no-learn"
            print(
                f"  {k['name']:20} {k.get('prefix', '?'):14} "
                f"created {k.get('created', '?')}  {status}  {learn}"
            )
        return
    if keys_action == "revoke":
        if not target:
            print("Usage: levi cloud keys revoke <name|prefix>")
            raise SystemExit(2)
        try:
            record = apikeys.revoke_key(target)
        except apikeys.KeyError as exc:
            print(f"Error: {exc}")
            raise SystemExit(1) from None
        print("Revoked key %r (prefix %s)." % (record["name"], record["prefix"]))
        return
    if keys_action == "learn":
        if not target or (
            len(positionals) > 1 and positionals[1].lower() not in ("on", "off")
        ):
            print("Usage: levi cloud keys learn <name|prefix> on|off")
            raise SystemExit(2)
        want = positionals[1].lower() if len(positionals) > 1 else ""
        if want not in ("on", "off"):
            print("Usage: levi cloud keys learn <name|prefix> on|off")
            raise SystemExit(2)
        try:
            record = apikeys.set_learn(target, want == "on")
        except apikeys.KeyError as exc:
            print(f"Error: {exc}")
            raise SystemExit(1) from None
        print(
            "Key %r: growth learning %s."
            % (record["name"], "enabled" if record.get("learn") else "disabled")
        )
        return
    print(
        "Usage: levi cloud keys {create <name> [--no-learn]|list|revoke <name|prefix>|learn <name|prefix> on|off}"
    )
    raise SystemExit(2)


def _cmd_cloud_usage(args):
    """`levi cloud usage [--key NAME] [--limit N]`."""
    from levi.cloud import metering

    records = metering.read_usage(
        key_name=getattr(args, "cloud_key_filter", None),
        limit=getattr(args, "cloud_limit", None) or 20,
    )
    if not records:
        print("No usage recorded yet.")
        return
    for r in records:
        line = (
            f"  {r.get('ts', '?')}  {r.get('key_name', '?'):<16} "
            f"{r.get('endpoint', '?'):<16} steps={r.get('steps', 0)} "
            f"ok={r.get('ok', '?')}"
        )
        if not r.get("ok"):
            line += f" error={r.get('error')}"
        print(line)


def cmd_courses(args):
    """Awesome-courses curriculum knowledge base (ingested, extractive).

    Subcommands: `list [--subject SLUG]`, `brief <subject>`, `coverage`.
    All data comes from core/levi/knowledge/courses/ (catalog.json,
    briefs/, coverage.json) — counts are computed live, never hand-written.
    """
    import json
    from pathlib import Path

    base = Path(__file__).resolve().parent.parent / "knowledge" / "courses"
    catalog_p = base / "catalog.json"
    if not catalog_p.exists():
        print("Curriculum not ingested yet.")
        print("Run: python3 core/levi/knowledge/courses/ingest.py")
        return
    catalog = json.loads(catalog_p.read_text(encoding="utf-8"))
    action = getattr(args, "courses_action", None) or "list"

    if action == "brief":
        slug = (getattr(args, "subject", None) or "").strip().lower().replace("_", "-")
        if not slug:
            print("Usage: levi courses brief <subject>")
            print("Subjects:", ", ".join(s["slug"] for s in catalog["subjects"]))
            return
        brief_p = base / "briefs" / f"{slug}.md"
        if not brief_p.is_file():
            print(
                f"No field guide for {slug!r} yet — run build_briefs.py after ingesting."
            )
            return
        print(brief_p.read_text(encoding="utf-8"))
        return

    if action == "coverage":
        cov_p = base / "coverage.json"
        if not cov_p.exists():
            print("No coverage.json yet — run ingest.py first.")
            return
        records = json.loads(cov_p.read_text(encoding="utf-8"))
        from collections import Counter

        total = Counter(r["status"] for r in records)
        print("══ Curriculum coverage (from coverage.json) ══\n")
        print(f"  cataloged courses : {len(records)}")
        for status in ("ok", "dead", "skipped-video", "skipped-binary"):
            n = total.get(status, 0)
            print(f"  {status:14s}: {n}")
        print("\n  by subject:")
        for subj in catalog["subjects"]:
            c = Counter(r["status"] for r in records if r["subject"] == subj["slug"])
            print(
                f"    {subj['slug']:32s} ok={c.get('ok', 0):3d} "
                f"dead={c.get('dead', 0):3d} video={c.get('skipped-video', 0):3d} "
                f"bin={c.get('skipped-binary', 0):3d}"
            )
        chars = sum(
            int((r.get("detail") or "0").split()[0])
            for r in records
            if r["status"] == "ok"
        )
        print(
            f"\n  ingested text: ~{chars:,} chars across "
            f"{sum(1 for r in records if r['status'] == 'ok')} course pages"
        )
        return

    # action == "list"
    filt = (
        (getattr(args, "subject_filter", None) or "").strip().lower().replace("_", "-")
    )
    for subj in catalog["subjects"]:
        if filt and subj["slug"] != filt:
            continue
        print(f"══ {subj['name']} [{subj['slug']}] — {len(subj['courses'])} courses")
        if filt:
            for c in subj["courses"]:
                print(f"  - {c['title']} ({c['school'] or 'n/a'})")
                print(f"    {c['primary']}")
    if not filt:
        total = sum(len(s["courses"]) for s in catalog["subjects"])
        print(
            f"\n{total} courses across {len(catalog['subjects'])} subjects. "
            f"Use --subject <slug> to expand one."
        )


def cmd_security(args):
    """Offline defensive security knowledge index (topic names only, original prose).

    Subcommands: `list`, `search <query>`, `show <id>`.
    All data comes from core/levi/knowledge/security/catalog.json — 81 domains
    derived from the Awesome-Hacking meta-list's category names, each written
    fresh with defensive blue-team framing (detection + hardening, no
    attack how-tos). Works with zero network access.
    """
    from levi.knowledge.security.catalog import CatalogError, load_catalog

    try:
        catalog = load_catalog()
    except CatalogError as exc:
        print(f"Security index unavailable: {exc}")
        return
    entries = catalog.domains
    action = getattr(args, "security_action", None) or "list"

    if action == "search":
        q = (getattr(args, "query", None) or "").strip().lower()
        if not q:
            print("Usage: levi security search <query>")
            return
        hits = [
            e
            for e in entries
            if q in e.name.lower()
            or q in e.defensive_summary.lower()
            or q in e.detection_notes.lower()
            or q in e.hardening_notes.lower()
            or any(q in c.lower() for c in e.key_concepts)
        ]
        if not hits:
            print(f"No security domains match {q!r}.")
            return
        print(f"══ {len(hits)} match(es) for {q!r} ══")
        for e in hits:
            print(f"  {e.id:44s} {e.name}")
        return

    if action == "show":
        sid = (getattr(args, "query", None) or "").strip().lower().replace("_", "-")
        if not sid:
            print("Usage: levi security show <id>")
            return
        entry = next((e for e in entries if e.id == sid), None)
        if entry is None:
            print(f"Unknown security domain {sid!r}.")
            print("Use: levi security list")
            return
        print(f"══ {entry.name} [{entry.id}] ══\n")
        print(entry.defensive_summary + "\n")
        if entry.attack_relevant and entry.attack_profile:
            print("-- attack profile (threat knowledge, not instructions) --")
            print(entry.attack_profile + "\n")
        print("-- detection --")
        print(entry.detection_notes + "\n")
        print("-- hardening --")
        print(entry.hardening_notes + "\n")
        print("-- key concepts --")
        print("  " + ", ".join(entry.key_concepts) + "\n")
        print(f"-- reference --\n  {entry.reference or '(unlisted)'}")
        return

    # action == "list"
    for e in entries:
        print(f"  {e.id:44s} {e.name}")
    print(
        f"\n{len(entries)} security domains. "
        "Use: levi security search <query> | levi security show <id>"
    )


def cmd_bounty(args):
    """Bug-bounty recon pipeline — scoped, polite, recon-only.

    Subcommands:
      scope add|remove|list     manage enrolled program scopes
      recon <domain>            run enum -> probe -> content -> store
      findings [--new]          list stored findings (optionally only new)
      monitor --once            recon every enrolled scope, print only new
    """
    from levi.bounty.pipeline import run_monitor, run_recon
    from levi.bounty.scope import ScopeError, ScopeStore
    from levi.bounty.store import FindingStore

    cmd = getattr(args, "bounty_cmd", None) or "findings"

    if cmd == "scope":
        store = ScopeStore()
        scmd = getattr(args, "scope_cmd", None) or "list"
        if scmd == "add":
            dom = getattr(args, "domain", None)
            if not dom:
                print("Usage: levi bounty scope add <domain>")
                return
            try:
                added = store.add(dom)
            except ValueError as exc:
                print(f"scope add refused: {exc}")
                return
            print(f"Scope enrolled: {added}")
            print("Recon is authorized for this domain and its subdomains only.")
        elif scmd == "remove":
            dom = getattr(args, "domain", None)
            if not dom:
                print("Usage: levi bounty scope remove <domain>")
                return
            try:
                ok = store.remove(dom)
            except ValueError as exc:
                print(f"scope remove refused: {exc}")
                return
            print(f"Scope removed: {dom}" if ok else f"Not enrolled: {dom}")
        else:  # list
            doms = store.list()
            if not doms:
                print("No scopes enrolled. Use: levi bounty scope add <domain>")
                return
            print("Enrolled scopes (domain + subdomains):")
            for d in doms:
                print(f"  {d}")
        return

    if cmd == "recon":
        dom = getattr(args, "domain", None)
        if not dom:
            print("Usage: levi bounty recon <domain> [--ports 80,443,...]")
            return
        ports = None
        praw = getattr(args, "ports", None)
        if praw:
            try:
                ports = [int(p) for p in str(praw).split(",") if p.strip()]
            except ValueError:
                print(
                    "Invalid --ports (expected comma-separated integers, e.g. --ports 80,443)."
                )
                return
            bad = [p for p in ports if not 1 <= p <= 65535]
            if bad:
                print(f"Invalid --ports: port numbers must be 1-65535, got {bad}.")
                return
        try:
            report = run_recon(dom, ports=ports)
        except ScopeError as exc:
            print(f"SCOPE REFUSED: {exc}")
            return
        except ValueError as exc:
            print(f"Invalid target: {exc}")
            return
        print(f"══ recon {report['domain']} [scope: {report['scope']}] ══")
        print(f"  subdomains alive : {len(report['subdomains'])}")
        print(f"  hosts probed     : {report['hosts_probed']}")
        print(f"  findings new     : {report['findings_new']}")
        print(f"  findings total   : {report['findings_total']}")
        if report["errors"]:
            print("  errors:")
            for e in report["errors"][:5]:
                print(f"    - {e}")
        return

    if cmd == "monitor":
        try:
            result = run_monitor()
        except Exception as exc:
            print(f"monitor failed: {exc}")
            return
        new = result["new_findings"]
        if not new:
            print("monitor: no new findings since last run.")
            return
        print(f"══ monitor: {len(new)} new finding(s) ══")
        for f in new:
            print(f"  [{f['kind']}] {f['target']}: {f['detail'][:100]}")
        return

    # cmd == "findings" (default)
    fstore = FindingStore()
    items = (
        fstore.new_since_last_run() if getattr(args, "new", False) else fstore.list()
    )
    if not items:
        print(
            "No findings stored yet. Enroll a scope, then: levi bounty recon <domain>"
        )
        return
    label = "new findings" if getattr(args, "new", False) else "findings"
    print(f"══ {len(items)} {label} ══")
    for f in items:
        print(f"  [{f.kind:16s}] {f.target}: {f.detail[:110]}")
        if f.kind == "possible_exposure":
            print(f"      evidence: {f.evidence}")


def cmd_console(args):
    """Interactive text dashboard — menu-driven, built on the ux effects kit.

    Every screen calls existing module functions only; the console adds no
    new capabilities. Requires an interactive terminal.
    """
    from levi.console.app import run

    raise SystemExit(run())


def cmd_sim(args):
    """Bounded text simulations — clearly labeled, deterministic, zero network."""
    from levi.sim import SCENARIOS, run_scenario

    if getattr(args, "list", False) or not getattr(args, "scenario", None):
        print("Available simulations (all clearly labeled SIMULATION, zero network):")
        for name, fn in SCENARIOS.items():
            doc = (fn.__doc__ or "").strip().splitlines()
            blurb = doc[0] if doc else ""
            print(f"  {name:16s} {blurb}")
        print("\nUsage: levi sim <scenario> [--seed N]")
        return
    name = args.scenario
    if name not in SCENARIOS:
        print(f"Unknown scenario {name!r}. See: levi sim --list")
        return
    raise SystemExit(run_scenario(name, seed=getattr(args, "seed", None)))


def cmd_project(args):
    """Pre-MVP service capability-discovery phase runner + HITL + capability log."""
    from levi.project.phases import PhaseRunner
    from levi.project.hitl import HITLGate

    r = PhaseRunner()
    action = getattr(args, "project_action", None) or "status"
    if getattr(args, "url", None):
        r.set_url(args.url)
        print(f"URL set: {args.url}")
    if (
        action in ("status", None)
        and not getattr(args, "run", None)
        and not getattr(args, "complete", None)
    ):
        if not getattr(args, "url", None):
            print(r.status())
        else:
            print(r.status())
        return
    if getattr(args, "run", None):
        print(r.run_phase(args.run))
        return
    if getattr(args, "complete", None):
        print(r.complete(args.complete))
        print(r.status())
        return
    if getattr(args, "log_text", None):
        print(r.add_log_note(args.log_text, skill=getattr(args, "skill", "") or ""))
        return
    if action == "log":
        print(r.log.format())
        return
    if action == "hitl":
        g = HITLGate()
        if getattr(args, "approve", None):
            req = g.decide(args.approve, "approve", getattr(args, "note", "") or "")
            print(f"Approved {req.id}")
            return
        if getattr(args, "deny", None):
            req = g.decide(args.deny, "deny", getattr(args, "note", "") or "")
            print(f"Denied {req.id}")
            return
        print(g.format_pending())
        return
    if action == "phases":
        print(r.status())
        return
    print(r.status())


def cmd_mono(args):
    """Show monotropism tunnel state."""
    from levi.persona.monotropism import MonotropismTracker

    m = MonotropismTracker()
    sample = getattr(args, "sense", None)
    if sample:
        m.sense(sample)
        print(f"Sensed: {sample[:80]}")
    print(m.format_status())


def cmd_wit(args):
    """Show ND comedy spectrum + calibrated wit for a sample tone."""
    from levi.persona.wit_layer import list_styles, calibrate_wit, wit_system_block

    print("=== LEVI Wit Spectrum (neurodivergent comedy styles) ===\n")
    for s in list_styles():
        print(f"  {s['id']:22} | {s['label']}")
        print(f"    root: {s['cognitive_root']}  arousal: {s['arousal']}")
        print(f"    {s['description'][:120]}...")
        print()
    tone = getattr(args, "tone", None) or "playful"
    cfg = calibrate_wit(
        user_tone=tone,
        intensity=0.5,
        regulation="match_light" if tone == "playful" else "steady",
        intrigue=True,
    )
    print(f"--- Calibrated for tone={tone} ---")
    print(f"  enabled={cfg.enabled} mode={cfg.mode} intensity={cfg.intensity:.2f}")
    print(f"  styles={cfg.active_styles}")
    print(f"  reason={cfg.reason}")
    print()
    print(wit_system_block(cfg)[:900])


def cmd_personas(args):
    lat = PersonaLattice()
    keys = lat.keys()
    core = [k for k in keys if not k.startswith("lens_") and not k.startswith("mood_")]
    print(f"Persona lattice: {len(keys)} total · {len(core)} core (non-lens/mood)")
    print("Core sample:")
    for k in core[:25]:
        p = lat.get(k)
        print(f"  {k:28} {p.display_name if p else ''}")
    print("… levi chat --personas  |  levi chat /personas <filter>")
    print('Lock: levi chat --persona normal  or  levi ask -p strategist "..."')


def cmd_skills(args):
    reg = SkillRegistry()
    for s in reg.list():
        mark = " ·user" if "user-created" in s.tags else ""
        print(f"  {s.id:22} | {s.description[:60]}{mark}")


def cmd_agents(args):
    for a in SpecialistRegistry().list():
        print(f"  {a.id:14} | {a.role[:50]}")


def cmd_graph(args):
    eng = InterpenetrationEngine()
    if not _verbose(args):
        st = eng.stats()
        print(f"Capability graph: {st['nodes']} nodes · {st['composites']} composites")
        print("Everything interpenetrates under policy.")
        return
    print(json.dumps(eng.stats(), indent=2))


def cmd_image(args):
    from levi.media.pollinations import generate, story_still, image_url

    if getattr(args, "url_only", False):
        print(image_url(getattr(args, "prompt", None) or "abstract"))
        return
    if getattr(args, "story", None):
        from levi.graph.story_fabric import StoryFabric

        s = StoryFabric().get(args.story)
        if not s:
            print("story not found")
            return
        img = story_still(
            s.title, s.genre, beat=getattr(args, "beat", None) or "midpoint"
        )
        print(img.format())
        return
    img = generate(
        getattr(args, "prompt", None) or "cinematic still",
        width=int(getattr(args, "width", 1024) or 1024),
        height=int(getattr(args, "height", 1024) or 1024),
        model=getattr(args, "model", None) or "flux",
        save=not getattr(args, "no_save", False),
    )
    print(img.format())


def cmd_story(args):
    if getattr(args, "craft", False):
        from levi.lwp.premium_craft import craft_menu

        print(craft_menu())
        return

    """L.W.P. Story Fabric — cascade-ordered create/expand + social/series modes."""
    from levi.graph.story_fabric import StoryFabric

    fab = StoryFabric()
    if getattr(args, "create", None):
        genre = getattr(args, "genre", None) or "systems_horror"
        auto = bool(
            getattr(args, "auto", False) or getattr(args, "bidirectional", False)
        )
        fwd = getattr(args, "auto_forward", None)
        bak = getattr(args, "auto_backward", None)
        # Same-time: forward + backward in one create
        if auto or (fwd is not None and bak is not None):
            forward_n = int(fwd) if fwd is not None else 0
            backward_n = int(bak) if bak is not None else 3
            s = fab.create_bidirectional(
                args.create,
                genre=genre,
                title=getattr(args, "title", None),
                forward=forward_n,
                backward=backward_n,
            )
            print(
                "══ Forward + Backwords (Joyner-style: first→last / last→first, same units)"
            )
        elif fwd is not None or bak is not None:
            try:
                s = fab.create_story(
                    args.create, genre=genre, title=getattr(args, "title", None)
                )
            except ValueError:
                # Loud refusal (blueprint §5.3): re-raise so the CLI's
                # structured-error surface reports it with a non-zero exit —
                # never print-and-return-0, which reads as success.
                raise
            if bak is not None and int(bak) > 0:
                s = fab.auto_backward(s.id, depth=int(bak))
            if fwd is not None and int(fwd) >= 0:
                s = fab.auto_forward(s.id, beats=int(fwd))
        else:
            try:
                s = fab.create_story(
                    args.create, genre=genre, title=getattr(args, "title", None)
                )
            except ValueError:
                # Loud refusal (blueprint §5.3) — see above.
                raise
        words = len((s.body or "").split())
        print(f"══ Created {s.id}")
        print(
            f"title={s.title}  genre={s.genre}  chars={len(s.characters)}  beats={len(s.beats)}  words≈{words}"
        )
        print(
            "Cast:",
            ", ".join(f"{c.name}({c.archetype.value})" for c in s.characters[:6]),
        )
        print("Beats:", " → ".join(b.name for b in s.beats))
        print("─" * 48)
        print(s.body[:3200])
        if len(s.body) > 3200:
            print("...")
        print("─" * 48)
        print('Talk to LEVI:  levi chat "…"   ·  levi ask "Who are you?"')
        print(f"Forward more:  levi story --expand {s.id} --auto-forward 2")
        print(f"Backwards:     levi story --expand {s.id} --auto-backward 2")
        return
    if getattr(args, "expand", None):
        sid = args.expand
        if (
            getattr(args, "auto", False)
            or getattr(args, "auto_forward", None) is not None
            or getattr(args, "auto_backward", None) is not None
        ):
            bak = getattr(args, "auto_backward", None)
            fwd = getattr(args, "auto_forward", None)
            if getattr(args, "auto", False) and bak is None and fwd is None:
                bak, fwd = 3, 0
            if bak is not None and int(bak) > 0:
                s = fab.auto_backward(sid, depth=int(bak))
            if fwd is not None and int(fwd) >= 0:
                s = fab.auto_forward(sid, beats=int(fwd))
            elif getattr(args, "auto", False) and fwd is None:
                s = fab.auto_forward(sid, beats=0)
            s = fab.get(sid)
            words = len((s.body or "").split())
            print(f"══ Auto-generated {s.id}")
            print(f"beats={len(s.beats)}  words≈{words}")
            print("Beats:", " → ".join(b.name for b in s.beats))
            print("─" * 48)
            print(s.body[-2000:])
            return
        focus = getattr(args, "focus", None) or "next_beat"
        s = fab.expand(sid, focus=focus)
        words = len((s.body or "").split())
        last = s.beats[-1].name if s.beats else "?"
        print(f"══ Expanded {s.id}  focus={focus}  +beat={last}")
        print(f"beats={len(s.beats)}  words≈{words}")
        print("Beats:", " → ".join(b.name for b in s.beats))
        print("─" * 48)
        print(s.body[-1600:])
        return
    if getattr(args, "mode", None) and getattr(args, "id", None):
        s = fab.modify(args.id, args.mode, getattr(args, "instruction", "") or "")
        print(f"Mode {args.mode} on {s.id}")
        print(s.body[-1200:])
        return
    if getattr(args, "show", None):
        s = fab.get(args.show)
        if not s:
            print("Not found")
            return
        print(s.body)
        return
    stories = fab.list()
    if not stories:
        print("No stories. Create:")
        print(
            '  levi story --create "A city that bills unlived dreams" --genre systems_horror'
        )
        print("  levi story --expand <id> --focus next_beat")
        print("  levi story --id <id> --mode social_media")
        print("  levi story --id <id> --mode abridged_series")
        return
    for s in stories[:15]:
        print(f"  {s.id}  [{s.genre}] {s.title[:50]}  beats={len(s.beats)}")


def cmd_genres(args):
    reg = GenreRegistry()
    check = reg.integrity_check()
    print(
        f"Genres: {check['actual']}/{check['expected']}  Integrity: {'OK' if check['ok'] else 'FAIL'}"
    )
    if args.all:
        print(", ".join(reg.ids()))
    elif args.category:
        from levi.graph.genres import GenreCategory

        try:
            c = GenreCategory(args.category)
            print(", ".join(g.id for g in reg.list(c)))
        except ValueError:
            print("Unknown category")
    else:
        for k, v in sorted(check["categories"].items()):
            print(f"  {k}: {v}")


def cmd_factory(args):
    if getattr(args, "factory_action", None) == "status":
        return cmd_factory_status(args)
    fac = SoftwareFactory()
    if args.create:
        p = fac.create(args.create, args.idea or args.create)
        print(f"Created [{p.id}] {p.name} stage={p.stage.value}")
        return
    if args.advance:
        p = fac.advance(args.advance, summary=args.summary or "")
        print(f"[{p.id}] stage={p.stage.value} iteration={p.iteration}")
        if p.metadata.get("sandbox_path"):
            print(f"Sandbox: {p.metadata['sandbox_path']}")
        return
    if args.run:
        from levi.factory.sandbox import Sandbox

        p = fac.get(args.run)
        if not p:
            print("Unknown project")
            return
        sb = Sandbox(p.id)
        files = sb.list_files()
        print(f"Sandbox files: {files}")
        smoke = sb.run_smoke(["status"])
        if smoke.get("ok"):
            print(smoke.get("stdout") or "(ok, no output)")
        else:
            print("Smoke failed:", smoke.get("error") or smoke.get("stderr") or smoke)
        return
    if getattr(args, "test", None):
        p = fac.get(args.test)
        if not p:
            print("Unknown project")
            return
        result = fac.run_smoke_test(args.test)
        if result.get("ok"):
            print(f"[{args.test}] smoke OK")
            if result.get("stdout"):
                print(result["stdout"].rstrip())
        else:
            print(f"[{args.test}] smoke FAIL")
            print(result.get("error") or result.get("stderr") or result)
        return
    print(json.dumps(fac.status(), indent=2))
    for p in fac.list()[:10]:
        print(f"  {p.id} | {p.stage.value:14} | {p.name}")


def cmd_automations(args):
    reg = AutomationRegistry()
    print(json.dumps(reg.status(), indent=2))
    for a in reg.list():
        print(f"  {a.id} | {a.status.value:8} | {a.name}")


def cmd_remember(args):
    content = args.content or " ".join(args.extra)
    if not content:
        print("Usage: levi remember <text>")
        return
    store = MemoryStore()
    entry = store.add(
        MemoryType.SEMANTIC,
        content=content,
        importance=args.importance,
        source="user",
        tags=args.tags.split(",") if args.tags else [],
    )
    print(f"Remembered [{entry.id}]")


def cmd_recall(args):
    store = MemoryStore()
    results = (
        store.search(args.query, limit=args.limit)
        if args.query
        else store.list(limit=args.limit)
    )
    for e in results:
        print(f"[{e.memory_type.value:12}] {e.content[:100]}")


def cmd_cloud(args):
    """Phase A/B/C + crypto + ZK + sync dry-run — fused cloud wings surface.

    Also routes the LEVI-as-cloud API surface: ``keys`` and ``usage``.
    """
    action = (getattr(args, "cloud_action", None) or "all").lower()
    if action == "keys":
        return _cmd_cloud_keys(args)
    if action == "usage":
        return _cmd_cloud_usage(args)
    from levi.cloud.surface import CloudSurface

    surf = CloudSurface()
    action = (getattr(args, "cloud_action", None) or "all").lower()
    if action in ("stage", "stages", "map", "phase", "phases"):
        print(surf.report_phases())
    elif action in ("argon2", "argon2id", "argon"):
        print(surf.report_argon2())
    elif action in ("ratchet", "signal"):
        print(surf.report_ratchet())
    elif action in ("crypto",):
        print(surf.report_crypto())
    elif action in ("zk", "zero-knowledge"):
        print(surf.report_zk())
    elif action in ("sync", "dry-run", "dryrun"):
        print(surf.report_sync())
    elif action in ("demo",):
        import json

        print(json.dumps(surf.demo(), indent=2))
    else:
        print(surf.report_all())


def cmd_model(args):
    """Full Cloud Model — L.W.P. SSA fused into LEVI (local-first, cloud optional)."""
    from levi.cloud.model import FullCloudModel

    m = FullCloudModel()
    action = (getattr(args, "model_action", None) or "status").lower()
    if action in ("status", "report"):
        print(m.report())
    elif action in ("expand",):
        print(
            m.expand(
                n=getattr(args, "n", 1) or 1,
                seed=getattr(args, "seed", None),
                polish=bool(getattr(args, "polish", False)),
            )
        )
    elif action in ("deny",):
        print(m.deny())
    elif action in ("approve",):
        print(m.approve())
    elif action in ("reim", "echo"):
        print(
            m.reim(
                tracks=getattr(args, "tracks", 3) or 3, seed=getattr(args, "seed", None)
            )
        )
    elif action in ("crown",):
        print(m.crown(getattr(args, "index", 0) or 0))
    elif action in ("rupture", "wyrd"):
        print(m.rupture(getattr(args, "lens", None) or "mccarthy"))
    elif action in ("causal", "bleed"):
        print(m.causal())
    elif action in ("manuscript", "ms"):
        print(m.manuscript(limit=getattr(args, "limit", 0) or 0))
    elif action in ("configure", "config"):
        print(
            m.configure(
                direction=getattr(args, "direction", None),
                phase=getattr(args, "phase", None),
                power=getattr(args, "power", None),
                genres=getattr(args, "genres", None),
                pov=getattr(args, "pov", None),
                seed=getattr(args, "seed", None),
            )
        )
    elif action in ("genres",):
        print(m.genres_list())
    elif action in ("story",):
        premise = getattr(args, "seed", None) or "A lattice opens under weather law."
        try:
            print(
                m.story_create(
                    premise, genre=getattr(args, "genres", None) or "literary"
                )
            )
        except ValueError:
            # Loud refusal (blueprint §5.3): let the structured-error
            # surface report it with a non-zero exit, never swallow it.
            raise
    elif action in ("characters", "cast"):
        print(m.characters(genre=getattr(args, "genres", None) or "literary"))
    elif action in ("mirror",):
        print(m.mirror(getattr(args, "seed", None) or "cloud model"))
    elif action in ("rail",):
        print(m.rail_status())
    elif action in ("smoke", "all"):
        print(m.run_all_smoke())
    elif action in ("snapshot", "json"):
        import json

        print(json.dumps(m.snapshot(), indent=2))
    else:
        print(m.report())
        print(
            "\nActions: status|expand|deny|approve|reim|crown|rupture|causal|manuscript|configure|genres|story|characters|mirror|rail|smoke|snapshot"
        )


def cmd_chat(args):
    """Enterprise chat companion — multi-turn session with personas & modes."""
    from levi.ei.chat_companion import ChatCompanion, list_sessions

    if getattr(args, "list_sessions", False):
        rows = list_sessions()
        if not rows:
            print("No sessions yet. Start: levi chat")
            return
        for r in rows:
            print(
                f"{r['id']}  msgs={r['messages']:<4}  {r.get('mode', '')}  {r.get('title', '')[:40]}"
            )
        return
    if getattr(args, "personas", False):
        c = ChatCompanion()
        print(c.list_personas(getattr(args, "filter", None)))
        return
    c = ChatCompanion(
        session_id=getattr(args, "session", None),
        persona_id=getattr(args, "personality", None) or getattr(args, "persona", None),
        mode=getattr(args, "mode", None) or "companion",
        profile=getattr(args, "profile", None),
    )
    if getattr(args, "message", None):
        msg = args.message
        if getattr(args, "extra", None):
            msg = (msg + " " + " ".join(args.extra)).strip()
        print(c.say(msg, verbose=getattr(args, "verbose", False)))
        return
    # REPL
    c.repl()


def cmd_enterprise(args):
    """Enterprise readiness checklist — streamline toward production posture."""
    from levi.ops.enterprise import format_enterprise_report

    print(format_enterprise_report())


def cmd_scorecard(args):
    """10/10 cloud model scorecard for LEVI SI."""
    from levi.cloud.scorecard import format_scorecard

    print(format_scorecard())


def cmd_si(args):
    """LEVI SI — symbiotic intelligence identity."""
    from levi.identity.si import si_block

    print(si_block())


def cmd_cognition(args):
    """Where LEVI lives: personas, wit/sarcasm spectrum, cognition organs."""
    from levi.persona.wit_layer import list_styles, calibrate_wit
    from levi.identity.si import si_block

    lat = PersonaLattice()
    keys = lat.keys()
    core = [k for k in keys if not k.startswith("lens_") and not k.startswith("mood_")]
    print(si_block())
    print()
    print(f"══ Personas  total={len(keys)}  core={len(core)} ══")
    print("Core:", ", ".join(core))
    print("Use:  levi chat --persona strategist <msg>")
    print("      levi ask -p philosopher <msg>")
    print("      levi personas")
    print()
    print("══ Wit / sarcasm spectrum ══")
    for s in list_styles():
        print(f"  {s['id']:22} {s['label']}")
    cfg = calibrate_wit(
        user_tone="playful", intensity=0.55, regulation="match_light", intrigue=True
    )
    print(
        f"Sample calibration: enabled={cfg.enabled} styles={cfg.active_styles} intensity={cfg.intensity:.2f}"
    )
    print("HARD RULE: wit muted under crisis/distress.")
    print("Use:  levi wit --tone playful")
    print("      levi daemon lock-wit  (see daemon help)")
    print()
    print("══ Cognition organs ══")
    print(
        "  orchestration loop  — UNDERSTAND → companion → persona → specialists → synthesize"
    )
    print("  nervous system      — stress/anxiety/workload/bond → persona matrix")
    print("  monotropism         — interest tunnel depth + switch cost")
    print("  offline companion   — crisis floor + structured care without LLM")
    print("  corpus/brain        — A–Z knowledge, hyperdrive, heavy pack")
    print("  Full Cloud Model    — L.W.P. literary SSA")
    print("Paths: ~/.levi/  (profile, corpus, chat_sessions, lwp_model_state)")
    print("Code:  VYVE_LEVI_PLATFORM/levi_core/levi/")


def cmd_premium(args):
    """25 premium must-haves for next-gen offline SI."""
    from levi.premium.features import format_features, format_compact

    if getattr(args, "compact", False):
        print(format_compact())
    else:
        print(format_features(verbose=not getattr(args, "quiet", False)))


def cmd_voice(args):
    """LEVI voice registers — 14 original SI registers."""
    from levi.persona.levi import (
        format_levi_roster,
        get,
        register_into_lattice,
        all_variants,
    )

    var = getattr(args, "variant", None)
    if var:
        # allow short names: care, ops, ...
        key = var if var.startswith("levi_") else f"levi_{var}"
        if var in ("prime", "primary", "voice"):
            key = "levi"
        v = get(key) or get(var)
        if not v:
            print(f"Unknown variant: {var}")
            print("Available:", ", ".join(x.id for x in all_variants()))
            return
        print(f"══ {v.name} ══")
        print(v.tagline)
        print(f"voice: {v.voice}")
        print(f"strengths: {', '.join(v.strengths)}")
        print(f"forbids: {', '.join(v.forbids)}")
        print(f"intensity: {v.intensity:.2f}")
        print()
        print(v.system_block)
        return
    if getattr(args, "register", False):
        lat = PersonaLattice()
        n = register_into_lattice(lat)
        print(f"Registered {n} LEVI variants into persona lattice.")
        print("Total personas:", len(lat.keys()))
        return
    print(format_levi_roster())


def cmd_unique(args):
    """Unique unreplicable LEVI organs."""
    from levi.premium.unique import format_uniques

    print(format_uniques())


def cmd_x100(args):
    """×100 upgrade rail — aggressive SI improvement surface."""
    from levi.ops.x100 import format_x100

    print(format_x100())


def cmd_max(args):
    """MAX upgrade — densest counts + law + seed pointer."""
    from levi.ops.max_upgrade import format_max

    print(format_max())


def cmd_interpenetrate(args):
    """Organ mesh — how LEVI systems couple."""
    from levi.ops.interpenetrate import format_mesh, smoke

    print(format_mesh())
    if getattr(args, "smoke", False):
        print("\n── smoke ──")
        for k, v in smoke().items():
            print(f"  {k}: {v}")


def cmd_max10(args):
    """MAX ×10 combined densest posture."""
    from levi.ops.max10 import format_max10

    print(format_max10())


def cmd_stress(args):
    """Stress test / verify engines; rate story quality batch."""
    from levi.ops.stress import run_stress
    from levi.ops.retention import touch_session

    touch_session()
    print(run_stress())


def cmd_retention(args):
    """Local retention posture (no dark patterns)."""
    from levi.ops.retention import format_retention, touch_session

    if getattr(args, "touch", False):
        touch_session()
    print(format_retention())


def cmd_dna(args):
    """20 retired × 20 modern software DNA pairs."""
    from levi.premium.software_dna import format_dna

    print(format_dna())


def cmd_intel(args):
    """Intelligence forms that integrate with LEVI SI."""
    from levi.identity.intelligence_forms import format_forms

    print(format_forms())


def cmd_giant(args):
    """Tech-giant-class capabilities with LEVI spin."""
    from levi.premium.tech_giant_spin import format_spins

    print(format_spins())


def cmd_future(args):
    """Future integration ideas (outer planets)."""
    from levi.ops.future_integrations import format_future

    print(format_future())


def cmd_here(args):
    """Where is LEVI — entry map to the living SI."""
    from levi.identity.si import si_block
    from levi.ei.offline_companion import synthesize

    print(si_block())
    print("")
    print("══ WHERE IS LEVI ══")
    print("  Code:   VYVE_LEVI_PLATFORM/levi_core/levi/")
    print("  Data:   ~/.levi/")
    print("  UI:     python -m levi.cli.main serve-ui")
    print("")
    print("Talk to LEVI now:")
    print('  python -m levi.cli.main chat "Who are you?"')
    print('  python -m levi.cli.main ask "Who are you?"')
    print('  python -m levi.cli.main chat --persona levi "Status."')
    print("")
    print("Story (auto forward + backward):")
    print('  python -m levi.cli.main story --create "A lattice opens" --auto')
    print("  python -m levi.cli.main story --expand <id> --auto-forward 0")
    print("  python -m levi.cli.main story --expand <id> --auto-backward 3")
    print("")
    print("── live reply ──")
    print(synthesize("Who are you?"))


def cmd_talk(args):
    """Mass-friendly chat entry — LEVI SI with hardwired quality traits."""
    from levi.ei.chat_companion import ChatCompanion
    from levi.ei.mass_chat import format_traits

    profile = getattr(args, "profile", None) or "levi"
    if getattr(args, "list_profiles", False):
        print(format_traits())
        return
    c = ChatCompanion(
        session_id=getattr(args, "session", None),
        persona_id=getattr(args, "persona", None) or getattr(args, "personality", None),
        mode=getattr(args, "mode", None) or "companion",
        profile=profile,
    )
    msg = getattr(args, "message", None)
    if msg:
        if getattr(args, "extra", None):
            msg = (msg + " " + " ".join(args.extra)).strip()
        print(c.say(msg, verbose=getattr(args, "verbose", False)))
        return
    print(c.welcome())
    print("")
    c.repl()


def cmd_profiles(args):
    from levi.ei.mass_chat import format_traits, usability_report

    if getattr(args, "rate", False):
        print(usability_report())
        return
    print(format_traits())


def cmd_traits(args):
    from levi.ei.mass_chat import format_traits, usability_report

    if getattr(args, "rate", False):
        print(usability_report())
        return
    print(format_traits())


def _local_model_choices() -> list[str]:
    """Model keys for `levi agent model pull --model`. Lazy import keeps
    `levi` startup fast; falls back to the default key if the module
    cannot load (pull will then report the real error)."""
    try:
        from levi.agent.local_model import MODELS

        return list(MODELS)
    except Exception:
        return ["qwen3-0.6b"]


def _provider_choices() -> list[str]:
    """`--provider` choices: LEVI family first, then other sources. Lazy
    import keeps `levi` startup fast; falls back to the legacy list."""
    try:
        from levi.agent.providers import provider_names

        return provider_names()
    except Exception:
        return ["local", "levi-brain", "levi-local", "openai", "anthropic"]


# === MEGAZORD-AXIS1-REGION-BEGIN: one CLI surface (axis 1) ===
# Thin adapters: every landed subsystem reachable from `levi`. Each adapter
# delegates to the subsystem's own entry point — NO reimplementation here.
# Subsystems whose owning axis has not landed yet print an honest
# "not yet landed" and exit 2 (never a traceback, never a fake success).


def _axis1_not_landed(what: str):
    """Honest gap: the owning axis has not merged this yet. Exit 2."""
    print(
        "not yet landed: %s — the owning axis has not merged it yet." % what,
        file=sys.stderr,
    )
    raise SystemExit(2)


def _axis1_delegate(module: str, args, attr: str = "main"):
    """Delegate to ``levi.<module>.__main__.main`` with REMAINDER argv."""
    import importlib

    entry = getattr(importlib.import_module("levi.%s.__main__" % module), attr)
    rc = entry(list(getattr(args, "argv", None) or []))
    if rc:
        raise SystemExit(rc)


def _axis1_importable(dotted: str) -> bool:
    try:
        import importlib

        importlib.import_module(dotted)
        return True
    except Exception:
        return False


def _axis1_field(obj, *names, default=""):
    """Duck-typed field read: dict key first, then attribute."""
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return default


def cmd_archive(args):
    """The LEVI Archive — Smithsonian of forgotten software (passthrough)."""
    _axis1_delegate("archive", args)


def cmd_galaxy(args):
    """Galaxy ecosystem: list/search/install packages (passthrough)."""
    _axis1_delegate("galaxy", args)


def cmd_perpetual(args):
    """Perpetual engine: pulse, hunt waves, services (passthrough)."""
    _axis1_delegate("perpetual", args)


def cmd_oath(args):
    """Oath trust mesh: init/doctor/key/contact/command/run/inbox/daemon/audit."""
    _axis1_delegate("oath", args)


def _axis1_shelf_modules(package: str):
    """[(name, first-doc-line)] for every public submodule of a warehouse pkg."""
    import importlib
    import pkgutil

    pkg = importlib.import_module("levi.%s" % package)
    out = []
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda m: m.name):
        if info.name.startswith("_"):
            continue
        mod = importlib.import_module("levi.%s.%s" % (package, info.name))
        doc = (mod.__doc__ or "").strip().splitlines()
        out.append((info.name, doc[0] if doc else ""))
    return out


def _axis1_shelf_cmd(args, package: str, action_attr: str, name_attr: str, title: str):
    action = getattr(args, action_attr, None) or "list"
    if action == "list":
        print("=== %s ===" % title)
        for name, blurb in _axis1_shelf_modules(package):
            print("  %-14s %s" % (name, blurb[:100]))
        print("\nPull one off the shelf: `levi %s show <name>`" % package)
        return
    name = getattr(args, name_attr, None) or ""
    for mod_name, _blurb in _axis1_shelf_modules(package):
        if mod_name == name:
            import importlib

            doc = getattr(
                importlib.import_module("levi.%s.%s" % (package, name)),
                "__doc__",
                "",
            )
            print((doc or "(no docs for %s)" % name).strip())
            return
    print(
        "unknown %s %r — browse with `levi %s list`" % (package, name, package),
        file=sys.stderr,
    )
    raise SystemExit(2)


def cmd_methods(args):
    """Methods warehouse: forgotten human techniques, LEVI-native."""
    _axis1_shelf_cmd(
        args, "methods", "methods_action", "methods_name", "Methods warehouse — shelves"
    )


def cmd_revival(args):
    """Revivals warehouse: retired-software ideas reborn as LEVI originals."""
    _axis1_shelf_cmd(
        args,
        "revival",
        "revival_action",
        "revival_name",
        "Revivals warehouse — shelves",
    )


_MEGAZORD_AXES = (
    ("one CLI surface", "levi.cli.main"),
    ("bloodstream turn pipeline", "levi.bloodstream.turn"),
    ("capability registry / atlas", "levi.interop.atlas"),
    ("unified daemon", "levi.daemon.supervisor"),
    ("cross-module workflows", "levi.workflows"),
    ("home / config root", None),  # ~/.levi exists
    ("unified docs atlas", None),  # docs/CAPABILITIES.md in checkout
    ("cross-module proof harness", None),  # tests/test_cli_megazord_surface.py
    ("growth loop", "levi.growth"),
    ("life-pack export", "levi.lifepack.pack"),
)


def cmd_megazord(args):
    """MEGAZORD¹⁰ organism self-report: which of the 10 axes have landed."""
    action = getattr(args, "megazord_action", None) or "status"
    if action != "status":
        print("unknown megazord action %r" % action, file=sys.stderr)
        raise SystemExit(2)
    print("=== MEGAZORD¹⁰ — organism self-report ===")
    home = Path.home() / ".levi"
    repo = Path(__file__).resolve().parents[3]
    landed = 0
    for i, (label, dotted) in enumerate(_MEGAZORD_AXES, 1):
        if dotted:
            ok = _axis1_importable(dotted)
        elif label == "home / config root":
            ok = home.is_dir()
        elif label == "unified docs atlas":
            ok = (repo / "docs" / "CAPABILITIES.md").is_file()
        else:  # cross-module proof harness
            ok = (repo / "tests" / "test_cli_megazord_surface.py").is_file()
        landed += 1 if ok else 0
        print(
            "  [%s] axis %2d: %-32s %s"
            % ("x" if ok else " ", i, label, "landed" if ok else "not yet landed")
        )
    try:
        from levi.interop import atlas as _atlas

        ap = getattr(_atlas, "atlas_path", None)
        atlas_path = str(ap() if callable(ap) else ap) if ap else "~/.levi/atlas.json"
    except Exception:
        atlas_path = "not yet landed (levi.interop.atlas)"
    print("atlas path: %s" % atlas_path)
    try:
        from levi.lifepack.pack import PACK_VERSION as _lpv

        lpv = str(_lpv)
    except Exception:
        lpv = "unknown"
    print("lifepack format version: %s" % lpv)
    try:
        from levi.interop import warehouses as _wh

        rows = _wh.list_warehouses()
        print("warehouses: %d" % len(rows))
    except Exception:
        print("warehouses: not yet landed (levi.interop.warehouses)")
    print("axes landed: %d/10" % landed)


def cmd_atlas(args):
    """Capability atlas export (warehouse-grouped when the axis lands)."""
    action = getattr(args, "atlas_action", None) or "export"
    if action != "export":
        print("unknown atlas action %r" % action, file=sys.stderr)
        raise SystemExit(2)
    try:
        from levi.interop.atlas import export_atlas, write_atlas
    except Exception:
        _axis1_not_landed("levi.interop.atlas (capability atlas)")
    data = export_atlas()
    out = getattr(args, "out", None)
    if out:
        try:
            written = write_atlas(out)
        except TypeError:
            # Alternate contract variant: write_atlas(data, path).
            written = write_atlas(data, out)
        print("atlas written → %s" % written)
        return
    # Read whatever structure export_atlas() returns: grouped or flat.
    if isinstance(data, dict) and "warehouses" in data:
        whs = data["warehouses"]
        pairs = (
            whs.items()
            if isinstance(whs, dict)
            else [(getattr(w, "name", "?"), w) for w in whs]
        )
        print("=== capability atlas (by warehouse) ===")
        for name, w in pairs:
            count = _axis1_field(w, "inventory_count", "count", "items", default="?")
            print("  %-22s %s item(s)" % (name, count))
    elif isinstance(data, (list, tuple)):
        print("atlas: %d entries (flat)" % len(data))
    elif isinstance(data, dict):
        keys = list(data)[:12]
        print(
            "atlas: %d top-level groups: %s"
            % (len(data), ", ".join(str(k) for k in keys))
        )
    else:
        print(str(data)[:2000])


def cmd_workflow(args):
    """Cross-module flagship workflows (axis 5)."""
    action = getattr(args, "workflow_action", None) or "list"
    try:
        from levi.workflows import list_workflows, run_workflow
    except Exception:
        _axis1_not_landed("levi.workflows (cross-module workflows)")
    if action == "list":
        for w in list_workflows() or []:
            print(
                "  %-24s %s"
                % (
                    _axis1_field(w, "name", "id"),
                    _axis1_field(w, "summary", "description", default="")[:90],
                )
            )
        return
    name = getattr(args, "name", None)
    if not name:
        print("usage: levi workflow run <name>", file=sys.stderr)
        raise SystemExit(2)
    rc = run_workflow(name)
    if rc:
        raise SystemExit(rc)


def cmd_warehouse(args):
    """Browse LEVI's warehouses: list, browse shelves, inventory, pull."""
    try:
        from levi.interop import warehouses as _wh
    except Exception:
        _axis1_not_landed("levi.interop.warehouses (warehouse registry)")
    action = getattr(args, "warehouse_action", None) or "list"
    if action == "list":
        print("=== LEVI warehouses ===")
        for w in _wh.list_warehouses() or []:
            name = _axis1_field(w, "name", "id")
            summary = _axis1_field(w, "summary", "description", default="")
            count = _axis1_field(w, "inventory_count", "count", "items", default="?")
            print("  %s\n    %s [%s item(s)]" % (name, summary, count))
        print(
            "\n`levi warehouse browse <name>` — shelves · "
            "`levi warehouse inventory <name>` — stock · "
            "`levi warehouse pull <warehouse> <item>` — inspect"
        )
        return
    if action == "browse":
        name = getattr(args, "name", None)
        if not name:
            print("usage: levi warehouse browse <name>", file=sys.stderr)
            raise SystemExit(2)
        info = _wh.browse_warehouse(name)
        print(
            "=== warehouse: %s ===" % _axis1_field(info, "title", "name", default=name)
        )
        summary = _axis1_field(info, "summary", "description", default="")
        if summary:
            print(summary)
        shelves = _axis1_field(info, "shelves", "modules", "sections", default=[]) or []
        for s in shelves:
            sname = _axis1_field(s, "module", "name", "id")
            ssum = _axis1_field(s, "summary", "description", default="")
            provides = _axis1_field(s, "provides", "items", default=[]) or []
            extra = (" · %d item(s)" % len(provides)) if provides else ""
            print("  %-24s %s%s" % (sname, ssum[:80], extra))
        hint = _axis1_field(info, "pull_hint", "hint", default="")
        if hint:
            print("\n%s" % hint)
        return
    if action == "inventory":
        name = getattr(args, "name", None)
        if not name:
            print("usage: levi warehouse inventory <name>", file=sys.stderr)
            raise SystemExit(2)
        limit = getattr(args, "limit", 20) or 20
        raw = _wh.warehouse_inventory(name) or []
        if isinstance(raw, dict):
            items = raw.get("items") or []
            total = raw.get("total", len(items))
        else:
            items = list(raw)
            total = len(items)
        shown = list(items)[:limit]
        print("=== inventory: %s (%d of %d shown) ===" % (name, len(shown), total))
        for it in shown:
            print(
                "  %-28s %s"
                % (
                    _axis1_field(it, "id", "name"),
                    _axis1_field(it, "summary", "description", "blurb", default="")[
                        :80
                    ],
                )
            )
        return
    if action == "pull":
        warehouse = getattr(args, "name", None)
        item = getattr(args, "item", None)
        if not warehouse or not item:
            print("usage: levi warehouse pull <warehouse> <item>", file=sys.stderr)
            raise SystemExit(2)
        try:
            detail = _wh.pull_from_shelf(warehouse, item)
        except (ValueError, KeyError, LookupError) as exc:
            print("pull failed: %s" % exc, file=sys.stderr)
            raise SystemExit(1)
        if isinstance(detail, str):
            print(detail)
        elif isinstance(detail, dict):
            print(
                "%s — %s"
                % (
                    _axis1_field(detail, "id", "name", default=item),
                    _axis1_field(detail, "summary", "description", default=""),
                )
            )
            invoke = _axis1_field(
                detail, "invoke", "how_to_invoke", "usage", default=""
            )
            if invoke:
                print("invoke: %s" % invoke)
            rest = {
                k: v
                for k, v in detail.items()
                if k
                not in (
                    "id",
                    "name",
                    "summary",
                    "description",
                    "invoke",
                    "how_to_invoke",
                    "usage",
                )
            }
            if rest:
                print(json.dumps(rest, indent=2, default=str)[:3000])
        else:
            print(json.dumps(detail, indent=2, default=str))
        return
    print("unknown warehouse action %r" % action, file=sys.stderr)
    raise SystemExit(2)


def cmd_bloodstream(args):
    """Single-bloodstream turn pipeline (axis 2)."""
    action = getattr(args, "bloodstream_action", None) or "turn"
    from levi.bloodstream.turn import run_turn

    if action == "turn":
        text = " ".join(getattr(args, "text", None) or [])
        if not text:
            print("usage: levi bloodstream turn <text>", file=sys.stderr)
            raise SystemExit(2)
        res = run_turn(text)
        print(res.reply)
        print(
            "— route=%s behavior=%s persona=%s risk=%s"
            % (res.route, res.behavior, res.persona_id, res.risk_level)
        )
        print("  stages: %s · trace=%s" % (", ".join(res.stage_names()), res.trace_id))
        if not res.ok:
            raise SystemExit(1)
        return
    if action == "bus-test":
        res = run_turn("megazord bus self-test probe")
        ok = bool(res.ok and res.stage_names())
        print(
            "bus-test: %s — %d stage(s): %s"
            % (
                "PASS" if ok else "FAIL",
                len(res.stage_names()),
                ", ".join(res.stage_names()),
            )
        )
        if not ok:
            raise SystemExit(1)
        return
    print("unknown bloodstream action %r" % action, file=sys.stderr)
    raise SystemExit(2)


_WAYMAKER_LINE = "Waymaker law: where there isn't a way, LEVI creates one."


def _axis1_waymaker_jobs():
    """Read-only peek at the workflows worker's waymaker queue (defensive)."""
    try:
        from levi import workflows as _wf
    except Exception:
        return None
    fn = getattr(_wf, "waymaker_jobs", None)
    if not callable(fn):
        return None
    try:
        res = fn()
    except Exception:
        return None
    if isinstance(res, int):
        return res
    if isinstance(res, (list, tuple)):
        return len(res)
    if isinstance(res, dict):
        for key in ("count", "pending", "depth"):
            if isinstance(res.get(key), int):
                return res[key]
        jobs = res.get("jobs")
        if isinstance(jobs, (list, tuple)):
            return len(jobs)
    return None


def cmd_factory_status(args):
    """Factory production line: hunt → archive → manufacture → stock → galaxy."""
    print("=== LEVI factory — production line ===")
    print(_WAYMAKER_LINE)
    home = Path.home()
    print("\n[intake] perpetual hunt")
    try:
        from levi.perpetual import hunt as _hunt

        state = _hunt.load_state()
        done = [w for w in state.waves if w.status == "completed"]
        last = max(done, key=lambda w: w.completed_at or "") if done else None
        print("  waves completed: %d" % len(done))
        if last:
            print(
                "  last wave: %s (%s) — %d findings @ %s"
                % (last.id, last.theme_id, last.findings_count, last.completed_at)
            )
        if state.next_due:
            print("  next due: %s" % state.next_due)
    except Exception:
        print("  not landed: levi.perpetual")
    print("\n[processing] archive")
    try:
        from levi.archive.store import ArchiveStore

        print("  records: %d" % ArchiveStore().count())
    except Exception:
        print("  not landed: levi.archive.store")
    print("\n[manufacture] build queue")
    try:
        from levi.perpetual import hunt as _hunt

        queue = _hunt.read_build_queue()
        print("  queued builds: %d" % len(queue))
        waymaker = _axis1_waymaker_jobs()
        if waymaker is None:
            print("  waymaker queue: not yet exposed (workflows axis pending)")
        else:
            print("  waymaker queue: %d job(s)" % waymaker)
    except Exception:
        print("  not landed: levi.perpetual build queue")
    print("\n[stocking] warehouses")
    try:
        from levi.interop import warehouses as _wh

        rows = _wh.list_warehouses() or []
        total = 0
        for w in rows:
            count = _axis1_field(w, "inventory_count", "count", "items", default=0)
            total += count if isinstance(count, int) else 0
        print("  warehouses: %d · inventoried items: %d" % (len(rows), total))
    except Exception:
        print("  not yet landed: levi.interop.warehouses")
    print("\n[distribution] galaxy")
    try:
        from levi.galaxy.registry import GalaxyRegistry

        pkgs = GalaxyRegistry(home / ".levi").list()
        print("  installed packages: %d" % len(pkgs))
    except Exception:
        print("  not landed: levi.galaxy.registry")


def _cmd_lifepack_preview(args, home=None):
    """`levi lifepack preview <file>`: diff without writing (axis 10)."""
    from levi.lifepack.pack import (
        LifepackError,
        _resolve_home,
        preview_import,
        validate_pack,
    )

    home = _resolve_home(home)
    path = Path(getattr(args, "file", "") or "")
    try:
        pack = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print("cannot read pack %s: %s" % (path, exc), file=sys.stderr)
        raise SystemExit(1)
    try:
        validate_pack(pack)
    except LifepackError as exc:
        print("invalid life pack: %s" % exc, file=sys.stderr)
        raise SystemExit(1)
    for line in preview_import(pack, home):
        print(line)
    print("(preview only — nothing was written)")


def cmd_daemon_services(args):
    """`levi daemon services`: unified supervisor catalog + health (axis 4)."""
    try:
        from levi.daemon import supervisor as _sup
    except Exception:
        _axis1_not_landed("levi.daemon.supervisor (unified daemon supervisor)")
    name = getattr(args, "target", None)
    if name:
        st = _sup.service_status(name)
        print("%s: %s — %s" % (st["name"], st["status"], st["detail"]))
        print("hint: %s" % _axis1_field(st, "start_hint", default=""))
        if not st["ok"]:
            raise SystemExit(1)
        return
    statuses = _sup.all_status()
    up = sum(1 for s in statuses.values() if s["ok"])
    print("=== daemon services (%d/%d up) ===" % (up, len(statuses)))
    for sname, st in statuses.items():
        mark = "up  " if st["ok"] else "DOWN"
        print("  [%s] %-16s %s" % (mark, sname, st["detail"][:110]))
    downs = [s for s in statuses.values() if not s["ok"]]
    if downs:
        print("\nstart hints for down services:")
        for st in downs:
            print(
                "  %-16s %s" % (st["name"], _axis1_field(st, "start_hint", default=""))
            )


# === MEGAZORD-AXIS1-REGION-END ===


def main():
    parser = argparse.ArgumentParser(description="LEVI × L.W.P. Kernel")
    parser.add_argument("--personality", "-p", default=None)
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show internal routing / IR / specialists",
    )
    sub = parser.add_subparsers(dest="command")

    # Retention surface
    init_p = sub.add_parser("init", help="First-run onboarding (5-minute win)")
    init_p.add_argument("--name", default=None)
    init_p.add_argument("--goal", default=None)
    init_p.add_argument("--loop", default=None)
    init_p.add_argument("--yes", action="store_true", help="Skip constructive confirms")
    sub.add_parser("home", help="Shelf + continuity")
    sub.add_parser("continue", help="Continue latest shelf item")
    sub.add_parser("morning", help="Daily goal + shelf + next move")
    exp = sub.add_parser("export", help="Export life pack zip")
    imp = sub.add_parser("import", help="Import life pack zip")
    imp.add_argument("path", help="Path to life_pack_*.zip")
    imp.add_argument(
        "--replace", action="store_true", help="Replace namespaces from pack"
    )
    exp.add_argument("--out", default=None)
    tpl = sub.add_parser("templates", help="List/apply free templates")
    tpl.add_argument("--use", default=None)

    sub.add_parser("status")
    ask_p = sub.add_parser("ask")
    ask_p.add_argument(
        "--ultimate", action="store_true", help="Full organism synthesis path"
    )
    ask_p.add_argument("question", nargs="?", default=None)
    ask_p.add_argument("extra", nargs="*", default=[])
    turn_p = sub.add_parser(
        "turn",
        help="One bloodstream turn: EI → persona → governor → factory/organ/model → policy → memory → trace",
    )
    turn_p.add_argument("text", nargs="?", default=None)
    turn_p.add_argument("extra", nargs="*", default=[])
    turn_p.add_argument(
        "--persona", default=None, help="Persona lens id (default: normal)"
    )
    turn_p.add_argument(
        "--provider",
        default=None,
        help="Explicit model provider (default: provider chain)",
    )
    turn_p.add_argument(
        "--session", default="default", help="Session id for EI/persona continuity"
    )
    turn_p.add_argument(
        "--composite",
        default=None,
        help="Named composite whose strictest risk ceiling applies",
    )
    turn_p.add_argument(
        "--yes",
        action="store_true",
        help="Approve consequential acts without prompting",
    )
    turn_p.add_argument(
        "--dry-run", action="store_true", help="Walk the gate without executing"
    )
    sub.add_parser("personas")
    wit_p = sub.add_parser("wit", help="ND comedy spectrum + calibrated wit preview")
    rail_p = sub.add_parser("rail", help="Opportunity Rail HITL-gated automation")
    rail_p.add_argument("--start", default=None)
    rail_p.add_argument("--title", default="")
    rail_p.add_argument("--advance", default=None)
    rail_p.add_argument("--approved", action="store_true")
    mir_p = sub.add_parser("mirror", help="L.W.P. Mirror Cascade reverse cross-check")
    mir_p.add_argument("--seed", default="")
    mir_p.add_argument("--context", default="")
    lwp_p = sub.add_parser("lwp-model", help="L.W.P. Model offline literary engine")
    lwp_p.add_argument("--expand", action="store_true")
    lwp_p.add_argument("-n", type=int, default=None)
    lwp_p.add_argument("--seed", default=None)
    lwp_p.add_argument("--direction", default=None)
    lwp_p.add_argument("--pov", default=None)
    lwp_p.add_argument("--genres", default=None)
    lwp_p.add_argument("--reim", action="store_true")
    lwp_p.add_argument("--tracks", type=int, default=3)
    lwp_p.add_argument("--deny", action="store_true")
    lwp_p.add_argument("--approve", action="store_true")
    lwp_p.add_argument("--rupture", action="store_true")
    lwp_p.add_argument("--lens", default="mccarthy")
    ch = sub.add_parser("characters", help="L.W.P. Character Graph (unlimited types)")
    ch.add_argument("--mint", action="store_true")
    ch.add_argument("--weave", action="store_true")
    ch.add_argument("-n", type=int, default=4)
    ch.add_argument("--seed", default=None)
    sub.add_parser("watch", help="Standing Watch sentinel")
    cru = sub.add_parser("crucible", help="Constrained execution chamber")
    cru.add_argument("--syntax", default=None)
    cru.add_argument("--eval", default=None)
    cru.add_argument("--file", default=None)
    cru.add_argument("--content", default=None)
    svc = sub.add_parser("services", help="Local service mesh catalog")
    svc.add_argument("--query", default=None)
    sui = sub.add_parser("serve-ui", help="Local interactive UI (ops + L.W.P. Model)")
    sui.add_argument("--port", type=int, default=8765)
    sui.add_argument("--no-browser", action="store_true")
    sub.add_parser("provenance", help="Closed-source LEVI DNA vs foreign branding")
    sub.add_parser("perfection", help="Perfection layer score")
    free_p = sub.add_parser(
        "free", help="Free integration lattice + interpenetration matrix"
    )
    free_p.add_argument("--matrix", action="store_true")
    free_p.add_argument(
        "--json",
        action="store_true",
        help="JSON export (with --matrix: full graph; with --path/--neighborhood: query result)",
    )
    free_p.add_argument(
        "--path",
        nargs=2,
        metavar=("A", "B"),
        default=None,
        help="Shortest interpenetration path between two asset ids",
    )
    free_p.add_argument(
        "--neighborhood",
        default=None,
        metavar="ID",
        help="Assets within --depth hops of an asset id",
    )
    free_p.add_argument(
        "--depth", type=int, default=1, help="Hop depth for --neighborhood (default 1)"
    )
    sub.add_parser(
        "production", help="Production table: prehistoric+modern+LEVI-unique"
    )
    sub.add_parser("go", help="Fast path: integrate+ladder+ops")
    sub.add_parser("integrate", help="Cross-module integration audit")
    ops_p = sub.add_parser(
        "ops", help="Operational layer — pulse+kernel+rail+HITL surface"
    )
    ops_p.add_argument("--cycle", default=None, help="Run unified cycle for task")
    ops_p.add_argument("--execute", action="store_true")
    ops_p.add_argument("--rail-dry", default=None, help="Rail dry-run until HITL")
    ops_p.add_argument("--estop", action="store_true")
    ops_p.add_argument("--clear-estop", action="store_true")
    ops_p.add_argument("--reason", default="operator")
    lad_p = sub.add_parser(
        "ladder", help="Build ladder Step 1 readiness (no placeholders)"
    )
    lad_p.add_argument("--json", action="store_true")
    org_p = sub.add_parser(
        "organism", help="One symbiotic system map LEVI x LWP x Factory"
    )
    org_p.add_argument(
        "--register", action="store_true", help="Register organs into capability graph"
    )
    sub.add_parser("charter", help="LEVI Charter identity constitution")
    sym_p = sub.add_parser("symbiosis", help="Asset other-half map + value check")
    sym_p.add_argument("--asset", default=None)
    sym_p.add_argument(
        "--value", default=None, help="Check action for non-malicious value"
    )
    sym_p.add_argument("--orphans", action="store_true")
    sb_p = sub.add_parser("sandbox", help="Syntax+smoke sandbox for a project path")
    sb_p.add_argument("--path", default=".")
    plug_p = sub.add_parser("plugins", help="Closed-source capability/plugin catalog")
    plug_p.add_argument("--category", default=None)
    plug2_p = sub.add_parser(
        "plugin", help="Plugin connectors: list + execute (blueprint §3)"
    )
    plug2_sub = plug2_p.add_subparsers(dest="plugin_action")
    plug2_sub.add_parser("list", help="List registered plugin connectors")
    plug2_e = plug2_sub.add_parser("exec", help="Execute a connector operation")
    plug2_e.add_argument("connector")
    plug2_e.add_argument("operation")
    plug2_e.add_argument(
        "--param", action="append", default=[], help="k=v params (repeatable)"
    )
    plug2_e.add_argument(
        "--yes", action="store_true", help="Confirm a write operation (HITL gate)"
    )
    plug2_e.add_argument("--json", action="store_true", help="Print the result as JSON")
    ref_p = sub.add_parser(
        "reference",
        help="Universal provider references: plug external providers in as references",
    )
    ref_p.add_argument(
        "reference_action",
        nargs="?",
        default="list",
        choices=["add", "remove", "list"],
        help="reference action",
    )
    ref_p.add_argument("provider", nargs="?", default=None, help="add: provider name")
    ref_p.add_argument(
        "--kind",
        default="other",
        choices=["mcp-server", "plugin", "model", "media", "other"],
        help="add: what the reference is plugged into",
    )
    ref_p.add_argument(
        "--detail",
        action="append",
        default=[],
        help="add: extra detail as k=v (repeatable)",
    )
    ref_p.add_argument(
        "--id",
        dest="ref_id",
        default=None,
        help="add: local id (default ref-<slug>); remove: id to unplug",
    )
    doc_p = sub.add_parser(
        "doc",
        help="Document skills: read/create docx, xlsx, pptx; read pdf",
    )
    doc_sub = doc_p.add_subparsers(dest="doc_action")
    doc_r = doc_sub.add_parser("read", help="Read text from a document file")
    doc_r.add_argument("file", help="Path to .docx/.xlsx/.pptx/.pdf")
    doc_r.add_argument("--json", action="store_true", help="Print as JSON")
    doc_w = doc_sub.add_parser("write", help="Create a document file")
    doc_w.add_argument(
        "format", choices=["docx", "xlsx", "pptx"], help="format to create"
    )
    doc_w.add_argument("file", help="Output path")
    doc_w.add_argument("--title", default=None, help="Document/slide title")
    doc_w.add_argument(
        "--paragraph",
        action="append",
        default=[],
        help="docx: paragraph text (repeatable)",
    )
    doc_w.add_argument(
        "--table",
        action="append",
        default=[],
        help='docx: one table as "r1c1,r1c2;r2c1,r2c2" (repeatable)',
    )
    doc_w.add_argument(
        "--header",
        action="append",
        default=[],
        help="xlsx: column header (repeatable)",
    )
    doc_w.add_argument(
        "--row",
        action="append",
        default=[],
        help='xlsx: one data row as "a,b,c" (repeatable)',
    )
    doc_w.add_argument(
        "--slide",
        action="append",
        default=[],
        help='pptx: one slide as "Title|bullet1;bullet2" (repeatable)',
    )
    fin_p = sub.add_parser(
        "finance",
        help="Paper-only finance: quotes, indicators, signals, paper orders (blueprint §5)",
    )
    fin_sub = fin_p.add_subparsers(dest="finance_action")
    fin_q = fin_sub.add_parser("quote", help="Latest close + day range via Stooq")
    fin_q.add_argument("sym", help="US symbol, e.g. AAPL")
    fin_q.add_argument("--json", action="store_true", help="Print the quote as JSON")
    fin_i = fin_sub.add_parser(
        "indicators", help="Indicator snapshot for the latest bar"
    )
    fin_i.add_argument("sym", help="US symbol, e.g. AAPL")
    fin_s = fin_sub.add_parser(
        "signal", help="Advisory signal (paper-only, not financial advice)"
    )
    fin_s.add_argument("sym", help="US symbol, e.g. AAPL")
    fin_s.add_argument("--json", action="store_true", help="Print the signal as JSON")
    fin_pf = fin_sub.add_parser("portfolio", help="Show the paper portfolio ledger")
    fin_pf.add_argument(
        "--json", action="store_true", help="Print the portfolio summary as JSON"
    )
    fin_o = fin_sub.add_parser("order", help="Paper order (HITL: needs --yes)")
    fin_o.add_argument("sym", help="US symbol, e.g. AAPL")
    fin_o.add_argument("qty", type=float, help="Quantity (> 0)")
    fin_o.add_argument(
        "--side", required=True, choices=["buy", "sell"], help="buy or sell"
    )
    fin_o.add_argument(
        "--yes", action="store_true", help="Explicit human confirmation (HITL gate)"
    )
    fin_o.add_argument(
        "--live",
        action="store_true",
        help="Refused: live trading is not enabled in this build",
    )
    fin_d = fin_sub.add_parser("deposit", help="Fund the paper portfolio")
    fin_d.add_argument("amount", type=float, help="Amount (> 0)")
    forge_p = sub.add_parser(
        "forge",
        help="LEVI Forge: local-first code home (git hosting, issues, PRs, CI, export)",
    )
    forge_p.add_argument(
        "forge_args",
        nargs=argparse.REMAINDER,
        help="passed through to the forge CLI (see: levi forge --help)",
    )
    ag_p = sub.add_parser(
        "agent",
        help="Agent runtime: step-level tool loop, tools, HTTP service (blueprint §7)",
    )
    ag_sub = ag_p.add_subparsers(dest="agent_action")
    ag_run = ag_sub.add_parser(
        "run", help="Run a task through the step-level tool loop"
    )
    ag_run.add_argument("task", help="Task description for the agent")
    ag_run.add_argument(
        "--provider",
        choices=_provider_choices(),
        default=None,
        help="Chat provider (default: LEVI-first chain — best available LEVI weight, else rules planner)",
    )
    ag_run.add_argument(
        "--yes",
        action="store_true",
        help="Pre-grant consent for gated tools for THIS run only. "
        "There is no global gate-disabling flag. Without --yes, "
        "gate trips prompt interactively (TTY only) or are denied.",
    )
    ag_run.add_argument(
        "--max-steps", type=int, default=10, help="Max provider turns (default 10)"
    )
    ag_run.add_argument(
        "--workspace", default=None, help="Workspace root for agent file/shell tools"
    )
    ag_run.add_argument(
        "--json", action="store_true", help="Print the transcript as JSON"
    )
    ag_run.add_argument(
        "--register",
        default=None,
        metavar="VARIANT",
        help="Speak as a LEVI SI register (e.g. levi_ops). "
        "Valid ids: levi, levi_care, levi_ops, levi_challenger, "
        "levi_literary, levi_forensic, levi_void, levi_builder, "
        "levi_mirror, levi_architect, levi_sentinel, levi_oracle, "
        "levi_companion, levi_wit.",
    )
    ag_run.add_argument(
        "--affect",
        action="store_true",
        help="Enable the 5D affect engine: per-turn affect scan, "
        "de-escalation policy, register hints (docs/AFFECT.md).",
    )
    ag_sub.add_parser(
        "tools", help="List agent tools with descriptions and confirmation flags"
    )
    ag_chat = ag_sub.add_parser(
        "chat", help="Interactive long-conversation chat with session memory"
    )
    ag_chat.add_argument(
        "--session",
        default="default",
        help="Session name (default: default). Re-running resumes it.",
    )
    ag_chat.add_argument(
        "--provider",
        choices=_provider_choices(),
        default=None,
        help="Chat provider (default: LEVI-first chain — best available LEVI weight, else rules planner)",
    )
    ag_chat.add_argument(
        "--yes",
        action="store_true",
        help="Pre-grant consent for gated tools for THIS session only.",
    )
    ag_chat.add_argument(
        "--max-steps",
        type=int,
        default=10,
        help="Max provider turns per message (default 10)",
    )
    ag_chat.add_argument(
        "--workspace", default=None, help="Workspace root for agent file/shell tools"
    )
    ag_chat.add_argument(
        "--register",
        default=None,
        metavar="VARIANT",
        help="Speak as a LEVI SI register for the whole session "
        "(e.g. levi_care). See `levi agent run --help` for the id list.",
    )
    ag_chat.add_argument(
        "--affect",
        action="store_true",
        help="Enable the 5D affect engine for the session (docs/AFFECT.md).",
    )
    ag_model = ag_sub.add_parser(
        "model", help="The LEVI model family: list, status, pull, use"
    )
    ag_msub = ag_model.add_subparsers(dest="agent_model_action")
    ag_msub.add_parser(
        "list", help="List the LEVI family first, then other selectable sources"
    )
    ag_use = ag_msub.add_parser(
        "use", help="Persist the default LEVI weight (~/.levi/agent/model_choice.json)"
    )
    ag_use.add_argument(
        "name", help="LEVI family member: levi-tiny | levi-0.6b | levi-4b"
    )
    ag_pull = ag_msub.add_parser(
        "pull",
        help="Download a LEVI remix's GGUF weights (and the runner, best effort)",
    )
    ag_pull.add_argument(
        "name",
        nargs="?",
        default=None,
        help="LEVI family remix to pull: levi-0.6b | levi-4b (levi-tiny is trained, not downloaded)",
    )
    ag_pull.add_argument(
        "--model",
        default=None,
        choices=sorted(_local_model_choices()),
        help="Legacy base-model key (default: qwen3-0.6b). Prefer the positional LEVI name.",
    )
    ag_pull.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if the weights file is already present",
    )
    ag_msub.add_parser(
        "status",
        help="Report the active LEVI weight, family readiness, and other sources",
    )
    ag_serve = ag_sub.add_parser(
        "serve", help="Serve the agent over HTTP (requires LEVI_AGENT_TOKEN)"
    )
    ag_serve.add_argument(
        "--host", default="127.0.0.1", help="Bind address (default 127.0.0.1)"
    )
    ag_serve.add_argument("--port", type=int, default=8765, help="Port (default 8765)")
    bld_p = sub.add_parser(
        "builder", help="E3-E6 Emergency Builder (scaffold to product)"
    )
    bld_p.add_argument("--plan", default=None, help="Goal text")
    bld_p.add_argument("--tier", default="E4", help="E3|E4|E5|E6")
    bld_p.add_argument("--name", default="new_project")
    bld_p.add_argument("--target", default="independent", help="independent|levi")
    bld_p.add_argument("--apply", default=None, help="Job id to apply")
    bld_p.add_argument("--force", action="store_true")
    uni_p = sub.add_parser("unified", help="LEVI Daemon Core unified cycle")
    uni_p.add_argument("--cycle", default=None, help="Run one cycle for task text")
    uni_p.add_argument(
        "--execute", action="store_true", help="Allow local-safe execute steps"
    )
    uni_p.add_argument("--estop", action="store_true")
    uni_p.add_argument("--clear-estop", action="store_true")
    uni_p.add_argument("--reason", default="")
    dem_p = sub.add_parser("demand", help="DemandPulse scan / opportunities")
    dem_p.add_argument("--scan", default=None)
    dem_p.add_argument("--segment", default="general")
    dem_p.add_argument("--title", default=None, help="Score opportunity title")
    dem_p.add_argument("--demand-score", dest="demand_score", type=float, default=0.6)
    dem_p.add_argument("--serviceability", type=float, default=0.6)
    dem_p.add_argument("--cost", type=float, default=0.2)
    dem_p.add_argument(
        "--five-factor",
        action="store_true",
        help="Score --title with the five-factor model instead of worth",
    )
    dem_p.add_argument("--ff-demand", type=float, default=None)
    dem_p.add_argument("--ff-market", type=float, default=None)
    dem_p.add_argument("--ff-gap", type=float, default=None)
    dem_p.add_argument("--ff-velocity", type=float, default=None)
    dem_p.add_argument("--ff-feasibility", type=float, default=None)
    dem_p.add_argument(
        "--ff-basis",
        default=None,
        help="Basis note recorded for every factor (required)",
    )
    dem_p.add_argument(
        "--ff-weights",
        default=None,
        help='Override weights, e.g. "0.3,0.25,0.2,0.15,0.1"',
    )
    dem_p.add_argument("--ff-threshold", type=float, default=75.0)
    inc_p = sub.add_parser(
        "income", help="Income Factory (capability, not whole purpose)"
    )
    inc_p.add_argument("--compose", default=None)
    inc_p.add_argument("--service", default="service modernization")
    mh_p = sub.add_parser("memory-hierarchy", help="Memory hierarchy + why-belief")
    mh_p.add_argument("--why", default=None, help="Trace belief to evidence")
    gr_p = sub.add_parser("growth", help="Raise baby Levi: developmental learning loop")
    gr_p.add_argument(
        "growth_action",
        nargs="?",
        default="status",
        choices=[
            "status",
            "cycle",
            "journal",
            "learnings",
            "forget",
            "curriculum",
            "study",
            "pack",
            "export-corpus",
        ],
    )
    gr_p.add_argument(
        "curriculum_action",
        nargs="?",
        default="load",
        choices=["load", "list", "run", "trend"],
        help="curriculum: load|list; study: run|trend "
        "(shared second positional; the action picks its own)",
    )
    gr_p.add_argument(
        "--study-model",
        action="store_true",
        help="study: allow model reflection instead of rules-only",
    )
    gr_p.add_argument(
        "--dry-run", action="store_true", help="cycle: preview without writing anything"
    )
    gr_p.add_argument(
        "--no-model",
        action="store_true",
        help="cycle: use rule-based reflection only (offline)",
    )
    gr_p.add_argument("--limit", type=int, default=10, help="journal: entries to show")
    gr_p.add_argument("--kind", default="", help="learnings: filter by kind")
    gr_p.add_argument(
        "--id",
        dest="forget_id",
        default="",
        help="forget: learning id prefix to remove",
    )
    gr_p.add_argument(
        "--tag", default="", help="forget: remove learnings with this tag"
    )
    gr_p.add_argument(
        "--out",
        default="",
        help="export-corpus: destination JSONL file",
    )
    gr_p.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="export-corpus: only learnings at or above this confidence",
    )
    gr_p.add_argument(
        "--build",
        action="store_true",
        help="pack: build a versioned learning pack from shareable learnings",
    )
    gr_p.add_argument(
        "--ingest",
        default="",
        help="pack: ingest a learning pack file (offline fallback)",
    )
    gr_p.add_argument(
        "--sync",
        action="store_true",
        help="pack: pull the latest learning pack from the cloud server and ingest it",
    )
    gr_p.add_argument(
        "--pack-list", action="store_true", help="pack: list installed learning packs"
    )
    gr_p.add_argument(
        "--min-corroboration",
        type=int,
        default=0,
        help="pack build: only include learnings corroborated at least N times",
    )
    gr_p.add_argument(
        "--server",
        default="",
        help="pack sync: cloud server base URL (or LEVI_CLOUD_SERVER)",
    )
    gr_p.add_argument(
        "--api-key",
        default="",
        help="pack sync: API key or owner token (or LEVI_API_KEY / LEVI_AGENT_TOKEN)",
    )
    brain_p = sub.add_parser("brain", help="Corpus + indexed brain table + export")
    brain_p.add_argument(
        "brain_action",
        nargs="?",
        default="table",
        choices=["table", "corpus", "set", "export", "atlas"],
    )
    brain_p.add_argument(
        "--seed-atlas", action="store_true", help="Pre-load offline brain A-Z atlas"
    )
    brain_p.add_argument(
        "--seed-expand", action="store_true", help="Mass combinatorial corpus expand"
    )
    brain_p.add_argument(
        "--seed-hyperdrive",
        action="store_true",
        help="Seed high-signal hyperdrive operational units",
    )
    brain_p.add_argument(
        "--seed-knowledge",
        action="store_true",
        help="Seed A–Z subjects, events, inventors, stars, X-domain",
    )
    # >>> LEVI Stage-1 lineage — seed path (source-sync entry `levi-ai`)
    brain_p.add_argument(
        "--seed-stage1",
        action="store_true",
        help="Seed 25 Stage-1 nano literacy units (rewritten textbook facts)",
    )
    # <<< LEVI Stage-1 lineage
    brain_p.add_argument(
        "--seed-knowledge-heavy",
        action="store_true",
        help="Heavy knowledge: depth A–Z, more figures, cognition, wit",
    )
    brain_p.add_argument(
        "--seed-x100",
        action="store_true",
        help="×100 densified operators knowledge pack",
    )
    brain_p.add_argument(
        "--seed-max", action="store_true", help="MAX knowledge pack (~2500 units)"
    )
    brain_p.add_argument(
        "--seed-expand2",
        action="store_true",
        help="Expansion pack II (interpenetration literacy)",
    )
    brain_p.add_argument("--expand-limit", type=int, default=25000)
    brain_p.add_argument("--add", default=None)
    brain_p.add_argument("--kind", default="OBSERVED")
    brain_p.add_argument("--source", default="")
    brain_p.add_argument("--domain", default="general")
    brain_p.add_argument("--key", default="note")
    brain_p.add_argument("--value", default="")
    brain_p.add_argument("--query", default="")
    echo_p = sub.add_parser("echo", help="Echo organ — taken/not-taken/wild")
    echo_p.add_argument("--seed", default="silence")
    man_p = sub.add_parser("mandella", help="Mandella organ — domain stakes")
    man_p.add_argument("--domain", default="build")
    man_p.add_argument("--seed", default="")
    sub.add_parser("pulse", help="Local pulse self-check")
    rel_p = sub.add_parser("relay", help="Model relay status / test")
    rel_p.add_argument("--test", action="store_true")
    vault_p = sub.add_parser("vault", help="Vault seal encrypt local notes")
    vault_p.add_argument("--passphrase", default="")
    vault_p.add_argument("--put", default=None)
    vault_p.add_argument("--text", default=None)
    vault_p.add_argument("--get", default=None)
    crs_p = sub.add_parser("courses", help="awesome-courses curriculum knowledge base")
    crs_p.add_argument(
        "courses_action",
        nargs="?",
        default="list",
        choices=["list", "brief", "coverage"],
    )
    crs_p.add_argument(
        "subject", nargs="?", default=None, help="subject slug (for brief)"
    )
    crs_p.add_argument(
        "--subject",
        dest="subject_filter",
        default=None,
        help="expand one subject in list",
    )
    sec_p = sub.add_parser(
        "security", help="offline defensive security knowledge index"
    )
    sec_p.add_argument(
        "security_action",
        nargs="?",
        default="list",
        choices=["list", "search", "show"],
    )
    sec_p.add_argument(
        "query", nargs="?", default=None, help="search query or entry id (for show)"
    )
    bty_p = sub.add_parser(
        "bounty", help="bug-bounty recon: scoped, polite, recon-only"
    )
    bty_cmd = bty_p.add_subparsers(dest="bounty_cmd")
    bty_scope = bty_cmd.add_parser("scope", help="manage enrolled program scopes")
    bty_scope_cmd = bty_scope.add_subparsers(dest="scope_cmd")
    for _sc in ("add", "remove", "list"):
        _p = bty_scope_cmd.add_parser(_sc)
        if _sc in ("add", "remove"):
            _p.add_argument("domain", help="program domain to enroll/remove")
    bty_recon = bty_cmd.add_parser(
        "recon", help="run enum -> probe -> content -> store"
    )
    bty_recon.add_argument("domain", help="target domain (must be in scope)")
    bty_recon.add_argument(
        "--ports", default=None, help="comma-separated ports, e.g. 80,443,8080"
    )
    bty_find = bty_cmd.add_parser("findings", help="list stored findings")
    bty_find.add_argument("--new", action="store_true", help="only new since last run")
    bty_cmd.add_parser("monitor", help="recon all scopes, print only new findings")
    con_p = sub.add_parser(
        "console", help="interactive text dashboard (security, bounty, demand)"
    )
    sim_p = sub.add_parser(
        "sim", help="bounded text simulations (clearly labeled, zero network)"
    )
    sim_p.add_argument(
        "scenario",
        nargs="?",
        default=None,
        help="scenario to run (see: levi sim --list)",
    )
    sim_p.add_argument("--list", action="store_true", help="list available scenarios")
    sim_p.add_argument("--seed", type=int, default=None, help="deterministic seed")
    # >>> LEVI backup module — minimal hook (backup coordinator)
    register_backup_parser(sub)
    # <<< LEVI backup module
    # >>> LEVI jobs module — minimal hook (Hybrid Search & Apply tracker)
    register_jobs_parser(sub)
    # <<< LEVI jobs module
    # >>> LEVI teach module — minimal hook (teach worker)
    register_teach_parser(sub)
    # <<< LEVI teach module
    # >>> LEVI Stage-1 lineage — minimal hooks (source-sync entry `levi-ai`)
    register_surgeon_parser(sub)
    register_automation_parser(sub)
    # <<< LEVI Stage-1 lineage
    news_p = sub.add_parser(
        "news", help="Current-events ingest (dated recall, not live)"
    )
    news_p.add_argument(
        "news_action",
        nargs="?",
        default="latest",
        choices=["refresh", "latest", "search"],
    )
    news_p.add_argument("news_arg", nargs="?", default=None, help="query for search")
    news_p.add_argument("--limit", type=int, default=10)
    sub.add_parser(
        "capabilities", help="Honest capability atlas: what LEVI can do"
    ).add_argument("domain", nargs="?", default=None, help="domain id (optional)")
    aff_p = sub.add_parser("affect", help="5D emotional-intelligence engine")
    aff_p.add_argument(
        "affect_action", nargs="?", default="status", choices=["status", "detect"]
    )
    aff_p.add_argument(
        "affect_arg", nargs="?", default=None, help="text to analyze (for detect)"
    )
    lab_p = sub.add_parser("lab", help="LEVI Lab: on-device agentic AI demos")
    lab_p.add_argument(
        "lab_action",
        nargs="?",
        default="scenarios",
        choices=["scenarios", "run", "footprint", "card", "chat"],
    )
    lab_p.add_argument(
        "lab_arg", nargs="?", default=None, help="scenario id (run) or model key (card)"
    )
    lab_p.add_argument(
        "--live",
        action="store_true",
        help="run: execute the loop live instead of playing back the fixture",
    )
    lab_p.add_argument("--params", default="0.6B", help="footprint: e.g. 30B")
    lab_p.add_argument(
        "--quant", default="int4", help="footprint: fp32/fp16/bf16/int8/int4"
    )
    lab_p.add_argument("--ctx", default="32k", help="footprint: e.g. 32k")
    lab_p.add_argument(
        "--endpoint",
        default=None,
        help="chat: OpenAI-compatible base URL (or LEVI_LAB_ENDPOINT)",
    )
    lab_p.add_argument("--model", default=None, help="chat: model id")
    # --- LEVI Boot Camp: 30-day 24/7 program (academy-owned block) ---
    acad_p = sub.add_parser(
        "academy", help="LEVI Boot Camp: 30-day 24/7 training program"
    )
    acad_p.add_argument(
        "academy_action",
        nargs="?",
        default="status",
        choices=["status", "session"],
    )
    acad_p.add_argument("--day", type=int, default=None, help="session: day 1-30")
    acad_p.add_argument("--block", type=int, default=None, help="session: block 1-4")
    # --- end academy-owned block ---
    proj_p = sub.add_parser(
        "project",
        help="Pre-MVP phase runner / HITL / capability log (service capability-discovery)",
    )
    mcp_p = sub.add_parser(
        "mcp",
        help="MCP: serve LEVI's tools, or connect LEVI out to external MCP servers",
    )
    mcp_p.add_argument(
        "mcp_action",
        nargs="?",
        default="serve",
        choices=["serve", "add", "remove", "list-servers", "catalog"],
        help="mcp action",
    )
    mcp_p.add_argument(
        "name",
        nargs="?",
        default=None,
        help="add/remove: server name (with --catalog, defaults to the entry name)",
    )
    mcp_p.add_argument(
        "--catalog",
        default=None,
        metavar="ENTRY",
        help="add: install a server from the curated catalog "
        "(`levi mcp catalog` to browse; one-command install)",
    )
    mcp_p.add_argument(
        "--url",
        default=None,
        help="add: Streamable-HTTP endpoint URL (e.g. http://host:8899/mcp)",
    )
    mcp_p.add_argument(
        "--cmd",
        default=None,
        help='add: stdio server command line, quoted (e.g. "npx -y some-mcp-server")',
    )
    mcp_p.add_argument(
        "--client-transport",
        default="",
        help="add: http|stdio (auto-detected from --url/--cmd by default)",
    )
    mcp_p.add_argument(
        "--header",
        action="append",
        default=[],
        help="add: extra HTTP header as KEY=VALUE (repeatable)",
    )
    mcp_p.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="add: per-call timeout in seconds (default 30)",
    )
    mcp_p.add_argument(
        "--reference",
        default=None,
        help="add: external provider behind this server, recorded as a "
        "reference (e.g. KAI-9000) — never a source, never LEVI identity",
    )
    mcp_p.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "http"],
        help="stdio: full owner registry (for local MCP clients); http: restricted cloud-safe profile",
    )
    mcp_p.add_argument("--host", default="127.0.0.1", help="http: bind address")
    mcp_p.add_argument("--port", type=int, default=8899, help="http: bind port")
    mcp_p.add_argument(
        "--token", default="", help="http: optional Bearer token (401 without it)"
    )
    mcp_p.add_argument(
        "--consent",
        action="store_true",
        help="stdio: pre-authorize confirmation-gated tools (owner only; off by default)",
    )
    soul_p = sub.add_parser(
        "soul", help="Owner soul: system-prompt override (~/.levi/soul.md)"
    )
    soul_p.add_argument(
        "action",
        nargs="?",
        default="show",
        choices=["show", "edit-note"],
        help="show the override, or how to edit it",
    )
    hb_p = sub.add_parser(
        "heartbeat", help="Autonomous self-check: quiet when healthy, digest when not"
    )
    hb_p.add_argument(
        "heartbeat_action",
        nargs="?",
        default="run",
        choices=["run", "status"],
        help="heartbeat action",
    )
    hb_p.add_argument(
        "--force", action="store_true", help="run: ignore interval/active-hours gating"
    )
    hb_p.add_argument(
        "--interval-min",
        type=int,
        default=None,
        help="run: override the check interval in minutes",
    )
    to_p = sub.add_parser(
        "torch", help="Pass the torch: mentor bundle for a new LEVI instance"
    )
    to_p.add_argument(
        "torch_action",
        nargs="?",
        default="create",
        choices=["create", "read", "sign"],
        help="create: package a bundle; read: ingest one as seed; sign: sign the founder's note",
    )
    to_p.add_argument(
        "path",
        nargs="?",
        default="",
        help="bundle file (create: optional output path; read/sign: required)",
    )
    to_p.add_argument(
        "--yes",
        action="store_true",
        help="read: ingest after the preview (Plan→Preview→Permission)",
    )
    to_p.add_argument(
        "--by",
        dest="sign_by",
        default="",
        help="sign: who is signing the founder's note",
    )
    to_p.add_argument(
        "--note", dest="sign_note", default="", help="sign: the founder's note text"
    )
    lp_p = sub.add_parser(
        "lifepack", help="Life pack: portable LEVI state (export/import)"
    )
    lp_p.add_argument(
        "lifepack_action",
        choices=["export", "import", "preview"],
        help="lifepack action (preview: diff without writing)",
    )
    lp_p.add_argument("file", help="pack file to write (export) or read (import)")
    lp_p.add_argument(
        "--preview",
        action="store_true",
        help="import: show the diff without writing anything",
    )
    lp_p.add_argument(
        "--yes",
        action="store_true",
        help="import: confirm non-interactively (otherwise prompts)",
    )
    # `levi pack`: life-pack *bundles* — the tamper-evident, optionally
    # encrypted .tar.gz shipping format (Megazord axis 10). The passphrase
    # is NEVER a CLI arg (it would land in shell history): it comes from
    # --passphrase-env VAR or an interactive prompt.
    pk_p = sub.add_parser(
        "pack", help="Life-pack bundles: encrypted portable state (.tar.gz)"
    )
    pk_sub = pk_p.add_subparsers(dest="pack_action")
    pk_exp = pk_sub.add_parser("export", help="Export this home to a bundle")
    pk_exp.add_argument(
        "--output",
        default=None,
        help="Destination path (default: ./levi-lifepack-<utc>.tar.gz[.enc])",
    )
    pk_exp.add_argument(
        "--passphrase-env",
        default=None,
        help="Env var holding the bundle passphrase (encrypts the bundle)",
    )
    pk_exp.add_argument(
        "--no-encrypt",
        action="store_true",
        help="Write the bundle UNENCRYPTED (loud warning: personal state inside)",
    )
    pk_imp = pk_sub.add_parser("import", help="Import a bundle into this home")
    pk_imp.add_argument("bundle", help="Path to the .tar.gz[.enc] bundle")
    pk_imp.add_argument(
        "--preview",
        action="store_true",
        help="Verify the bundle and show the diff without writing anything",
    )
    pk_imp.add_argument(
        "--passphrase-env",
        default=None,
        help="Env var holding the bundle passphrase (for encrypted bundles)",
    )
    pk_imp.add_argument(
        "--yes",
        action="store_true",
        help="Confirm a real import without an interactive prompt",
    )
    proj_p.add_argument(
        "project_action",
        nargs="?",
        default="status",
        choices=["status", "log", "hitl", "phases"],
    )
    proj_p.add_argument("--url", default=None, help="Public site URL for archaeology")
    proj_p.add_argument("--run", default=None, help="Run phase id e.g. P0, P1")
    proj_p.add_argument("--complete", default=None, help="Mark phase complete")
    proj_p.add_argument(
        "--log", dest="log_text", default=None, help="Append capability log note"
    )
    proj_p.add_argument("--skill", default="", help="Future skill tag for log")
    proj_p.add_argument("--approve", default=None, help="HITL request id to approve")
    proj_p.add_argument("--deny", default=None, help="HITL request id to deny")
    proj_p.add_argument("--note", default="", help="HITL decision note")
    mono_p = sub.add_parser("mono", help="Monotropism interest tunnel state")
    mono_p.add_argument(
        "--sense", default=None, help="Sample text to sense into tunnel"
    )
    wit_p.add_argument(
        "--tone", default="playful", help="Sample user tone for calibration"
    )
    dae = sub.add_parser("daemon", help="Control daemon: personas, wit, alchemy")
    dae.add_argument(
        "action",
        nargs="?",
        default="status",
        help="status|services|clear|alchemy|lock-persona|boost-persona|lock-wit|force-alchemy",
    )
    dae.add_argument("--target", default=None)
    dae.add_argument("--turns", type=int, default=10)
    dae.add_argument("--strength", type=float, default=0.6)
    dae.add_argument("--intensity", type=float, default=0.55)
    dae.add_argument("--off", action="store_true", help="For alchemy: disable")
    nerv = sub.add_parser("nervous", help="Affect matrix + persona activation scores")
    nerv.add_argument(
        "--unlock", action="store_true", help="Clear explicit persona lock"
    )
    nerv.add_argument(
        "--reset", action="store_true", help="Reset affect and usage counters"
    )
    nerv.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Dump full status JSON (affect, blend, hysteresis)",
    )
    sub.add_parser("skills")
    sub.add_parser("agents")
    g = sub.add_parser("graph")
    g.add_argument("--seed", default=None)
    img_p = sub.add_parser("image", help="Pollinations image gen for LEVI x LWP")
    img_p.add_argument("--prompt", default=None)
    img_p.add_argument("--story", default=None, help="Story id for still")
    img_p.add_argument("--beat", default="midpoint")
    img_p.add_argument("--width", type=int, default=1024)
    img_p.add_argument("--height", type=int, default=1024)
    img_p.add_argument("--model", default="flux")
    img_p.add_argument("--url-only", action="store_true")
    img_p.add_argument("--no-save", action="store_true")
    st = sub.add_parser("story", help="Create/list/expand L.W.P. stories")
    st.add_argument("--create", default=None, help="Premise for a new story")
    st.add_argument("--craft", action="store_true", help="Premium craft lenses menu")
    st.add_argument(
        "--expand", default=None, help="Story id to expand (cascade next beat)"
    )
    st.add_argument(
        "--focus", default="next_beat", help="next_beat|character|atmosphere"
    )
    st.add_argument("--id", default=None, help="Story id for --mode")
    st.add_argument(
        "--mode", default=None, help="social_media|abridged_series|void|spiral|..."
    )
    st.add_argument("--instruction", default="")
    st.add_argument("--show", default=None)
    st.add_argument("--genre", default="literary")
    st.add_argument("--title", default=None)
    st.add_argument(
        "--auto",
        action="store_true",
        help="Forward + backward generation at the same time",
    )
    st.add_argument(
        "--bidirectional",
        action="store_true",
        help="Alias: forward + backward same time",
    )
    st.add_argument(
        "--auto-forward",
        type=int,
        default=None,
        metavar="N",
        help="Auto N forward beats (0=fill cascade)",
    )
    st.add_argument(
        "--auto-backward",
        type=int,
        default=None,
        metavar="N",
        help="Auto N prior-cause beats",
    )
    ge = sub.add_parser("genres")
    ge.add_argument("--all", action="store_true")
    ge.add_argument("--category", default=None)
    fac_p = sub.add_parser("factory")
    fac_p.add_argument(
        "factory_action",
        nargs="?",
        default=None,
        choices=["status"],
        help="status: production-line view (hunt → archive → manufacture → stock → galaxy)",
    )
    fac_p.add_argument("--create", default=None)
    fac_p.add_argument("--idea", default=None)
    fac_p.add_argument("--advance", default=None)
    fac_p.add_argument("--summary", default="")
    fac_p.add_argument("--run", default=None, help="Run scaffolded main.py in sandbox")
    fac_p.add_argument(
        "--test", default=None, help="Smoke-test sandbox main.py (closed loop)"
    )
    sub.add_parser("automations")
    rem = sub.add_parser("remember")
    rem.add_argument("content", nargs="?", default=None)
    rem.add_argument("extra", nargs="*", default=[])
    rem.add_argument("--importance", type=float, default=0.6)
    rem.add_argument("--tags", default="")
    rec = sub.add_parser("recall")
    rec.add_argument("query", nargs="?", default=None)
    rec.add_argument("--limit", type=int, default=10)

    chat_p = sub.add_parser(
        "chat", help="Enterprise chat companion (session + personas + modes)"
    )
    chat_p.add_argument(
        "message", nargs="?", default=None, help="One-shot message (omit for REPL)"
    )
    chat_p.add_argument("extra", nargs="*", default=[])
    chat_p.add_argument("--session", default=None, help="Resume session id")
    chat_p.add_argument("--persona", default=None, help="Lock persona id")
    chat_p.add_argument(
        "--profile", "-P", default=None, help="spark|workbench|careful|edge|prime|care"
    )
    chat_p.add_argument(
        "--mode",
        default="companion",
        help="companion|mentor|challenger|writer|builder|quiet",
    )
    chat_p.add_argument("--list-sessions", action="store_true")
    chat_p.add_argument("--personas", action="store_true")
    chat_p.add_argument("--filter", default=None)
    sub.add_parser("enterprise", help="Enterprise readiness checklist")
    sub.add_parser("scorecard", help="10/10 SI cloud model scorecard")
    sub.add_parser("si", help="Synthetic intelligence identity")
    sub.add_parser("cognition", help="Personas, wit/sarcasm, cognition map")
    prem = sub.add_parser("premium", help="25 premium must-haves (next-gen offline SI)")
    voice_p = sub.add_parser(
        "voice",
        help="LEVI voice registers (14 original SI registers)",
    )
    voice_p.add_argument(
        "--variant",
        "-v",
        default=None,
        help="care|ops|challenger|literary|forensic|void|builder|mirror",
    )
    voice_p.add_argument(
        "--register",
        action="store_true",
        help="Register LEVI voices into persona lattice",
    )
    sub.add_parser("unique", help="Unique unreplicable LEVI organs")
    sub.add_parser("x100", help="×100 upgrade rail (status · law · next slices)")
    sub.add_parser("max", help="MAX upgrade (2500 knowledge · full counts)")
    sub.add_parser("max10", help="MAX ×10 combined (MAX + expansion pack)")
    sub.add_parser("stress", help="Stress test / verify engines + story quality")
    sub.add_parser("here", help="Where is LEVI — talk to SI now")
    talk_p = sub.add_parser("talk", help="Easy chat (mass-friendly profiles)")
    talk_p.add_argument("message", nargs="?", default=None)
    talk_p.add_argument("extra", nargs="*")
    talk_p.add_argument(
        "--profile",
        "-P",
        default="levi",
        help="levi|spark|workbench|careful|edge|prime|care",
    )
    talk_p.add_argument("--persona", default=None)
    talk_p.add_argument("--mode", default=None)
    talk_p.add_argument("--session", default=None)
    talk_p.add_argument("--list-profiles", action="store_true")
    prof_p = sub.add_parser(
        "profiles", help="LEVI hardwired quality traits (alias of traits)"
    )
    sub.add_parser("traits", help="LEVI hardwired quality traits (not presets)")
    prof_p.add_argument("--rate", action="store_true", help="Usability scorecard")
    sub.add_parser("dna", help="20 retired × 20 modern software DNA")
    sub.add_parser("intel", help="Intelligence forms × SI")
    sub.add_parser("giant", help="Tech-giant class × LEVI spin")
    sub.add_parser("future", help="Future integration ideas")
    ret = sub.add_parser("retention", help="Local retention posture (no dark patterns)")
    ret.add_argument("--touch", action="store_true", help="Count a session")
    ip = sub.add_parser("interpenetrate", help="Organ interpenetration mesh")
    ip.add_argument("--smoke", action="store_true", help="Import-path coupling smoke")
    prem.add_argument("--compact", action="store_true")
    prem.add_argument("--quiet", "-q", action="store_true")

    model_p = sub.add_parser(
        "model", help="Full Cloud Model — L.W.P. × LEVI literary SSA + integrations"
    )
    model_p.add_argument(
        "model_action",
        nargs="?",
        default="status",
        help="status|expand|deny|approve|reim|crown|rupture|causal|manuscript|configure|genres|story|characters|mirror|rail|smoke|snapshot",
    )
    model_p.add_argument("-n", type=int, default=1)
    model_p.add_argument("--seed", default=None)
    model_p.add_argument("--tracks", type=int, default=3)
    model_p.add_argument("--index", type=int, default=0, help="crown track index")
    model_p.add_argument("--lens", default="mccarthy")
    model_p.add_argument("--direction", default=None)
    model_p.add_argument("--phase", default=None)
    model_p.add_argument("--power", default=None)
    model_p.add_argument("--genres", default=None)
    model_p.add_argument("--pov", default=None)
    model_p.add_argument("--limit", type=int, default=0)
    model_p.add_argument("--polish", action="store_true", help="optional relay polish")

    cloud_p = sub.add_parser(
        "cloud",
        help="LEVI-as-cloud API keys/usage + product stages A/B/C + crypto protocol + ZK + sync dry-run",
    )
    cloud_p.add_argument(
        "cloud_action",
        nargs="?",
        default="all",
        help="keys|usage|all|stages|argon2|ratchet|crypto|zk|sync|demo  (alias: phases)",
    )
    cloud_p.add_argument(
        "cloud_args",
        nargs="*",
        help="extra args for 'keys' (create <name> | list | revoke <name|prefix>)",
    )
    cloud_p.add_argument(
        "--no-learn",
        dest="cloud_no_learn",
        action="store_true",
        help="keys create: opt this key out of growth learning",
    )
    cloud_p.add_argument(
        "--key",
        dest="cloud_key_filter",
        default=None,
        help="usage: only show records for this key name",
    )
    cloud_p.add_argument(
        "--limit",
        dest="cloud_limit",
        type=int,
        default=20,
        help="usage: most recent N records (default 20)",
    )

    # === MEGAZORD-AXIS1-REGION-BEGIN: one-CLI-surface parser registration ===
    # Parallel tracks: keep ALL axis-1 adapter wiring inside this delimited
    # region — do not scatter axis-1 hunks elsewhere in this file.
    arch_p = sub.add_parser(
        "archive",
        help="The LEVI Archive — Smithsonian of forgotten software",
    )
    arch_p.add_argument(
        "argv",
        nargs=argparse.REMAINDER,
        help="passed through to `python -m levi.archive`",
    )
    gal_p = sub.add_parser("galaxy", help="Galaxy ecosystem: packages, services")
    gal_p.add_argument(
        "argv",
        nargs=argparse.REMAINDER,
        help="passed through to `python -m levi.galaxy`",
    )
    meth_p = sub.add_parser(
        "methods", help="Methods warehouse: forgotten techniques, LEVI-native"
    )
    meth_p.add_argument(
        "methods_action",
        nargs="?",
        default="list",
        choices=["list", "show"],
        help="list shelves, or show one method",
    )
    meth_p.add_argument(
        "methods_name", nargs="?", default=None, help="method name for `show`"
    )
    rev_p = sub.add_parser(
        "revival", help="Revivals warehouse: retired-software ideas reborn"
    )
    rev_p.add_argument(
        "revival_action",
        nargs="?",
        default="list",
        choices=["list", "show"],
        help="list shelves, or show one revival",
    )
    rev_p.add_argument(
        "revival_name", nargs="?", default=None, help="revival name for `show`"
    )
    perp_p = sub.add_parser(
        "perpetual", help="Perpetual engine: pulse, hunts, services"
    )
    perp_p.add_argument(
        "argv",
        nargs=argparse.REMAINDER,
        help="passed through to `python -m levi.perpetual`",
    )
    oath_p = sub.add_parser(
        "oath", help="Oath trust mesh: keys, contacts, commands, audit"
    )
    oath_p.add_argument(
        "argv",
        nargs=argparse.REMAINDER,
        help="passed through to `python -m levi.oath`",
    )
    meg_p = sub.add_parser("megazord", help="MEGAZORD¹⁰ organism self-report")
    meg_p.add_argument(
        "megazord_action",
        nargs="?",
        default="status",
        choices=["status"],
        help="megazord action",
    )
    atlas_p = sub.add_parser(
        "atlas", help="Capability atlas (warehouse-grouped when landed)"
    )
    atlas_p.add_argument(
        "atlas_action",
        nargs="?",
        default="export",
        choices=["export"],
        help="atlas action",
    )
    atlas_p.add_argument(
        "--out",
        default=None,
        help="write atlas JSON to PATH (default: print summary)",
    )
    wf_p = sub.add_parser("workflow", help="Cross-module flagship workflows")
    wf_p.add_argument(
        "workflow_action",
        nargs="?",
        default="list",
        choices=["list", "run"],
        help="workflow action",
    )
    wf_p.add_argument("name", nargs="?", default=None, help="workflow name for `run`")
    wh_p = sub.add_parser(
        "warehouse", help="Browse LEVI's warehouses (not a tool belt)"
    )
    wh_p.add_argument(
        "warehouse_action",
        nargs="?",
        default="list",
        choices=["list", "browse", "inventory", "pull"],
        help="warehouse action",
    )
    wh_p.add_argument(
        "name",
        nargs="?",
        default=None,
        help="warehouse name (browse/inventory), or warehouse for `pull`",
    )
    wh_p.add_argument("item", nargs="?", default=None, help="item id for `pull`")
    wh_p.add_argument(
        "--limit", type=int, default=20, help="inventory: max items (default 20)"
    )
    bs_p = sub.add_parser("bloodstream", help="Single-bloodstream turn pipeline")
    bs_p.add_argument(
        "bloodstream_action",
        nargs="?",
        default="turn",
        choices=["turn", "bus-test"],
        help="bloodstream action",
    )
    bs_p.add_argument("text", nargs=argparse.REMAINDER, help="turn text (for `turn`)")
    # === MEGAZORD-AXIS1-REGION-END ===

    # === KING-REGION-BEGIN: King control plane (core/levi/king) ===
    # Parallel tracks: keep ALL King wiring inside this delimited region —
    # do not scatter King hunks elsewhere in this file.
    try:
        from levi.king.cli import register_king as _king_register

        _king_register(sub)
    except Exception:
        # King degrades: the CLI still boots without the control plane.
        pass
    # === KING-REGION-END ===

    # === SKILL-CREATE-REGION-BEGIN: skill scaffolder (core/levi/skill/creator.py) ===
    # Parallel tracks: keep ALL skill-scaffold wiring inside this delimited
    # region — do not scatter hunks elsewhere in this file.
    try:
        from levi.skill.creator import register_skill as _skill_register

        _skill_register(sub)
    except Exception:
        # Skill scaffolder degrades: the CLI still boots without it.
        pass
    # === SKILL-CREATE-REGION-END ===

    # === FLEET-REGION-BEGIN: Fleet command registration ===
    # Parallel tracks: keep ALL fleet wiring inside this delimited region —
    # do not scatter fleet hunks elsewhere in this file.
    try:
        from levi.fleet.cli import register_fleet as _fleet_register

        _fleet_register(sub)
    except Exception:
        # Fleet degrades: the CLI still boots without the workforce layer.
        pass
    # === FLEET-REGION-END ===

    # === CONTROL-REGION-BEGIN: Control-plane command registration ===
    # Parallel tracks: keep ALL control-plane wiring inside this delimited
    # region — do not scatter control hunks elsewhere in this file.
    try:
        from levi.control.cli import register_control as _control_register

        _control_register(sub)
    except Exception:
        # Control degrades: the CLI still boots without the control plane.
        pass
    # === CONTROL-REGION-END ===

    # === PWA-REGION-BEGIN: PWA command registration ===
    # Parallel tracks: keep ALL pwa wiring inside this delimited region —
    # do not scatter pwa hunks elsewhere in this file.
    try:
        from levi.pwa.cli import register_pwa as _pwa_register

        _pwa_register(sub)
    except Exception:
        # PWA degrades: the CLI still boots without the chat UI layer.
        pass
    # === PWA-REGION-END ===

    # === SANDBOX-REGION-BEGIN: Linux sandbox command registration ===
    # Parallel tracks: keep ALL sandbox wiring inside this delimited region —
    # do not scatter sandbox hunks elsewhere in this file.
    try:
        from levi.sandbox.cli import register_sandbox as _sandbox_register

        _sandbox_register(sub)
    except Exception:
        # Sandbox degrades: the CLI still boots without the sandbox layer.
        pass
    # === SANDBOX-REGION-END ===

    args = parser.parse_args()
    if not args.command:
        banner()
        p = ProfileStore().load()
        if not p.onboarded:
            print("Start here:  python -m levi.cli.main init")
        else:
            print(
                f"Welcome back, {p.name or 'friend'}.  Try: home | ask | templates | continue"
            )
        parser.print_help()
        return

    cmds = {
        "init": cmd_init,
        "home": cmd_home,
        "continue": cmd_continue,
        "morning": cmd_morning,
        "import": cmd_import,
        "export": cmd_export,
        "templates": cmd_templates,
        "status": cmd_status,
        "ask": cmd_ask,
        "turn": cmd_turn,
        "personas": cmd_personas,
        "wit": cmd_wit,
        "daemon": cmd_daemon,
        "mono": cmd_mono,
        "rail": cmd_rail,
        "mirror": cmd_mirror,
        "lwp-model": cmd_lwp_model,
        "characters": cmd_characters,
        "watch": cmd_watch,
        "crucible": cmd_crucible,
        "services": cmd_services,
        "serve-ui": cmd_serve_ui,
        "provenance": cmd_provenance,
        "perfection": cmd_perfection,
        "free": cmd_free,
        "production": cmd_production,
        "go": cmd_go,
        "integrate": cmd_integrate,
        "ops": cmd_ops,
        "ladder": cmd_ladder,
        "organism": cmd_organism,
        "charter": cmd_charter,
        "symbiosis": cmd_symbiosis,
        "sandbox": cmd_sandbox,
        "plugins": cmd_plugins,
        "plugin": cmd_plugin,
        "reference": cmd_reference,
        "doc": cmd_doc,
        "finance": cmd_finance,
        "forge": cmd_forge,
        "agent": cmd_agent,
        "builder": cmd_builder,
        "unified": cmd_unified,
        "demand": cmd_demand,
        "income": cmd_income,
        "memory-hierarchy": cmd_memory_hierarchy,
        "growth": cmd_growth,
        "brain": cmd_brain,
        "echo": cmd_echo,
        "mandella": cmd_mandella,
        "pulse": cmd_pulse,
        "relay": cmd_relay,
        "vault": cmd_vault,
        "courses": cmd_courses,
        "security": cmd_security,
        "bounty": cmd_bounty,
        "console": cmd_console,
        "sim": cmd_sim,
        # >>> LEVI backup module — minimal hook (backup coordinator)
        "backup": cmd_backup,
        # <<< LEVI backup module
        # >>> LEVI jobs module — minimal hook (Hybrid Search & Apply tracker)
        "jobs": cmd_jobs,
        # <<< LEVI jobs module
        # >>> LEVI teach module — minimal hook (teach worker)
        "teach": cmd_teach,
        # <<< LEVI teach module
        # >>> LEVI Stage-1 lineage — minimal hooks (source-sync entry `levi-ai`)
        "surgeon": cmd_surgeon,
        "automation": cmd_automation,
        # <<< LEVI Stage-1 lineage
        "news": cmd_news,
        "capabilities": cmd_capabilities,
        "affect": cmd_affect,
        "lab": cmd_lab,
        "academy": cmd_academy,  # academy-owned
        "project": cmd_project,
        "nervous": cmd_nervous,
        "skills": cmd_skills,
        "agents": cmd_agents,
        "graph": cmd_graph,
        "image": cmd_image,
        "story": cmd_story,
        "genres": cmd_genres,
        "factory": cmd_factory,
        "automations": cmd_automations,
        "remember": cmd_remember,
        "recall": cmd_recall,
        "cloud": cmd_cloud,
        "model": cmd_model,
        "chat": cmd_chat,
        "enterprise": cmd_enterprise,
        "scorecard": cmd_scorecard,
        "si": cmd_si,
        "cognition": cmd_cognition,
        "premium": cmd_premium,
        "voice": cmd_voice,
        "unique": cmd_unique,
        "x100": cmd_x100,
        "max": cmd_max,
        "max10": cmd_max10,
        "stress": cmd_stress,
        "here": cmd_here,
        "talk": cmd_talk,
        "profiles": cmd_profiles,
        "traits": cmd_traits,
        "retention": cmd_retention,
        "dna": cmd_dna,
        "intel": cmd_intel,
        "giant": cmd_giant,
        "future": cmd_future,
        "interpenetrate": cmd_interpenetrate,
    }
    # === KING-REGION-BEGIN: King command dispatch ===
    # Parallel tracks: keep ALL King wiring inside this delimited region.
    try:
        from levi.king.cli import cmd_king as _cmd_king

        cmds["king"] = _cmd_king
    except Exception:
        pass
    # === KING-REGION-END ===
    # === SKILL-CREATE-REGION-BEGIN: skill command dispatch ===
    try:
        from levi.skill.creator import cmd_skill as _cmd_skill

        cmds["skill"] = _cmd_skill
    except Exception:
        pass
    # === SKILL-CREATE-REGION-END ===
    # === MCP-REGION-BEGIN: MCP server command dispatch ===
    try:
        from levi.mcp.cli import cmd_mcp as _cmd_mcp

        cmds["mcp"] = _cmd_mcp
    except Exception:
        pass
    # === MCP-REGION-END ===
    # === FLEET-REGION-BEGIN: Fleet command dispatch ===
    try:
        from levi.fleet.cli import cmd_fleet as _cmd_fleet

        cmds["fleet"] = _cmd_fleet
    except Exception:
        pass
    # === FLEET-REGION-END ===
    # === CONTROL-REGION-BEGIN: Control-plane command dispatch ===
    try:
        from levi.control.cli import (
            cmd_approve as _cmd_approve,
            cmd_ledger as _cmd_ledger,
            cmd_route as _cmd_route,
        )

        cmds["approve"] = _cmd_approve
        cmds["ledger"] = _cmd_ledger
        cmds["route"] = _cmd_route
    except Exception:
        pass
    # === CONTROL-REGION-END ===
    # === PWA-REGION-BEGIN: PWA command dispatch ===
    try:
        from levi.pwa.cli import cmd_pwa as _cmd_pwa

        cmds["pwa"] = _cmd_pwa
    except Exception:
        pass
    # === PWA-REGION-END ===
    # === SANDBOX-REGION-BEGIN: Linux sandbox command dispatch ===
    # Parallel tracks: keep ALL sandbox dispatch inside this delimited region —
    # do not scatter sandbox hunks elsewhere in this file.
    try:
        from levi.sandbox.cli import cmd_sandbox as _cmd_sandbox

        cmds["sandbox"] = _cmd_sandbox
    except Exception:
        pass
    # === SANDBOX-REGION-END ===
    # === SOUL-REGION-BEGIN: Soul command dispatch ===
    try:
        from levi.agent.soul import cmd_soul as _cmd_soul

        cmds["soul"] = _cmd_soul
    except Exception:
        pass
    # === SOUL-REGION-END ===
    # === HEARTBEAT-REGION-BEGIN: Heartbeat command dispatch ===
    try:
        from levi.daemon.heartbeat import cmd_heartbeat as _cmd_heartbeat

        cmds["heartbeat"] = _cmd_heartbeat
    except Exception:
        pass
    # === HEARTBEAT-REGION-END ===
    # === LIFEPACK-REGION-BEGIN: Life-pack command dispatch ===
    try:
        from levi.lifepack.pack import cmd_lifepack as _cmd_lifepack

        cmds["lifepack"] = _cmd_lifepack
    except Exception:
        pass
    # `levi pack`: bundle (tar.gz + manifest + optional Fernet) dispatch.
    try:
        from levi.lifepack.bundle import cmd_pack as _cmd_pack

        cmds["pack"] = _cmd_pack
    except Exception:
        pass
    # === LIFEPACK-REGION-END ===
    # === TORCH-REGION-BEGIN: Pass-the-torch command dispatch ===
    try:
        from levi.torch import cmd_torch as _cmd_torch

        cmds["torch"] = _cmd_torch
    except Exception:
        pass
    # === TORCH-REGION-END ===
    # === MEGAZORD-AXIS1-REGION-BEGIN: axis-1 dispatch registration ===
    # Parallel tracks: keep ALL axis-1 dispatch hunks inside this region.
    cmds["archive"] = cmd_archive
    cmds["galaxy"] = cmd_galaxy
    cmds["methods"] = cmd_methods
    cmds["revival"] = cmd_revival
    cmds["perpetual"] = cmd_perpetual
    cmds["oath"] = cmd_oath
    cmds["megazord"] = cmd_megazord
    cmds["atlas"] = cmd_atlas
    cmds["workflow"] = cmd_workflow
    cmds["warehouse"] = cmd_warehouse
    cmds["bloodstream"] = cmd_bloodstream
    # lifepack preview: fill the gap without touching levi/lifepack/pack.py.
    try:
        from levi.lifepack.pack import cmd_lifepack as _cmd_lifepack_base

        def _cmd_lifepack(args, _base=_cmd_lifepack_base):
            if getattr(args, "lifepack_action", None) == "preview":
                return _cmd_lifepack_preview(args)
            return _base(args)

        cmds["lifepack"] = _cmd_lifepack
    except Exception:
        pass
    # === MEGAZORD-AXIS1-REGION-END ===
    fn = cmds.get(args.command)
    if fn:
        try:
            fn(args)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            # Structured error surface (levi.ops.errors) — never a raw
            # traceback for operators; still non-zero exit for scripts.
            from levi.ops.errors import LeviError

            err = LeviError(
                code="cli:%s" % (args.command or "unknown"),
                message=str(e)[:200] or e.__class__.__name__,
                recoverable=True,
                detail={"command": args.command or ""},
            )
            print(err.format(), file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
