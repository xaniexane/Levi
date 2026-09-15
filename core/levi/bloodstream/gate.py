"""Policy gate — Plan → Preview → Permission → Execute → Verify → Receipt.

There are no bypass paths. Every consequential act in the bloodstream
passes through all six steps:

1. Plan    — PolicyEngine.propose()
2. Preview — PolicyEngine.preview() (what would happen, explicit-approval flag)
3. Permission — auto-approve at/below the ceiling; above it, the HITL
   ``confirm`` callback decides. No callback + above ceiling → the act does
   NOT execute; the outcome reports awaiting_permission.
4. Execute — the action callable runs (skipped on dry_run / awaiting).
5. Verify — the verify callable checks the world actually changed.
6. Receipt — PolicyEngine.mark_completed() → Receipt with verified flag.

Risk >= 2, factory execute/package stages, and any external send MUST come
through here. Risk 0–1 still walks all six steps; Permission is simply
automatic for them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from levi.policy.gates import (
    ActionProposal,
    ActionStatus,
    PolicyEngine,
    Receipt,
    RiskLevel,
)


@dataclass
class GateOutcome:
    proposal: ActionProposal
    preview: Dict[str, Any] = field(default_factory=dict)
    approved: bool = False
    auto_approved: bool = False
    awaiting_permission: bool = False
    executed: bool = False
    verified: bool = False
    receipt: Optional[Receipt] = None
    dry_run: bool = False
    error: Optional[str] = None

    @property
    def receipt_id(self) -> Optional[str]:
        return self.receipt.id if self.receipt else None


def run_gated(
    *,
    engine: PolicyEngine,
    description: str,
    risk_level: RiskLevel,
    reason: str,
    execute: Callable[[], str],
    verify: Optional[Callable[[], bool]] = None,
    confirm: Optional[Callable[[ActionProposal], bool]] = None,
    auto_approve_up_to: Optional[RiskLevel] = None,
    dry_run: bool = False,
    affected_systems: Optional[List[str]] = None,
    reversible: bool = True,
) -> GateOutcome:
    """Run one consequential act through the full six-step gate."""
    # 1. Plan
    proposal = engine.propose(
        description=description,
        risk_level=risk_level,
        reason=reason,
        affected_systems=affected_systems or [],
        reversible=reversible,
    )
    # 2. Preview
    preview = engine.preview(proposal.id) or {}
    outcome = GateOutcome(proposal=proposal, preview=preview, dry_run=dry_run)

    # 3. Permission — explicit ceiling wins; otherwise the engine's own.
    ceiling = (
        auto_approve_up_to
        if auto_approve_up_to is not None
        else engine.auto_approve_up_to
    )
    if risk_level <= ceiling:
        engine.approve(
            proposal.id, note="auto-approved by policy (risk within ceiling)"
        )
        outcome.approved = True
        outcome.auto_approved = True
    elif confirm is not None:
        try:
            granted = bool(confirm(proposal))
        except Exception:
            granted = False
        if granted:
            engine.approve(proposal.id, note="approved by human via HITL confirm")
            outcome.approved = True
        else:
            engine.deny(proposal.id, note="denied by human via HITL confirm")
            outcome.awaiting_permission = False
            return outcome
    else:
        # No HITL channel and above the auto-approve ceiling: NEVER execute.
        engine.request_permission(proposal.id)  # marks AWAITING_PERMISSION
        outcome.awaiting_permission = True
        return outcome

    # 4. Execute (never on dry_run)
    if dry_run:
        outcome.executed = False
    else:
        try:
            result_summary = execute()
        except Exception as exc:  # noqa: BLE001 — the turn must survive this
            proposal.status = ActionStatus.FAILED
            outcome.error = f"{exc.__class__.__name__}: {exc}"[:300]
            return outcome
        outcome.executed = True

    # 5. Verify
    if verify is not None:
        try:
            outcome.verified = bool(verify())
        except Exception:
            outcome.verified = False
    else:
        outcome.verified = outcome.executed or dry_run

    # 6. Receipt
    summary = (
        f"dry-run preview only (not executed): {description}"
        if dry_run
        else (
            result_summary
            if outcome.executed
            else f"approved but not executed: {description}"
        )
    )
    try:
        outcome.receipt = engine.mark_completed(
            proposal.id,
            result_summary=summary,
            verified=outcome.verified,
            details={"dry_run": dry_run, "auto_approved": outcome.auto_approved},
        )
    except KeyError:
        outcome.error = (outcome.error or "") + " [receipt failed: proposal lost]"
    return outcome
