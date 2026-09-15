"""
Skill / Capability Registry
Discoverable, versioned, risk-tagged skills that LEVI can invoke under policy.
First concrete step toward the Capability Graph.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import uuid


class SkillRisk(int, Enum):
    INFO = 0
    LOW = 1
    MODERATE = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Skill:
    id: str
    name: str
    description: str
    category: str
    risk_level: SkillRisk = SkillRisk.LOW
    permissions: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    supports_rollback: bool = True
    tags: List[str] = field(default_factory=list)
    version: str = "0.1.0"
    handler: Optional[Callable[..., Any]] = field(default=None, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("handler", None)
        d["risk_level"] = int(self.risk_level)
        return d


# ── Built-in skill handlers (local, safe) ─────────────────────

def _skill_status(_: Dict[str, Any] | None = None) -> str:
    return "LEVI core online. Local-first. Companion active. Policy gated."


def _skill_remember(args: Dict[str, Any] | None = None) -> str:
    from levi.memory.store import MemoryStore
    from levi.memory.types import MemoryType
    args = args or {}
    content = args.get("content") or args.get("text") or ""
    if not content:
        return "Nothing to remember."
    store = MemoryStore()
    entry = store.add(
        MemoryType.SEMANTIC,
        content=content,
        importance=float(args.get("importance", 0.6)),
        source="skill",
        tags=args.get("tags") or ["skill"],
    )
    return f"Remembered [{entry.id}]: {content[:80]}{'…' if len(content) > 80 else ''}"


def _skill_recall(args: Dict[str, Any] | None = None) -> str:
    from levi.memory.store import MemoryStore
    args = args or {}
    query = args.get("query") or args.get("text") or ""
    store = MemoryStore()
    if query:
        results = store.search(query, limit=5)
    else:
        results = store.list(limit=5)
    if not results:
        return "No matching memories."
    lines = [f"[{e.memory_type.value}] {e.content[:100]}" for e in results]
    return "\n".join(lines)


def _skill_list_personas(_: Dict[str, Any] | None = None) -> str:
    from levi.persona.lattice import PersonaLattice
    lattice = PersonaLattice()
    return ", ".join(p.id for p in lattice.list())


def _skill_companion_status(_: Dict[str, Any] | None = None) -> str:
    return (
        "Companion identity active: Best Friend · Mentor · Challenger · Protector. "
        "Emphasis shifts with context and risk. Never overrides Integrity or Policy."
    )


def _skill_phase1_checklist(_: Dict[str, Any] | None = None) -> str:
    return (
        "Phase 1 checklist:\n"
        "✓ Core package + CLI\n"
        "✓ 5D EI + Companion guidance\n"
        "✓ Full Persona Lattice (incl. interrogation, no_hero, reframe)\n"
        "✓ Multi-type Memory (local)\n"
        "✓ Model Abstraction (local-first + fallback)\n"
        "✓ Policy Engine (risk 0–4 + Plan/Preview/Permission)\n"
        "✓ Skill Registry\n"
        "✓ Agent Specialist Registry\n"
        "✓ Orchestration loop (Intent→Companion→Persona→Specialists→Skills→Policy)\n"
        "✓ L.W.P. structural primitives (cascade, spiral, circuit breaker, governor, bible, banks)\n"
        "✓ Software Factory foundation (LEVI-native capability, pipeline live)\n"
        "✓ Automation Registry\n"
        "✓ Genres 97/97 interpenetrable\n"
        "✓ Ollama chat wiring (activates when ollama serve + model present)\n"
        "✓ Sandbox scaffold (factory architecture→scaffold writes files)\n"
        "✓ Agent runtime (governor + circuit breaker)\n"
        "✓ Smoke suite (6/6)\n"
        "✓ Learning Track 0\n"
        "○ Learning Track 1\n"
        "○ Full sandbox execute/test binary"
    )



def _skill_interpenetration_stats(_: Dict[str, Any] | None = None) -> str:
    from levi.graph.interpenetration import InterpenetrationEngine
    eng = InterpenetrationEngine()
    import json
    return json.dumps(eng.stats(), indent=2)


def _skill_suggest_compose(args: Dict[str, Any] | None = None) -> str:
    from levi.graph.interpenetration import InterpenetrationEngine
    args = args or {}
    seed = args.get("seed") or args.get("text") or "persona.interrogation"
    # Allow bare names
    if not seed.startswith(("persona.", "skill.", "spec.", "role.", "lwp.")):
        for prefix in ("persona.", "skill.", "spec.", "role.", "lwp."):
            candidate = prefix + seed
            eng = InterpenetrationEngine()
            if candidate in eng.nodes:
                seed = candidate
                break
    eng = InterpenetrationEngine()
    suggestions = eng.suggest_compositions(seed, limit=6)
    if not suggestions:
        return f"No suggestions for {seed} (unknown or isolated)."
    lines = [f"Interpenetration suggestions for {seed}:"]
    for s in suggestions:
        lines.append(f"  × {s['with']} ({s['kind']}) risk≤{s['combined_risk']} — {s['reason']}")
    lines.append("Use compose skill to create a named composite.")
    return "\n".join(lines)


def _skill_compose(args: Dict[str, Any] | None = None) -> str:
    from levi.graph.interpenetration import InterpenetrationEngine
    args = args or {}
    name = args.get("name") or "Unnamed Composite"
    parts = args.get("parts") or []
    if isinstance(parts, str):
        parts = [p.strip() for p in parts.split(",") if p.strip()]
    if not parts:
        return "Provide parts=[id,id,...] to compose."
    eng = InterpenetrationEngine()
    try:
        comp = eng.propose_composite(
            name=name,
            part_ids=parts,
            description=args.get("description", ""),
            behavior_summary=args.get("behavior", ""),
            tags=args.get("tags") or ["user_composed"],
        )
        return (
            f"Proposed composite [{comp.id}]\n"
            f"  Name: {comp.name}\n"
            f"  Parts: {', '.join(comp.parts)}\n"
            f"  Risk ceiling: {comp.risk_ceiling}\n"
            f"  Verified: {comp.verified} (run verify under policy to promote)"
        )
    except KeyError as e:
        return f"Compose failed: {e}"


def _skill_genres(args: Dict[str, Any] | None = None) -> str:
    from levi.graph.genres import GenreRegistry, GenreCategory
    args = args or {}
    reg = GenreRegistry()
    check = reg.integrity_check()
    cat = args.get("category") or args.get("text")
    if cat and cat not in ("genres", "list genres", "all genres", ""):
        # try match category
        try:
            c = GenreCategory(cat.strip().lower().replace(" ", "_"))
            items = reg.list(c)
            return f"{c.value} ({len(items)}): " + ", ".join(g.id for g in items)
        except Exception:
            pass
    lines = [
        f"L.W.P. Genre Registry: {check['actual']}/{check['expected']} formal genres",
        f"Integrity: {'OK' if check['ok'] else 'FAIL — DO NOT TRUNCATE'}",
        "Categories:",
    ]
    for k, v in sorted(check["categories"].items()):
        lines.append(f"  {k}: {v}")
    lines.append("Rule: Never silently truncate. User-designed genres are additive only.")
    return "\n".join(lines)


def _skill_list_all_genres(_: Dict[str, Any] | None = None) -> str:
    from levi.graph.genres import GenreRegistry
    reg = GenreRegistry()
    return f"All {reg.count()} genres:\n" + ", ".join(reg.ids())



def _skill_factory_status(_: Dict[str, Any] | None = None) -> str:
    from levi.factory.pipeline import SoftwareFactory
    import json
    return json.dumps(SoftwareFactory().status(), indent=2)


def _skill_factory_create(args: Dict[str, Any] | None = None) -> str:
    from levi.factory.pipeline import SoftwareFactory
    from levi.orchestration.nl_ir import NLIRCompiler, IRKind
    args = args or {}
    raw = (args.get("idea") or args.get("text") or args.get("content") or "").strip()
    if not raw:
        return "Provide natural language to compile NL→IR for a build."
    ir = NLIRCompiler().compile_build(raw)
    fac = SoftwareFactory()
    proj = fac.create(name=ir.name, idea=ir.to_factory_idea())
    proj.metadata["nl_ir"] = ir.to_dict()
    proj.risk_ceiling = ir.risk_ceiling
    fac.projects[proj.id] = proj
    fac._persist()
    proj = fac.advance(proj.id, summary=f"NL→IR compiled (confidence={ir.confidence:.2f})")
    return (
        f"NL→IR → Factory DNA\n"
        f"IR [{ir.id}] conf={ir.confidence:.2f} artifact={ir.artifact_type.value} lang={ir.language}\n"
        f"Features: {', '.join(ir.features) or '—'} | Constraints: {', '.join(ir.constraints) or '—'}\n"
        f"Project [{proj.id}] stage={proj.stage.value} name={proj.name}\n"
        f"Idea(IR): {proj.idea[:180]}\n"
        f"Advance: levi factory --advance {proj.id}"
    )


def _skill_factory_advance(args: Dict[str, Any] | None = None) -> str:
    from levi.factory.pipeline import SoftwareFactory
    args = args or {}
    pid = args.get("project_id") or args.get("id")
    if not pid:
        return "Provide project_id"
    fac = SoftwareFactory()
    try:
        proj = fac.advance(pid, summary=args.get("summary", ""))
        return f"[{proj.id}] now at stage={proj.stage.value} iteration={proj.iteration}"
    except Exception as e:
        return f"Advance failed: {e}"


def _skill_automation_status(_: Dict[str, Any] | None = None) -> str:
    from levi.daemon.automation import AutomationRegistry
    import json
    return json.dumps(AutomationRegistry().status(), indent=2)


def _skill_automation_list(_: Dict[str, Any] | None = None) -> str:
    from levi.daemon.automation import AutomationRegistry
    reg = AutomationRegistry()
    items = reg.list()
    if not items:
        return "No automations yet."
    return "\n".join(f"{a.id} | {a.status.value} | {a.name} | risk≤{a.risk_ceiling}" for a in items)



def _skill_agent_run(args: Dict[str, Any] | None = None) -> str:
    from levi.agent.runtime import AgentRuntime
    args = args or {}
    intent = args.get("text") or args.get("intent") or "status"
    rt = AgentRuntime()
    run = rt.run(intent, max_steps=4)
    lines = [f"Agent run [{run.id}] ok={run.ok} risk≤{run.risk_ceiling}"]
    for s in run.steps:
        lines.append(f"  {s.specialist_id}: {s.action} → {s.result[:100]}")
    lines.append(f"Final: {run.final[:200]}")
    return "\n".join(lines)



def _skill_intent_map(args: Dict[str, Any] | None = None) -> str:
    from levi.orchestration.intent import motivation_graph_for
    import json
    args = args or {}
    raw = (args.get("text") or args.get("request") or "").strip()
    if not raw:
        return "Provide text to map."
    skill_ids = list(args.get("skills") or [])
    g = motivation_graph_for(raw, skill_ids)
    out = {
        "intent": g.intent.to_dict(),
        "possibilities": [
            {
                "direction": p.direction.value,
                "description": p.description,
                "relevance": p.relevance,
                "feasibility": p.feasibility,
                "confidence": p.confidence,
            }
            for p in g.ranked()
        ],
    }
    return json.dumps(out, indent=2)


def _skill_compile_ir(args: Dict[str, Any] | None = None) -> str:
    from levi.orchestration.nl_ir import NLIRCompiler
    import json
    args = args or {}
    raw = (args.get("text") or args.get("idea") or "").strip()
    if not raw:
        return "Provide text to compile."
    ir = NLIRCompiler().compile(raw)
    return json.dumps(ir.to_dict(), indent=2)



def _skill_automation_create(args: Dict[str, Any] | None = None) -> str:
    from levi.orchestration.nl_ir import NLIRCompiler, IRKind
    from levi.daemon.automation import AutomationRegistry, AutomationAction, TriggerKind
    args = args or {}
    raw = (args.get("text") or args.get("idea") or "").strip()
    if not raw:
        return "Provide automation NL to compile."
    ir = NLIRCompiler().compile_automate(raw)
    reg = AutomationRegistry()
    trigger = TriggerKind.SCHEDULE if ir.trigger == "schedule" else (
        TriggerKind.EVENT if ir.trigger == "event" else TriggerKind.MANUAL
    )
    actions = [AutomationAction(skill_id=a, args={}, risk_level=0) for a in ir.actions]
    auto = reg.create(
        name=ir.name,
        description=ir.goal,
        actions=actions or [AutomationAction("status", {}, 0)],
        trigger=trigger,
        risk_ceiling=ir.risk_ceiling,
        tags=["nl_ir", ir.id],
    )
    return (
        f"NL→IR → Automation DNA\n"
        f"IR [{ir.id}] trigger={ir.trigger} schedule={ir.schedule}\n"
        f"Actions: {', '.join(ir.actions)}\n"
        f"Automation [{auto.id}] {auto.name} status={auto.status.value}"
    )



def _skill_story_create(args: Dict[str, Any] | None = None) -> str:
    from levi.graph.story_fabric import StoryFabric
    from levi.graph.genres import GenreRegistry
    import re
    args = args or {}
    text_in = (args.get("text") or args.get("premise") or "").strip()
    genre = (args.get("genre") or "").strip().lower().replace(" ", "_")
    gids = GenreRegistry().ids()
    if not genre:
        lower = text_in.lower()
        for gid in sorted(gids, key=len, reverse=True):
            flex = gid.replace("_", r"[_ ]")
            if re.search(rf"\bin\s+{flex}\b", lower):
                genre = gid
                break
        if not genre:
            genre = "literary"
    premise = text_in
    premise = re.sub(r"(?i)^(?:write|create|make)\s+(?:me\s+)?(?:a\s+)?story\s+", "", premise)
    flex = genre.replace("_", r"[_ ]")
    premise = re.sub(rf"(?i)^in\s+{flex}\s+", "", premise)
    premise = re.sub(r"(?i)^about\s+", "", premise).strip()
    if not premise or len(premise) < 3:
        premise = text_in
    count = int(args.get("characters") or args.get("count") or 4)
    arch = args.get("archetypes")
    if isinstance(arch, str):
        arch = [a.strip() for a in arch.split(",") if a.strip()]
    fab = StoryFabric()
    story = fab.create_story(premise=premise, genre=genre, character_count=count, archetypes=arch)
    return (
        f"Story [{story.id}]  genre={story.genre}  title={story.title}\n"
        f"Cast: {', '.join(c.name + ' (' + c.archetype.value + ')' for c in story.characters)}\n\n"
        f"{story.body[:1200]}{'…' if len(story.body)>1200 else ''}\n\n"
        f"Expand: story_expand {story.id} | Modify: story_modify {story.id} mode=void"
    )


def _skill_story_expand(args: Dict[str, Any] | None = None) -> str:
    from levi.graph.story_fabric import StoryFabric
    args = args or {}
    sid = args.get("story_id") or args.get("id") or ""
    text_in = args.get("text") or ""
    import re
    if not sid:
        m = re.search(r"story\.([a-f0-9]+)", text_in)
        if m:
            sid = "story." + m.group(1)
    if not sid:
        fab = StoryFabric()
        stories = fab.list()
        if not stories:
            return "No stories yet. Create one first."
        sid = stories[0].id
    focus = args.get("focus") or "next_beat"
    if "character" in text_in.lower():
        focus = "character"
    elif "atmosphere" in text_in.lower():
        focus = "atmosphere"
    fab = StoryFabric()
    try:
        story = fab.expand(sid, focus=focus)
    except KeyError:
        return f"Unknown story {sid}"
    return f"Expanded [{story.id}] focus={focus}\n\n{story.body[-800:]}"


def _skill_story_modify(args: Dict[str, Any] | None = None) -> str:
    from levi.graph.story_fabric import StoryFabric
    args = args or {}
    text_in = args.get("text") or ""
    sid = args.get("story_id") or args.get("id") or ""
    mode = args.get("mode") or "void"
    import re
    if not sid:
        m = re.search(r"story\.([a-f0-9]+)", text_in)
        if m:
            sid = "story." + m.group(1)
    for mname in ("void", "interrogation", "reframe", "noir", "horror", "compress", "soft_landing", "spiral"):
        if mname in text_in.lower():
            mode = mname
            break
    if not sid:
        fab = StoryFabric()
        stories = fab.list()
        if not stories:
            return "No stories yet."
        sid = stories[0].id
    fab = StoryFabric()
    try:
        story = fab.modify(sid, mode=mode, instruction=text_in)
    except KeyError:
        return f"Unknown story {sid}"
    return f"Modified [{story.id}] mode={mode}\n\n{story.body[-900:]}"


def _skill_list_characters(_: Dict[str, Any] | None = None) -> str:
    from levi.graph.story_fabric import StoryFabric
    arches = StoryFabric().list_archetypes()
    return f"Character archetypes ({len(arches)}):\n" + ", ".join(arches)


BUILTIN_SKILLS: List[Skill] = [
    Skill(
        id="status",
        name="System Status",
        description="Report LEVI core status",
        category="system",
        risk_level=SkillRisk.INFO,
        handler=_skill_status,
        tags=["system", "health"],
    ),
    Skill(
        id="remember",
        name="Remember",
        description="Store a semantic memory entry",
        category="memory",
        risk_level=SkillRisk.LOW,
        permissions=["memory.write"],
        handler=_skill_remember,
        tags=["memory"],
    ),
    Skill(
        id="recall",
        name="Recall",
        description="Search or list memories",
        category="memory",
        risk_level=SkillRisk.INFO,
        permissions=["memory.read"],
        handler=_skill_recall,
        tags=["memory"],
    ),
    Skill(
        id="list_personas",
        name="List Personas",
        description="List available persona keys",
        category="persona",
        risk_level=SkillRisk.INFO,
        handler=_skill_list_personas,
        tags=["persona"],
    ),
    Skill(
        id="companion_status",
        name="Companion Status",
        description="Report companion identity state",
        category="companion",
        risk_level=SkillRisk.INFO,
        handler=_skill_companion_status,
        tags=["companion"],
    ),
    Skill(
        id="phase1_checklist",
        name="Phase 1 Checklist",
        description="Show current Phase 1 progress checklist",
        category="meta",
        risk_level=SkillRisk.INFO,
        handler=_skill_phase1_checklist,
        tags=["meta", "progress"],
    ),
    Skill(
        id="interpenetration_stats",
        name="Interpenetration Stats",
        description="Capability graph and composite statistics",
        category="graph",
        risk_level=SkillRisk.INFO,
        handler=_skill_interpenetration_stats,
        tags=["graph", "interpenetration"],
    ),
    Skill(
        id="suggest_compose",
        name="Suggest Compose",
        description="Suggest interpenetration partners for a node",
        category="graph",
        risk_level=SkillRisk.INFO,
        handler=_skill_suggest_compose,
        tags=["graph", "interpenetration"],
    ),
    Skill(
        id="compose",
        name="Compose",
        description="Propose a new composite capability from parts",
        category="graph",
        risk_level=SkillRisk.MODERATE,
        permissions=["graph.write"],
        requires_confirmation=True,
        handler=_skill_compose,
        tags=["graph", "interpenetration"],
    ),
    Skill(
        id="genres",
        name="Genre Registry",
        description="L.W.P. complete genre registry (all 97 formal genres)",
        category="lwp",
        risk_level=SkillRisk.INFO,
        handler=_skill_genres,
        tags=["genre", "lwp"],
    ),
    Skill(
        id="list_all_genres",
        name="List All Genres",
        description="List every formal L.W.P. genre id",
        category="lwp",
        risk_level=SkillRisk.INFO,
        handler=_skill_list_all_genres,
        tags=["genre", "lwp"],
    ),
    Skill(
        id="factory_status",
        name="Factory Status",
        description="Software Factory project statistics",
        category="factory",
        risk_level=SkillRisk.INFO,
        handler=_skill_factory_status,
        tags=["factory"],
    ),
    Skill(
        id="factory_create",
        name="Factory Create",
        description="Create a new Software Factory project from an idea",
        category="factory",
        risk_level=SkillRisk.LOW,
        permissions=["factory.write"],
        handler=_skill_factory_create,
        tags=["factory"],
    ),
    Skill(
        id="factory_advance",
        name="Factory Advance",
        description="Advance a factory project one pipeline stage",
        category="factory",
        risk_level=SkillRisk.MODERATE,
        permissions=["factory.write"],
        requires_confirmation=True,
        handler=_skill_factory_advance,
        tags=["factory"],
    ),
    Skill(
        id="automation_status",
        name="Automation Status",
        description="Automation registry statistics",
        category="automation",
        risk_level=SkillRisk.INFO,
        handler=_skill_automation_status,
        tags=["automation"],
    ),
    Skill(
        id="automation_list",
        name="Automation List",
        description="List registered automations",
        category="automation",
        risk_level=SkillRisk.INFO,
        handler=_skill_automation_list,
        tags=["automation"],
    ),
    Skill(
        id="automation_create",
        name="Automation Create",
        description="Compile NL→IR and create automation",
        category="automation",
        risk_level=SkillRisk.LOW,
        permissions=["automation.write"],
        handler=_skill_automation_create,
        tags=["automation", "nl_ir"],
    ),
    Skill(
        id="compile_ir",
        name="Compile IR",
        description="Compile natural language to Build/Automate intermediate representation",
        category="orchestration",
        risk_level=SkillRisk.INFO,
        handler=_skill_compile_ir,
        tags=["nl_ir", "orchestration"],
    ),
    Skill(
        id="story_create",
        name="Story Create",
        description="Create a story in a genre with varied characters (L.W.P. Story Fabric)",
        category="lwp",
        risk_level=SkillRisk.LOW,
        handler=_skill_story_create,
        tags=["story", "lwp", "genre"],
    ),
    Skill(
        id="story_expand",
        name="Story Expand",
        description="Expand a story (beat, character, atmosphere)",
        category="lwp",
        risk_level=SkillRisk.LOW,
        handler=_skill_story_expand,
        tags=["story", "lwp"],
    ),
    Skill(
        id="story_modify",
        name="Story Modify",
        description="Modify story via modes: void, interrogation, reframe, noir, horror, spiral…",
        category="lwp",
        risk_level=SkillRisk.LOW,
        handler=_skill_story_modify,
        tags=["story", "lwp", "mode"],
    ),
    Skill(
        id="list_characters",
        name="List Character Archetypes",
        description="List L.W.P. story character archetype variety",
        category="lwp",
        risk_level=SkillRisk.INFO,
        handler=_skill_list_characters,
        tags=["story", "character"],
    ),
    Skill(
        id="intent_map",
        name="Intent Map",
        description="Map a request to a structured intent (objective, why, constraints, direction)",
        category="orchestration",
        risk_level=SkillRisk.INFO,
        handler=_skill_intent_map,
        tags=["intent", "orchestration"],
    ),
    Skill(
        id="agent_run",
        name="Agent Run",
        description="Bounded specialist execution loop under governor/breaker",
        category="agent",
        risk_level=SkillRisk.MODERATE,
        permissions=["agent.run"],
        handler=_skill_agent_run,
        tags=["agent", "runtime"],
    ),
]

class SkillRegistry:
    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        for s in BUILTIN_SKILLS:
            self.register(s)
        # LEVI cybersecurity skill pack (100 original playbooks).
        # Lazy import: cyber_skills imports Skill/SkillRisk from this module.
        from levi.skill.cyber_skills import CYBER_SKILLS
        for s in CYBER_SKILLS:
            self.register(s)

    def register(self, skill: Skill) -> None:
        self._skills[skill.id] = skill

    def get(self, skill_id: str) -> Optional[Skill]:
        return self._skills.get(skill_id)

    def list(self, category: Optional[str] = None, tag: Optional[str] = None) -> List[Skill]:
        results = list(self._skills.values())
        if category:
            results = [s for s in results if s.category == category]
        if tag:
            results = [s for s in results if tag in s.tags]
        return sorted(results, key=lambda s: s.id)

    def invoke(self, skill_id: str, args: Optional[Dict[str, Any]] = None) -> Any:
        skill = self.get(skill_id)
        if not skill:
            raise KeyError(f"Unknown skill: {skill_id}")
        if skill.handler is None:
            raise RuntimeError(f"Skill {skill_id} has no handler")
        return skill.handler(args or {})

    def catalog(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self.list()]
