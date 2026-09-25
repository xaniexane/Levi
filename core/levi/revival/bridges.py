"""Revival bridges — the hands, not the organs.

LEVI's revival modules (Echo blueprints, Alpha generators) speak their
own dialect. The demand, jobs, skills, and orchestration organs speak
LEVI's. This module is the handshake: thin, honest glue that carries a
revival artifact to the real organs without re-implementing them.

Rules of the bridge:

- Read-only against the organs. Nothing here duplicates DemandPulse,
  the job tracker, or the skill registry — they are imported, never
  re-built.
- Never fabricate. DemandPulse scores arrive as data, not invention;
  the bridge registers a blueprint's prompt as a HYPOTHESIS seed and
  reports exactly that. No five-factor card is conjured without real
  factor evidence.
- Nothing auto-approves. Blueprint jobs land in the pipeline's draft
  state (``new``) with a HITL note; skills register as review-required
  plans with ``requires_confirmation=True``. The bridge never builds,
  never executes, never moves anything forward on its own.
- Honest degradation: every bridge returns ``{"ok": False, "reason": ...}``
  when the organ or the input genuinely isn't there — never a fake score,
  never a silent success.

Public surface:

- ``score_blueprint(blueprint, pulse=None)``
- ``blueprint_to_job(blueprint, tracker=None)``
- ``hand_skill_to_registry(files, registry=None, skill_id=None, name=None,
  description=None)``
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .omega.blueprint import validate_blueprint

ORIGIN = "levi-revival/bridges"

# The real organs' draft state. The job pipeline has no "needs-approval"
# status of its own; ``new`` is its initial draft state, so blueprints
# land there and the note carries the HITL marking.
_JOB_SOURCE = "revival-echo"
_JOB_NOTE_PREFIX = "HITL review required"


def _blueprint_title(blueprint: Dict[str, Any]) -> str:
    return str(blueprint.get("title") or blueprint.get("name") or "untitled").strip()


def score_blueprint(blueprint: Any, pulse: Optional[Any] = None) -> Dict[str, Any]:
    """Run DemandPulse scoring over a blueprint's prompt/title.

    Uses the real ``levi.demand`` API: the blueprint's prompt is
    registered via ``DemandPulse.scan_seed`` as a HYPOTHESIS signal —
    the organ's honest entry point for user/context text. A
    five-factor score card is deliberately *not* fabricated here:
    that needs real factor evidence with bases, which a blueprint
    doesn't have; the signal id is returned so a caller can score it
    later with genuine factors.

    Returns ``{"ok": True, "signal_id", "signal", "pulse", "note"}``
    or ``{"ok": False, "reason": ...}``.
    """
    check = validate_blueprint(blueprint)
    if not check["ok"]:
        return {
            "ok": False,
            "reason": "invalid blueprint: " + "; ".join(check["errors"]),
        }
    prompt = str(blueprint.get("prompt") or "").strip()
    if not prompt:
        return {"ok": False, "reason": "blueprint has no prompt text to score"}
    try:
        if pulse is None:
            from levi.demand.pulse import DemandPulse

            pulse = DemandPulse()
    except Exception as exc:
        return {"ok": False, "reason": f"DemandPulse unavailable: {exc}"}
    try:
        signal = pulse.scan_seed(prompt, segment="revival")
    except Exception as exc:
        return {"ok": False, "reason": f"scan_seed failed: {exc}"}
    return {
        "ok": True,
        "signal_id": signal.id,
        "signal": signal.to_dict(),
        "pulse": type(pulse).__name__,
        "note": (
            "Registered as a HYPOTHESIS demand signal via the real "
            "DemandPulse.scan_seed. No five-factor card was created — "
            "that requires real factor evidence, and the bridge does "
            "not invent scores."
        ),
    }


def blueprint_to_job(blueprint: Any, tracker: Optional[Any] = None) -> Dict[str, Any]:
    """Create a jobs-tracker entry from an Echo blueprint.

    HITL-friendly by construction: the entry lands in the pipeline's
    draft state (``new``) with source ``revival-echo`` and a note
    marking it as needing human approval. Idempotent via
    ``JobTracker.upsert`` — re-bridging the same blueprint refreshes,
    never duplicates. Nothing moves to ``active`` on its own; that is a
    human's (or policy's) call.

    Returns ``{"ok": True, "job_id", "created", "status"}`` or
    ``{"ok": False, "reason": ...}``.
    """
    check = validate_blueprint(blueprint)
    if not check["ok"]:
        return {
            "ok": False,
            "reason": "invalid blueprint: " + "; ".join(check["errors"]),
        }
    try:
        if tracker is None:
            from levi.jobs.tracker import JobTracker

            tracker = JobTracker()
    except Exception as exc:
        return {"ok": False, "reason": f"JobTracker unavailable: {exc}"}
    title = _blueprint_title(blueprint)
    types = ", ".join(str(t) for t in blueprint.get("product_types", []))
    note = (
        f"{_JOB_NOTE_PREFIX}: Echo blueprint "
        f"'{blueprint.get('name', '')}' needs human approval before "
        f"anything builds. product_types=[{types}] "
        f"artifacts={len(blueprint.get('artifacts', []))} "
        f"prompt={str(blueprint.get('prompt', ''))[:200]}"
    )
    try:
        job, created = tracker.upsert(
            title=title, company="", source=_JOB_SOURCE, note=note
        )
    except Exception as exc:
        return {"ok": False, "reason": f"job upsert failed: {exc}"}
    return {
        "ok": True,
        "job_id": job.id,
        "created": created,
        "status": job.status,
        "note": (
            "Landed in draft state 'new'. A human (or policy-gated move) "
            "must advance it — the bridge never auto-approves."
        ),
    }


def _slug(text: str) -> str:
    slug = "".join(c.lower() if c.isalnum() else "-" for c in text).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "revival-skill"


def _revival_handler(files: Dict[str, str], skill_id: str):
    """Stub handler: presents the plan, never executes generated code."""
    file_list = "\n".join(f"  - {path}" for path in sorted(files))

    def _handle(args: Optional[Dict[str, Any]] = None) -> str:
        return (
            f"Revival skill plan [{skill_id}] — NOT auto-executed.\n"
            f"Generated files ({len(files)}):\n{file_list}\n\n"
            "This is a reviewed-plan handoff from LEVI's revival surface. "
            "Read the files, confirm the contents, then wire a real handler "
            "or install via the user-skill flow before it does anything."
        )

    return _handle


def _check_files(files: Any) -> Optional[str]:
    if not isinstance(files, dict) or not files:
        return "files must be a non-empty {path: content} dict"
    for path, content in files.items():
        if not isinstance(path, str) or not path.strip():
            return f"file path must be a non-empty string, got {path!r}"
        if path.strip().startswith("/") or ".." in path.replace("\\", "/").split("/"):
            return f"refusing unsafe path: {path!r}"
        if not isinstance(content, str):
            return f"content for {path!r} must be a string"
    return None


def hand_skill_to_registry(
    files: Any,
    registry: Optional[Any] = None,
    skill_id: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Hand Alpha's skill-generator {path: content} output to the skill system.

    The real ``SkillRegistry`` accepts ``Skill`` objects with handlers.
    A generated scaffold has no handler yet, so the bridge registers a
    review-required plan skill: an INFO-risk ``Skill`` whose handler only
    *presents* the generated files and how to wire them. It can never
    execute generated code, and ``requires_confirmation=True`` keeps the
    policy gate in front of any invocation.

    With ``registry=None`` nothing is registered: the caller gets an
    explicit plan dict describing the human steps to install the skill
    (e.g. write a SKILL.md under ``~/.levi/skills/<id>/`` or call
    ``SkillRegistry().register``).

    Returns ``{"ok": True, "registered", "skill_id", ...}`` or
    ``{"ok": False, "reason": ...}``.
    """
    bad = _check_files(files)
    if bad:
        return {"ok": False, "reason": bad}
    files = {str(p).strip(): str(c) for p, c in files.items()}
    try:
        from levi.skill.registry import Skill, SkillRisk
    except Exception as exc:
        return {"ok": False, "reason": f"skill registry unavailable: {exc}"}
    sid = _slug(skill_id or name or next(iter(files)))
    skill_name = (name or sid.replace("-", " ").title()).strip()
    skill_desc = (
        description
        or f"Revival-generated skill plan from LEVI's revival surface ({ORIGIN}); "
        "review-required, presents generated files, executes nothing."
    ).strip()
    skill = Skill(
        id=sid,
        name=skill_name,
        description=skill_desc,
        category="revival",
        risk_level=SkillRisk.INFO,
        requires_confirmation=True,
        tags=["revival", "needs-review"],
        version="0.1.0",
        handler=_revival_handler(files, sid),
    )
    plan = {
        "skill_id": sid,
        "name": skill_name,
        "files": sorted(files),
        "steps": [
            f"Review the {len(files)} generated file(s) for safety and intent.",
            f"To install as a user skill: write a SKILL.md frontmatter file under "
            f"~/.levi/skills/{sid}/ and let the registry discover it.",
            "To wire live behavior: replace the plan handler with a real one "
            "and register via SkillRegistry().register(skill).",
        ],
    }
    if registry is None:
        return {
            "ok": True,
            "registered": False,
            "skill_id": sid,
            "plan": plan,
            "note": (
                "No registry handed in — nothing was registered. "
                "Follow the plan steps to install."
            ),
        }
    register = getattr(registry, "register", None)
    if not callable(register):
        return {
            "ok": False,
            "reason": "registry has no register(skill) method; "
            "hand a real SkillRegistry or None for the plan dict",
        }
    try:
        register(skill)
    except Exception as exc:
        return {"ok": False, "reason": f"register failed: {exc}"}
    return {
        "ok": True,
        "registered": True,
        "skill_id": sid,
        "skill": skill.to_dict(),
        "files": sorted(files),
        "note": (
            "Registered as a review-required plan skill (INFO risk, "
            "requires_confirmation=True). Its handler presents the "
            "generated files and executes nothing."
        ),
    }


# ---- orchestration ----------------------------------------------------
# The orchestration organ lives at levi.orchestration.loop: Orchestrator
# exposes turn(user_text) -> TurnResult, and levi.orchestration.nl_ir
# offers NLIRCompiler for structured handoffs. No bridge duplicates the
# loop here; a revival artifact reaches the orchestrator the same way
# any intent does — as user text through turn(). This is documented, not
# wrapped, because a wrapper would add indirection without judgment.


def orchestration_entry_points() -> Dict[str, List[str]]:
    """Verified orchestration entry points (documented, not wrapped)."""
    return {
        "levi.orchestration.loop": [
            "Orchestrator(persona_id=None, auto_approve_up_to=RiskLevel.LOW) "
            "-> TurnResult via .turn(user_text: str)",
            "TurnResult fields: intent, persona_id, companion_summary, "
            "specialists, skills_considered, response, policy_receipt",
        ],
        "levi.orchestration.nl_ir": [
            "NLIRCompiler().compile(text) / .compile_build(text) / "
            ".compile_automate(text) -> IR with to_dict()",
        ],
    }
