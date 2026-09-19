"""Escalation — the clean entry point to the counsels.

``counsel_agent(agent_id, ...)`` is the single door: the automation engine,
the Operator-contract paths, and the agent twin-pair layer's merge/judge
protocol escalate hard cases here. Intake takes the agent id plus both
hemisphere positions; verdicts are per-agent and delivered to both
hemispheres.

Merge/judge compatibility: the pair must converge to one action. When the
hemispheres diverge, counsel arbitrates the divergence. What counsel cannot
settle (critical-stakes divergence ending hold-for-human/refuse) escalates
to the keeper — flagged on the verdict, never decided unilaterally.

Dry-run safe: with ``dry_run=True`` the counsel still deliberates fully
(the verdict is real advice), but nothing is persisted — no receipt file,
no growth-journal write. Counsel never commands: the returned verdict is
advisory; the agent pair decides (and the keeper overrules).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from levi.automation.minions import MINIONS, Minion
from levi.ci import aici, mapping, receipts, sici, signal, twins, xici
from levi.ci.counsel import Case, CloudCounsel, Verdict
from levi.ci.twins import AgentCase, HemispherePosition, arbitrate_agent_case

_COUNSELS = {"AICI": aici.AICI, "SICI": sici.SICI, "XICI": xici.XICI}


def find_minion(minion_id: str) -> Minion:
    for m in MINIONS:
        if m.id == minion_id:
            return m
    raise KeyError(f"unknown minion id: {minion_id}")


def counsel_for(minion: Minion) -> CloudCounsel:
    """The class counsel for one agent's intake record.

    Raises for intake-capped rows. ``Minion`` here is strictly the frozen
    intake-record dataclass; the living entity served is the agent.
    """
    class_tag = mapping.class_for_minion(minion)
    counsel_name = mapping.counsel_for_class(class_tag)
    if not counsel_name:
        raise ValueError(
            f"agent {minion.id} is capped at intake — no counsel serves it yet"
        )
    return _COUNSELS[counsel_name]()


def counsel_for_agent(agent_id: str) -> CloudCounsel:
    """The class counsel for one agent-twin by agent id."""
    class_tag = mapping.class_for_agent(agent_id)
    return counsel_for_class(class_tag)


def counsel_for_class(class_tag: str) -> CloudCounsel:
    """The counsel serving a class directly ('AI' | 'SI' | 'XI')."""
    name = mapping.counsel_for_class(class_tag)
    if not name:
        raise ValueError(f"no counsel serves class {class_tag!r}")
    return _COUNSELS[name]()


@dataclass
class EscalationResult:
    verdict: Verdict
    receipt: Optional[Dict[str, Any]]
    signal_entry: Optional[Dict[str, Any]]
    dry_run: bool


def _persist(verdict: Verdict, ruling_context: str) -> tuple:
    receipt = receipts.mint_verdict_receipt(
        {
            "verdict_id": verdict.verdict_id,
            "counsel": verdict.counsel,
            "minion_id": verdict.minion_id,
            "agent_id": verdict.agent_id,
            "minion_class": verdict.minion_class,
            "case_fingerprint": verdict.case_fingerprint,
            "ruling": verdict.ruling,
            "ts": verdict.ts,
        }
    )
    entry = signal.export_verdict(verdict, receipt, ruling_context)
    return receipt, entry


def counsel_agent(
    agent_id: str,
    question: str,
    left_stance: str,
    right_stance: str,
    left_reasoning: str = "",
    right_reasoning: str = "",
    context: Optional[Dict[str, Any]] = None,
    stakes: str = "routine",
    dry_run: bool = True,
    ruling_context: str = "",
) -> EscalationResult:
    """Escalate a hard case for one agent-twin pair to its class counsel.

    Intake takes the agent id plus both hemisphere positions. The verdict
    is per-agent, delivered to both hemispheres; divergences are arbitrated,
    and what counsel cannot settle is flagged ``escalate_to_keeper``.

    Deliberation always runs in full. With ``dry_run=True`` (default)
    nothing is persisted — no receipt file, no growth-journal write.
    """
    class_tag = mapping.class_for_agent(agent_id)
    counsel_obj = counsel_for_class(class_tag)
    agent_case = AgentCase(
        agent_id=agent_id,
        agent_class=class_tag,
        question=question,
        left=HemispherePosition(
            side="left", stance=left_stance, reasoning=left_reasoning
        ),
        right=HemispherePosition(
            side="right", stance=right_stance, reasoning=right_reasoning
        ),
        stakes=stakes,
        context=dict(context or {}),
    )
    verdict = arbitrate_agent_case(counsel_obj, agent_case)
    if dry_run:
        return EscalationResult(
            verdict=verdict, receipt=None, signal_entry=None, dry_run=True
        )
    receipt, entry = _persist(verdict, ruling_context)
    return EscalationResult(
        verdict=verdict, receipt=receipt, signal_entry=entry, dry_run=False
    )


def counsel(
    minion_id: str,
    question: str,
    context: Optional[Dict[str, Any]] = None,
    stakes: str = "routine",
    dry_run: bool = True,
    ruling_context: str = "",
) -> EscalationResult:
    """Escalate a hard case to the agent's class counsel.

    Backward-compatible entry: the single-position case is delivered to
    both hemispheres undiverged. Prefer :func:`counsel_agent` for
    hemisphere-aware intake.
    """
    return counsel_agent(
        agent_id=minion_id,
        question=question,
        left_stance="unified",
        right_stance="unified",
        context=context,
        stakes=stakes,
        dry_run=dry_run,
        ruling_context=ruling_context,
    )
