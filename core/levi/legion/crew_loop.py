"""Legion crew execution loop: the agentic turn loop behind every crew member.

ORIGINALS-FIRST — this module adds execution; it invents nothing about
the product:

- ``docs/LEGION.md`` (Chauncey, 2026-09-18): "one face the customer talks
  to, the legion (tailored team of agents) behind it doing the work."
- ``legion/team.py``: ``CrewMember``, ``Team``, ``assemble_team``,
  responsibilities, and the one-face handoff lattice. Roster, operator
  resolution, and handoff rules are untouched — this module only runs
  turns through them.
- ``legion/skill_pool/pool.py``: the ONE shared pool. Every tool a crew
  member touches resolves through ``get_pool()`` — no per-member
  registries, no copies. (Chauncey, 2026-09-22: "let all of legion have
  a skill pool", "they all use [it]".)
- ``levi.agent.loop.run_subtask``: the canonical step-level tool loop
  every turn runs through.
- ``levi.agent.assistant``: assistant-core system-prompt section and
  memory-context builders.

LAWS (declared in plain words, guarded in code, proven in tests):

1. "The roster stays the source of truth." ``run_crew_turn`` never
   assembles, mutates, or reseats a team — it resolves a member that is
   already on it.
2. "One pool, every member." Every tool resolves through the same
   ``get_pool()`` singleton Nanobit uses. Never a per-member copy. When
   the pool has no keyword match for a role, the member gets the general
   business shelf as a labeled fallback — still the same pool object,
   never an empty toolbelt and never a private registry.
3. "Labeled skills never fake execution." Pool skills with no wired
   handler become tools that say so honestly — backend flag in the
   description, ``ok=False`` with "nothing was executed" on call. The
   single exception is ``legion_skill_finder`` (read-only skill search),
   which genuinely runs because it is pure lookup with no side effects.
4. "Handoff rules are law in the prompt and in routing." The member's
   system prompt carries its handoff rules verbatim: what it cannot
   finish hands back to the face role; complaints, payment disputes,
   and anything unsafe go to the owner. The loop never silently reroutes
   a turn to another member — routing stays the router's job
   (``legion/product.py``).
5. "Unknown members fail loudly." A member id that is not on the team
   raises ``LegionError`` naming the team and its real roles — never a
   guess, never a silent default.
6. "The crew never moves money and never wears another brand." Stated in
   every turn's system prompt, not assumed.

PROOF (honest): behavioral verification — property tests in
``tests/test_legion_crew_loop.py``, not a formal proof.

Dynasty eyes-only: no dynasty/IP material in this module.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from levi.agent.assistant import assistant_system_prompt
from levi.agent.loop import AgentTranscript, run_subtask
from levi.agent.tools import Tool, ToolRegistry, ToolResult
from levi.legion.skill_pool.pool import get_pool
from levi.legion.team import HandoffRule, Team

from .product import LegionError

__all__ = [
    "shared_pool",
    "registry_from_skills",
    "member_system_prompt",
    "run_crew_turn",
]

# Cap: a turn sees a handful of the best-matching skills, never the
# whole 80-skill pool — the loop's tool list stays small and honest.
_MAX_SKILLS_PER_TURN = 8


def shared_pool():
    """The ONE shared skill pool — the same singleton object Nanobit
    resolves through (``levi.revival.omega.nanobit.skill_pool``).
    Callers never instantiate their own."""
    return get_pool()


def _tool_name(skill_id: str) -> str:
    """Deterministic tool name for a pool skill id."""
    safe = re.sub(r"[^a-z0-9]+", "_", (skill_id or "").lower()).strip("_")
    return f"skill_{safe or 'unknown'}"


def _honest_stub(skill: Dict[str, Any]):
    """A handler that refuses to fake execution — the honest face of a
    pool skill with no wired handler in this build."""
    skill_id = skill["id"]
    backend = skill["backend"]

    def _handler(args: Dict[str, Any]) -> ToolResult:
        _ = args
        return ToolResult(
            ok=False,
            output="",
            error=(
                f"skill {skill_id!r} is labeled {backend!r} in the shared "
                f"skill pool — no wired handler exists for it in this "
                f"build, so nothing was executed and nothing was faked. "
                f"Escalate to a wired surface (the LEVI agent core) when "
                f"real execution is needed."
            ),
        )

    return _handler


def _finder_handler(pool) -> Any:
    """The one genuinely-wired pool tool: ``legion_skill_finder`` is
    pure read-only skill lookup — safe to actually run."""

    def _handler(args: Dict[str, Any]) -> ToolResult:
        query = str((args or {}).get("query", "") or "")
        matches = pool.find_skill(query)[:5]
        if not matches:
            return ToolResult(
                ok=True,
                output=f"no pool skills matched {query!r}",
            )
        lines = [
            f"- {m['id']} [{m['backend']}] executable_now={m['executable_now']}: "
            f"{m['description'][:120]}"
            for m in matches
        ]
        return ToolResult(ok=True, output="\n".join(lines))

    return _handler


def registry_from_skills(
    skills: List[Dict[str, Any]], *, pool=None
) -> ToolRegistry:
    """Build a :class:`ToolRegistry` from pool skill dicts.

    Every tool resolves through the shared pool object (``pool`` or
    ``get_pool()``). Skills without wired handlers become honest stubs
    (law 3); ``legion_skill_finder`` is wired for real because it is
    read-only lookup. Tool names are deterministic ``skill_<id>``.
    """
    pool = pool if pool is not None else get_pool()
    registry = ToolRegistry()
    seen = set()
    for skill in skills or []:
        skill_id = str(skill.get("id", "") or "")
        if not skill_id or skill_id in seen:
            continue
        seen.add(skill_id)
        name = _tool_name(skill_id)
        backend = skill.get("backend", "?")
        executable = bool(skill.get("executable_now", False))
        if skill_id == "legion_skill_finder":
            handler = _finder_handler(pool)
            note = "WIRED: genuinely runs read-only skill search on the shared pool."
        else:
            handler = _honest_stub(skill)
            note = (
                "NOT wired in this build — calls return ok=False honestly; "
                "nothing is executed or faked."
            )
        registry.register(
            Tool(
                name=name,
                description=(
                    f"{skill.get('name', skill_id)}: "
                    f"{skill.get('description', '')} "
                    f"[pool backend={backend}, executable_now={executable}] "
                    f"{note}"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "what to look up / the task detail",
                        },
                    },
                },
                handler=handler,
            )
        )
    return registry


def _member_handoffs(team: Team, role: str) -> List[HandoffRule]:
    """Handoff rules that name this member as the one handing off, plus
    the team-wide owner catch-all."""
    rules = [r for r in team.handoff_rules if r.from_role == role]
    rules += [r for r in team.handoff_rules if r.to_role == "owner"]
    return rules


def member_system_prompt(team: Team, role: str, responsibility: str) -> str:
    """Role-context system prompt for one crew member's turn.

    Assistant core + who this member is + its handoff rules verbatim +
    the crew's honest limits (never moves money, never wears another
    brand, never guesses — hands off instead).
    """
    identity = (team.business_name or "Legion").strip() or "Legion"
    lines = [assistant_system_prompt(identity=identity), ""]
    lines.append(f"You are the {role} on the {identity} crew.")
    lines.append(f"Your responsibility: {responsibility}")
    lines.append("")
    rules = _member_handoffs(team, role)
    if rules:
        lines.append("Handoff rules — these are law, not suggestions:")
        for r in rules:
            lines.append(
                f"- when '{r.event}': {r.from_role} hands to {r.to_role}"
                + (f" ({r.note})" if r.note else "")
            )
        lines.append("")
    lines.append(
        "Honest limits, always: you never move money, never touch payments, "
        "never claim to be another company's product, and never guess at "
        "an answer you do not have — you hand off to the face role "
        f"({team.face_role}) instead. Report what tools actually returned, "
        "including failures."
    )
    return "\n".join(lines)


def _resolve_member(team: Team, member_id: str):
    """Find the crew member by role id. Unknown ids fail LOUDLY —
    ``LegionError`` naming the team and its real roles (law 5)."""
    if not isinstance(team, Team):
        raise LegionError(f"run_crew_turn: 'team' must be a Team, got {type(team).__name__}")
    want = (member_id or "").strip()
    for member in team.crew:
        if member.role == want:
            return member
    real = [m.role for m in team.crew]
    raise LegionError(
        f"unknown crew member {member_id!r} on team {team.team_id!r} — "
        f"real roles: {real}. Refusing to guess."
    )


def run_crew_turn(
    team: Team,
    member_id: str,
    task: str,
    *,
    max_steps: int = 10,
    provider: Optional[Any] = None,
) -> AgentTranscript:
    """Run one crew member's turn through the agentic tool loop.

    Flow: resolve member (loud on unknown) -> build role-context system
    prompt -> resolve tools through the SHARED pool -> ``run_subtask`` ->
    return the transcript. Handoff rules are carried in the prompt; the
    loop never silently reroutes the turn to another member (law 4).

    ``provider`` may be a :class:`ChatProvider`, a provider-name string,
    or ``None`` for the default selection.
    """
    if not isinstance(task, str) or not task.strip():
        raise ValueError(
            f"run_crew_turn: 'task' must be a non-empty string, got {task!r}"
        )
    member = _resolve_member(team, member_id)
    pool = shared_pool()
    matched = pool.skills_for(member.role) + pool.find_skill(task)
    skills: List[Dict[str, Any]] = []
    seen = set()
    for s in matched:
        sid = s.get("id")
        if sid and sid not in seen:
            seen.add(sid)
            skills.append(s)
    if not skills:
        # Honest fallback, still through the shared pool: when the pool
        # has nothing keyword-matched for a role, the member gets the
        # general business shelf rather than an empty toolbelt. Labeled
        # here, not hidden.
        for s in pool.skills_for("business"):
            sid = s.get("id")
            if sid and sid not in seen:
                seen.add(sid)
                skills.append(s)
    skills = skills[:_MAX_SKILLS_PER_TURN]
    registry = registry_from_skills(skills, pool=pool)
    system = member_system_prompt(team, member.role, member.responsibility)
    transcript = run_subtask(
        task=task,
        provider=provider,
        registry=registry,
        max_steps=max_steps,
        system_prompt=system,
    )
    # law 4: no silent rerouting — the transcript of THIS member's turn
    # is returned as-is, even when the model asks for a handoff. Routing
    # stays the router's job (legion/product.py).
    return transcript
