"""
Policy & Permission Gates
Risk levels 0–4. Plan → Preview → Permission → Execute → Verify → Receipt.
No consequential action bypasses this layer.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime, timezone
import uuid


class RiskLevel(int, Enum):
    INFO = 0  # Pure information
    LOW = 1  # Low risk local actions
    MODERATE = 2  # Moderate impact
    HIGH = 3  # High impact
    CRITICAL = 4  # Financial / security / irreversible


class ActionStatus(str, Enum):
    PROPOSED = "proposed"
    PREVIEWED = "previewed"
    AWAITING_PERMISSION = "awaiting_permission"
    APPROVED = "approved"
    DENIED = "denied"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class ActionProposal:
    id: str
    description: str
    risk_level: RiskLevel
    reason: str
    affected_systems: List[str] = field(default_factory=list)
    estimated_impact: str = ""
    permissions_required: List[str] = field(default_factory=list)
    reversible: bool = True
    status: ActionStatus = ActionStatus.PROPOSED
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    decided_at: Optional[str] = None
    decision_note: Optional[str] = None
    result_summary: Optional[str] = None
    receipt_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["risk_level"] = int(self.risk_level)
        d["status"] = self.status.value
        return d


@dataclass
class Receipt:
    id: str
    action_id: str
    outcome: str
    verified: bool
    timestamp: str
    details: Dict[str, Any] = field(default_factory=dict)


class PolicyEngine:
    """
    Enforces risk-based approval.
    Level 0–1 can auto-approve under default policy.
    Level 2+ require explicit approval (configurable later).
    """

    def __init__(self, auto_approve_up_to: RiskLevel = RiskLevel.LOW):
        self.auto_approve_up_to = auto_approve_up_to
        self._pending: Dict[str, ActionProposal] = {}
        self._history: List[ActionProposal] = []
        self._receipts: Dict[str, Receipt] = {}

    def propose(
        self,
        description: str,
        risk_level: RiskLevel,
        reason: str,
        affected_systems: Optional[List[str]] = None,
        estimated_impact: str = "",
        permissions_required: Optional[List[str]] = None,
        reversible: bool = True,
    ) -> ActionProposal:
        proposal = ActionProposal(
            id=str(uuid.uuid4()),
            description=description,
            risk_level=risk_level,
            reason=reason,
            affected_systems=affected_systems or [],
            estimated_impact=estimated_impact,
            permissions_required=permissions_required or [],
            reversible=reversible,
        )
        self._pending[proposal.id] = proposal
        return proposal

    def preview(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        p = self._pending.get(proposal_id)
        if not p:
            return None
        p.status = ActionStatus.PREVIEWED
        return {
            "action": p.description,
            "risk_level": int(p.risk_level),
            "reason": p.reason,
            "affected_systems": p.affected_systems,
            "estimated_impact": p.estimated_impact,
            "permissions_required": p.permissions_required,
            "reversible": p.reversible,
            "requires_explicit_approval": p.risk_level > self.auto_approve_up_to,
        }

    def request_permission(self, proposal_id: str) -> ActionProposal:
        p = self._pending[proposal_id]
        if p.risk_level <= self.auto_approve_up_to:
            return self.approve(proposal_id, note="auto-approved by policy")
        p.status = ActionStatus.AWAITING_PERMISSION
        return p

    def approve(self, proposal_id: str, note: str = "") -> ActionProposal:
        p = self._pending[proposal_id]
        p.status = ActionStatus.APPROVED
        p.decided_at = datetime.now(timezone.utc).isoformat()
        p.decision_note = note or "approved"
        return p

    def deny(self, proposal_id: str, note: str = "") -> ActionProposal:
        p = self._pending.pop(proposal_id)
        p.status = ActionStatus.DENIED
        p.decided_at = datetime.now(timezone.utc).isoformat()
        p.decision_note = note or "denied"
        self._history.append(p)
        return p

    def mark_completed(
        self,
        proposal_id: str,
        result_summary: str,
        verified: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ) -> Receipt:
        p = self._pending.pop(proposal_id, None)
        if p is None:
            # already moved?
            raise KeyError(f"Proposal {proposal_id} not found")
        p.status = ActionStatus.COMPLETED
        p.result_summary = result_summary
        receipt = Receipt(
            id=str(uuid.uuid4()),
            action_id=p.id,
            outcome=result_summary,
            verified=verified,
            timestamp=datetime.now(timezone.utc).isoformat(),
            details=details or {},
        )
        p.receipt_id = receipt.id
        self._history.append(p)
        self._receipts[receipt.id] = receipt
        return receipt

    def status(self) -> Dict[str, Any]:
        return {
            "auto_approve_up_to": int(self.auto_approve_up_to),
            "pending": len(self._pending),
            "history_count": len(self._history),
            "receipts": len(self._receipts),
            "invariant": "No consequential action bypasses policy layer",
        }
