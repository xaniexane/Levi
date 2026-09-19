"""The Forge rail — one driver for Plan→Preview→Permission→Execute→Verify→Receipt.

Built ON ``levi.policy.gates.PolicyEngine`` (the binding law's rail), not a
second copy of it. The engine owns the state machine; this module adds what
the Forge's machines need around it:

* deny-closed planning — unknown or forbidden tools are proposed and then
  *denied*, so the refusal itself is on the record;
* preview artifacts — diffs, command lines, target URLs travel with the
  proposal so Permission is granted over something concrete;
* a single ``execute()`` that refuses unapproved work, runs a verifier,
  and always ends in a Receipt (success or failure — both are receipted);
* JSONL receipt persistence with a bounded, documented shape.

This is an original, from-scratch implementation for LEVI.
Not artificial. Synthetic.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..policy.gates import ActionStatus, PolicyEngine, Receipt, RiskLevel

ORIGIN = "levi-forge/rail"

#: How much of a tool's output may be embedded in a persisted receipt.
#: The full output still goes to the caller; the log stays bounded.
RECEIPT_OUTPUT_LIMIT = 4096


class RailError(Exception):
    """Base error for rail violations."""


class DeniedError(RailError):
    """Raised when an action is deny-closed: unknown tool or forbidden pattern."""


class NeedsApprovalError(RailError):
    """Raised when an action needs explicit operator approval before execute()."""


class NotApprovedError(RailError):
    """Raised when execute() is called on a proposal that was never approved."""


def jsonl_sink(path: "str | Path") -> Callable[[Dict[str, Any]], None]:
    """Return a receipt sink appending one JSON object per line to *path*."""
    path = Path(path)

    def _sink(record: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")

    return _sink


def _bounded(value: Any, limit: int = RECEIPT_OUTPUT_LIMIT) -> Any:
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + f"\n…[truncated {len(value) - limit} chars]"
    return value


class Rail:
    """Drives consequential actions through the binding rail.

    Typical flow per action::

        pid = rail.plan(tool=..., description=..., risk=..., reason=..., artifacts={...})
        rail.preview(pid)          # what the operator sees before deciding
        rail.permit(pid)           # auto-approves INFO/LOW, else awaits operator
        rail.approve(pid, note)    # operator, only when permit() left it awaiting
        receipt = rail.execute(pid, fn, verify=verify_fn)

    Or the short path for low-risk work::

        receipt = rail.run_now(tool=..., description=..., risk=RiskLevel.LOW,
                               reason=..., fn=..., verify=...)
    """

    def __init__(
        self,
        *,
        policy: Optional[PolicyEngine] = None,
        receipt_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
        actor: str = "operator",
    ) -> None:
        self.policy = policy or PolicyEngine()
        self.receipt_sink = receipt_sink
        self.actor = actor
        self._artifacts: Dict[str, Dict[str, Any]] = {}

    # -- plan ------------------------------------------------------------
    def plan(
        self,
        *,
        tool: str,
        description: str,
        risk: RiskLevel,
        reason: str,
        affected: Optional[List[str]] = None,
        impact: str = "",
        permissions: Optional[List[str]] = None,
        reversible: bool = True,
        artifacts: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Propose an action. Returns the proposal id (status: proposed)."""
        proposal = self.policy.propose(
            description=f"[{tool}] {description}",
            risk_level=risk,
            reason=reason,
            affected_systems=affected or [tool],
            estimated_impact=impact,
            permissions_required=permissions or [],
            reversible=reversible,
        )
        if artifacts:
            self._artifacts[proposal.id] = dict(artifacts)
        return proposal.id

    def deny_closed(self, *, tool: str, reason: str) -> Dict[str, Any]:
        """Record a deny-closed refusal: propose at CRITICAL, then deny.

        The refusal lands in policy history, so "the machine said no" is
        itself auditable. Always raises :class:`DeniedError`.
        """
        pid = self.plan(
            tool=tool,
            description="deny-closed refusal",
            risk=RiskLevel.CRITICAL,
            reason=reason,
            reversible=True,
        )
        denied = self.policy.deny(pid, note=f"deny-closed: {reason}")
        record = denied.to_dict()
        record["denied_by"] = "rail"
        raise DeniedError(f"{tool}: denied — {reason}")

    # -- preview / permission ---------------------------------------------
    def preview(self, proposal_id: str) -> Dict[str, Any]:
        """What the operator decides over: policy preview + stored artifacts."""
        view = self.policy.preview(proposal_id)
        if view is None:
            raise RailError(f"preview: unknown proposal {proposal_id!r}")
        artifacts = self._artifacts.get(proposal_id, {})
        return {**view, "artifacts": {k: _bounded(v) for k, v in artifacts.items()}}

    def permit(self, proposal_id: str):
        """request_permission: auto-approves INFO/LOW, else awaits the operator."""
        return self.policy.request_permission(proposal_id)

    def approve(self, proposal_id: str, note: str = "") -> None:
        self.policy.approve(proposal_id, note=note or f"approved by {self.actor}")

    def deny(self, proposal_id: str, note: str = "") -> None:
        self.policy.deny(proposal_id, note=note or f"denied by {self.actor}")

    # -- execute / verify / receipt ----------------------------------------
    def execute(
        self,
        proposal_id: str,
        fn: Callable[[], "tuple[str, Dict[str, Any]]"],
        *,
        verify: Optional[Callable[[Dict[str, Any]], "tuple[bool, str]"]] = None,
    ) -> Receipt:
        """Run an approved action, verify it, and receipt the outcome.

        ``fn`` returns ``(summary, details)``. ``verify(details)`` returns
        ``(ok, note)``. Refuses unless the proposal is APPROVED. Failures —
        in ``fn`` or in ``verify`` — still produce a Receipt, marked
        ``verified=False``. Nothing that reaches here runs unapproved.
        """
        proposal = self.policy._get_pending(proposal_id, action="execute")
        if proposal.status == ActionStatus.AWAITING_PERMISSION:
            raise NeedsApprovalError(
                f"execute: proposal {proposal_id!r} is awaiting explicit "
                "operator approval — approve() it first"
            )
        if proposal.status != ActionStatus.APPROVED:
            raise NotApprovedError(
                f"execute: proposal {proposal_id!r} has status "
                f"{proposal.status.value!r}; only approved actions execute"
            )
        proposal.status = ActionStatus.EXECUTING
        try:
            summary, details = fn()
            ok, note = (True, "ok") if verify is None else verify(details)
            outcome = summary if ok else f"{summary} — VERIFY FAILED: {note}"
            receipt = self.policy.mark_completed(
                proposal_id,
                result_summary=outcome,
                verified=bool(ok),
                details={**details, "verify_note": note},
            )
        except Exception as exc:  # noqa: BLE001 — failure must still receipt
            receipt = self.policy.mark_completed(
                proposal_id,
                result_summary=f"FAILED: {exc}",
                verified=False,
                details={"error": f"{type(exc).__name__}: {exc}"},
            )
        self._persist_receipt(receipt)
        return receipt

    def run_now(
        self,
        *,
        tool: str,
        description: str,
        risk: RiskLevel,
        reason: str,
        fn: Callable[[], "tuple[str, Dict[str, Any]]"],
        verify: Optional[Callable[[Dict[str, Any]], "tuple[bool, str]"]] = None,
        affected: Optional[List[str]] = None,
        impact: str = "",
        reversible: bool = True,
        artifacts: Optional[Dict[str, Any]] = None,
    ) -> Receipt:
        """Full rail pass for low-risk work: plan→preview→permit→execute→receipt.

        Raises :class:`NeedsApprovalError` when the risk level needs an
        explicit operator decision — the proposal stays pending for them.
        """
        pid = self.plan(
            tool=tool,
            description=description,
            risk=risk,
            reason=reason,
            affected=affected,
            impact=impact,
            reversible=reversible,
            artifacts=artifacts,
        )
        decided = self.permit(pid)
        if decided.status == ActionStatus.AWAITING_PERMISSION:
            raise NeedsApprovalError(
                f"run_now: {tool} needs explicit operator approval (proposal {pid})"
            )
        return self.execute(pid, fn, verify=verify)

    # -- introspection ------------------------------------------------------
    def pending(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self.policy._pending.values()]

    def history(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self.policy._history]

    def status(self) -> Dict[str, Any]:
        return self.policy.status()

    # -- persistence ----------------------------------------------------------
    def _persist_receipt(self, receipt: Receipt) -> None:
        if self.receipt_sink is None:
            return
        record = asdict(receipt)
        record["actor"] = self.actor
        record["origin"] = ORIGIN
        record["details"] = {
            k: _bounded(v) for k, v in record.get("details", {}).items()
        }
        try:
            self.receipt_sink(record)
        except OSError:
            # Receipt persistence is best-effort: the in-memory receipt is
            # still returned to the caller. Never fail the action over logging.
            pass


def machine_root(home: "str | Path | None" = None, *parts: str) -> Path:
    """Resolve ``~/.levi/forge/machine[/<parts>]`` (or ``$LEVI_FORGE_HOME``).

    Created owner-only (0700). Mirrors :func:`levi.forge.home.forge_home`'s
    lazy resolution so tests can redirect it with ``LEVI_FORGE_HOME``.
    """
    from .home import forge_home

    root = forge_home(home) / "machine"
    if parts:
        root = root / Path(*parts)
    root.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(root, 0o700)
    except OSError:
        pass
    return root
