#!/usr/bin/env python3
"""
LEVI × L.W.P. CLI — Companion + constructive DNA + retention surface
Power complexity is soft by default; use --verbose for internals.
"""

from __future__ import annotations
import argparse
import json
import sys
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
    loop_map = {"1": "companion", "2": "writing", "3": "building",
                "companion": "companion", "writing": "writing", "building": "building"}
    preferred = loop_map.get(loop, "companion")
    p.name = name
    p.goal_this_week = goal
    p.preferred_loop = preferred
    p.onboarded = True
    p.confirm_constructive = not args.yes
    store.save(p)

    # Seed memory
    mem = MemoryStore()
    mem.add(MemoryType.SEMANTIC, content=f"User name: {name}", importance=0.9, source="init", tags=["profile"])
    if goal:
        mem.add(MemoryType.SEMANTIC, content=f"Goal this week: {goal}", importance=0.85, source="init", tags=["goal"])

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
    print("  levi ask \"...\"       — talk to me")
    if preferred == "writing":
        print("  levi templates     — try systems_horror_seed")
    elif preferred == "building":
        print("  levi templates     — try checklist_cli")
    else:
        print("  levi ask \"Who are you?\"")
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
    print(f"Model: {'local ready' if st.get('local_available') else 'offline fallback (ollama optional)'}")
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
        print("Nothing on the shelf yet. Try: levi templates  or  levi ask \"Build me...\"")
        return
    print(f"Continuing [{item.kind}] {item.title} ({item.id})\n")
    orch = Orchestrator(persona_id=args.personality)
    if item.kind == "story":
        r = orch.turn(f"expand story {item.id}")
        print(r.response if not _verbose(args) else r.response)
        try:
            from levi.runtime.continuity import ContinuityShelf
            ContinuityShelf().snapshot(last_ask=getattr(args, "text", "") or "", last_reply=str(r.response)[:200])
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
            print("Voice: local model not detected. Structural path still works offline.")
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
        print(f"Model: {'local' if router.status().get('local_available') else 'offline fallback'}")
        print(f"Memory entries: {memory.stats().get('total', 0)}")
        print(f"Skills: {len(skills.list())} · Specialists: {len(agents.list())}")
        print(f"Shelf items: {len(collect_shelf())}")
        if not router.status().get("local_available"):
            print("\nTip: ollama serve && ollama pull llama3.2")
        return

    print("=== LEVI System Status (verbose) ===\n")
    print(json.dumps({"profile": p.to_dict(), "memory": memory.stats(),
                      "model": router.status(), "policy": policy.status()}, indent=2))


def cmd_ask(args):
    if getattr(args, "ultimate", False):
        from levi.ei.ultimate_path import ultimate_reply
        q = (getattr(args, "question", None) or "") + " " + " ".join(getattr(args, "extra", None) or [])
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
        print('Usage: levi turn [--persona NAME] [--provider NAME] [--session ID] '
              '[--composite NAME] [--yes] [--dry-run] "your text"')
        return

    if getattr(args, "yes", False):
        confirm = lambda proposal: True  # noqa: E731
    else:
        def confirm(proposal):
            try:
                ans = input(
                    f"Approve '{proposal.description}' "
                    f"(risk {int(proposal.risk_level)})? [y/N] "
                ).strip().lower()
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
        print(rail.advance(args.advance, hitl_approved=bool(getattr(args, "approved", False))))
        return
    print(rail.format_status())

def cmd_mirror(args):
    from levi.lwp.mirror_cascade import reverse_crosscheck
    print(reverse_crosscheck(getattr(args, "seed", None) or "empty", getattr(args, "context", "") or ""))


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
        print(eng.reim_forks(seed=getattr(args, "seed", None), tracks=int(getattr(args, "tracks", None) or 3)))
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
    from levi.identity.provenance import provenance_report, scan_tree_for_foreign_branding
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
            print(json.dumps({"schema": "levi.free_graph.path/v1", "from": a,
                              "to": b, "path": route}, indent=2))
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
            print(json.dumps({"schema": "levi.free_graph.neighborhood/v1", "id": nid,
                              "depth": depth,
                              "layers": {str(k): v for k, v in layers.items()}}, indent=2))
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
            class A:
                pass
            cmd_ladder(A())
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
        print(f"Unknown connector {getattr(args, 'connector', None)!r}. Try: levi plugin list")
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
        print(_json.dumps({
            "connector": result.connector,
            "operation": result.operation,
            "ok": result.ok,
            "status": result.status,
            "message": result.message,
            "data": result.data,
            "request_made": result.request_made,
        }, indent=2))
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

    ADVISORY_BANNER = "══ ADVISORY ONLY — paper only, not financial advice ══"

    def _bars_for(symbol: str, days: int = 120) -> list:
        provider = _market.StooqProvider()
        try:
            return provider.daily_bars(symbol, days=days)
        except _market.MarketDataError as exc:
            # Honest failure: name what happened, print no numbers, exit 1.
            print(f"Market data unavailable for {symbol}: {exc}")
            raise SystemExit(1) from None

    def _fmt(value, need: int, have: int, decimals: int = 4) -> str:
        if value is None:
            return f"n/a (needs {need} bars, have {have})"
        return f"{value:.{decimals}f}"

    action = getattr(args, "finance_action", None)

    # -- quote -----------------------------------------------------------
    if action == "quote":
        symbol = str(getattr(args, "sym", "") or "").upper()
        bars = _bars_for(symbol, days=10)
        last = bars[-1]
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
            print(f"  day range ${last.low:,.2f} – ${last.high:,.2f}  "
                  f"volume {last.volume:,.0f}")
            print("  source: Stooq daily bars (keyless)")
        return

    # -- indicators -------------------------------------------------------
    if action == "indicators":
        symbol = str(getattr(args, "sym", "") or "").upper()
        bars = _bars_for(symbol)
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
        print(f"══ {symbol} indicators — latest bar {last.date}, "
              f"close ${last.close:,.2f} ══")
        print(f"  SMA20            {_fmt(sma20, 20, n)}")
        print(f"  EMA12            {_fmt(ema12, 12, n)}")
        print(f"  EMA26            {_fmt(ema26, 26, n)}")
        print(f"  RSI14            {_fmt(rsi14, 15, n, decimals=1)}")
        print(f"  MACD line        {_fmt(macd_line, 26, n)}")
        print(f"  MACD signal      {_fmt(macd_signal, 34, n)}")
        print(f"  MACD histogram   {_fmt(macd_hist, 34, n)}")
        print(f"  Bollinger 20     upper {_fmt(bb_upper, 20, n)}  "
              f"middle {_fmt(bb_middle, 20, n)}  lower {_fmt(bb_lower, 20, n)}")
        print(f"  ATR14            {_fmt(atr14, 14, n)}")
        print(f"  Stoch %K/%D      {_fmt(stoch_k, 14, n, decimals=1)} / "
              f"{_fmt(stoch_d, 16, n, decimals=1)}")
        print(f"  OBV              {obv_val:,.0f}")
        print(f"  ADX14            {_fmt(adx14, 28, n, decimals=1)}")
        print(f"  +DI14/-DI14      {_fmt(plus_di14, 15, n, decimals=1)} / "
              f"{_fmt(minus_di14, 15, n, decimals=1)}")
        print(f"  VWAP             {_fmt(vwap_val, 1, n)}")
        if regime["regime"] == "unknown":
            print(f"  Regime           n/a (needs 28 bars, have {n})")
        else:
            print(f"  Regime           {regime['regime']} "
                  f"(ADX14 {regime['adx']:.1f}, ATR% {regime['atr_pct']:.2f})")
        return

    # -- signal ------------------------------------------------------------
    if action == "signal":
        symbol = str(getattr(args, "sym", "") or "").upper()
        try:
            signal = _signals.generate_signal(symbol, provider=_market.StooqProvider())
        except _market.MarketDataError as exc:
            # Never fabricate a signal from a failed fetch.
            print(f"Market data unavailable for {symbol}: {exc}")
            raise SystemExit(1) from None
        narrative = _signals.narrate(signal)
        if getattr(args, "json", False):
            print(_json.dumps({
                "symbol": signal.symbol,
                "direction": signal.direction,
                "confidence": signal.confidence,
                "rationale": signal.rationale,
                "indicator_snapshot": signal.indicator_snapshot,
                "generated_at": signal.generated_at,
                "advisory": signal.advisory,
                "narrative": narrative,
            }, indent=2))
            return
        print(ADVISORY_BANNER)
        print(f"Signal for {signal.symbol}: {signal.direction.upper()}  "
              f"(confidence {signal.confidence:.2f})")
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
        provider = _market.StooqProvider()
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
        missing = [s for s in summary.get("warnings", [])
                   if positions.get(s, {}).get("qty", 0) > 0]
        if getattr(args, "json", False):
            if fetch_failures:
                summary["fetch_failures"] = fetch_failures
            print(_json.dumps(summary, indent=2))
            return
        print("══ Paper portfolio (SIMULATED — no real money) ══")
        print(f"  cash: ${summary['cash']:,.2f}")
        for symbol, pos in positions.items():
            if pos.get("qty", 0) > 0:
                line = (f"  {symbol}: qty {pos['qty']:g} @ avg "
                        f"${pos['avg_cost']:,.2f}")
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
            print("  warnings: could not fetch latest prices for "
                  + ", ".join(missing)
                  + " — valued at average cost, not zeroed")
        return

    # -- order ---------------------------------------------------------------
    if action == "order":
        symbol = str(getattr(args, "sym", "") or "").upper()
        # Live trading is structurally impossible in this build. Refuse any
        # live-shaped request first — never let it fall through to a broker
        # silently, and never reach AlpacaConnector from this command.
        if getattr(args, "live", False) or _os.environ.get("LEVI_BROKER_LIVE"):
            print("Live trading is NOT enabled in this build. The order was NOT placed.")
            print("This command can only ever place paper orders.")
            print("Enabling live trading would require (none of it is wired here):")
            print("  1. a deliberate dependency decision with sign-off (blueprint §1.1)")
            print("  2. a wired AlpacaConnector transport (stdlib urllib or an approved SDK)")
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
            print("Order NOT placed: paper orders require an explicit --yes "
                  "(HITL gate, blueprint §1.5).")
            print(f"  Would have placed: {side or '?'} {qty:g} {symbol} "
                  "@ latest Stooq close (paper).")
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
        except (_broker.InvalidOrder, _broker.OrderNotConfirmed,
                _broker.NoReferencePrice) as exc:
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
        print(f"Paper cash is now ${portfolio.cash:,.2f} "
              "(SIMULATED — no real money)")
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
        print(f"Deposited ${amount:,.2f} into the PAPER portfolio "
              "(SIMULATED — no real money).")
        print(f"Paper cash is now ${portfolio.cash:,.2f}  (saved: {saved_path})")
        return

    if action is None:
        print("Usage: levi finance <quote|indicators|signal|portfolio|order|deposit>")
        print("  levi finance quote <SYM>                    — latest close + day range (Stooq)")
        print("  levi finance indicators <SYM>               — SMA/EMA/RSI/MACD/Bollinger/ATR/Stoch/OBV/ADX/VWAP + regime snapshot")
        print("  levi finance signal <SYM>                   — advisory signal (paper-only, not financial advice)")
        print("  levi finance portfolio [--json]             — paper ledger: cash, positions, P&L")
        print("  levi finance order <SYM> <QTY> --side buy|sell [--yes]  — paper order (needs --yes)")
        print("  levi finance deposit <AMOUNT>               — fund the paper portfolio")
        return

    print(f"Unknown finance action {action!r}")
    raise SystemExit(2)

