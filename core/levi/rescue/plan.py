"""Act three — the rescue plan (preview-first, operator-approved).

Each audit finding becomes a rescue item: the action, a human-readable
preview of what will change, a risk level, reversibility, and the
affected surface. Every item rides the forge rail as a proposal
(Plan → Preview → Permission), and the business owner approves the
whole plan before any remodel step may run.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import ensure_home, episode_rail, rescue_home
from . import ledger as stone
from . import analytics
from .audit import AuditReport
from .intake import get_invitation

try:
    from ..forge.rail import Rail
    from ..policy.gates import RiskLevel
except Exception:  # pragma: no cover — import-guarded for hermetic use
    Rail = None  # type: ignore
    RiskLevel = None  # type: ignore


class PlanNotApprovedError(RuntimeError):
    """Raised when remodel is attempted on a plan the owner never approved."""


SEVERITY_RISK = {
    "low": "LOW",
    "medium": "MODERATE",
    "high": "HIGH",
    "critical": "HIGH",
}

STATUS_DRAFT = "draft"
STATUS_APPROVED = "approved"
STATUS_DENIED = "denied"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _risk(severity: str):
    name = SEVERITY_RISK.get(severity, "MODERATE")
    return getattr(RiskLevel, name) if RiskLevel is not None else name


@dataclass
class RescueItem:
    """One promised fix, preview-first.

    ``target`` is the numeric healthy-state for the item's metric
    (from the analytics baseline): what healthy looks like, in numbers.
    """

    id: str
    check_id: str
    finding_title: str
    severity: str
    action: str
    preview: str
    risk: str
    reversible: bool
    affected: List[str]
    proposal_id: str = ""
    target: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RescueItem":
        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in data.items() if k in known}
        clean.setdefault("affected", [])
        return cls(**clean)


@dataclass
class RescuePlan:
    id: str
    audit_id: str
    invitation_id: str
    business: str
    status: str = STATUS_DRAFT
    items: List[RescueItem] = field(default_factory=list)
    owner: str = ""
    decided_at: str = ""
    decision_note: str = ""
    created_at: str = ""
    # Cost-cutting pillar: draft targets from the owner's stated spend.
    # Proposed by the module, approved by the owner with the plan.
    cost_targets: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["items"] = [i.to_dict() for i in self.items]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RescuePlan":
        data = dict(data)
        data["items"] = [RescueItem.from_dict(i) for i in data.get("items", [])]
        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in data.items() if k in known}
        clean.setdefault("items", [])
        return cls(**clean)


def _rail(home) -> "Rail":
    return episode_rail(home)


def _next_id(home) -> str:
    state_path = rescue_home(home) / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        state = {}
    n = int(state.get("plan_counter", 0)) + 1
    state["plan_counter"] = n
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return "plan-%04d" % n


def _action_for(finding) -> str:
    return {
        "reachable": "restore the page so it answers HTTP 200",
        "has-title": "give the page a real title",
        "has-heading": "add a clear top-level heading",
        "contact-visible": "put a phone number or email where visitors can find it",
        "links-resolve": "repair or remove the dead link markers",
        "forms-described": "give the form named, labeled fields",
    }.get(finding.check_id, "remediate: %s" % finding.title)


def build_plan(home, audit: AuditReport, rail: Optional["Rail"] = None) -> RescuePlan:
    """Turn audit findings into a draft rescue plan; each item gets a rail proposal.

    Rescue items carry numeric targets from the analytics baseline.
    The cost-cutting pillar rides along: draft cost targets from the
    owner's stated spend are attached for the owner to approve, revise,
    or reject with the plan.
    """
    rail = rail or _rail(home)
    items: List[RescueItem] = []
    for n, f in enumerate(audit.findings, 1):
        risk = _risk(f.severity)
        target = analytics.target_for(f.check_id, audit.baseline)
        preview = "BEFORE: %s\nAFTER: %s" % (f.title, _action_for(f))
        if target:
            op = "≥" if target["direction"] == "at_least" else "≤"
            before = target.get("before")
            preview += "\nTARGET: %s %s %s%s" % (
                target["metric"],
                op,
                target["target"],
                " (now %s)" % before if before is not None else "",
            )
        item = RescueItem(
            id="item-%02d" % n,
            check_id=f.check_id,
            finding_title=f.title,
            severity=f.severity,
            action=_action_for(f),
            preview=preview,
            risk=risk.name if hasattr(risk, "name") else str(risk),
            reversible=f.severity in ("low", "medium"),
            affected=[e.ref for e in f.evidence],
            target=target,
        )
        item.proposal_id = rail.plan(
            tool="rescue-remodel",
            description="rescue item %s: %s" % (item.id, item.action),
            risk=risk,
            reason="owner-requested rescue for %s (finding: %s)"
            % (audit.business, f.title),
            affected=item.affected,
            impact=item.preview,
            reversible=item.reversible,
            artifacts={"item": item.to_dict()},
        )
        items.append(item)
    plan = RescuePlan(
        id=_next_id(home),
        audit_id=audit.id,
        invitation_id=audit.invitation_id,
        business=audit.business,
        items=items,
        created_at=_now(),
        cost_targets=analytics.propose_cost_targets(
            get_invitation(home, audit.invitation_id).costs
        ),
    )
    path = ensure_home(home) / "plans" / ("%s.json" % plan.id)
    path.write_text(
        json.dumps(plan.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    stone.record(
        home,
        "plan.drafted",
        audit.invitation_id,
        {
            "plan_id": plan.id,
            "items": len(items),
            "cost_targets": len(plan.cost_targets),
            "cost_actions": sorted({t["action"] for t in plan.cost_targets}),
        },
    )
    return plan


def get_plan(home, plan_id: str) -> RescuePlan:
    path = ensure_home(home) / "plans" / ("%s.json" % plan_id)
    return RescuePlan.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _save(home, plan: RescuePlan) -> None:
    path = ensure_home(home) / "plans" / ("%s.json" % plan.id)
    path.write_text(
        json.dumps(plan.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )


def preview_plan(
    home, plan_id: str, rail: Optional["Rail"] = None
) -> List[Dict[str, Any]]:
    """The owner-facing view: every item's rail preview."""
    rail = rail or _rail(home)
    plan = get_plan(home, plan_id)
    return [rail.preview(item.proposal_id) for item in plan.items]


