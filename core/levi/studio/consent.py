"""Omega Studio consent kit — the human-in-the-loop consent gate.

The original Omega Studio gated *side-effect actions* on human consent:
the agent proposes, a Rego policy pre-screens, the human approves or
denies, and every step lands in the HMAC-signed audit trail.

Consent lifecycle
-----------------
``pending`` → ``granted`` | ``denied``. A pending request that passes its
``expires_at`` becomes ``expired`` — and ``expired`` counts as denied.

LAWS (fail-closed, always)
--------------------------
1. **Undecided is denied.** ``is_granted`` is true only for an explicit,
   unexpired ``granted`` record. Pending, denied, expired, and unknown
   ids are all denied.
2. **Policy pre-screen.** Every request is decided against the Rego
   policy first; a policy ``deny`` short-circuits to ``denied`` with the
   reason recorded — the human never sees what the policy already
   refused.
3. **Everything is audited.** Request, decision, approval, denial, and
   expiry are all appended to the HMAC-signed trail.
4. **No silent re-use.** A granted consent covers exactly one action
   described in the request; ``consume`` marks it used and a second
   ``consume`` is denied.

stdlib-only, local-first, no network.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .audit import AuditTrail
from .policy import DECISION_ALLOW, Policy

__all__ = [
    "ConsentError",
    "ConsentRequest",
    "ConsentGate",
    "DEFAULT_TTL_SECONDS",
]

DEFAULT_TTL_SECONDS = 15 * 60  # 15 minutes, like the original's session window


class ConsentError(Exception):
    """A consent operation was refused."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ConsentRequest:
    """One human-in-the-loop consent request."""

    id: str
    action: str
    actor: str
    resource: str
    context: Dict[str, Any]
    policy_decision: str
    status: str = "pending"  # pending | granted | denied | expired
    created_at: str = ""
    expires_at: str = ""
    decided_by: str = ""
    decided_at: str = ""
    reason: str = ""
    consumed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "actor": self.actor,
            "resource": self.resource,
            "context": self.context,
            "policy_decision": self.policy_decision,
            "status": self.status,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
            "reason": self.reason,
            "consumed": self.consumed,
        }


class ConsentGate:
    """The HITL consent gate: policy pre-screen, human decision, audit."""

    def __init__(
        self,
        policy: Policy,
        directory: "str | Path",
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self.policy = policy
        self.ttl = max(1, int(ttl_seconds))
        self.audit = AuditTrail.open(Path(directory) / "audit")
        self._requests: Dict[str, ConsentRequest] = {}

    # -- requests -------------------------------------------------------

    def request(
        self,
        action: str,
        actor: str,
        resource: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ConsentRequest:
        """Propose a side-effect action. Policy-deny short-circuits."""
        for name, value in (("action", action), ("actor", actor), ("resource", resource)):
            if not str(value).strip():
                raise ConsentError(f"consent {name} is required")
        ctx = dict(context or {})
        # The policy sees the full decision document.
        decision_input = {"action": action, "actor": actor, "resource": resource, **ctx}
        decision = self.policy.decide(decision_input)
        now = _utcnow()
        req = ConsentRequest(
            id="cr_" + secrets.token_hex(8),
            action=str(action),
            actor=str(actor),
            resource=str(resource),
            context=ctx,
            policy_decision=decision,
            created_at=now.isoformat(timespec="seconds"),
            expires_at=(now + timedelta(seconds=self.ttl)).isoformat(timespec="seconds"),
        )
        if decision != DECISION_ALLOW:
            req.status = "denied"
            req.reason = "policy denied before human review"
            req.decided_at = req.created_at
            self.audit.append(
                "consent.policy_denied",
                {"id": req.id, "action": action, "actor": actor, "resource": resource},
            )
        else:
            self.audit.append(
                "consent.requested",
                {"id": req.id, "action": action, "actor": actor, "resource": resource,
                 "expires_at": req.expires_at},
            )
        self._requests[req.id] = req
        return req

    def get(self, request_id: str) -> ConsentRequest:
        req = self._requests.get(request_id)
        if req is None:
            raise ConsentError(f"unknown consent request {request_id!r}")
        self._expire_if_due(req)
        return req

    def pending(self) -> List[ConsentRequest]:
        out = []
        for req in self._requests.values():
            self._expire_if_due(req)
            if req.status == "pending":
                out.append(req)
        return out

    # -- human decisions -------------------------------------------------

    def approve(self, request_id: str, approver: str) -> ConsentRequest:
        req = self.get(request_id)
        if req.status != "pending":
            raise ConsentError(f"cannot approve a {req.status} request")
        if not str(approver).strip():
            raise ConsentError("approver name is required: approvals are signed work")
        req.status = "granted"
        req.decided_by = str(approver)
        req.decided_at = _utcnow().isoformat(timespec="seconds")
        self.audit.append(
            "consent.granted", {"id": req.id, "by": req.decided_by,
                               "action": req.action, "resource": req.resource}
        )
        return req

    def deny(self, request_id: str, approver: str, reason: str) -> ConsentRequest:
        req = self.get(request_id)
        if req.status != "pending":
            raise ConsentError(f"cannot deny a {req.status} request")
        if not str(reason).strip():
            raise ConsentError("a denial reason is required: deniers sign their work")
        req.status = "denied"
        req.decided_by = str(approver)
        req.decided_at = _utcnow().isoformat(timespec="seconds")
        req.reason = str(reason)
        self.audit.append(
            "consent.denied", {"id": req.id, "by": req.decided_by,
                              "reason": req.reason, "action": req.action}
        )
        return req

    # -- checks -----------------------------------------------------------

    def _expire_if_due(self, req: ConsentRequest) -> None:
        if req.status != "pending":
            return
        try:
            exp = datetime.fromisoformat(req.expires_at)
        except ValueError:
            req.status = "expired"
            return
        if _utcnow() >= exp:
            req.status = "expired"
            req.decided_at = _utcnow().isoformat(timespec="seconds")
            self.audit.append("consent.expired", {"id": req.id, "action": req.action})

    def is_granted(self, request_id: str) -> bool:
        """True only for an explicit, unexpired, unconsumed grant."""
        try:
            req = self.get(request_id)
        except ConsentError:
            return False  # unknown id: denied
        return req.status == "granted" and not req.consumed

    def consume(self, request_id: str) -> bool:
        """Mark a granted consent as used. Second consume is denied."""
        req = self.get(request_id)
        if req.status != "granted" or req.consumed:
            return False
        req.consumed = True
        self.audit.append("consent.consumed", {"id": req.id, "action": req.action})
        return True

    def verify_audit(self):
        """Replay the HMAC-signed trail. Returns ``(ok, findings)``."""
        return self.audit.verify()