def cmd_agent(args):
    """Agent runtime (blueprint §7): run a task through the step-level tool
    loop, list tools, or serve the agent over HTTP. Agent modules are
    imported lazily here so `levi` startup stays fast."""
    import sys as _sys
    action = getattr(args, "agent_action", None)

    def _kai_register_system() -> tuple[str | None, str | None]:
        """Validate --register and return (variant_id, system_prompt).

        Returns (None, None) when no --register was given. Exits 2 with the
        valid id list on an unknown id.
        """
        variant_id = getattr(args, "register", None) or ""
        variant_id = variant_id.strip()
        if not variant_id:
            return None, None
        from levi.persona.kai9000 import get as _kai_get, all_variants, system_for
        variant = _kai_get(variant_id)
        if variant is None:
            valid = ", ".join(v.id for v in all_variants())
            print(f"Unknown KAI-9000 register {variant_id!r}. Valid ids: {valid}")
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
        serve(host=getattr(args, "host", None) or "127.0.0.1",
              port=int(getattr(args, "port", None) or 8765))
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
        register_id, register_system = _kai_register_system()
        if register_id:
            print(f"KAI-9000 register: {register_id}\n")
        use_affect = bool(getattr(args, "affect", False))
        affect_session = None
        if use_affect:
            from levi.affect import SessionEI
            affect_session = SessionEI(
                register_id=(getattr(args, "register", None) or "kai_9000"))
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
        from levi.agent import local_model
        maction = getattr(args, "agent_model_action", None)
        if maction == "status":
            from levi.agent import local_model
            from levi.agent import brain_provider
            brain = brain_provider.NativeBrainProvider().status()
            print("══ Native brain (levi-brain) status ══\n")
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
            print(f"  torch     : {'AVAILABLE' if brain['torch_available'] else 'MISSING (pip install torch to run the brain)'}")
            print()
            if brain["available"]:
                print("  Provider  : AVAILABLE — select with --provider levi-brain or LEVI_PROVIDER=levi-brain")
            else:
                print("  Provider  : UNAVAILABLE — explicit requests fall back to the rule-based `local` planner")
            print()
            print("── Legacy llama-server path (levi-local) ──\n")
            report = local_model.status_report()
            print(f"  Model dir : {report['model_dir']}")
            if report["weights"]:
                mb = (report["weights_bytes"] or 0) / 1e6
                sha = (report["weights_sha256"] or "")[:16]
                print(f"  Weights   : PRESENT  {Path(report['weights']).name} "
                      f"({mb:.0f}MB{', sha256 ' + sha + '…' if sha else ''})")
                native = report.get("weights_native_ctx")
                print(f"  Context   : {report['ctx_size']} tokens"
                      f"{' (model native: %d; set LEVI_LOCAL_CTX_SIZE to change)' % native if native else ''}")
            else:
                print("  Weights   : MISSING — no .gguf file in the model dir")
                print("              (legacy path; the native brain above is the supported direction)")
            if report["runner"]:
                print(f"  Runner    : PRESENT  {report['runner']}")
            else:
                print("  Runner    : MISSING — llama-server not found on PATH")
            print()
            if report["available"]:
                print("  Provider  : AVAILABLE (legacy) — select explicitly with --provider levi-local")
                print("              It is NOT in the automatic chain anymore.")
            else:
                print("  Provider  : UNAVAILABLE — explicit requests fall back to the rule-based `local` planner")
                print("              The system says so honestly; it never pretends the model exists.")
            return
        if maction == "pull":
            model_key = getattr(args, "model", None) or local_model.DEFAULT_MODEL_KEY
            force = bool(getattr(args, "force", False))

            def _progress(done, total):
                if total:
                    pct = 100.0 * done / total
                    print(f"\r  {done/1e6:7.1f}MB / {total/1e6:.1f}MB ({pct:5.1f}%)",
                          end="", flush=True)
                else:
                    print(f"\r  {done/1e6:7.1f}MB downloaded", end="", flush=True)

            spec = local_model.MODELS.get(model_key)
            if spec is None:
                print(f"Unknown model {model_key!r} (known: {', '.join(sorted(local_model.MODELS))})")
                raise SystemExit(2)
            if getattr(args, "model", None) is None:
                print("Available models (intelligence-per-RAM tradeoff — bigger is smarter, not magic):")
                for key in sorted(local_model.MODELS):
                    s = local_model.MODELS[key]
                    mark = "  [default]" if key == local_model.DEFAULT_MODEL_KEY else ""
                    print(f"  {key}{mark}: {s['display']} (~{s['approx_bytes']/1e6:.0f}MB)")
                    print(f"      {s['blurb']}")
                    print(f"      {s['ram_note']}")
                print()
            dest = Path(local_model.model_dir()) / spec["file"]
            if dest.is_file() and not force:
                print(f"Weights already present: {dest}")
                print("Use --force to re-download.")
            else:
                print(f"Downloading {spec['display']} (~{spec['approx_bytes']/1e6:.0f}MB)…")
                print(f"  {spec['ram_note']}")
                print(f"  {spec['url']}")
                try:
                    dest = local_model.download_weights(model_key, force=force,
                                                        progress=_progress)
                except local_model.PullError as exc:
                    print(f"\npull failed: {exc}")
                    print("Partial files were cleaned up. Check your connection and retry; "
                          "nothing half-installed was left behind.")
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
        print("Usage: levi agent model <pull|status>")
        print("  levi agent model status")
        print("  levi agent model pull [--model qwen3-0.6b] [--force]")
        return

    if action == "run":
        from levi.agent.loop import run_subtask
        from levi.agent.providers import select_provider
        from levi.agent.tools import build_default_registry

        task = getattr(args, "task", None) or ""
        if not task.strip():
            print("Usage: levi agent run \"<task>\" [--provider local|levi-local|openai|anthropic] [--yes] [--max-steps N]")
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
                register_id=(getattr(args, "register", None) or "kai_9000"))
            print("Affect engine: ON (5D EI modulation, docs/AFFECT.md)\n")
        registry = build_default_registry(
            workspace_root=getattr(args, "workspace", None) or None,
            consent=consent,
            confirm=None if consent else _confirm,
            affect_tracker=affect_session,
        )
        print(f"Running with provider={getattr(provider, 'name', '?')} "
              f"consent={'yes (--yes)' if consent else 'no (gates will prompt/deny)'} ...\n")
        _attach_mcp(registry)
        register_id, register_system = _kai_register_system()
        if register_id:
            print(f"KAI-9000 register: {register_id}\n")
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
        if getattr(args, "json", False):
            import json as _json
            print(_json.dumps(transcript.to_dict(), indent=2))
        else:
            for step in transcript.steps:
                print(f"── step {step.index + 1} ──")
                if step.provider_text:
                    print(f"  agent: {step.provider_text[:300]}")
                for call, result in zip(step.tool_calls, step.results, strict=False):
                    args_preview = {k: (str(v)[:80]) for k, v in (call.get("args") or {}).items()}
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
    print("  levi agent run \"<task>\" [--provider local|levi-local|openai|anthropic] [--yes] [--max-steps N] [--workspace DIR]")
    print("  levi agent chat [--session NAME] [--provider ...] [--yes] [--workspace DIR]")
    print("  levi agent tools")
    print("  levi agent serve [--host 127.0.0.1] [--port 8765]   (requires LEVI_AGENT_TOKEN)")
    print("  levi agent model <status|pull>   (Levi Local offline model management)")
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
            o = dp.score_opportunity(
                s.id, args.title,
                demand_score=float(getattr(args, "demand_score", 0.6) or 0.6),
                serviceability=float(getattr(args, "serviceability", 0.6) or 0.6),
                startup_cost=float(getattr(args, "cost", 0.2) or 0.2),
            )
            print(f"Opportunity worth={o.worth:.2f}: {o.title}")
    print(dp.format_status())