def approve_plan(
    home, plan_id: str, owner: str, note: str = "", rail: Optional["Rail"] = None
) -> RescuePlan:
    """The owner approves: every rail proposal approved with the owner's note."""
    rail = rail or _rail(home)
    plan = get_plan(home, plan_id)
    if plan.status != STATUS_DRAFT:
        raise ValueError(
            "approve_plan: plan %r is %s, not draft" % (plan.id, plan.status)
        )
    for item in plan.items:
        rail.approve(item.proposal_id, note=note or "approved by %s (owner)" % owner)
    plan.status = STATUS_APPROVED
    plan.owner = owner
    plan.decided_at = _now()
    plan.decision_note = note
    _save(home, plan)
    stone.record(
        home,
        "plan.approved",
        plan.invitation_id,
        {
            "plan_id": plan.id,
            "owner": owner,
            "items": len(plan.items),
        },
    )
    return plan


def deny_plan(
    home, plan_id: str, owner: str, note: str = "", rail: Optional["Rail"] = None
) -> RescuePlan:
    """The owner denies: every rail proposal denied; the plan is dead."""
    rail = rail or _rail(home)
    plan = get_plan(home, plan_id)
    if plan.status != STATUS_DRAFT:
        raise ValueError("deny_plan: plan %r is %s, not draft" % (plan.id, plan.status))
    for item in plan.items:
        rail.deny(item.proposal_id, note=note or "denied by %s (owner)" % owner)
    plan.status = STATUS_DENIED
    plan.owner = owner
    plan.decided_at = _now()
    plan.decision_note = note
    _save(home, plan)
    stone.record(
        home,
        "plan.denied",
        plan.invitation_id,
        {
            "plan_id": plan.id,
            "owner": owner,
        },
    )
    return plan


def require_approved(home, plan_id: str) -> RescuePlan:
    """The remodel gate: only an owner-approved plan may remodel."""
    plan = get_plan(home, plan_id)
    if plan.status != STATUS_APPROVED:
        raise PlanNotApprovedError(
            "remodel refused: plan %r is %s — the owner must approve the "
            "rescue plan before anything is rebuilt" % (plan.id, plan.status)
        )
    return plan


__all__ = [
    "PlanNotApprovedError",
    "RescueItem",
    "RescuePlan",
    "STATUS_APPROVED",
    "STATUS_DENIED",
    "STATUS_DRAFT",
    "approve_plan",
    "build_plan",
    "deny_plan",
    "get_plan",
    "preview_plan",
    "require_approved",
]
