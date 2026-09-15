"""
Basic Orchestration Loop
UNDERSTAND → COMPANION/EI → PERSONA → SPECIALISTS → SKILLS/POLICY → SYNTHESIZE

Phase 1 version: deterministic routing, no unbound agent spawning.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from levi.ei.five_d import FiveDEI
from levi.ei.companion import CompanionCore
from levi.persona.lattice import PersonaLattice
from levi.persona.nervous_system import NervousSystem
from levi.persona.wit_layer import calibrate_wit, wit_system_block
from levi.persona.behaviors import apply_special_behavior
from levi.daemon.control import ControlDaemon
from levi.persona.monotropism import MonotropismTracker
from levi.agent.specialists import SpecialistRegistry
from levi.skill.registry import SkillRegistry
from levi.policy.gates import PolicyEngine, RiskLevel
from levi.memory.store import MemoryStore
from levi.memory.types import MemoryType
from levi.orchestration.intent import build_intent_map
from levi.model.abstraction import ModelRouter, GenerationRequest


@dataclass
class TurnResult:
    intent: str
    persona_id: str
    companion_summary: str
    specialists: List[str]
    skills_considered: List[str]
    response: str
    is_special_behavior: bool = False
    policy_receipt: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)




def _continuity_block() -> str:
    """Inject profile name, weekly goal, and latest shelf into every ask prompt."""
    bits: List[str] = []
    try:
        from levi.identity.profile import ProfileStore
        p = ProfileStore().load()
        if p and getattr(p, "name", None):
            bits.append(f"The human's name is {p.name}.")
        if p and getattr(p, "goal_this_week", None):
            bits.append(f"Their goal this week: {p.goal_this_week}.")
    except Exception:
        pass
    try:
        from levi.identity.shelf import collect_shelf
        shelf = collect_shelf()
        if shelf:
            top = shelf[0]
            bits.append(f'Shelf (recent work): {top.kind} "{top.title}" — {top.summary[:100]}.')
        else:
            bits.append("Shelf is empty.")
    except Exception:
        bits.append("Shelf unavailable.")
    return (" ".join(bits) + " ") if bits else ""


class Orchestrator:
    def __init__(
        self,
        persona_id: Optional[str] = None,
        auto_approve_up_to: RiskLevel = RiskLevel.LOW,
        soft_power: bool = True,
        force_constructive: bool = False,
    ):
        self.ei = FiveDEI()
        self.companion = CompanionCore(self.ei)
        self.lattice = PersonaLattice(default=persona_id or "normal")
        self.nervous = NervousSystem(persona_ids=self.lattice.keys())
        if persona_id:
            self.lattice.set_active(persona_id)
            self.nervous.lock(persona_id)
        self.specialists = SpecialistRegistry()
        self.skills = SkillRegistry()
        self.policy = PolicyEngine(auto_approve_up_to=auto_approve_up_to)
        self.memory = MemoryStore()
        self.router = ModelRouter()
        self.soft_power = soft_power
        self.force_constructive = force_constructive
        self._clarification_counts: Dict[str, int] = {}
        self._detail_levels: Dict[str, int] = {}
        self._pending_constructive: Optional[Dict[str, Any]] = None
        self._active_stack = None
        self._wit = None
        self.control = ControlDaemon()
        self.mono = MonotropismTracker()


    def _stack_prompt_block(self) -> str:
        stack = getattr(self, "_active_stack", None)
        if not stack:
            return ""
        def resolve(pid: str) -> str:
            p = self.lattice.get(pid)
            if not p:
                return pid
            return f"{p.display_name} ({p.communication_style})"
        try:
            return stack.prompt_block(resolve)
        except Exception:
            lab = getattr(stack, "label", None)
            return f"Ensemble: {lab() if callable(lab) else lab}."

    def set_persona(self, persona_id: str) -> bool:
        ok = self.lattice.set_active(persona_id)
        if ok:
            self.nervous.lock(persona_id)
        return ok

    def unlock_persona(self) -> None:
        """Release explicit persona lock; nervous matrix resumes selection."""
        self.nervous.unlock()

    def turn(self, user_text: str) -> TurnResult:
        # UNDERSTAND — structured intent sketch; never allowed to break the turn
        try:
            intent_map = build_intent_map(user_text).to_dict()
        except Exception:
            intent_map = {"literal_request": user_text or "", "confidence": 0.0}
        # Nervous system: score stress/anxiety/workload/bond → persona lens
        # (skipped when user locked a persona via --personality / set_persona)
        shelf_count = 0
        try:
            from levi.identity.shelf import collect_shelf
            shelf_count = len(collect_shelf())
        except Exception:
            pass
        # Monotropism: update interest tunnel before persona selection
        try:
            self.mono.sense(user_text)
        except Exception:
            pass

        stack = None
        if not self.nervous._locked_persona:
            if hasattr(self.nervous, "select_stack"):
                stack = self.nervous.select_stack(
                    user_text,
                    context={"shelf_count": shelf_count},
                )
                chosen = stack.primary
            else:
                chosen = self.nervous.select(
                    user_text,
                    context={"shelf_count": shelf_count},
                )
            self.lattice.set_active(chosen)
        else:
            self.nervous.sense(user_text, context={"shelf_count": shelf_count})
            self.nervous._persist()

        persona = self.lattice.current()
        persona_id = persona.id if persona else "normal"
        self._active_stack = stack
        self._wit = None

        # Bond reinforcement on collaborative constructive asks
        if any(w in user_text.lower() for w in ("thank", "please help", "let's", "lets ", "together")):
            self.nervous.reinforce_bond(0.03)

        # 1. Memory of the interaction
        self.memory.add(
            MemoryType.EPISODIC,
            content=f"User: {user_text}",
            importance=0.4,
            source="user",
            tags=["turn", persona_id],
        )

        # 2. EI + Companion
        ei_state = self.ei.evaluate(user_text)
        guidance = self.companion.guide(
            user_text,
            context={"has_history": self.memory.stats()["total"] > 1},
        )

        # 3. Specialist selection (advisory for now)
        selected = self.specialists.select_for_intent(user_text)
        specialist_ids = [s.id for s in selected]

        # 4. Special persona control flow (interrogation / no_hero / reframe)
        session_key = persona_id
        prior = self._clarification_counts.get(session_key, 0)
        detail = self._detail_levels.get(session_key, 0)
        special = apply_special_behavior(
            user_text, persona, prior_clarifications=prior, detail_level=detail
        )

        if special is not None:
            response_text, is_final, new_detail = special
            if persona and persona.requires_explicit_answer_request:
                if not is_final:
                    self._clarification_counts[session_key] = prior + 1
                else:
                    self._clarification_counts[session_key] = 0
            if persona and getattr(persona, "no_hero_mode", False):
                self._detail_levels[session_key] = new_detail

            return TurnResult(
                intent=user_text,
                persona_id=persona_id,
                companion_summary=guidance.summary,
                specialists=specialist_ids,
                skills_considered=[],
                response=response_text,
                is_special_behavior=True,
                metadata={
                    "intent_map": intent_map,
                    "ei": ei_state.as_dict(),
                    "clarifications": self._clarification_counts.get(session_key, 0),
                    "detail_level": self._detail_levels.get(session_key, 0),
                },
            )

        # 5. Skill consideration — priority order matters (factory before checklist)
        skills_hit: List[str] = []
        lower = user_text.lower()

        # High-priority: Software Factory (LEVI-native capability)
        if any(p in lower for p in (
            "build me", "build a", "make an app", "make a tool", "create an app",
            "software factory", "factory create", "create project", "new project",
            "scaffold",
        )):
            skills_hit.append("factory_create")
        elif "advance" in lower and ("project" in lower or "factory" in lower or "proj." in lower):
            skills_hit.append("factory_advance")
        elif "factory" in lower and "status" in lower:
            skills_hit.append("factory_status")
        elif "automation" in lower and ("list" in lower or "status" in lower):
            skills_hit.append("automation_status")
        elif any(h in lower for h in ("automate", "every morning", "every day", "schedule a", "whenever i")):
            skills_hit.append("automation_create")
        elif "checklist" in lower or (("phase 1" in lower or "phase1" in lower) and "progress" in lower):
            skills_hit.append("phase1_checklist")
        elif "remember" in lower and "this" in lower:
            skills_hit.append("remember")
        elif "recall" in lower or "what do you remember" in lower:
            skills_hit.append("recall")
        elif "persona" in lower and "list" in lower:
            skills_hit.append("list_personas")
        elif "companion" in lower and "status" in lower:
            skills_hit.append("companion_status")
        elif lower.strip() in ("status", "system status", "health"):
            skills_hit.append("status")
        elif "interpenetration" in lower or "capability graph" in lower or lower.strip() == "graph":
            skills_hit.append("interpenetration_stats")
        elif "suggest" in lower and ("compose" in lower or "combin" in lower or "interpenetra" in lower):
            skills_hit.append("suggest_compose")
        elif lower.startswith("compose ") or "compose with" in lower:
            skills_hit.append("compose")
        elif "genre" in lower:
            skills_hit.append("genres")
        elif any(w in lower for w in ("run agents", "agent run", "delegate specialists")):
            skills_hit.append("agent_run")
        elif any(w in lower for w in ("write a story", "create a story", "story in", "make a story")):
            skills_hit.append("story_create")
        elif "expand" in lower and "story" in lower:
            skills_hit.append("story_expand")
        elif ("modify" in lower and "story" in lower) or any(
            m in lower for m in ("story void", "story noir", "story interrogation", "story spiral")
        ):
            skills_hit.append("story_modify")
        elif "character archetype" in lower or "list characters" in lower:
            skills_hit.append("list_characters")
        elif any(w in lower for w in ("compile ir", "nl-ir", "nl→ir", "show ir", "to ir")):
            skills_hit.append("compile_ir")

        # 6. Constructive confirm (soft UX) — factory/story don't surprise
        CONSTRUCTIVE = {"factory_create", "story_create", "automation_create"}
        if skills_hit and skills_hit[0] in CONSTRUCTIVE and not self.force_constructive:
            try:
                from levi.identity.profile import ProfileStore
                if ProfileStore().load().confirm_constructive:
                    skill_id = skills_hit[0]
                    label = {
                        "factory_create": "build a project (Factory DNA)",
                        "story_create": "start a story (L.W.P. Story Fabric)",
                        "automation_create": "create an automation",
                    }.get(skill_id, skill_id)
                    try:
                        prof = ProfileStore().load()
                        prof.pending_skill = skill_id
                        prof.pending_text = user_text
                        ProfileStore().save(prof)
                    except Exception:
                        pass
                    return TurnResult(
                        intent=user_text,
                        persona_id=persona_id,
                        companion_summary=guidance.summary,
                        specialists=specialist_ids,
                        skills_considered=skills_hit,
                        response=(
                            f"That sounds like you want to {label}.\n\n"
                            f"Say **yes, do it** (or **yes**) to proceed, or rephrase.\n"
                            f"Tip: levi init --yes disables this confirm. Templates: levi templates"
                        ),
                        metadata={"intent_map": intent_map, "pending_constructive": skill_id, "soft_confirm": True},
                    )
            except Exception:
                pass

        # 6b. Honor constructive confirm
        low = user_text.lower().strip()
        if low in ("yes", "yes, do it", "do it", "confirm", "y", "yes do it"):
            try:
                from levi.identity.profile import ProfileStore
                prof = ProfileStore().load()
                if prof.pending_skill and prof.pending_text:
                    skills_hit = [prof.pending_skill]
                    user_text = prof.pending_text
                    prof.pending_skill = ""
                    # keep pending_text for audit
                    ProfileStore().save(prof)
                    self.force_constructive = True
            except Exception:
                pass

        # 7. If a low-risk skill matches, invoke under policy
        if skills_hit:
            skill_id = skills_hit[0]
            skill = self.skills.get(skill_id)
            if skill:
                risk = RiskLevel(int(skill.risk_level))
                proposal = self.policy.propose(
                    description=f"Invoke skill: {skill.name}",
                    risk_level=risk,
                    reason="Matched user intent to registered skill",
                    affected_systems=["local"],
                    permissions_required=skill.permissions,
                )
                preview = self.policy.preview(proposal.id)
                if preview and not preview["requires_explicit_approval"]:
                    self.policy.request_permission(proposal.id)
                    try:
                        result = self.skills.invoke(skill_id, {"text": user_text})
                        receipt = self.policy.mark_completed(
                            proposal.id,
                            result_summary=str(result)[:200],
                            verified=True,
                        )
                        return TurnResult(
                            intent=user_text,
                            persona_id=persona_id,
                            companion_summary=guidance.summary,
                            specialists=specialist_ids,
                            skills_considered=skills_hit,
                            response=str(result),
                            policy_receipt=receipt.id,
                            metadata={"intent_map": intent_map, "skill": skill_id, "ei": ei_state.as_dict()},
                        )
                    except Exception as e:
                        return TurnResult(
                            intent=user_text,
                            persona_id=persona_id,
                            companion_summary=guidance.summary,
                            specialists=specialist_ids,
                            skills_considered=skills_hit,
                            response=f"Skill error: {e}",
                            metadata={"intent_map": intent_map, "skill": skill_id, "error": str(e)},
                        )

        # 7. Default: model generation with full companion + persona guidance
        # Soft power: do not dump organs/IR unless caller uses --verbose path.
        role_str = ", ".join(r.value for r in guidance.primary_roles)
        tone_str = "; ".join(guidance.tone_notes)
        continuity = _continuity_block()
        protective = "; ".join(guidance.protective_notes) if guidance.protective_notes else ""
        # Light–dark + ND spectrum wit (muted under distress / grief / crisis)
        # Control daemon may force wit styles; crisis regulation still wins inside calibrate_wit
        intrigue = bool(getattr(self._active_stack, "intrigue", False)) if self._active_stack else False
        ut = getattr(guidance, "user_tone", None) or getattr(self.ei.state, "user_tone", None) or "neutral"
        reg = getattr(guidance, "regulation", None) or getattr(self.ei.state, "tone_regulation", None) or "steady"
        inten = float(getattr(self.ei.state, "user_intensity", None) or 0.3)
        force_styles = None
        try:
            force_styles = self.control.wit_force_styles()
        except Exception:
            force_styles = None
        preferred = {}
        try:
            preferred = dict(self.mono.wit_preferred() or {})
        except Exception:
            preferred = {}
        # positive prefs only for calibrate (negatives handled by not selecting)
        preferred_pos = {k: v for k, v in preferred.items() if v > 0}
        self._wit = calibrate_wit(
            user_tone=ut,
            intensity=inten,
            regulation=reg,
            intrigue=intrigue and (getattr(self.mono.state.active, 'depth', 0) or 0) < 0.55,
            force_styles=force_styles,
            preferred_styles=preferred_pos or None,
        )
        wit_block = wit_system_block(self._wit)
        # Alchemy + Life equation (x+y=z) — core navigable logic
        core_logic = ""
        try:
            core_logic = self.control.core_logic_block(
                user_text=user_text,
                tone_primary=getattr(ut, "primary", None) or str(ut) if ut else "neutral",
            )
            self.control.tick_turn()
        except Exception:
            core_logic = ""
        mono_block = ""
        try:
            mono_block = self.mono.prompt_block()
        except Exception:
            mono_block = ""
        user_frame = ""
        if getattr(guidance, "user_tone", None):
            user_frame = (
                f"User emotional frame: {guidance.user_tone} "
                f"(regulation={getattr(guidance, 'regulation', 'steady')}). "
                f"Match the need, not the arousal. Do not escalate, mock, or minimize. "
            )
        if protective:
            user_frame += f"Protective constraints: {protective}. "
        system = (
            f"You are LEVI — one coherent super-system: "
            f"companion (friend/mentor/challenger/protector) + L.W.P. structure + "
            f"constructive Factory DNA (not a side app). "
            f"Roles this turn: {role_str}. Tone: {tone_str}. "
            f"Persona lens: {persona.display_name if persona else 'Normal'} — "
            f"{persona.description if persona else ''}. "
            f"{self._stack_prompt_block()} "
            f"{user_frame}"
            f"{continuity}"
            f"When the user wants to build, you build under cascade/governor/policy — "
            f"you do not 'open a factory app'. "
            f"Always: honest, non-sycophantic, never fabricate. Label uncertainty. "
            f"Protect the user. Local-first. Prefer continuity and clear care over performance. "
            f"Do not dump internal architecture, specialist names, or IR unless the user asks. "
            f"Challenge level this turn is capped; do not push harder than care allows. "
            f"{wit_block} "
            f"{core_logic} "
            f"{mono_block}"
        )
        result = self.router.generate(
            GenerationRequest(prompt=user_text, system=system),
            prefer_local=True,
        )

        return TurnResult(
            intent=user_text,
            persona_id=persona_id,
            companion_summary=guidance.summary,
            specialists=specialist_ids,
            skills_considered=skills_hit,
            response=result.text,
            metadata={
                "intent_map": intent_map,
                "model": result.model_id,
                "local": result.is_local,
                "ei": ei_state.as_dict(),
            },
        )