def cmd_income(args):
    from levi.income.factory import IncomeFactory
    fac = IncomeFactory()
    if getattr(args, "compose", None):
        plan = fac.compose(args.compose, service=getattr(args, "service", None) or "service modernization")
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
    if getattr(args, "seed_knowledge_heavy", False):
        from levi.brain.seed_knowledge_heavy import seed as seed_h, format_index as fmt_h
        print(fmt_h())
        n = seed_h()
        print(f"Heavy knowledge seed: {n} additional units (depth A–Z, cognition, wit rules).")
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
                    print(getattr(h, "text", h)[:200] if not isinstance(h, str) else h[:200])
                    print("---")
            else:
                print(c.format())
            return
        if getattr(args, "add", None):
            u = c.add(args.add, kind=getattr(args, "kind", None) or "OBSERVED", source=getattr(args, "source", "") or "")
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
    """
    from levi.growth import cycle as _cycle
    from levi.growth import journal as _journal

    action = getattr(args, "growth_action", "status") or "status"

    if action == "status":
        s = _cycle.status()
        print("=== LEVI growth ===")
        print(f"stage: {s['stage']} — {s['stage_blurb']}")
        print(f"cycles completed: {s['cycles_completed']}")
        print(f"learnings consolidated: {s['learnings_consolidated']}")
        if s["learnings_by_kind"]:
            kinds = ", ".join(f"{k}={v}" for k, v in sorted(s["learnings_by_kind"].items()))
            print(f"by kind: {kinds}")
        print(f"experiences pending: {s['experiences_pending']}")
        last = s["last_cycle"]
        if last:
            print(f"last cycle: {last['id']} at {last['ts']} "
                  f"(mode={last['mode']}, accepted={last['accepted']})")
        else:
            print("last cycle: none yet — run `levi growth cycle` to begin")
        print(f"growth dir: {s['growth_dir']}")
        return

    if action == "cycle":
        dry = bool(getattr(args, "dry_run", False))
        use_model = not bool(getattr(args, "no_model", False))
        print("Running growth cycle"
              + (" (dry run — nothing will be written)" if dry else "")
              + (" (rules only)" if not use_model else "")
              + " …")
        report = _cycle.run_cycle(use_model=use_model, dry_run=dry)
        print(f"cycle {report['cycle_id']}: "
              f"{report['experiences']} experiences, "
              f"mode={report['mode']}, "
              f"{report['learnings_proposed']} proposed → "
              f"{report['consolidation']['accepted']} accepted, "
              f"{report['consolidation']['corroborated']} corroborated, "
              f"{report['consolidation']['skipped']} skipped")
        for learning in report["learnings"]:
            print(f"  [{learning['kind']}] ({learning['confidence']:.2f}) {learning['content'][:160]}")
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
                print(f"{e.get('ts')} {e.get('id')}: "
                      f"{e.get('experiences', 0)} exp, mode={e.get('mode')}, "
                      f"accepted={e.get('accepted', 0)}, "
                      f"corroborated={e.get('corroborated', 0)}"
                      + (" (quiet)" if e.get("quiet") else ""))
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
            kinds = [t for t in e.tags if t in ("fact", "preference", "procedural", "correction")]
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
            entries = [e for e in store.list(limit=5000)
                       if "growth" in e.tags and e.id.startswith(target_id)]
            for e in entries:
                if store.delete(e.id):
                    removed += 1
        elif tag:
            entries = [e for e in store.list(limit=5000)
                       if "growth" in e.tags and tag in e.tags]
            for e in entries:
                if store.delete(e.id):
                    removed += 1
        else:
            print("Specify --id <id> or --tag <tag> to forget.")
            return
        _journal.append_entry({"kind": "forget", "removed": removed,
                               "by_id": bool(target_id), "tag": tag or None})
        print(f"Forgot {removed} learning(s).")
        return

    print(f"Unknown growth action: {action}")

def cmd_echo(args):
    from levi.organs.echo import run_echo, format_echo
    print(format_echo(run_echo(getattr(args, "seed", None) or "silence")))

def cmd_mandella(args):
    from levi.organs.mandella import run_mandella, format_mandella
    print(format_mandella(run_mandella(getattr(args, "domain", None) or "build", getattr(args, "seed", "") or "")))

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
        return (f"[{it.get('date', '?')}] ({it.get('source', '?')}) {it.get('title', '')}\n"
                f"    {it.get('summary', '')}\n    {it.get('url', '')}")

    if action == "search":
        q = (getattr(args, "news_arg", None) or "").strip().lower()
        if not q:
            print("Usage: levi news search <query>")
            return
        terms = [t for t in q.split() if len(t) > 2]
        hits = [it for it in items
                if any(t in f"{it.get('title', '')} {it.get('summary', '')}".lower() for t in terms)]
        hits.sort(key=lambda it: it.get("date", ""), reverse=True)
        print(f"{len(hits)} match(es) for {q!r} (dates shown — dated recall):")
        for it in hits[:20]:
            print(fmt(it))
        return

    # latest
    limit = getattr(args, "limit", 10) or 10
    items.sort(key=lambda it: it.get("date", ""), reverse=True)
    print(f"Latest ingested headlines (newest date: {items[0].get('date', '?')} — dated recall):")
    for it in items[:limit]:
        print(fmt(it))


def cmd_capabilities(args):
    """Print the honest capability atlas (all or one domain)."""
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent / "knowledge" / "capabilities" / "atlas.json"
    atlas = json.loads(path.read_text(encoding="utf-8"))
    domain = getattr(args, "domain", None)
    domains = atlas["domains"]
    if domain:
        domains = [d for d in domains if d["id"] == domain]
        if not domains:
            print(f"Unknown domain {domain!r}. Known: {', '.join(d['id'] for d in atlas['domains'])}")
            return
    for d in domains:
        print(f"## {d['name']} [{d['id']}]")
        print(d["description"])
        print(f"Tools: {', '.join(d['tools'])}")
        print(f"Limits: {'; '.join(d['known_limits'])}\n")
    print("Honesty rule: if it is not in this atlas or the tool list, the agent says so.")


def cmd_affect(args):
    """5D emotional-intelligence engine: detect affect or show the spec."""
    action = getattr(args, "affect_action", None) or "status"
    if action == "detect":
        from levi.affect import detect, evaluate, suggest_register
        text = getattr(args, "affect_arg", None) or ""
        if not text:
            print("Usage: levi affect detect \"some text\"")
            return
        r = detect(text)
        d = evaluate(text, r)
        s = suggest_register(text, r, d)
        print(f"dominant : {r.dominant} (valence {r.valence:+.2f}, "
              f"arousal {r.arousal:.2f}, confidence {r.confidence:.2f})")
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
    print("                       the 14 KAI-9000 registers + repair/rapport.")
    print("\nHonesty rule: this is pattern-based affect modeling, not felt")
    print("emotion. No sentience or subjective-experience claims — ever.")
    print("Full spec: docs/AFFECT.md")


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
            print("Example: levi lab chat --endpoint http://localhost:8080 --model qwen3-0.6b")
            print("(Serve one with: levi agent model pull, then llama-server on :8080.)")
            return
        model = getattr(args, "model", None) or "qwen3-0.6b"
        probe = lab_live.probe(endpoint)
        print(lab_live.format_probe(probe))
        if not probe["ok"]:
            return
        print(f"Chatting with {model} — empty line quits.\n")
        messages = [{"role": "system",
                     "content": "You are LEVI, a local-first synthetic-intelligence assistant."}]
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
    """`levi cloud keys create <name>|list|revoke <name|prefix>`."""
    from levi.cloud import apikeys

    rest = list(getattr(args, "cloud_args", None) or [])
    keys_action = rest[0].lower() if rest else ""
    target = rest[1] if len(rest) > 1 else None
    if keys_action == "create":
        if not target:
            print("Usage: levi cloud keys create <name>")
            raise SystemExit(2)
        try:
            raw, record = apikeys.create_key(target)
        except apikeys.KeyError as exc:
            print(f"Error: {exc}")
            raise SystemExit(1) from None
        # The raw key is printed ONCE and never stored. Warn loudly.
        print(raw)
        print()
        print("API key created for %r (prefix %s)." % (record["name"], record["prefix"]))
        print("This is the ONLY time the full key is shown — copy it now.")
        print("It is stored as a SHA-256 hash only; it cannot be recovered.")
        return
    if keys_action == "list":
        keys = apikeys.list_keys()
        if not keys:
            print("No API keys.")
            return
        for k in keys:
            status = "REVOKED" if k.get("revoked") else "active"
            print(f"  {k['name']:20} {k.get('prefix', '?'):14} "
                  f"created {k.get('created', '?')}  {status}")
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
    print("Usage: levi cloud keys {create <name>|list|revoke <name|prefix>}")
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
        line = (f"  {r.get('ts', '?')}  {r.get('key_name', '?'):<16} "
                f"{r.get('endpoint', '?'):<16} steps={r.get('steps', 0)} "
                f"ok={r.get('ok', '?')}")
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
            print(f"No field guide for {slug!r} yet — run build_briefs.py after ingesting.")
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
            print(f"    {subj['slug']:32s} ok={c.get('ok',0):3d} "
                  f"dead={c.get('dead',0):3d} video={c.get('skipped-video',0):3d} "
                  f"bin={c.get('skipped-binary',0):3d}")
        chars = sum(int((r.get("detail") or "0").split()[0])
                    for r in records if r["status"] == "ok")
        print(f"\n  ingested text: ~{chars:,} chars across "
              f"{sum(1 for r in records if r['status']=='ok')} course pages")
        return

    # action == "list"
    filt = (getattr(args, "subject_filter", None) or "").strip().lower().replace("_", "-")
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
        print(f"\n{total} courses across {len(catalog['subjects'])} subjects. "
              f"Use --subject <slug> to expand one.")


def cmd_project(args):
    """Pre-MVP service capability-discovery phase runner + HITL + capability log."""
    from levi.project.phases import PhaseRunner
    from levi.project.hitl import HITLGate
    r = PhaseRunner()
    action = getattr(args, "project_action", None) or "status"
    if getattr(args, "url", None):
        r.set_url(args.url)
        print(f"URL set: {args.url}")
    if action in ("status", None) and not getattr(args, "run", None) and not getattr(args, "complete", None):
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
    print("Lock: levi chat --persona normal  or  levi ask -p strategist \"...\"")


def cmd_skills(args):
    reg = SkillRegistry()
    for s in reg.list():
        print(f"  {s.id:22} | {s.description[:60]}")


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
        img = story_still(s.title, s.genre, beat=getattr(args, "beat", None) or "midpoint")
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
        auto = bool(getattr(args, "auto", False) or getattr(args, "bidirectional", False))
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
            print("══ Forward + Backwords (Joyner-style: first→last / last→first, same units)")
        elif fwd is not None or bak is not None:
            try:
                s = fab.create_story(args.create, genre=genre, title=getattr(args, "title", None))
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
                s = fab.create_story(args.create, genre=genre, title=getattr(args, "title", None))
            except ValueError:
                # Loud refusal (blueprint §5.3) — see above.
                raise
        words = len((s.body or "").split())
        print(f"══ Created {s.id}")
        print(f"title={s.title}  genre={s.genre}  chars={len(s.characters)}  beats={len(s.beats)}  words≈{words}")
        print("Cast:", ", ".join(f"{c.name}({c.archetype.value})" for c in s.characters[:6]))
        print("Beats:", " → ".join(b.name for b in s.beats))
        print("─" * 48)
        print(s.body[:3200])
        if len(s.body) > 3200:
            print("...")
        print("─" * 48)
        print("Talk to LEVI:  levi chat \"…\"   ·  levi ask \"Who are you?\"")
        print(f"Forward more:  levi story --expand {s.id} --auto-forward 2")
        print(f"Backwards:     levi story --expand {s.id} --auto-backward 2")
        return
    if getattr(args, "expand", None):
        sid = args.expand
        if getattr(args, "auto", False) or getattr(args, "auto_forward", None) is not None or getattr(args, "auto_backward", None) is not None:
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
        print('  levi story --create "A city that bills unlived dreams" --genre systems_horror')
        print("  levi story --expand <id> --focus next_beat")
        print("  levi story --id <id> --mode social_media")
        print("  levi story --id <id> --mode abridged_series")
        return
    for s in stories[:15]:
        print(f"  {s.id}  [{s.genre}] {s.title[:50]}  beats={len(s.beats)}")


def cmd_genres(args):
    reg = GenreRegistry()
    check = reg.integrity_check()
    print(f"Genres: {check['actual']}/{check['expected']}  Integrity: {'OK' if check['ok'] else 'FAIL'}")
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
    entry = store.add(MemoryType.SEMANTIC, content=content, importance=args.importance,
                      source="user", tags=args.tags.split(",") if args.tags else [])
    print(f"Remembered [{entry.id}]")


def cmd_recall(args):
    store = MemoryStore()
    results = store.search(args.query, limit=args.limit) if args.query else store.list(limit=args.limit)
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
        print(m.expand(n=getattr(args, "n", 1) or 1, seed=getattr(args, "seed", None),
                       polish=bool(getattr(args, "polish", False))))
    elif action in ("deny",):
        print(m.deny())
    elif action in ("approve",):
        print(m.approve())
    elif action in ("reim", "echo"):
        print(m.reim(tracks=getattr(args, "tracks", 3) or 3, seed=getattr(args, "seed", None)))
    elif action in ("crown",):
        print(m.crown(getattr(args, "index", 0) or 0))
    elif action in ("rupture", "wyrd"):
        print(m.rupture(getattr(args, "lens", None) or "mccarthy"))
    elif action in ("causal", "bleed"):
        print(m.causal())
    elif action in ("manuscript", "ms"):
        print(m.manuscript(limit=getattr(args, "limit", 0) or 0))
    elif action in ("configure", "config"):
        print(m.configure(
            direction=getattr(args, "direction", None),
            phase=getattr(args, "phase", None),
            power=getattr(args, "power", None),
            genres=getattr(args, "genres", None),
            pov=getattr(args, "pov", None),
            seed=getattr(args, "seed", None),
        ))
    elif action in ("genres",):
        print(m.genres_list())
    elif action in ("story",):
        premise = getattr(args, "seed", None) or "A lattice opens under weather law."
        try:
            print(m.story_create(premise, genre=getattr(args, "genres", None) or "literary"))
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
        print("\nActions: status|expand|deny|approve|reim|crown|rupture|causal|manuscript|configure|genres|story|characters|mirror|rail|smoke|snapshot")



def cmd_chat(args):
    """Enterprise chat companion — multi-turn session with personas & modes."""
    from levi.ei.chat_companion import ChatCompanion, list_sessions
    if getattr(args, "list_sessions", False):
        rows = list_sessions()
        if not rows:
            print("No sessions yet. Start: levi chat")
            return
        for r in rows:
            print(f"{r['id']}  msgs={r['messages']:<4}  {r.get('mode','')}  {r.get('title','')[:40]}")
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
    cfg = calibrate_wit(user_tone="playful", intensity=0.55, regulation="match_light", intrigue=True)
    print(f"Sample calibration: enabled={cfg.enabled} styles={cfg.active_styles} intensity={cfg.intensity:.2f}")
    print("HARD RULE: wit muted under crisis/distress.")
    print("Use:  levi wit --tone playful")
    print("      levi daemon lock-wit  (see daemon help)")
    print()
    print("══ Cognition organs ══")
    print("  orchestration loop  — UNDERSTAND → companion → persona → specialists → synthesize")
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



def cmd_kai(args):
    """KAI-9000 family — redesigned SI registers."""
    from levi.persona.kai9000 import format_kai_roster, get, register_into_lattice, all_variants
    var = getattr(args, "variant", None)
    if var:
        # allow short names: care, ops, ...
        key = var if var.startswith("kai_") else f"kai_9000_{var}" if var != "9000" else "kai_9000"
        if var in ("9000", "primary", "kai"):
            key = "kai_9000"
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
        print(f"Registered {n} KAI-9000 variants into persona lattice.")
        print("Total personas:", len(lat.keys()))
        return
    print(format_kai_roster())


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
    print('  python -m levi.cli.main chat --persona kai_9000 "Status."')
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


def main():
    parser = argparse.ArgumentParser(description="LEVI × L.W.P. Kernel")
    parser.add_argument("--personality", "-p", default=None)
    parser.add_argument("--verbose", "-v", action="store_true", help="Show internal routing / IR / specialists")
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
    imp.add_argument("--replace", action="store_true", help="Replace namespaces from pack")
    exp.add_argument("--out", default=None)
    tpl = sub.add_parser("templates", help="List/apply free templates")
    tpl.add_argument("--use", default=None)

    sub.add_parser("status")
    ask_p = sub.add_parser("ask")
    ask_p.add_argument("--ultimate", action="store_true", help="Full organism synthesis path")
    ask_p.add_argument("question", nargs="?", default=None)
    ask_p.add_argument("extra", nargs="*", default=[])
    turn_p = sub.add_parser("turn", help="One bloodstream turn: EI → persona → governor → factory/organ/model → policy → memory → trace")
    turn_p.add_argument("text", nargs="?", default=None)
    turn_p.add_argument("extra", nargs="*", default=[])
    turn_p.add_argument("--persona", default=None, help="Persona lens id (default: normal)")
    turn_p.add_argument("--provider", default=None, help="Explicit model provider (default: provider chain)")
    turn_p.add_argument("--session", default="default", help="Session id for EI/persona continuity")
    turn_p.add_argument("--composite", default=None, help="Named composite whose strictest risk ceiling applies")
    turn_p.add_argument("--yes", action="store_true", help="Approve consequential acts without prompting")
    turn_p.add_argument("--dry-run", action="store_true", help="Walk the gate without executing")
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
    free_p = sub.add_parser("free", help="Free integration lattice + interpenetration matrix")
    free_p.add_argument("--matrix", action="store_true")
    free_p.add_argument("--json", action="store_true",
                        help="JSON export (with --matrix: full graph; with --path/--neighborhood: query result)")
    free_p.add_argument("--path", nargs=2, metavar=("A", "B"), default=None,
                        help="Shortest interpenetration path between two asset ids")
    free_p.add_argument("--neighborhood", default=None, metavar="ID",
                        help="Assets within --depth hops of an asset id")
    free_p.add_argument("--depth", type=int, default=1,
                        help="Hop depth for --neighborhood (default 1)")
    sub.add_parser("production", help="Production table: prehistoric+modern+LEVI-unique")
    sub.add_parser("go", help="Fast path: integrate+ladder+ops")
    sub.add_parser("integrate", help="Cross-module integration audit")
    ops_p = sub.add_parser("ops", help="Operational layer — pulse+kernel+rail+HITL surface")
    ops_p.add_argument("--cycle", default=None, help="Run unified cycle for task")
    ops_p.add_argument("--execute", action="store_true")
    ops_p.add_argument("--rail-dry", default=None, help="Rail dry-run until HITL")
    ops_p.add_argument("--estop", action="store_true")
    ops_p.add_argument("--clear-estop", action="store_true")
    ops_p.add_argument("--reason", default="operator")
    lad_p = sub.add_parser("ladder", help="Build ladder Step 1 readiness (no placeholders)")
    lad_p.add_argument("--json", action="store_true")
    org_p = sub.add_parser("organism", help="One symbiotic system map LEVI x LWP x Factory")
    org_p.add_argument("--register", action="store_true", help="Register organs into capability graph")
    sub.add_parser("charter", help="LEVI Charter identity constitution")
    sym_p = sub.add_parser("symbiosis", help="Asset other-half map + value check")
    sym_p.add_argument("--asset", default=None)
    sym_p.add_argument("--value", default=None, help="Check action for non-malicious value")
    sym_p.add_argument("--orphans", action="store_true")
    sb_p = sub.add_parser("sandbox", help="Syntax+smoke sandbox for a project path")
    sb_p.add_argument("--path", default=".")
    plug_p = sub.add_parser("plugins", help="Closed-source capability/plugin catalog")
    plug_p.add_argument("--category", default=None)
    plug2_p = sub.add_parser("plugin", help="Plugin connectors: list + execute (blueprint §3)")
    plug2_sub = plug2_p.add_subparsers(dest="plugin_action")
    plug2_sub.add_parser("list", help="List registered plugin connectors")
    plug2_e = plug2_sub.add_parser("exec", help="Execute a connector operation")
    plug2_e.add_argument("connector")
    plug2_e.add_argument("operation")
    plug2_e.add_argument("--param", action="append", default=[], help="k=v params (repeatable)")
    plug2_e.add_argument("--yes", action="store_true", help="Confirm a write operation (HITL gate)")
    plug2_e.add_argument("--json", action="store_true", help="Print the result as JSON")
    fin_p = sub.add_parser("finance", help="Paper-only finance: quotes, indicators, signals, paper orders (blueprint §5)")
    fin_sub = fin_p.add_subparsers(dest="finance_action")
    fin_q = fin_sub.add_parser("quote", help="Latest close + day range via Stooq")
    fin_q.add_argument("sym", help="US symbol, e.g. AAPL")
    fin_q.add_argument("--json", action="store_true", help="Print the quote as JSON")
    fin_i = fin_sub.add_parser("indicators", help="Indicator snapshot for the latest bar")
    fin_i.add_argument("sym", help="US symbol, e.g. AAPL")
    fin_s = fin_sub.add_parser("signal", help="Advisory signal (paper-only, not financial advice)")
    fin_s.add_argument("sym", help="US symbol, e.g. AAPL")
    fin_s.add_argument("--json", action="store_true", help="Print the signal as JSON")
    fin_pf = fin_sub.add_parser("portfolio", help="Show the paper portfolio ledger")
    fin_pf.add_argument("--json", action="store_true", help="Print the portfolio summary as JSON")
    fin_o = fin_sub.add_parser("order", help="Paper order (HITL: needs --yes)")
    fin_o.add_argument("sym", help="US symbol, e.g. AAPL")
    fin_o.add_argument("qty", type=float, help="Quantity (> 0)")
    fin_o.add_argument("--side", required=True, choices=["buy", "sell"], help="buy or sell")
    fin_o.add_argument("--yes", action="store_true", help="Explicit human confirmation (HITL gate)")
    fin_o.add_argument("--live", action="store_true", help="Refused: live trading is not enabled in this build")
    fin_d = fin_sub.add_parser("deposit", help="Fund the paper portfolio")
    fin_d.add_argument("amount", type=float, help="Amount (> 0)")
    ag_p = sub.add_parser("agent", help="Agent runtime: step-level tool loop, tools, HTTP service (blueprint §7)")
    ag_sub = ag_p.add_subparsers(dest="agent_action")
    ag_run = ag_sub.add_parser("run", help="Run a task through the step-level tool loop")
    ag_run.add_argument("task", help="Task description for the agent")
    ag_run.add_argument("--provider", choices=["local", "levi-brain", "levi-local", "openai", "anthropic"], default=None,
                        help="Chat provider (default: select_provider chain, levi-local-first)")
    ag_run.add_argument("--yes", action="store_true",
                        help="Pre-grant consent for gated tools for THIS run only. "
                             "There is no global gate-disabling flag. Without --yes, "
                             "gate trips prompt interactively (TTY only) or are denied.")
    ag_run.add_argument("--max-steps", type=int, default=10, help="Max provider turns (default 10)")
    ag_run.add_argument("--workspace", default=None, help="Workspace root for agent file/shell tools")
    ag_run.add_argument("--json", action="store_true", help="Print the transcript as JSON")
    ag_run.add_argument("--register", default=None, metavar="VARIANT",
                        help="Speak as a KAI-9000 SI register (e.g. kai_9000_ops). "
                             "Valid ids: kai_9000, kai_9000_care, kai_9000_ops, kai_9000_challenger, "
                             "kai_9000_literary, kai_9000_forensic, kai_9000_void, kai_9000_builder, "
                             "kai_9000_mirror, kai_9000_architect, kai_9000_sentinel, kai_9000_oracle, "
                             "kai_9000_muse, kai_9000_grok.")
    ag_run.add_argument("--affect", action="store_true",
                        help="Enable the 5D affect engine: per-turn affect scan, "
                             "de-escalation policy, register hints (docs/AFFECT.md).")
    ag_sub.add_parser("tools", help="List agent tools with descriptions and confirmation flags")
    ag_chat = ag_sub.add_parser("chat", help="Interactive long-conversation chat with session memory")
    ag_chat.add_argument("--session", default="default",
                         help="Session name (default: default). Re-running resumes it.")
    ag_chat.add_argument("--provider", choices=["local", "levi-brain", "levi-local", "openai", "anthropic"], default=None,
                         help="Chat provider (default: select_provider chain, levi-local-first)")
    ag_chat.add_argument("--yes", action="store_true",
                         help="Pre-grant consent for gated tools for THIS session only.")
    ag_chat.add_argument("--max-steps", type=int, default=10, help="Max provider turns per message (default 10)")
    ag_chat.add_argument("--workspace", default=None, help="Workspace root for agent file/shell tools")
    ag_chat.add_argument("--register", default=None, metavar="VARIANT",
                        help="Speak as a KAI-9000 SI register for the whole session "
                             "(e.g. kai_9000_care). See `levi agent run --help` for the id list.")
    ag_chat.add_argument("--affect", action="store_true",
                         help="Enable the 5D affect engine for the session "
                              "(docs/AFFECT.md).")
    ag_model = ag_sub.add_parser("model", help="Manage the Levi Local offline model (weights + runner)")
    ag_msub = ag_model.add_subparsers(dest="agent_model_action")
    ag_pull = ag_msub.add_parser("pull", help="Download GGUF weights (and the llama-server runner, best effort)")
    ag_pull.add_argument("--model", default=None, choices=sorted(_local_model_choices()),
                         help="Model to download (default: qwen3-0.6b).")
    ag_pull.add_argument("--force", action="store_true",
                         help="Re-download even if the weights file is already present")
    ag_msub.add_parser("status", help="Report Levi Local readiness: weights, runner, provider availability")
    ag_serve = ag_sub.add_parser("serve", help="Serve the agent over HTTP (requires LEVI_AGENT_TOKEN)")
    ag_serve.add_argument("--host", default="127.0.0.1", help="Bind address (default 127.0.0.1)")
    ag_serve.add_argument("--port", type=int, default=8765, help="Port (default 8765)")
    bld_p = sub.add_parser("builder", help="E3-E6 Emergency Builder (scaffold to product)")
    bld_p.add_argument("--plan", default=None, help="Goal text")
    bld_p.add_argument("--tier", default="E4", help="E3|E4|E5|E6")
    bld_p.add_argument("--name", default="new_project")
    bld_p.add_argument("--target", default="independent", help="independent|levi")
    bld_p.add_argument("--apply", default=None, help="Job id to apply")
    bld_p.add_argument("--force", action="store_true")
    uni_p = sub.add_parser("unified", help="LEVI Daemon Core unified cycle")
    uni_p.add_argument("--cycle", default=None, help="Run one cycle for task text")
    uni_p.add_argument("--execute", action="store_true", help="Allow local-safe execute steps")
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
    inc_p = sub.add_parser("income", help="Income Factory (capability, not whole purpose)")
    inc_p.add_argument("--compose", default=None)
    inc_p.add_argument("--service", default="service modernization")
    mh_p = sub.add_parser("memory-hierarchy", help="Memory hierarchy + why-belief")
    mh_p.add_argument("--why", default=None, help="Trace belief to evidence")
    gr_p = sub.add_parser("growth", help="Raise baby Levi: developmental learning loop")
    gr_p.add_argument("growth_action", nargs="?", default="status",
                      choices=["status", "cycle", "journal", "learnings", "forget"])
    gr_p.add_argument("--dry-run", action="store_true",
                      help="cycle: preview without writing anything")
    gr_p.add_argument("--no-model", action="store_true",
                      help="cycle: use rule-based reflection only (offline)")
    gr_p.add_argument("--limit", type=int, default=10, help="journal: entries to show")
    gr_p.add_argument("--kind", default="", help="learnings: filter by kind")
    gr_p.add_argument("--id", dest="forget_id", default="",
                      help="forget: learning id prefix to remove")
    gr_p.add_argument("--tag", default="", help="forget: remove learnings with this tag")
    brain_p = sub.add_parser("brain", help="Corpus + indexed brain table + export")
    brain_p.add_argument("brain_action", nargs="?", default="table", choices=["table", "corpus", "set", "export", "atlas"])
    brain_p.add_argument("--seed-atlas", action="store_true", help="Pre-load offline brain A-Z atlas")
    brain_p.add_argument("--seed-expand", action="store_true", help="Mass combinatorial corpus expand")
    brain_p.add_argument("--seed-hyperdrive", action="store_true", help="Seed high-signal hyperdrive operational units")
    brain_p.add_argument("--seed-knowledge", action="store_true", help="Seed A–Z subjects, events, inventors, stars, X-domain")
    brain_p.add_argument("--seed-knowledge-heavy", action="store_true", help="Heavy knowledge: depth A–Z, more figures, cognition, wit")
    brain_p.add_argument("--seed-x100", action="store_true", help="×100 densified operators knowledge pack")
    brain_p.add_argument("--seed-max", action="store_true", help="MAX knowledge pack (~2500 units)")
    brain_p.add_argument("--seed-expand2", action="store_true", help="Expansion pack II (interpenetration literacy)")
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
    crs_p.add_argument("courses_action", nargs="?", default="list",
                       choices=["list", "brief", "coverage"])
    crs_p.add_argument("subject", nargs="?", default=None,
                       help="subject slug (for brief)")
    crs_p.add_argument("--subject", dest="subject_filter", default=None,
                       help="expand one subject in list")
    news_p = sub.add_parser("news", help="Current-events ingest (dated recall, not live)")
    news_p.add_argument("news_action", nargs="?", default="latest",
                        choices=["refresh", "latest", "search"])
    news_p.add_argument("news_arg", nargs="?", default=None,
                        help="query for search")
    news_p.add_argument("--limit", type=int, default=10)
    sub.add_parser("capabilities", help="Honest capability atlas: what LEVI can do").add_argument(
        "domain", nargs="?", default=None, help="domain id (optional)")
    aff_p = sub.add_parser("affect", help="5D emotional-intelligence engine")
    aff_p.add_argument("affect_action", nargs="?", default="status",
                       choices=["status", "detect"])
    aff_p.add_argument("affect_arg", nargs="?", default=None,
                       help="text to analyze (for detect)")
    lab_p = sub.add_parser("lab", help="LEVI Lab: on-device agentic AI demos")
    lab_p.add_argument("lab_action", nargs="?", default="scenarios",
                       choices=["scenarios", "run", "footprint", "card", "chat"])
    lab_p.add_argument("lab_arg", nargs="?", default=None,
                       help="scenario id (run) or model key (card)")
    lab_p.add_argument("--live", action="store_true",
                       help="run: execute the loop live instead of playing back the fixture")
    lab_p.add_argument("--params", default="0.6B", help="footprint: e.g. 30B")
    lab_p.add_argument("--quant", default="int4", help="footprint: fp32/fp16/bf16/int8/int4")
    lab_p.add_argument("--ctx", default="32k", help="footprint: e.g. 32k")
    lab_p.add_argument("--endpoint", default=None,
                       help="chat: OpenAI-compatible base URL (or LEVI_LAB_ENDPOINT)")
    lab_p.add_argument("--model", default=None, help="chat: model id")
    proj_p = sub.add_parser("project", help="Pre-MVP phase runner / HITL / capability log (service capability-discovery)")
    mcp_p = sub.add_parser("mcp", help="MCP: serve LEVI's tools, or connect LEVI out to external MCP servers")
    mcp_p.add_argument("mcp_action", nargs="?", default="serve",
                       choices=["serve", "add", "remove", "list-servers"],
                       help="mcp action")
    mcp_p.add_argument("name", nargs="?", default=None,
                       help="add/remove: server name")
    mcp_p.add_argument("--url", default=None,
                       help="add: Streamable-HTTP endpoint URL (e.g. http://host:8899/mcp)")
    mcp_p.add_argument("--cmd", default=None,
                       help="add: stdio server command line, quoted (e.g. \"npx -y some-mcp-server\")")
    mcp_p.add_argument("--client-transport", default="",
                       help="add: http|stdio (auto-detected from --url/--cmd by default)")
    mcp_p.add_argument("--header", action="append", default=[],
                       help="add: extra HTTP header as KEY=VALUE (repeatable)")
    mcp_p.add_argument("--timeout", type=float, default=None,
                       help="add: per-call timeout in seconds (default 30)")
    mcp_p.add_argument("--transport", default="stdio", choices=["stdio", "http"],
                       help="stdio: full owner registry (for local MCP clients); http: restricted cloud-safe profile")
    mcp_p.add_argument("--host", default="127.0.0.1", help="http: bind address")
    mcp_p.add_argument("--port", type=int, default=8899, help="http: bind port")
    mcp_p.add_argument("--token", default="", help="http: optional Bearer token (401 without it)")
    mcp_p.add_argument("--consent", action="store_true",
                       help="stdio: pre-authorize confirmation-gated tools (owner only; off by default)")
    proj_p.add_argument("project_action", nargs="?", default="status", choices=["status", "log", "hitl", "phases"])
    proj_p.add_argument("--url", default=None, help="Public site URL for archaeology")
    proj_p.add_argument("--run", default=None, help="Run phase id e.g. P0, P1")
    proj_p.add_argument("--complete", default=None, help="Mark phase complete")
    proj_p.add_argument("--log", dest="log_text", default=None, help="Append capability log note")
    proj_p.add_argument("--skill", default="", help="Future skill tag for log")
    proj_p.add_argument("--approve", default=None, help="HITL request id to approve")
    proj_p.add_argument("--deny", default=None, help="HITL request id to deny")
    proj_p.add_argument("--note", default="", help="HITL decision note")
    mono_p = sub.add_parser("mono", help="Monotropism interest tunnel state")
    mono_p.add_argument("--sense", default=None, help="Sample text to sense into tunnel")
    wit_p.add_argument("--tone", default="playful", help="Sample user tone for calibration")
    dae = sub.add_parser("daemon", help="Control daemon: personas, wit, alchemy")
    dae.add_argument("action", nargs="?", default="status",
                     help="status|clear|alchemy|lock-persona|boost-persona|lock-wit|force-alchemy")
    dae.add_argument("--target", default=None)
    dae.add_argument("--turns", type=int, default=10)
    dae.add_argument("--strength", type=float, default=0.6)
    dae.add_argument("--intensity", type=float, default=0.55)
    dae.add_argument("--off", action="store_true", help="For alchemy: disable")
    nerv = sub.add_parser("nervous", help="Affect matrix + persona activation scores")
    nerv.add_argument("--unlock", action="store_true", help="Clear explicit persona lock")
    nerv.add_argument("--reset", action="store_true", help="Reset affect and usage counters")
    nerv.add_argument("--verbose", "-v", action="store_true",
                      help="Dump full status JSON (affect, blend, hysteresis)")
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
    st.add_argument("--expand", default=None, help="Story id to expand (cascade next beat)")
    st.add_argument("--focus", default="next_beat", help="next_beat|character|atmosphere")
    st.add_argument("--id", default=None, help="Story id for --mode")
    st.add_argument("--mode", default=None, help="social_media|abridged_series|void|spiral|...")
    st.add_argument("--instruction", default="")
    st.add_argument("--show", default=None)
    st.add_argument("--genre", default="literary")
    st.add_argument("--title", default=None)
    st.add_argument("--auto", action="store_true", help="Forward + backward generation at the same time")
    st.add_argument("--bidirectional", action="store_true", help="Alias: forward + backward same time")
    st.add_argument("--auto-forward", type=int, default=None, metavar="N", help="Auto N forward beats (0=fill cascade)")
    st.add_argument("--auto-backward", type=int, default=None, metavar="N", help="Auto N prior-cause beats")
    ge = sub.add_parser("genres")
    ge.add_argument("--all", action="store_true")
    ge.add_argument("--category", default=None)
    fac_p = sub.add_parser("factory")
    fac_p.add_argument("--create", default=None)
    fac_p.add_argument("--idea", default=None)
    fac_p.add_argument("--advance", default=None)
    fac_p.add_argument("--summary", default="")
    fac_p.add_argument("--run", default=None, help="Run scaffolded main.py in sandbox")
    fac_p.add_argument("--test", default=None, help="Smoke-test sandbox main.py (closed loop)")
    sub.add_parser("automations")
    rem = sub.add_parser("remember")
    rem.add_argument("content", nargs="?", default=None)
    rem.add_argument("extra", nargs="*", default=[])
    rem.add_argument("--importance", type=float, default=0.6)
    rem.add_argument("--tags", default="")
    rec = sub.add_parser("recall")
    rec.add_argument("query", nargs="?", default=None)
    rec.add_argument("--limit", type=int, default=10)



    chat_p = sub.add_parser("chat", help="Enterprise chat companion (session + personas + modes)")
    chat_p.add_argument("message", nargs="?", default=None, help="One-shot message (omit for REPL)")
    chat_p.add_argument("extra", nargs="*", default=[])
    chat_p.add_argument("--session", default=None, help="Resume session id")
    chat_p.add_argument("--persona", default=None, help="Lock persona id")
    chat_p.add_argument("--profile", "-P", default=None, help="spark|workbench|careful|edge|kai|care")
    chat_p.add_argument("--mode", default="companion", help="companion|mentor|challenger|writer|builder|quiet")
    chat_p.add_argument("--list-sessions", action="store_true")
    chat_p.add_argument("--personas", action="store_true")
    chat_p.add_argument("--filter", default=None)
    sub.add_parser("enterprise", help="Enterprise readiness checklist")
    sub.add_parser("scorecard", help="10/10 SI cloud model scorecard")
    sub.add_parser("si", help="Synthetic intelligence identity")
    sub.add_parser("cognition", help="Personas, wit/sarcasm, cognition map")
    prem = sub.add_parser("premium", help="25 premium must-haves (next-gen offline SI)")
    kai_p = sub.add_parser("kai", help="KAI-9000 family (original LEVI registers; reverse-engineered concept, heavily modified)")
    kai_p.add_argument("--variant", "-v", default=None, help="care|ops|challenger|literary|forensic|void|builder|mirror")
    kai_p.add_argument("--register", action="store_true", help="Register KAI into persona lattice")
    sub.add_parser("unique", help="Unique unreplicable LEVI organs")
    sub.add_parser("x100", help="×100 upgrade rail (status · law · next slices)")
    sub.add_parser("max", help="MAX upgrade (2500 knowledge · full counts)")
    sub.add_parser("max10", help="MAX ×10 combined (MAX + expansion pack)")
    sub.add_parser("stress", help="Stress test / verify engines + story quality")
    sub.add_parser("here", help="Where is LEVI — talk to SI now")
    talk_p = sub.add_parser("talk", help="Easy chat (mass-friendly profiles)")
    talk_p.add_argument("message", nargs="?", default=None)
    talk_p.add_argument("extra", nargs="*")
    talk_p.add_argument("--profile", "-P", default="levi", help="levi|spark|workbench|careful|edge|kai|care")
    talk_p.add_argument("--persona", default=None)
    talk_p.add_argument("--mode", default=None)
    talk_p.add_argument("--session", default=None)
    talk_p.add_argument("--list-profiles", action="store_true")
    prof_p = sub.add_parser("profiles", help="LEVI hardwired quality traits (alias of traits)")
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

    model_p = sub.add_parser("model", help="Full Cloud Model — L.W.P. × LEVI literary SSA + integrations")
    model_p.add_argument("model_action", nargs="?", default="status",
                         help="status|expand|deny|approve|reim|crown|rupture|causal|manuscript|configure|genres|story|characters|mirror|rail|smoke|snapshot")
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

    cloud_p = sub.add_parser("cloud", help="LEVI-as-cloud API keys/usage + product stages A/B/C + crypto protocol + ZK + sync dry-run")
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
        "--key", dest="cloud_key_filter", default=None,
        help="usage: only show records for this key name",
    )
    cloud_p.add_argument(
        "--limit", dest="cloud_limit", type=int, default=20,
        help="usage: most recent N records (default 20)",
    )

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

    args = parser.parse_args()
    if not args.command:
        banner()
        p = ProfileStore().load()
        if not p.onboarded:
            print("Start here:  python -m levi.cli.main init")
        else:
            print(f"Welcome back, {p.name or 'friend'}.  Try: home | ask | templates | continue")
        parser.print_help()
        return

    cmds = {
        "init": cmd_init, "home": cmd_home, "continue": cmd_continue,
        "morning": cmd_morning, "import": cmd_import,
        "export": cmd_export, "templates": cmd_templates,
        "status": cmd_status, "ask": cmd_ask, "turn": cmd_turn, "personas": cmd_personas, "wit": cmd_wit,
        "daemon": cmd_daemon, "mono": cmd_mono, "rail": cmd_rail, "mirror": cmd_mirror, "lwp-model": cmd_lwp_model, "characters": cmd_characters, "watch": cmd_watch, "crucible": cmd_crucible, "services": cmd_services, "serve-ui": cmd_serve_ui, "provenance": cmd_provenance, "perfection": cmd_perfection, "free": cmd_free, "production": cmd_production, "go": cmd_go, "integrate": cmd_integrate, "ops": cmd_ops, "ladder": cmd_ladder, "organism": cmd_organism, "charter": cmd_charter, "symbiosis": cmd_symbiosis, "sandbox": cmd_sandbox, "plugins": cmd_plugins, "plugin": cmd_plugin, "finance": cmd_finance, "agent": cmd_agent, "builder": cmd_builder, "unified": cmd_unified,"demand": cmd_demand,"income": cmd_income,"memory-hierarchy": cmd_memory_hierarchy, "growth": cmd_growth, "brain": cmd_brain, "echo": cmd_echo, "mandella": cmd_mandella, "pulse": cmd_pulse, "relay": cmd_relay, "vault": cmd_vault, "courses": cmd_courses, "news": cmd_news, "capabilities": cmd_capabilities, "affect": cmd_affect, "lab": cmd_lab, "project": cmd_project, "nervous": cmd_nervous, "skills": cmd_skills, "agents": cmd_agents,
        "graph": cmd_graph,
        "image": cmd_image, "story": cmd_story, "genres": cmd_genres, "factory": cmd_factory, "automations": cmd_automations,
        "remember": cmd_remember, "recall": cmd_recall, "cloud": cmd_cloud, "model": cmd_model, "chat": cmd_chat, "enterprise": cmd_enterprise, "scorecard": cmd_scorecard, "si": cmd_si, "cognition": cmd_cognition, "premium": cmd_premium, "kai": cmd_kai, "unique": cmd_unique, "x100": cmd_x100, "max": cmd_max, "max10": cmd_max10, "stress": cmd_stress, "here": cmd_here, "talk": cmd_talk, "profiles": cmd_profiles, "traits": cmd_traits, "retention": cmd_retention, "dna": cmd_dna, "intel": cmd_intel, "giant": cmd_giant, "future": cmd_future, "interpenetrate": cmd_interpenetrate,
    }
    # === KING-REGION-BEGIN: King command dispatch ===
    # Parallel tracks: keep ALL King wiring inside this delimited region.
    try:
        from levi.king.cli import cmd_king as _cmd_king
        cmds["king"] = _cmd_king
    except Exception:
        pass
    # === KING-REGION-END ===
    # === MCP-REGION-BEGIN: MCP server command dispatch ===
    try:
        from levi.mcp.cli import cmd_mcp as _cmd_mcp
        cmds["mcp"] = _cmd_mcp
    except Exception:
        pass
    # === MCP-REGION-END ===
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
