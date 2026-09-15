"""Universal approval engine — Enterprise Phase 2 (blueprint §9).

Formalizes the L0–L4 control plane on top of
:class:`levi.policy.gates.PolicyEngine` — it does not fork it, it drives it.

Risk levels (shared vocabulary with :mod:`levi.policy.gates`)::

    L0 INFO      — pure information; auto-resolves, logged
    L1 LOW       — low-risk local actions; auto-resolves, logged
    L2 MODERATE  — moderate impact; pending approval
    L3 HIGH      — high impact; pending approval, real-time
    L4 CRITICAL  — financial / security / irreversible; pending approval

Decisions: ``approve-once`` (releases exactly one action), ``approve-for-
workflow`` (grants the same action key for the rest of a workflow/run),
``deny``. The pending queue persists at ``~/.levi/control/approvals.json``
(owner-only ``0o600``, atomic writes) so a CLI decision in one process
unblocks a worker waiting in another.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.policy.gates import PolicyEngine, RiskLevel, ActionStatus


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ApprovalError(Exception):
    """Base approval-engine error."""


class ApprovalBlocked(ApprovalError):
    """A guarded action did not come back approved.

    Carries the approval ``record`` so callers (fleet workers, the agent
    loop) can report the pending approval id instead of executing.
    """

    def __init__(self, record: Dict[str, Any], reason: str = ""):
        super().__init__(
            "action blocked: approval %s is %s%s"
            % (record.get("id"), record.get("status"), f" ({reason})" if reason else "")
        )
        self.record = record


class ApprovalNotFound(ApprovalError):
    """No approval with that id."""


# ---------------------------------------------------------------------------
# Record helpers
# ---------------------------------------------------------------------------


_RISK_NAMES = {
    RiskLevel.INFO: "info",
    RiskLevel.LOW: "low",
    RiskLevel.MODERATE: "moderate",
    RiskLevel.HIGH: "high",
    RiskLevel.CRITICAL: "critical",
}


def risk_name(level: RiskLevel) -> str:
    return _RISK_NAMES[level]


def approval_record(proposal) -> Dict[str, Any]:
    """Serialize a PolicyEngine ActionProposal to a plain record."""
    d = proposal.to_dict()
    d["risk_name"] = _RISK_NAMES.get(proposal.risk_level, "?")
    return d


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def _control_dir(home: Optional[Path] = None) -> Path:
    d = (home or Path.home()) / ".levi" / "control"
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


class ApprovalEngine:
    """L0–L4 approvals with a persisted pending queue.

    ``auto_approve_up_to`` mirrors the PolicyEngine default: L0/L1
    auto-resolve with logging; L2+ wait for a human. ``request`` never
    raises for policy reasons — it returns a record whose ``status``
    tells the caller what happened.
    """

    def __init__(
        self, home: Optional[Path] = None, auto_approve_up_to: RiskLevel = RiskLevel.LOW
    ) -> None:
        self._dir = _control_dir(home)
        self._path = self._dir / "approvals.json"
        self._policy = PolicyEngine(auto_approve_up_to=auto_approve_up_to)
        self._load()

    # -- persistence ----------------------------------------------------

    def _load(self) -> None:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        self._pending: Dict[str, Dict[str, Any]] = data.get("pending", {})
        self._history: List[Dict[str, Any]] = data.get("history", [])
        self._grants: Dict[str, Dict[str, Any]] = data.get("grants", {})

    def _save(self) -> None:
        data = {
            "pending": self._pending,
            "history": self._history[-500:],
            "grants": self._grants,
        }
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, self._path)

    # -- requests --------------------------------------------------------

    def request(
        self,
        description: str,
        risk_level: RiskLevel,
        *,
        reason: str = "",
        affected_systems: Optional[List[str]] = None,
        estimated_impact: str = "",
        reversible: bool = True,
        action_key: str = "",
        workflow_key: str = "",
        task_id: str = "",
        user_id: str = "local",
    ) -> Dict[str, Any]:
        """Request approval for an action. Returns the record.

        L0/L1 (or a matching workflow grant) → ``approved`` immediately.
        L2+ → ``awaiting_permission`` and persisted in the pending queue.
        """
        self._load()
        grant = self._find_grant(action_key, workflow_key)
        if grant is None:
            # No spam: return the existing pending record for the same
            # action+workflow instead of queueing a duplicate.
            reuse = self._find_pending(action_key, workflow_key)
            if reuse is not None:
                return reuse
            # One-time claim: an unconsumed approve-once decision for the
            # same action+workflow releases exactly one action on the
            # next request (e.g. a worker retrying after the human
            # decided in the CLI). Consumed exactly once.
            claimed = self._claim_approve_once(action_key, workflow_key)
            if claimed is not None:
                return claimed
        proposal = self._policy.propose(
            description=description,
            risk_level=risk_level,
            reason=reason,
            affected_systems=affected_systems,
            estimated_impact=estimated_impact,
            reversible=reversible,
        )
        record = approval_record(proposal)
        record.update(
            {
                "action_key": action_key,
                "workflow_key": workflow_key,
                "task_id": task_id,
                "user_id": user_id,
            }
        )
        if grant is not None or risk_level <= self._policy.auto_approve_up_to:
            decided = self._policy.approve(
                proposal.id,
                note=(
                    "auto-approved under workflow grant"
                    if grant is not None
                    else "auto-approved L%d by policy" % int(risk_level)
                ),
            )
            record = approval_record(decided)
            record.update(
                {
                    "action_key": action_key,
                    "workflow_key": workflow_key,
                    "task_id": task_id,
                    "user_id": user_id,
                    "grant": grant,
                }
            )
            self._history.append(record)
        else:
            record["status"] = ActionStatus.AWAITING_PERMISSION.value
            self._pending[record["id"]] = record
        self._save()
        return record

    def guard(
        self,
        description: str,
        risk_level: RiskLevel,
        *,
        timeout: Optional[float] = None,
        poll_interval: float = 0.2,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Request and, for L2+, optionally wait for a decision.

        ``timeout=None`` → return the pending record immediately (the
        caller escalates). ``timeout=0`` → same, non-blocking.
        ``timeout>0`` → poll the persisted queue until decided or the
        timeout elapses; on timeout the record keeps status
        ``awaiting_permission`` and gains ``timed_out: True``.
        """
        record = self.request(description, risk_level, **kwargs)
        if record["status"] != ActionStatus.AWAITING_PERMISSION.value:
            return record
        if not timeout:
            return record
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(poll_interval)
            current = self.get(record["id"])
            if current["status"] != ActionStatus.AWAITING_PERMISSION.value:
                return current
        record = self.get(record["id"])
        record["timed_out"] = True
        return record

    def require(
        self,
        description: str,
        risk_level: RiskLevel,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Like :meth:`guard` but raises :class:`ApprovalBlocked` unless
        the action came back approved. For workers: approved → proceed,
        anything else → do not execute."""
        record = self.guard(description, risk_level, **kwargs)
        if record["status"] != ActionStatus.APPROVED.value:
            raise ApprovalBlocked(
                record,
                "denied"
                if record["status"] == ActionStatus.DENIED.value
                else "still awaiting approval",
            )
        return record

    # -- decisions -------------------------------------------------------

    def get(self, approval_id: str) -> Dict[str, Any]:
        self._load()
        if approval_id in self._pending:
            return self._pending[approval_id]
        for record in self._history:
            if record["id"] == approval_id:
                return record
        raise ApprovalNotFound(f"no approval {approval_id!r}")

    def pending(self) -> List[Dict[str, Any]]:
        self._load()
        return sorted(self._pending.values(), key=lambda r: r.get("created_at", ""))

    def history(self, limit: int = 50) -> List[Dict[str, Any]]:
        self._load()
        return list(reversed(self._history[-limit:]))

    def approve_once(self, approval_id: str, note: str = "") -> Dict[str, Any]:
        """Approve exactly one action."""
        self._load()
        record = self._pending.pop(approval_id, None)
        if record is None:
            raise ApprovalNotFound(f"no pending approval {approval_id!r}")
        record["status"] = ActionStatus.APPROVED.value
        record["decision"] = "approve-once"
        record["decision_note"] = note or "approved once"
        record["decided_at"] = _now()
        self._history.append(record)
        self._save()
        return record

    def deny(self, approval_id: str, note: str = "") -> Dict[str, Any]:
        self._load()
        record = self._pending.pop(approval_id, None)
        if record is None:
            raise ApprovalNotFound(f"no pending approval {approval_id!r}")
        record["status"] = ActionStatus.DENIED.value
        record["decision"] = "deny"
        record["decision_note"] = note or "denied"
        record["decided_at"] = _now()
        self._history.append(record)
        self._save()
        return record

    def approve_for_workflow(
        self, approval_id: str, workflow_key: str = "", note: str = ""
    ) -> Dict[str, Any]:
        """Approve this action and grant the same ``action_key`` for the
        rest of ``workflow_key`` (e.g. a fleet run id)."""
        self._load()
        record = self._pending.pop(approval_id, None)
        if record is None:
            raise ApprovalNotFound(f"no pending approval {approval_id!r}")
        key = workflow_key or record.get("workflow_key", "")
        action_key = record.get("action_key", "")
        if action_key and key:
            self._grants[f"{key}:{action_key}"] = {
                "workflow_key": key,
                "action_key": action_key,
                "granted_at": _now(),
                "note": note or "approved for workflow",
            }
        record["status"] = ActionStatus.APPROVED.value
        record["decision"] = "approve-for-workflow"
        record["decision_note"] = note or "approved for workflow"
        record["decided_at"] = _now()
        self._history.append(record)
        self._save()
        return record

    def _find_grant(
        self, action_key: str, workflow_key: str
    ) -> Optional[Dict[str, Any]]:
        if not action_key or not workflow_key:
            return None
        return self._grants.get(f"{workflow_key}:{action_key}")

    def _find_pending(
        self, action_key: str, workflow_key: str
    ) -> Optional[Dict[str, Any]]:
        """Existing pending record for the same action+workflow, if any.

        Lets a worker that retries (or polls via ``guard``) reuse the
        one pending entry the human already sees instead of spamming
        the queue with duplicates.
        """
        if not action_key or not workflow_key:
            return None
        for record in self._pending.values():
            if (
                record.get("action_key") == action_key
                and record.get("workflow_key") == workflow_key
            ):
                return record
        return None

    def _claim_approve_once(
        self, action_key: str, workflow_key: str
    ) -> Optional[Dict[str, Any]]:
        """Consume an unconsumed approve-once decision, at most once.

        Returns the approved record on the first call for a matching
        decision; every later call finds it consumed and gets ``None``,
        so ``approve_once`` releases exactly one action.
        """
        if not action_key or not workflow_key:
            return None
        for record in reversed(self._history):
            if (
                record.get("decision") == "approve-once"
                and not record.get("consumed")
                and record.get("action_key") == action_key
                and record.get("workflow_key") == workflow_key
            ):
                record["consumed"] = True
                record["consumed_at"] = _now()
                self._save()
                claimed = dict(record)
                claimed["status"] = ActionStatus.APPROVED.value
                return claimed
        return None

    def revoke_grant(self, workflow_key: str, action_key: str) -> bool:
        self._load()
        removed = self._grants.pop(f"{workflow_key}:{action_key}", None)
        self._save()
        return removed is not None

    # -- introspection ---------------------------------------------------

    def status(self) -> Dict[str, Any]:
        self._load()
        by_risk: Dict[str, int] = {}
        for record in self._pending.values():
            by_risk[record.get("risk_name", "?")] = (
                by_risk.get(record.get("risk_name", "?"), 0) + 1
            )
        return {
            "pending": len(self._pending),
            "pending_by_risk": by_risk,
            "history": len(self._history),
            "grants": len(self._grants),
            "auto_approve_up_to": int(self._policy.auto_approve_up_to),
            "queue": str(self._path),
        }


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


@dataclass
class ApprovalRequest:
    """Convenience bundle for callers building a request."""

    description: str
    risk_level: RiskLevel
    reason: str = ""
    action_key: str = ""
    workflow_key: str = ""
    affected_systems: Optional[List[str]] = None
    estimated_impact: str = ""
