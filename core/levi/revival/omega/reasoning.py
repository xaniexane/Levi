"""Reasoned routing: Alpha reasons, Omega platforms and routes.

The call path ``reason_route(task_text, providers, mode=...)`` runs one
deliberation (Alpha's propose -> critique -> verdict) over the task text,
then routes the resulting task over the given providers under Nexus's
mode-aware policy. Alpha builds the understanding of the task; Omega
platforms the decision and does the routing. One call, "everything in
one", offline-first.

Two laws stay in force, unmixed:

- Alpha's HONESTY LAW: the verdict always states which substrate
  reasoned; the brain-voice proposal is heard, never obeyed (its score
  is capped below every rules stance); the brain is exercised, never
  assumed.
- Nexus's SOURCING LAW: only ``levi-local`` and ``levi-si-cloud`` are
  operational sources; ``reference`` providers are never eligible, in any
  mode, through this path or any other.

``Task`` facts (``kinds``, ``needs_local``) are explicit caller input or
reported defaults — never inferred from prose. The deliberation's job is
to reason about the task; the router's job is to rank providers against
explicit routing facts. What goes to the router is always reported, never
hallucinated.

Kind-derivation study verdict (2026-09-21, refinement pass): the
deliberation already extracts content words and a question type, and a
word -> kind lexicon was considered — but the explicit-facts design is
FINAL and unchanged. Words describe a task; they do not declare what the
job needs, so a lexicon would hallucinate requirements and smuggle
prose-derived facts past the report-not-hallucinate line. The deliberator
may interpret the task with words; the router's inputs are facts. The
default ``{'chat'}`` plus the reported caveat is the whole story.

Public surface:

- ``ReasonedPlan`` — the deliberation plus the routing decision:
  ``task_text``, ``task_type`` (Alpha's question type: ``yes-no``,
  ``information``, ``instruction``, ``fragment``, or ``open``), ``kinds``,
  ``needs_local``, ``verdict`` (Alpha's verdict dict), ``substrate``,
  ``limits``, ``routes`` (nexus ``Route`` entries, best first),
  ``top_provider`` (first eligible provider's name, or ``None``),
  ``caveats`` (the verdict's survived weakness and open question, plus
  a note when the routing kinds are the reported default),
  ``brain_voice`` (the brain-voice continuation verbatim when the brain
  ran — the evidence trail, heard never obeyed; ``None`` when the brain
  did not run).
- ``reason_route(task_text, providers, mode="balanced", *,
  kinds=None, needs_local=False, brain_dir=None)`` — deliberate, then
  route. Refuses empty task text with ``ValueError`` (like Alpha); raises
  ``RuntimeError`` when Alpha is unavailable in this build; unknown
  modes and empty provider lists raise ``ValueError`` (like Nexus).
- ``explain_plan(plan)`` — human-readable summary of the whole call
  path: verdict, answer, top provider, routes, caveats, substrate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from . import nexus

ORIGIN = "levi-revival-omega/reasoning"

# The routing facts the module falls back to when the caller supplies
# none. Reported as a default wherever the plan surfaces — never
# presented as something Alpha "read" from the task.
DEFAULT_KINDS = frozenset({"chat"})
DEFAULT_KINDS_CAVEAT = (
    "routing kinds defaulted to {'chat'}: no caller-supplied kinds, so the "
    "router ranked providers on generic conversation capability — pass "
    "kinds explicitly for anything else"
)


@dataclass
class ReasonedPlan:
    task_text: str
    task_type: str
    kinds: frozenset
    needs_local: bool
    verdict: Dict[str, Any]
    substrate: str
    limits: str
    routes: List[nexus.Route]
    top_provider: Optional[str]
    caveats: List[str] = field(default_factory=list)
    # The evidence trail: verbatim brain-voice continuation when the
    # brain ran (heard in deliberation, never obeyed in the verdict),
    # or None when the brain did not run. Labeled at display time.
    brain_voice: Optional[str] = None


def _task_type(proposals: Sequence[Dict[str, Any]]) -> str:
    for proposal in proposals:
        analysis = proposal.get("analysis")
        if isinstance(analysis, dict) and analysis.get("qtype"):
            return str(analysis["qtype"])
    return "unknown"


def _brain_voice_text(deliberated: Dict[str, Any], stance: str) -> Optional[str]:
    """Verbatim brain-voice continuation from the deliberation, if it ran.

    The brain-voice proposal is appended to ``deliberated["proposals"]``
    by Alpha's ``reason()`` only when the brain actually ran; otherwise
    there is no such proposal and the trail is absent (``None``), not
    invented. Labeled, verbatim, heard-never-obeyed.
    """
    for proposal in deliberated.get("proposals", []):
        if isinstance(proposal, dict) and proposal.get("stance") == stance:
            text = proposal.get("text")
            return str(text) if text is not None else None
    return None


def reason_route(
    task_text: str,
    providers: Sequence[nexus.Provider],
    mode: str = "balanced",
    *,
    kinds: Optional[frozenset] = None,
    needs_local: bool = False,
    brain_dir: Optional[str] = None,
) -> ReasonedPlan:
    """Deliberate over ``task_text`` with Alpha, then route with Omega.

    Alpha's verdict (chosen stance, answer, survived weakness, open
    question, substrate, honest limits) travels with the routing result;
    the routing itself is Nexus's unchanged policy over the same
    providers — the sourcing law holds exactly as in ``nexus.route``.
    """
    if not isinstance(task_text, str) or not task_text.strip():
        raise ValueError(
            "empty task: nothing to reason about — give Omega a task to route"
        )
    try:
        # lazy: omega stays import-light; both come from the same organ
        from levi.alpha.reason import BRAIN_STANCE, Reasoner
    except Exception as exc:  # noqa: BLE001 - honest, not a guess
        raise RuntimeError("alpha is unavailable in this build") from exc
    reasoner = Reasoner(brain_dir=brain_dir) if brain_dir else Reasoner()
    deliberated = reasoner.reason(task_text)
    routing_kinds = frozenset(kinds) if kinds is not None else DEFAULT_KINDS
    caveats: List[str] = []
    if kinds is None:
        caveats.append(DEFAULT_KINDS_CAVEAT)
    verdict = deliberated["verdict"]
    for key in ("survived_weakness", "open_question"):
        value = verdict.get(key)
        if value:
            caveats.append(f"{key.replace('_', ' ')}: {value}")
    task = nexus.Task(
        kinds=routing_kinds,
        needs_local=bool(needs_local),
        label=task_text.strip()[:80],
    )
    routes = nexus.route(task, providers, mode=mode)
    top = next((r.provider for r in routes if r.eligible), None)
    return ReasonedPlan(
        task_text=task_text.strip(),
        task_type=_task_type(deliberated.get("proposals", [])),
        kinds=routing_kinds,
        needs_local=bool(needs_local),
        verdict=verdict,
        substrate=deliberated["substrate"],
        limits=deliberated["limits"],
        routes=routes,
        top_provider=top,
        caveats=caveats,
        brain_voice=_brain_voice_text(deliberated, BRAIN_STANCE),
    )


def explain_plan(plan: ReasonedPlan) -> str:
    """One readable record of the whole reason-then-route call path."""
    lines = [
        f"task: {plan.task_text}",
        f"task type: {plan.task_type} | kinds: {sorted(plan.kinds)}"
        + (" | needs LEVI-local" if plan.needs_local else ""),
        f"verdict: {plan.verdict.get('chosen')} (score {plan.verdict.get('score')})",
        f"answer: {plan.verdict.get('answer')}",
        f"top provider: {plan.top_provider or '(none eligible)'}",
        "--- routes ---",
    ]
    lines.append(nexus.explain(plan.routes))
    if plan.caveats:
        lines.append("--- caveats ---")
        for caveat in plan.caveats:
            lines.append(f"  - {caveat}")
    if plan.brain_voice is not None:
        # The evidence trail, labeled verbatim: what the brain said is
        # reported exactly; it was heard in deliberation, never obeyed
        # in the verdict. Quoted with !r so it reads as quoted speech.
        lines.append("--- brain-voice (heard, never obeyed) ---")
        lines.append(f"  raw continuation, not reasoning: {plan.brain_voice!r}")
    lines.append(f"substrate: {plan.substrate}")
    lines.append(f"limits: {plan.limits}")
    return "\n".join(lines)


__all__ = [
    "ORIGIN",
    "DEFAULT_KINDS",
    "ReasonedPlan",
    "reason_route",
    "explain_plan",
]
