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


def _as_risk_level(value: Any, *, field: str = "risk_level") -> RiskLevel:
    """Coerce ints to RiskLevel; reject anything else with an actionable error."""
    if isinstance(value, RiskLevel):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        try:
            return RiskLevel(value)
        except ValueError:
            pass
    raise ValueError(
        f"{field} must be a levi.policy.gates.RiskLevel (or int 0-4), got {value!r}"
    )


def _non_empty_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string, got {value!r}")
    return value


def _str_list(value: Any, *, field: str) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise ValueError(f"{field} must be a list of strings, got {value!r}")
    return list(value)


class PolicyEngine:
    """
    Enforces risk-based approval.
    Level 0–1 can auto-approve under default policy.
    Level 2+ require explicit approval (configurable later).
    """

    def __init__(self, auto_approve_up_to: RiskLevel = RiskLevel.LOW):
        self.auto_approve_up_to = _as_risk_level(
            auto_approve_up_to, field="auto_approve_up_to"
        )
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
        description = _non_empty_str(description, field="description")
        reason = _non_empty_str(reason, field="reason")
        risk_level = _as_risk_level(risk_level)
        affected = _str_list(affected_systems, field="affected_systems")
        permissions = _str_list(permissions_required, field="permissions_required")
        if not isinstance(estimated_impact, str):
            raise ValueError(
                f"estimated_impact must be a string, got {estimated_impact!r}"
            )
        if not isinstance(reversible, bool):
            raise ValueError(f"reversible must be a bool, got {reversible!r}")
        proposal = ActionProposal(
            id=str(uuid.uuid4()),
            description=description,
            risk_level=risk_level,
            reason=reason,
            affected_systems=affected,
            estimated_impact=estimated_impact,
            permissions_required=permissions,
            reversible=reversible,
        )
        self._pending[proposal.id] = proposal
        return proposal

    def _get_pending(self, proposal_id: str, *, action: str) -> ActionProposal:
        """Fetch a pending proposal, or raise an actionable ValueError.

        Unknown ids used to leak a raw KeyError; they now say exactly
        what went wrong and which ids are still pending.
        """
        if not isinstance(proposal_id, str) or not proposal_id:
            raise ValueError(f"{action}: proposal id must be a non-empty string")
        try:
            return self._pending[proposal_id]
        except KeyError:
            known = sorted(self._pending)[:5]
            hint = f" (pending: {known})" if known else " (nothing pending)"
            raise ValueError(
                f"{action}: unknown proposal {proposal_id!r}{hint} — "
                "proposals leave the pending set once denied or completed; "
                "approved proposals stay listed until mark_completed()"
            ) from None

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
        p = self._get_pending(proposal_id, action="request_permission")
        if p.risk_level <= self.auto_approve_up_to:
            return self.approve(proposal_id, note="auto-approved by policy")
        p.status = ActionStatus.AWAITING_PERMISSION
        return p

    def approve(self, proposal_id: str, note: str = "") -> ActionProposal:
        p = self._get_pending(proposal_id, action="approve")
        p.status = ActionStatus.APPROVED
        p.decided_at = datetime.now(timezone.utc).isoformat()
        p.decision_note = note or "approved"
        return p

    def deny(self, proposal_id: str, note: str = "") -> ActionProposal:
        p = self._get_pending(proposal_id, action="deny")
        del self._pending[proposal_id]
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
        if not isinstance(result_summary, str) or not result_summary.strip():
            raise ValueError(
                "mark_completed: result_summary must be a non-empty string"
            )
        if details is not None and not isinstance(details, dict):
            raise ValueError("mark_completed: details must be a dict or None")
        p = self._pending.pop(proposal_id, None)
        if p is None:
            # Already moved out of pending (or never existed): say so plainly.
            raise ValueError(
                f"mark_completed: unknown proposal {proposal_id!r} — "
                "proposals leave the pending set once approved/denied/completed"
            )
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
