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

from levi.bloodstream.composites import effective_ceiling


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
    ceiling: Optional[RiskLevel] = None  # inherited ceiling (composite path)

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
    except (KeyError, ValueError):
        # PolicyEngine raises ValueError for unknown proposals (used to be a
        # raw KeyError); either way the receipt degrades, never crashes.
        outcome.error = (outcome.error or "") + " [receipt failed: proposal lost]"
    return outcome


def run_composite_gated(
    *,
    engine: PolicyEngine,
    name: str,
    components: List[Any],
    description: str,
    reason: str,
    execute: Callable[[], str],
    verify: Optional[Callable[[], bool]] = None,
    confirm: Optional[Callable[[ActionProposal], bool]] = None,
    authorization_level: Optional[Any] = None,
    auto_approve_up_to: Optional[RiskLevel] = None,
    dry_run: bool = False,
    affected_systems: Optional[List[str]] = None,
    reversible: bool = True,
) -> GateOutcome:
    """Run a composite (interpenetrated) action through the gate.

    The interpenetration composition law, as an engine:

    1. **Ceiling.** The effective risk ceiling of *components* is computed
       with :func:`levi.bloodstream.composites.effective_ceiling` —
       deny-closed, so unknown/unrated components raise the ceiling to the
       highest caution. The ceiling ordering comes solely from
       :mod:`levi.interop.risks`.
    2. **Authorization check.** When ``authorization_level`` is presented —
       the level the act claims to be authorized at — it must *meet* the
       inherited ceiling. Anything lower is DENIED outright: the outcome
       carries an explicit reason naming the ceiling and the component(s)
       that raised it, and nothing executes.
    3. **Six steps.** Otherwise the act runs through :func:`run_gated`
       with ``risk_level`` set to the inherited ceiling, so the full
       Plan → Preview → Permission → Execute → Verify → Receipt path still
       applies: the standing ceiling (``auto_approve_up_to`` or the
       engine's own) auto-approves only up to the inherited ceiling, and
       the human ``confirm`` channel decides above it — with the inherited
       ceiling named in the proposal the human sees.
    """
    from levi.interop import risks

    evidence = effective_ceiling(components)
    ceiling = risks.parse_level(evidence["ceiling"])
    raisers = sorted(
        cname
        for cname, clevel in evidence["contributions"].items()
        if risks.parse_level(clevel) == ceiling
    )
    audit_reason = "%s [composite %r: inherited risk ceiling %s, raised by %s]" % (
        reason,
        name,
        ceiling.name,
        ", ".join(raisers) if raisers else "<unknown>",
    )

    if authorization_level is not None:
        auth_level = risks.parse_level(authorization_level)
        if auth_level < ceiling:
            # Insufficient authorization: deny outright, with the ceiling
            # and its raisers named so the denial is auditable. Nothing
            # executes.
            proposal = engine.propose(
                description=description,
                risk_level=ceiling,
                reason=audit_reason,
                affected_systems=affected_systems or [],
                reversible=reversible,
            )
            preview = engine.preview(proposal.id) or {}
            denial = (
                "denied: composite %r inherits risk ceiling %s (raised by %s); "
                "presented authorization %s is below the ceiling — explicit "
                "approval at %s or above is required"
                % (
                    name,
                    ceiling.name,
                    ", ".join(raisers) if raisers else "<unknown>",
                    auth_level.name,
                    ceiling.name,
                )
            )
            engine.deny(proposal.id, note=denial)
            return GateOutcome(
                proposal=proposal,
                preview=preview,
                approved=False,
                awaiting_permission=False,
                executed=False,
                error=denial,
                ceiling=ceiling,
            )
        # The presented authorization meets the ceiling: it becomes the
        # standing ceiling for the six-step run, so Permission is automatic
        # (already proven sufficient) and confirm is only a backstop.
        outcome = run_gated(
            engine=engine,
            description=description,
            risk_level=ceiling,
            reason="%s; authorization presented at %s"
            % (audit_reason, auth_level.name),
            execute=execute,
            verify=verify,
            confirm=confirm,
            auto_approve_up_to=auth_level,
            dry_run=dry_run,
            affected_systems=affected_systems,
            reversible=reversible,
        )
        outcome.ceiling = ceiling
        return outcome

    # No explicit authorization: the standing ceiling (or the human channel)
    # decides, with the act priced at the inherited ceiling's risk level.
    outcome = run_gated(
        engine=engine,
        description=description,
        risk_level=ceiling,
        reason=audit_reason,
        execute=execute,
        verify=verify,
        confirm=confirm,
        auto_approve_up_to=auto_approve_up_to,
        dry_run=dry_run,
        affected_systems=affected_systems,
        reversible=reversible,
    )
    outcome.ceiling = ceiling
    return outcome
