"""The bloodstream turn pipeline — one organism, one turn.

Stage order is DNA and must not be reordered::

    companion_ei → persona → governor → route → policy → memory → trace
                                                            → promotion?

Route selection:
    constructive text ("build me", "scaffold", ...) → FACTORY cascade
    organ text (what-ifs / decide / choose)          → ORGAN (echo / mandella)
    everything else                                  → MODEL (provider chain + specialists)

Special persona behaviors (interrogation ⊥ no_hero) short-circuit the turn
with their own reply — at most ONE may fire per turn, enforced here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from levi.affect import SessionEI, modulate
from levi.affect.detector import EmotionReading
from levi.affect.policy import PolicyDecision, evaluate
from levi.persona.behaviors import apply_special_behavior
from levi.persona.lattice import Persona, PersonaLattice
from levi.graph.lwp_primitives import CircuitBreaker, Governor
from levi.policy.gates import PolicyEngine, RiskLevel

from levi.bloodstream.stages import (
    BehaviorKind,
    RouteKind,
    StageRecord,
    TurnContext,
    TurnResult,
)
from levi.bloodstream.trace import TRACE_FIELDS, TraceWriter, new_trace_id
from levi.bloodstream.gate import GateOutcome, run_gated
from levi.bloodstream.composites import CompositeRegistry


# ---------------------------------------------------------------------------
# Session-scoped state (in-memory; the stores on disk hold the durable part)
# ---------------------------------------------------------------------------

_sessions: Dict[str, SessionEI] = {}
_clarifications: Dict[Tuple[str, str], int] = {}
_detail_levels: Dict[Tuple[str, str], int] = {}


def _session_for(session_id: str) -> SessionEI:
    sess = _sessions.get(session_id)
    if sess is None:
        sess = SessionEI()
        _sessions[session_id] = sess
    return sess


def reset_session_state() -> None:
    """Clear in-memory session state (tests, fresh starts)."""
    _sessions.clear()
    _clarifications.clear()
    _detail_levels.clear()


# ---------------------------------------------------------------------------
# Intent heuristics (deterministic, offline)
# ---------------------------------------------------------------------------

_FACTORY_HINTS = (
    "build me",
    "build a",
    "create an app",
    "create a tool",
    "make an app",
    "make me",
    "scaffold",
    "factory create",
    "new project",
    "software factory",
)
_ECHO_HINTS = (
    "what if",
    "echoverse",
    "explore",
    "scenarios",
    "possibilities",
    "parallel",
    "what could",
)
_MANDELLA_HINTS = (
    "should i",
    "mandella",
    "decide",
    "choose",
    "a or b",
    "options",
    "which one",
    "help me pick",
)
_EXTERNAL_HINTS = (
    "send",
    "email",
    "post ",
    "publish",
    "deploy",
    "tweet",
    "message ",
    "pay",
    "buy ",
    "transfer",
    "wire ",
)


def _classify(text: str) -> Tuple[RouteKind, str]:
    lower = text.lower()
    if any(h in lower for h in _FACTORY_HINTS):
        return RouteKind.FACTORY, "constructive intent"
    if any(h in lower for h in _ECHO_HINTS):
        return RouteKind.ORGAN, "exploratory intent → echoverse"
    if any(h in lower for h in _MANDELLA_HINTS):
        return RouteKind.ORGAN, "decision intent → mandella"
    return RouteKind.MODEL, "conversational intent → model"


def _assess_risk(text: str, route: RouteKind) -> Tuple[RiskLevel, str]:
    lower = text.lower()
    if any(h in lower for h in _EXTERNAL_HINTS):
        return RiskLevel.HIGH, "external send / financial language"
    if route is RouteKind.FACTORY:
        return RiskLevel.MODERATE, "factory project creation"
    return RiskLevel.LOW, "local informational turn"


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------


def _stage_companion_ei(
    text: str, ctx: TurnContext
) -> Tuple[StageRecord, SessionEI, Dict[str, Any]]:
    """Companion + 5D EI. UX/state shaping only — never overrides safety,
    permission, or facts. Never claims sentience or feeling."""
    session = _session_for(ctx.session_id)
    reading: EmotionReading = session.observe_user(text)
    modulation = modulate(text, session)
    policy: PolicyDecision = evaluate(text, reading)
    ei_summary = {
        "dominant": getattr(reading, "dominant", "neutral"),
        "valence": round(float(getattr(reading, "valence", 0.0)), 3),
        "arousal": round(float(getattr(reading, "arousal", 0.0)), 3),
        "d5_integrity": "high",  # Integrity never degrades; recorded, not computed
        "deescalate": bool(getattr(policy, "deescalate", False)),
        "crisis": bool(getattr(policy, "crisis", False)),
        "register": getattr(modulation.get("suggestion"), "register_id", None)
        if isinstance(modulation, dict)
        else None,
    }
    record = StageRecord(
        stage="companion_ei",
        decision="observed",
        detail=ei_summary,
    )
    return (
        record,
        session,
        {"reading": reading, "modulation": modulation, "policy": policy},
    )


def _stage_persona(
    text: str, ctx: TurnContext
) -> Tuple[StageRecord, Persona, BehaviorKind, Optional[str]]:
    """Persona lens + special behaviors. interrogation ⊥ no_hero: at most one
    fires per turn. On conflict (both flags set) interrogation wins and the
    conflict is recorded — never mixed, never silent."""
    lattice = PersonaLattice()
    if ctx.persona_id:
        lattice.set_active(ctx.persona_id)
    persona = lattice.current()
    if persona is None:  # pragma: no cover — lattice always has a default
        persona = Persona(
            id="normal",
            display_name="Normal",
            description="",
            reasoning_bias="",
            communication_style="",
        )
    persona_id = persona.id

    key = (ctx.session_id, persona_id)
    prior = _clarifications.get(key, 0)
    detail = _detail_levels.get(key, 0)

    wants_interrogation = bool(persona.requires_explicit_answer_request)
    wants_no_hero = bool(persona.no_hero_mode)
    conflict = wants_interrogation and wants_no_hero

    behavior = BehaviorKind.NONE
    reply: Optional[str] = None
    special = apply_special_behavior(
        text, persona, prior_clarifications=prior, detail_level=detail
    )
    if special is not None:
        text_out, is_final, new_detail = special
        if wants_interrogation:
            behavior = BehaviorKind.INTERROGATION
            _clarifications[key] = 0 if is_final else prior + 1
        elif wants_no_hero:
            behavior = BehaviorKind.NO_HERO
            _detail_levels[key] = new_detail
        elif persona.reframes_questions:
            behavior = BehaviorKind.REFRAME
        reply = text_out

    record = StageRecord(
        stage="persona",
        decision=behavior.value,
        detail={
            "persona_id": persona_id,
            "behavior_conflict": conflict,
            "conflict_resolution": "interrogation takes precedence"
            if conflict
            else None,
        },
    )
    return record, persona, behavior, reply


def _stage_governor(
    text: str, ctx: TurnContext, route: RouteKind, base_risk: RiskLevel
) -> Tuple[StageRecord, bool, int, str]:
    """L.W.P. governor + circuit breaker + composite risk ceiling.

    Effective risk = max(intent risk, composite ceiling). Composites inherit
    the STRICTEST ceiling of their parts — the governor enforces it here.
    """
    gov = Governor(name="bloodstream-turn", budget=5.0)
    breaker = CircuitBreaker(name="bloodstream-turn", max_calls=50)
    allowed = gov.authorize(cost=0.1, complexity=1) and breaker.check()
    if breaker.tripped:
        allowed = False

    ceiling = int(base_risk)
    composite_name = None
    if ctx.composite_name:
        data_dir = ctx.data_dir or (Path.home() / ".levi" / "bloodstream")
        registry = CompositeRegistry(data_dir=data_dir)
        comp = registry.get(ctx.composite_name)
        if comp is not None:
            from levi.skill.registry import SkillRegistry
            from levi.agent.specialists import SpecialistRegistry
            from levi.daemon.automation import AutomationRegistry

            skills = SkillRegistry()
            specialists = SpecialistRegistry()
            auto_dir = (data_dir / "automations") if data_dir else None
            automations = (
                AutomationRegistry(data_dir=auto_dir)
                if auto_dir
                else AutomationRegistry()
            )
            ceiling = max(
                ceiling,
                registry.risk_ceiling(
                    comp,
                    skills=skills,
                    specialists=specialists,
                    automations=automations,
                ),
            )
            composite_name = comp.name

    record = StageRecord(
        stage="governor",
        decision="allowed" if allowed else "refused",
        detail={
            "governor_allowed": allowed,
            "breaker_tripped": breaker.tripped,
            "base_risk": int(base_risk),
            "composite": composite_name,
            "effective_risk": ceiling,
        },
    )
    return record, allowed, ceiling, composite_name or ""


# ---------------------------------------------------------------------------
# Route executors (each runs INSIDE the policy gate)
# ---------------------------------------------------------------------------


def _execute_factory(
    text: str, data_dir: Optional[Path]
) -> Tuple[Callable[[], str], Callable[[], bool]]:
    from levi.factory.pipeline import SoftwareFactory

    factory = SoftwareFactory(data_dir=data_dir)
    holder: Dict[str, Any] = {}

    def execute() -> str:
        name = " ".join(text.split()[:6])[:60] or "untitled"
        project = factory.create(name=f"turn: {name}", idea=text, risk_ceiling=2)
        holder["id"] = project.id
        return f"factory project {project.id} created (stage: {project.stage.value})"

    def verify() -> bool:
        pid = holder.get("id")
        return pid is not None and factory.get(pid) is not None

    return execute, verify


def _execute_organ(
    text: str, classification_detail: str
) -> Tuple[Callable[[], str], Callable[[], bool], List[str]]:
    if "mandella" in classification_detail:
        from levi.organs.mandella import run_mandella, format_mandella

        def execute() -> str:
            return format_mandella(run_mandella(domain="decision", seed=text))
    else:
        from levi.organs.echo import run_echo, format_echo

        def execute() -> str:
            return format_echo(run_echo(seed=text, cycles=3))

    def verify() -> bool:
        return True  # deterministic local organs; output presence is the check

    return execute, verify, []


def _execute_model(
    text: str, ctx: TurnContext, session: SessionEI, ei_hint: str
) -> Tuple[Callable[[], str], Callable[[], bool], Dict[str, Any]]:
    from levi.agent.loop import run_subtask

    holder: Dict[str, Any] = {}

    def execute() -> str:
        transcript = run_subtask(
            text,
            provider=ctx.provider,
            affect=True,
            affect_session=session,
            max_steps=ctx.max_model_steps,
        )
        holder["provider"] = transcript.provider_name
        holder["ok"] = transcript.ok
        holder["skills"] = [
            c.get("name") for s in transcript.steps for c in s.tool_calls
        ]
        reply = transcript.final.strip() or str(transcript)
        holder["reply"] = reply
        prefix = ei_hint.strip()
        return f"{prefix}\n\n{reply}" if prefix else reply

    def verify() -> bool:
        return bool(holder.get("ok", False))

    return execute, verify, holder


# ---------------------------------------------------------------------------
# Failure composting (REIM lives in lwp/model_engine.py — route, don't expand)
# ---------------------------------------------------------------------------


def _compost_failure(summary: str, data_dir: Optional[Path]) -> Dict[str, Any]:
    """Route a failed turn's residue to the existing REIM. Best-effort:
    composting must never break the turn that is already failing."""
    record: Dict[str, Any] = {"engine": "levi.lwp.model_engine.reim_forks", "ok": False}
    try:
        from levi.lwp.model_engine import LWPModelEngine

        path = (Path(data_dir) / "lwp_model_state.json") if data_dir else None
        engine = LWPModelEngine(path=path) if path else LWPModelEngine()
        out = engine.reim_forks(seed=summary[:200], tracks=2)
        record["ok"] = True
        record["tracks_excerpt"] = out[:600]
    except Exception as exc:  # noqa: BLE001
        record["error"] = f"{exc.__class__.__name__}: {exc}"[:200]
    return record


# ---------------------------------------------------------------------------
# The turn
# ---------------------------------------------------------------------------


def run_turn(text: str, ctx: Optional[TurnContext] = None) -> TurnResult:
    """Run one bloodstream turn. Deterministic and offline-first: every stage
    has a local fallback; the model stage uses the existing provider chain
    (rules-only LocalProvider by default)."""
    ctx = ctx or TurnContext()
    trace_id = new_trace_id()
    stages: List[StageRecord] = []
    data_dir = Path(ctx.data_dir) if ctx.data_dir else None

    def data_sub(name: str) -> Optional[Path]:
        return (data_dir / name) if data_dir else None

    try:
        # 1. Companion + 5D EI
        ei_record, session, ei_parts = _stage_companion_ei(text, ctx)
        stages.append(ei_record)
        ei_hint = ""
        modulation = ei_parts["modulation"]
        if isinstance(modulation, dict):
            ei_hint = str(modulation.get("hint") or "")

        # 2. Persona lens (interrogation ⊥ no_hero — never mixed)
        persona_record, persona, behavior, special_reply = _stage_persona(text, ctx)
        stages.append(persona_record)

        if special_reply is not None:
            # Special behavior short-circuits: still memory + trace, no model call.
            result = _finish(
                text=text,
                ctx=ctx,
                trace_id=trace_id,
                stages=stages,
                reply=special_reply,
                route=RouteKind.SPECIAL,
                behavior=behavior,
                persona_id=persona.id,
                risk=0,
                provider="special-behavior",
                skills=[],
                receipt_id=None,
                awaiting=False,
                outcome="replied",
                error=None,
                composted=None,
                data_dir=data_dir,
            )
            return result

        # 3. Route classification + risk
        route, route_detail = _classify(text)
        base_risk, risk_reason = _assess_risk(text, route)

        # 4. L.W.P. governor (+ composite ceiling)
        gov_record, allowed, effective_risk, composite_name = _stage_governor(
            text, ctx, route, base_risk
        )
        stages.append(gov_record)
        stages.append(
            StageRecord(
                stage="route",
                decision=route.value,
                detail={
                    "reason": route_detail,
                    "risk_reason": risk_reason,
                    "composite": composite_name or None,
                },
            )
        )

        if not allowed:
            return _finish(
                text=text,
                ctx=ctx,
                trace_id=trace_id,
                stages=stages,
                reply=(
                    "The turn governor refused this request (budget or breaker). "
                    "Nothing was executed."
                ),
                route=RouteKind.GOVERNED,
                behavior=behavior,
                persona_id=persona.id,
                risk=effective_risk,
                provider="none",
                skills=[],
                receipt_id=None,
                awaiting=False,
                outcome="governed",
                error=None,
                composted=None,
                data_dir=data_dir,
            )

        # 5. Build the route executor (runs INSIDE the policy gate)
        holder: Dict[str, Any] = {}
        if route is RouteKind.FACTORY:
            execute, verify = _execute_factory(text, data_sub("factory"))
            action_desc = f"factory: create project from turn ({text[:80]})"
        elif route is RouteKind.ORGAN:
            execute, verify, _ = _execute_organ(text, route_detail)
            action_desc = f"organ: {route_detail} ({text[:80]})"
        else:
            execute, verify, holder = _execute_model(text, ctx, session, ei_hint)
            action_desc = f"model turn via provider chain ({text[:80]})"

        # 6. Policy gate — Plan → Preview → Permission → Execute → Verify → Receipt
        engine = PolicyEngine(auto_approve_up_to=ctx.auto_approve_up_to)
        gate: GateOutcome = run_gated(
            engine=engine,
            description=action_desc,
            risk_level=RiskLevel(effective_risk),
            reason=f"bloodstream turn [{route.value}] — {risk_reason}",
            execute=execute,
            verify=verify,
            confirm=ctx.confirm,
            auto_approve_up_to=ctx.auto_approve_up_to,
            dry_run=ctx.dry_run,
            affected_systems=["local"],
            reversible=True,
        )
        stages.append(
            StageRecord(
                stage="policy",
                decision=(
                    "awaiting_permission"
                    if gate.awaiting_permission
                    else "denied"
                    if not gate.approved
                    else "dry_run"
                    if gate.dry_run
                    else "executed"
                ),
                detail={
                    "risk": effective_risk,
                    "auto_approved": gate.auto_approved,
                    "verified": gate.verified,
                    "receipt_id": gate.receipt_id,
                    "preview": gate.preview,
                },
            )
        )

        if gate.awaiting_permission:
            preview = gate.preview or {}
            reply = (
                "This needs your permission before I run it.\n\n"
                f"Action: {preview.get('action', action_desc)}\n"
                f"Risk: {preview.get('risk_level', effective_risk)} — "
                f"{preview.get('reason', risk_reason)}\n"
                f"Reversible: {preview.get('reversible', True)}\n\n"
                "Approve it and I'll execute, verify, and hand you a receipt."
            )
            return _finish(
                text=text,
                ctx=ctx,
                trace_id=trace_id,
                stages=stages,
                reply=reply,
                route=route,
                behavior=behavior,
                persona_id=persona.id,
                risk=effective_risk,
                provider=holder.get("provider", "none"),
                skills=holder.get("skills", []),
                receipt_id=None,
                awaiting=True,
                outcome="awaiting_permission",
                error=None,
                composted=None,
                data_dir=data_dir,
            )
        if not gate.approved:
            return _finish(
                text=text,
                ctx=ctx,
                trace_id=trace_id,
                stages=stages,
                reply="Denied at the permission gate. Nothing was executed.",
                route=route,
                behavior=behavior,
                persona_id=persona.id,
                risk=effective_risk,
                provider=holder.get("provider", "none"),
                skills=[],
                receipt_id=None,
                awaiting=False,
                outcome="denied",
                error=None,
                composted=None,
                data_dir=data_dir,
            )

        reply = holder.get("reply") or "done."
        if route is not RouteKind.MODEL and gate.receipt is not None:
            # factory/organ executors return their output as the execution
            # summary; surface it as the reply.
            reply = gate.receipt.outcome or reply
        if gate.error:
            raise RuntimeError(gate.error)

        return _finish(
            text=text,
            ctx=ctx,
            trace_id=trace_id,
            stages=stages,
            reply=reply,
            route=route,
            behavior=behavior,
            persona_id=persona.id,
            risk=effective_risk,
            provider=holder.get("provider", "policy-gate")
            if route is RouteKind.MODEL
            else "deterministic-local",
            skills=holder.get("skills", []),
            receipt_id=gate.receipt_id,
            awaiting=False,
            outcome="replied",
            error=None,
            composted=None,
            data_dir=data_dir,
        )

    except Exception as exc:  # noqa: BLE001 — the turn must never crash the caller
        summary = f"{exc.__class__.__name__}: {exc}"[:300]
        composted = _compost_failure(
            f"bloodstream turn failed: {summary} :: {text[:120]}", data_dir
        )
        stages.append(
            StageRecord(
                stage="failure", decision="composted", detail={"error": summary}
            )
        )
        return _finish(
            text=text,
            ctx=ctx,
            trace_id=trace_id,
            stages=stages,
            reply=(
                "Something broke mid-turn. The failure was recorded and its "
                "residue routed to REIM compost — it won't be silently dropped."
            ),
            route=RouteKind.FAILED,
            behavior=BehaviorKind.NONE,
            persona_id="unknown",
            risk=0,
            provider="none",
            skills=[],
            receipt_id=None,
            awaiting=False,
            outcome="failed",
            error=summary,
            composted=composted,
            data_dir=data_dir,
        )


def _finish(
    *,
    text: str,
    ctx: TurnContext,
    trace_id: str,
    stages: List[StageRecord],
    reply: str,
    route: RouteKind,
    behavior: BehaviorKind,
    persona_id: str,
    risk: int,
    provider: str,
    skills: List[str],
    receipt_id: Optional[str],
    awaiting: bool,
    outcome: str,
    error: Optional[str],
    composted: Optional[Dict[str, Any]],
    data_dir: Optional[Path],
) -> TurnResult:
    """Memory + trace + promotion eligibility. Shared by every exit path —
    no turn leaves without a trace."""
    # Memory: one episodic entry per turn
    memory_ok = False
    try:
        from levi.memory.store import MemoryStore
        from levi.memory.types import MemoryType

        mem_dir = (data_dir / "memory") if data_dir else None
        store = MemoryStore(data_dir=mem_dir) if mem_dir else MemoryStore()
        store.add(
            MemoryType.EPISODIC,
            content=f"User: {text[:500]}\nLevi ({route.value}): {reply[:500]}",
            importance=0.4,
            source="bloodstream",
            tags=["turn", "bloodstream", route.value, persona_id]
            + (["compost-pending"] if outcome == "failed" else []),
        )
        memory_ok = True
    except Exception:
        pass  # memory is durable-nice-to-have; never break the turn
    stages.append(
        StageRecord(
            stage="memory",
            decision="recorded" if memory_ok else "skipped",
            detail={"memory_type": "episodic", "source": "bloodstream"},
        )
    )

    # Trace: every field, every turn. The trace stage records itself as it
    # writes — the JSONL snapshot shows the full decision path including it.
    trace_stage = StageRecord(stage="trace", decision="pending", detail={})
    stages.append(trace_stage)
    trace: Dict[str, Any] = {
        "trace_id": trace_id,
        "session_id": ctx.session_id,
        "text_excerpt": text[:200],
        "stages": [s.to_dict() for s in stages],
        "provider": provider,
        "skills_invoked": skills,
        "policy_receipt_id": receipt_id,
        "risk_level": risk,
        "route": route.value,
        "outcome": outcome,
        "error": error,
        "composted": composted,
    }
    for f in TRACE_FIELDS:  # contract: no missing fields, ever
        trace.setdefault(f, None)
    trace_path = None
    trace_ok = False
    try:
        writer = TraceWriter(base_dir=(data_dir / "traces") if data_dir else None)
        trace_path = writer.write(trace)
        trace_ok = trace_path is not None
    except Exception:
        pass
    trace_stage.decision = "written" if trace_ok else "failed"
    trace_stage.detail = {"path": str(trace_path) if trace_path else None}

    promotion_eligible = receipt_id is not None and outcome == "replied"
    receipt_summary = (
        f"receipt {receipt_id[:8]}…"
        if receipt_id
        else "no receipt (no consequential act executed)"
    ) + f" · risk {risk} · route {route.value} · provider {provider}"

    return TurnResult(
        reply=reply,
        route=route,
        behavior=behavior,
        persona_id=persona_id,
        risk_level=risk,
        receipt_summary=receipt_summary,
        trace_id=trace_id,
        policy_receipt_id=receipt_id,
        awaiting_permission=awaiting,
        promotion_eligible=promotion_eligible,
        ok=outcome != "failed",
        error=error,
        stages=stages,
    )
