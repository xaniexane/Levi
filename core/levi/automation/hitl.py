"""LEVI-native HITL (human-in-the-loop) gate framework.

Every consequential automation step passes through a gate before it may
act. Gates are LEVI's own design — studied from the familiar
notification/dialog/approval patterns, rebuilt with LEVI's voice and the
standing law: Plan -> Preview -> Permission -> Execute -> Verify ->
Receipt. A gate never executes anything itself; it only records the
human's decision.

Gate kinds (mapped from the minion catalog's ``HITL Type`` column)::

    Notification            fire-and-forget notice; no decision needed
    Notification & Dialog   notice plus a dialog the human can answer
    Approval                explicit approve / deny required
    Edit & Approve          human may amend the payload, then approve
    Acknowledge             human confirms they saw it
    Confirm                 explicit yes/no confirmation

In dry-run and test contexts a gate resolves through an injected
*responder* callable instead of a real human, so runs stay side-effect
free and deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Optional


class GateKind(Enum):
    """The six LEVI-native gate kinds."""

    NOTIFICATION = "notification"
    DIALOG = "dialog"
    APPROVAL = "approval"
    EDIT_APPROVE = "edit_approve"
    ACKNOWLEDGE = "acknowledge"
    CONFIRM = "confirm"


# His catalog's HITL Type vocabulary -> GateKind. Unknown strings map to
# APPROVAL (fail closed: when in doubt, ask).
HITL_TYPE_MAP = {
    "Notification": GateKind.NOTIFICATION,
    "Notification & Dialog": GateKind.DIALOG,
    "Approval": GateKind.APPROVAL,
    "Edit & Approve": GateKind.EDIT_APPROVE,
    "Acknowledge": GateKind.ACKNOWLEDGE,
    "Confirm": GateKind.CONFIRM,
}


def gate_kind_for(hitl_type: str) -> GateKind:
    """Map a catalog HITL Type string to a GateKind (fail closed)."""
    return HITL_TYPE_MAP.get((hitl_type or "").strip(), GateKind.APPROVAL)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class GateRequest:
    """A permission request waiting on the human."""

    minion_id: str
    kind: GateKind
    prompt: str
    context: Dict[str, Any] = field(default_factory=dict)
    created_ts: str = ""

    def __post_init__(self) -> None:
        if not self.created_ts:
            self.created_ts = _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "minion_id": self.minion_id,
            "kind": self.kind.value,
            "prompt": self.prompt,
            "context": self.context,
            "created_ts": self.created_ts,
        }


@dataclass
class GateResult:
    """The human's (or responder's) decision on a gate."""

    request: GateRequest
    decision: str  # approved | denied | edited | acknowledged | noted
    edited_payload: Optional[Dict[str, Any]] = None
    note: str = ""
    resolved_ts: str = ""

    def __post_init__(self) -> None:
        if not self.resolved_ts:
            self.resolved_ts = _utcnow()

    @property
    def ok(self) -> bool:
        return self.decision in ("approved", "edited", "acknowledged", "noted")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "minion_id": self.request.minion_id,
            "kind": self.request.kind.value,
            "decision": self.decision,
            "edited_payload": self.edited_payload,
            "note": self.note,
            "resolved_ts": self.resolved_ts,
        }


# A responder answers a GateRequest without a real human present
# (dry-run, tests). Returns a dict like {"decision": "approved"} or
# {"decision": "edited", "edited_payload": {...}}.
Responder = Callable[[GateRequest], Dict[str, Any]]


def auto_approve(_request: GateRequest) -> Dict[str, Any]:
    """Dry-run responder: records that approval *would* be requested."""
    return {"decision": "approved", "note": "dry-run: approval simulated"}


def auto_deny(_request: GateRequest) -> Dict[str, Any]:
    """Test responder: the human says no."""
    return {"decision": "denied", "note": "test responder denied"}


class Gate:
    """One HITL checkpoint. Request, then resolve."""

    def __init__(self, request: GateRequest) -> None:
        self.request = request
        self.result: Optional[GateResult] = None

    def resolve(self, responder: Responder) -> GateResult:
        """Resolve the gate via a responder (human or simulated)."""
        answer = responder(self.request) or {}
        decision = str(answer.get("decision", "denied"))
        if self.request.kind is GateKind.NOTIFICATION:
            # A pure notification never blocks; it is only ever noted.
            decision = "noted"
        self.result = GateResult(
            request=self.request,
            decision=decision,
            edited_payload=answer.get("edited_payload"),
            note=str(answer.get("note", "")),
        )
        return self.result

    def require(self, responder: Responder) -> GateResult:
        """Resolve and raise if the human did not let it through."""
        result = self.resolve(responder)
        if not result.ok:
            raise GateDenied(result)
        return result


class GateDenied(Exception):
    """Raised when a required gate is denied."""

    def __init__(self, result: GateResult) -> None:
        self.result = result
        super().__init__(
            f"gate denied for minion {result.request.minion_id} "
            f"({result.request.kind.value}): {result.note or 'no reason given'}"
        )


def describe_gate(kind: GateKind) -> str:
    """One-line LEVI-voice description of what a gate asks of the human."""
    return {
        GateKind.NOTIFICATION: "LEVI tells you what happened. No reply needed.",
        GateKind.DIALOG: "LEVI tells you and listens — answer in the dialog.",
        GateKind.APPROVAL: "Nothing moves until you approve it.",
        GateKind.EDIT_APPROVE: "Amend it first if you like, then approve.",
        GateKind.ACKNOWLEDGE: "Tap acknowledge so LEVI knows you saw it.",
        GateKind.CONFIRM: "A straight yes or no from you.",
    }[kind]
