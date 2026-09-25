"""Cybrus money gateway — the ONLY path for money movement in LEVI.

Binding law (Chauncey, 2026-09-17): **Cybrus is the only one ever allowed
to handle money.** No other founder, agent, or module moves money except
through this gateway.

Honest state: NO live money rails exist in the repo (audit in
``docs/MONEY_LAW.md`` found zero payment-SDK imports and zero live money
paths — everything money-adjacent is accounting, drafts, or paper
simulation). This gateway is the single choke point, and it fails CLOSED:
``execute()`` refuses unless a rail is explicitly registered AND an
explicit Chauncey authorization is on record. There is no code path that
auto-registers a rail or auto-authorizes a movement.

Six-gate flow for any money operation:
    plan -> preview -> permission -> execute -> verify -> receipt

PERMISSION (tightened 2026-09-22, RIGHT mandate): permission is not a bare
in-memory object. ``authorize()`` requires an ``approval_id`` naming a
human-approved, unconsumed entry in the approval ledger whose details bind
it to THIS plan; the approval receipt is written to the hash-chained audit
log. ``execute()`` then consumes the approval atomically — one approval
authorizes at most one execution. Replaying a consumed approval, or
executing an already-executed plan, is refused (double-spend protection).

A rail is a REFERENCE to an external payment plug-in, never the plug-in
itself (per ``neighbor/pay.py`` doctrine: references, never core). The
plug-in performs the actual provider call; Cybrus authorizes, gates, and
audits. No rail plug-ins exist yet — when one is added it must be
registered here, by Chauncey, deliberately.

stdlib-only. Audit log is metadata only (operation, rail, identity,
decision, amount, currency) — never secrets, never credentials.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class MoneyOperation(str, Enum):
    CHARGE = "charge"
    REFUND = "refund"
    PAYOUT = "payout"
    TRANSFER = "transfer"
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"


class MoneyRefused(ValueError):
    """Base refusal: a money operation was not permitted."""


class NoRailConfigured(MoneyRefused):
    """Fail-closed: no registered rail for this operation."""


class NotAuthorized(MoneyRefused):
    """Fail-closed: no explicit Chauncey authorization on record."""


class ApprovalReceiptMissing(MoneyRefused):
    """Fail-closed: the authorization names no approval receipt.

    Remedy: request a human approval with
    ``MoneyGateway.request_execution_approval(plan, subject=...)`` and
    retry with ``approval_id`` set on the authorization.
    """


class ApprovalReplayRefused(MoneyRefused):
    """Fail-closed: the approval was already consumed (replay refused).

    One approval authorizes at most one execution. Request a fresh
    approval for another movement.
    """


class DoubleSpendRefused(MoneyRefused):
    """Fail-closed: this plan already has an executed movement on record."""


class MoneyApprovalRequired(MoneyRefused):
    """A money movement is blocked pending human approval (L11).

    Carries the pending ``approval_id`` — a verified human approves it
    with ``levi cybrus approve <id>`` and the movement is retried with
    ``approval_id=<id>`` on the authorization.
    """

    def __init__(self, approval_id: str, message: str):
        super().__init__(message)
        self.approval_id = approval_id


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utcnow_dt() -> datetime:
    return datetime.now(timezone.utc)


def _data_dir() -> Path:
    base = os.environ.get("LEVI_CYBRUS_DIR")
    return Path(base) / "money" if base else Path.home() / ".levi" / "cybrus" / "money"


def _audit_path() -> Path:
    return _data_dir() / "money_audit.jsonl"


def _rails_path() -> Path:
    return _data_dir() / "rails.json"


def _write_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    os.chmod(path, 0o600)


def _audit(event: str, detail: Dict[str, Any]) -> None:
    rec = {"ts": _utcnow(), "event": event}
    rec.update(detail)
    _write_jsonl(_audit_path(), rec)


@dataclass
class MoneyRail:
    """A registered money rail — a REFERENCE to an external payment
    plug-in, never the plug-in itself. The plug-in performs provider
    calls; Cybrus authorizes, gates, and audits."""

    name: str
    provider: str
    kind: str = "external-plugin"  # rails are always external references
    registered_by: str = ""
    approved_by: str = ""
    registered_at: str = field(default_factory=_utcnow)
    status: str = "active"  # active | suspended


@dataclass
class MoneyPlan:
    plan_id: str
    operation: str
    amount_minor: int  # integer minor units (cents) — no float money
    currency: str
    rail: str
    purpose: str
    identity: str
    created_at: str


@dataclass
class MoneyAuthorization:
    """Explicit authorization. ``authorized_by`` MUST be Chauncey's
    keeper identity — anything else refuses.

    ``approval_id`` names the human-approved approval-ledger entry that
    backs this authorization (RIGHT mandate, 2026-09-22). The entry must
    be approved, unconsumed, and bound to the plan; ``authorize()``
    writes the approval receipt to the hash-chained audit log and
    ``execute()`` consumes the approval atomically. A bare authorization
    with no approval receipt is refused — it is replayable by
    construction.
    """

    authorized_by: str
    plan_id: str
    operation: str
    note: str = ""
    approval_id: str = ""
    ts: str = field(default_factory=_utcnow)


#: Approval-ledger action name for money movements.
MONEY_APPROVAL_ACTION = "money.execute"


def _plan_details(plan: "MoneyPlan") -> Dict[str, Any]:
    """The canonical approval-details binding for a money plan.

    RED-1 exact-match law (approval.py): ``consume_approved`` requires
    the consume side to present EXACTLY the fields the approval
    carries — no more, no fewer. Both the raise site
    (:meth:`MoneyGateway.request_execution_approval`) and the consume
    site (:meth:`MoneyGateway.execute`) build from here: one source of
    truth, so the ceremony cannot drift apart again.
    """
    return {
        "plan_id": plan.plan_id, "operation": plan.operation,
        "amount_minor": plan.amount_minor,
        "currency": plan.currency, "rail": plan.rail,
        "purpose": plan.purpose, "identity": plan.identity,
        "created_at": plan.created_at,
    }


def _load_rails() -> Dict[str, MoneyRail]:
    p = _rails_path()
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    out = {}
    for name, rec in raw.items():
        try:
            out[name] = MoneyRail(**rec)
        except TypeError:
            continue
    return out


def _save_rails(rails: Dict[str, MoneyRail]) -> None:
    p = _rails_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({k: asdict(v) for k, v in rails.items()}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.chmod(p, 0o600)


class MoneyGateway:
    """The single choke point for money movement in LEVI.

    Nothing outside ``core/levi/cybrus/`` may move money; any module that
    needs a movement calls through this gateway. With no rails
    registered and no Chauncey authorization, every execute() refuses —
    that is the honest, fail-closed default.
    """

    KEEPER_IDENTITIES = frozenset({"chauncey", "keeper", "chauncey-logan"})

    # -- rails ------------------------------------------------------

    def register_rail(
        self,
        name: str,
        provider: str,
        *,
        registered_by: str,
        approved_by: str,
    ) -> MoneyRail:
        """Register a rail reference. Deliberate, human-approved, Chauncey
        only. Raises NotAuthorized otherwise — rails are never auto-added."""
        if approved_by.strip().lower() not in self.KEEPER_IDENTITIES:
            _audit(
                "rail_register_refused",
                {"name": name, "provider": provider, "approved_by": approved_by},
            )
            raise NotAuthorized(
                "money rails are registered by Chauncey only "
                f"(approved_by={approved_by!r} refused)"
            )
        rails = _load_rails()
        rail = MoneyRail(
            name=name, provider=provider, registered_by=registered_by,
            approved_by=approved_by,
        )
        rails[name] = rail
        _save_rails(rails)
        _audit(
            "rail_registered",
            {"name": name, "provider": provider, "approved_by": approved_by},
        )
        return rail

    def list_rails(self) -> List[MoneyRail]:
        return [r for r in _load_rails().values() if r.status == "active"]

    def suspend_rail(self, name: str, *, by: str) -> None:
        if by.strip().lower() not in self.KEEPER_IDENTITIES:
            raise NotAuthorized("only Chauncey suspends rails")
        rails = _load_rails()
        if name in rails:
            rails[name].status = "suspended"
            _save_rails(rails)
            _audit("rail_suspended", {"name": name, "by": by})

    # -- six gates --------------------------------------------------

    def plan(
        self,
        operation: MoneyOperation | str,
        amount_minor: int,
        currency: str,
        rail: str,
        purpose: str,
        identity: str,
    ) -> MoneyPlan:
        """PLAN: compute what a movement WOULD look like. No authorization,
        no movement, no writes beyond the audit trail."""
        op = MoneyOperation(operation)
        if not isinstance(amount_minor, int) or amount_minor <= 0:
            raise MoneyRefused("amount must be a positive integer of minor units")
        plan = MoneyPlan(
            plan_id="mpl_" + uuid.uuid4().hex[:12],
            operation=op.value,
            amount_minor=amount_minor,
            currency=currency.upper(),
            rail=rail,
            purpose=purpose,
            identity=identity,
            created_at=_utcnow(),
        )
        _audit(
            "planned",
            {
                "plan_id": plan.plan_id, "operation": plan.operation,
                "amount_minor": plan.amount_minor, "currency": plan.currency,
                "rail": plan.rail, "identity": identity,
            },
        )
        return plan

    def preview(self, plan: MoneyPlan) -> str:
        """PREVIEW: human-readable statement of the planned movement."""
        major = plan.amount_minor / 100
        return (
            f"MONEY PLAN {plan.plan_id}\n"
            f"  operation : {plan.operation}\n"
            f"  amount    : {major:,.2f} {plan.currency}\n"
            f"  rail      : {plan.rail}\n"
            f"  purpose   : {plan.purpose}\n"
            f"  identity  : {plan.identity}\n"
            f"  This movement does NOT execute without a registered rail\n"
            f"  AND explicit Chauncey authorization. Preview is not permission."
        )

    def request_execution_approval(
        self, plan: MoneyPlan, *, subject: str, ttl_seconds: int = 86400
    ) -> Dict[str, Any]:
        """Request the human approval a movement needs (L11 forward-motion).

        Creates a pending approval-ledger entry bound to this plan and
        returns it. A verified human approves it
        (``levi cybrus approve <id>``); the caller then retries with
        ``MoneyAuthorization(..., approval_id=<id>)``.
        """
        from levi.cybrus.approval import ApprovalEngine

        entry = ApprovalEngine().request_approval(
            action=MONEY_APPROVAL_ACTION,
            subject=subject,
            resource=f"money:{plan.rail}",
            risk="critical",
            details=_plan_details(plan),
            ttl_seconds=ttl_seconds,
        )
        _audit(
            "approval_requested",
            {"actor": subject, "plan_id": plan.plan_id,
             "approval_id": entry["id"], "operation": plan.operation},
        )
        return dict(entry)

    def plan_from_approval(
        self, approval_id: str, *, expected_operation: str
    ) -> MoneyPlan:
        """Rebuild the EXACT plan an approval was minted for.

        The retry side of the approval dance must not mint a fresh plan:
        the approval is bound to the plan it was minted for, and a new
        plan would fail that binding. The approval entry's sealed
        details carry the full plan; this reconstructs it. Refuses
        unknown ids, non-money approvals, operation mismatches, and
        entries missing plan fields.
        """
        from levi.cybrus.approval import ApprovalEngine

        try:
            entry = ApprovalEngine().get_entry(approval_id)
        except (KeyError, ValueError):
            raise ApprovalReceiptMissing(
                f"no approval {approval_id[:8]!r} on record: request one "
                "with request_execution_approval() first"
            )
        details = entry.get("details") or {}
        if entry.get("action") != MONEY_APPROVAL_ACTION:
            raise NotAuthorized(
                f"approval {approval_id[:8]!r} is not a money approval"
            )
        if details.get("operation") != expected_operation:
            raise NotAuthorized(
                f"approval {approval_id[:8]!r} was minted for "
                f"{details.get('operation')!r}, not {expected_operation!r}: "
                "request a fresh approval"
            )
        missing = [
            k for k in ("plan_id", "amount_minor", "currency", "rail",
                        "purpose", "identity", "created_at")
            if k not in details
        ]
        if missing:
            raise NotAuthorized(
                f"approval {approval_id[:8]!r} is missing plan fields "
                f"({', '.join(missing)}): request a fresh approval"
            )
        return MoneyPlan(
            plan_id=details["plan_id"],
            operation=details["operation"],
            amount_minor=int(details["amount_minor"]),
            currency=details["currency"],
            rail=details["rail"],
            purpose=details["purpose"],
            identity=details["identity"],
            created_at=details["created_at"],
        )

    def _resolve_approval(self, approval_id: str, plan: MoneyPlan) -> Dict[str, Any]:
        """Resolve + validate the approval behind an authorization.

        Raises :class:`ApprovalReceiptMissing` when the id is unknown,
        :class:`NotAuthorized` when it is not a live approval for THIS
        plan (denied/expired/consumed/rebound). Returns the entry.
        """
        from levi.cybrus.approval import ApprovalEngine

        engine = ApprovalEngine()
        try:
            entry = engine.get_entry(approval_id)
        except (KeyError, ValueError):
            _audit(
                "authorize_refused",
                {"actor": plan.identity, "plan_id": plan.plan_id,
                 "approval_id": approval_id, "reason": "unknown approval"},
            )
            raise ApprovalReceiptMissing(
                f"no approval {approval_id[:8]!r} on record: request one "
                "with request_execution_approval() first"
            )
        details = entry.get("details") or {}
        problems = []
        if entry.get("status") != "approved":
            problems.append(f"status is {entry.get('status')!r}, not 'approved'")
        if entry.get("action") != MONEY_APPROVAL_ACTION:
            problems.append(f"action is {entry.get('action')!r}, not 'money.execute'")
        if details.get("plan_id") != plan.plan_id:
            # Rebinding an approval minted for another plan is refused.
            problems.append("approval was not minted for this plan")
        if details.get("consumed_at"):
            problems.append("approval already consumed")
        try:
            expires = datetime.fromisoformat(entry["expires_at"])
        except (KeyError, ValueError, TypeError):
            problems.append("approval expiry unreadable")
        else:
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= _utcnow_dt():
                problems.append("approval expired")
        if problems:
            _audit(
                "authorize_refused",
                {"actor": plan.identity, "plan_id": plan.plan_id,
                 "approval_id": approval_id,
                 "reason": "; ".join(problems)},
            )
            raise NotAuthorized(
                "approval receipt invalid: " + "; ".join(problems)
                + ". Request a fresh approval."
            )
        return dict(entry)

    def _write_approval_receipt(
        self, plan: MoneyPlan, authorization: MoneyAuthorization, approval_id: str
    ) -> Dict[str, Any]:
        """Write the approval receipt to the hash-chained audit log.

        The receipt — not the in-memory authorization object — is the
        record the money path requires. Metadata only (L4).
        """
        from levi.cybrus.audit import AuditEngine

        return AuditEngine().append(
            "money.approval_receipt",
            authorization.authorized_by,
            {
                "plan_id": plan.plan_id, "operation": plan.operation,
                "amount_minor": plan.amount_minor, "currency": plan.currency,
                "rail": plan.rail, "identity": plan.identity,
                "approval_id": approval_id,
            },
        )

    def authorize(
        self, plan: MoneyPlan, authorization: MoneyAuthorization
    ) -> MoneyAuthorization:
        """PERMISSION: explicit Chauncey authorization for one plan.

        Requires an ``approval_id`` naming a human-approved, unconsumed
        approval-ledger entry bound to this plan. Writes the approval
        receipt to the hash-chained audit log. A bare authorization with
        no receipt is refused (it is replayable by construction).
        """
        if authorization.plan_id != plan.plan_id:
            _audit(
                "authorize_refused",
                {"plan_id": plan.plan_id, "reason": "plan_id mismatch"},
            )
            raise NotAuthorized("authorization plan_id does not match plan")
        if authorization.authorized_by.strip().lower() not in self.KEEPER_IDENTITIES:
            _audit(
                "authorize_refused",
                {
                    "plan_id": plan.plan_id,
                    "authorized_by": authorization.authorized_by,
                    "reason": "not keeper",
                },
            )
            raise NotAuthorized(
                "money authorization is Chauncey's alone "
                f"(got {authorization.authorized_by!r})"
            )
        if not authorization.approval_id:
            _audit(
                "authorize_refused",
                {"plan_id": plan.plan_id, "reason": "no approval receipt"},
            )
            raise ApprovalReceiptMissing(
                "money authorization requires an approval receipt: "
                "request_execution_approval(plan, subject=...) then retry "
                "with approval_id set. Bare authorizations are refused."
            )
        entry = self._resolve_approval(authorization.approval_id, plan)
        receipt = self._write_approval_receipt(
            plan, authorization, entry["id"]
        )
        _audit(
            "authorized",
            {
                "plan_id": plan.plan_id, "operation": plan.operation,
                "authorized_by": authorization.authorized_by,
                "approval_id": entry["id"],
                "receipt_seq": receipt["seq"],
            },
        )
        return authorization

    def execute(
        self, plan: MoneyPlan, authorization: MoneyAuthorization
    ) -> Dict[str, Any]:
        """EXECUTE: perform the movement. Fail-closed: refuses unless the
        rail is registered AND the authorization is valid. With no rails
        in the registry (current state), this ALWAYS refuses.

        The approval behind the authorization is consumed atomically here
        (L5): one approval authorizes at most one execution. Replaying a
        consumed approval raises :class:`ApprovalReplayRefused`; a plan
        that already executed raises :class:`DoubleSpendRefused`.
        """
        self.authorize(plan, authorization)  # re-verify permission at execute time
        from levi.cybrus.approval import ApprovalEngine

        consumed = ApprovalEngine().consume_approved(
            MONEY_APPROVAL_ACTION, _plan_details(plan)
        )
        if consumed is None or consumed["id"] != authorization.approval_id:
            _audit(
                "execute_refused",
                {
                    "plan_id": plan.plan_id,
                    "approval_id": authorization.approval_id,
                    "reason": "approval replay: already consumed or rebound",
                },
            )
            raise ApprovalReplayRefused(
                "approval receipt already consumed: one approval moves "
                "money at most once (replay refused). Request a fresh "
                "approval for another movement."
            )
        if self._already_executed(plan.plan_id):
            _audit(
                "execute_refused",
                {
                    "plan_id": plan.plan_id,
                    "approval_id": authorization.approval_id,
                    "reason": "double spend: plan already executed",
                },
            )
            raise DoubleSpendRefused(
                f"plan {plan.plan_id} already has an executed movement on "
                "record: double spend refused."
            )
        _audit(
            "approval_consumed",
            {
                "plan_id": plan.plan_id,
                "approval_id": authorization.approval_id,
            },
        )
        rails = _load_rails()
        rail = rails.get(plan.rail)
        if rail is None or rail.status != "active":
            _audit(
                "execute_refused",
                {
                    "plan_id": plan.plan_id, "rail": plan.rail,
                    "approval_id": authorization.approval_id,
                    "reason": "no active rail",
                },
            )
            raise NoRailConfigured(
                f"no active money rail named {plan.rail!r} — "
                "movement refused. Register a rail (Chauncey, deliberately) first."
            )
        # A registered rail is a reference to an external plug-in; the
        # plug-in performs the provider call. No plug-ins exist yet, so a
        # registered rail alone is never enough to move money — this is
        # the honest boundary, not a TODO.
        _audit(
            "execute_refused",
            {
                "plan_id": plan.plan_id, "rail": plan.rail,
                "approval_id": authorization.approval_id,
                "reason": "no rail plug-in wired",
            },
        )
        raise NoRailConfigured(
            f"rail {plan.rail!r} is registered but no payment plug-in is wired — "
            "movement refused. Rails are references; the plug-in is separate."
        )

    def _already_executed(self, plan_id: str) -> bool:
        """True when the money audit log holds an executed movement for
        this plan (double-spend check)."""
        p = _audit_path()
        if not p.exists():
            return False
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except OSError:
            return False
        for line in lines:
            if f'"{plan_id}"' not in line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("event") == "executed" and rec.get("plan_id") == plan_id:
                return True
        return False

    def verify(self, plan_id: str) -> Dict[str, Any]:
        """VERIFY: confirm the audit record of a plan's full gate trail.

        Complete means: the plan was planned, an approval receipt for it
        sits in the hash-chained audit log, and the execution reached a
        terminal state (``execute_refused`` or ``executed``).
        """
        events = [
            json.loads(line)
            for line in _audit_path().read_text(encoding="utf-8").splitlines()
            if f'"{plan_id}"' in line
        ] if _audit_path().exists() else []
        kinds = [e.get("event") for e in events]
        receipt_ok = self._approval_receipt_in_chain(plan_id)
        terminal = "execute_refused" in kinds or "executed" in kinds
        return {
            "plan_id": plan_id,
            "events": kinds,
            "approval_receipt_in_chain": receipt_ok,
            "complete": receipt_ok and terminal,
        }

    def _approval_receipt_in_chain(self, plan_id: str) -> bool:
        """True when a money.approval_receipt for this plan sits in the
        hash-chained audit log (the receipt the money path requires)."""
        from levi.cybrus.audit import AuditEngine

        for rec in AuditEngine().tail(5000):
            details = rec.get("details") or {}
            if (rec.get("event") == "money.approval_receipt"
                    and details.get("plan_id") == plan_id):
                return True
        return False

    def receipt(self, plan_id: str) -> Dict[str, Any]:
        """RECEIPT: the final record — what was decided and why."""
        v = self.verify(plan_id)
        v["law"] = "Cybrus alone handles money."
        v["approval_id"] = self._approval_id_for_plan(plan_id)
        v["ts"] = _utcnow()
        return v

    def _approval_id_for_plan(self, plan_id: str) -> Optional[str]:
        from levi.cybrus.audit import AuditEngine

        for rec in AuditEngine().tail(5000):
            details = rec.get("details") or {}
            if (rec.get("event") == "money.approval_receipt"
                    and details.get("plan_id") == plan_id):
                return details.get("approval_id")
        return None

    # -- audit ------------------------------------------------------

    def audit_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        p = _audit_path()
        if not p.exists():
            return []
        lines = p.read_text(encoding="utf-8").splitlines()
        out = []
        for line in lines[-limit:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out


def status() -> Dict[str, Any]:
    """Gateway status: the law, rail count, fail-closed posture."""
    gw = MoneyGateway()
    return {
        "law": "Cybrus is the only one ever allowed to handle money.",
        "active_rails": len(gw.list_rails()),
        "execute_posture": "fail-closed: refuses without a registered rail + Chauncey authorization",
        "live_rails_exist": False,
    }
