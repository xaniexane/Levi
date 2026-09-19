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
import stat
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


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    keeper identity — anything else refuses."""

    authorized_by: str
    plan_id: str
    operation: str
    note: str = ""
    ts: str = field(default_factory=_utcnow)


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

    def authorize(
        self, plan: MoneyPlan, authorization: MoneyAuthorization
    ) -> MoneyAuthorization:
        """PERMISSION: explicit Chauncey authorization for one plan."""
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
        _audit(
            "authorized",
            {
                "plan_id": plan.plan_id, "operation": plan.operation,
                "authorized_by": authorization.authorized_by,
            },
        )
        return authorization

    def execute(
        self, plan: MoneyPlan, authorization: MoneyAuthorization
    ) -> Dict[str, Any]:
        """EXECUTE: perform the movement. Fail-closed: refuses unless the
        rail is registered AND the authorization is valid. With no rails
        in the registry (current state), this ALWAYS refuses."""
        self.authorize(plan, authorization)  # re-verify permission at execute time
        rails = _load_rails()
        rail = rails.get(plan.rail)
        if rail is None or rail.status != "active":
            _audit(
                "execute_refused",
                {
                    "plan_id": plan.plan_id, "rail": plan.rail,
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
                "reason": "no rail plug-in wired",
            },
        )
        raise NoRailConfigured(
            f"rail {plan.rail!r} is registered but no payment plug-in is wired — "
            "movement refused. Rails are references; the plug-in is separate."
        )

    def verify(self, plan_id: str) -> Dict[str, Any]:
        """VERIFY: confirm the audit record of a plan's full gate trail."""
        events = [
            json.loads(line)
            for line in _audit_path().read_text(encoding="utf-8").splitlines()
            if f'"{plan_id}"' in line
        ] if _audit_path().exists() else []
        kinds = [e.get("event") for e in events]
        return {"plan_id": plan_id, "events": kinds, "complete": "execute_refused" in kinds or "executed" in kinds}

    def receipt(self, plan_id: str) -> Dict[str, Any]:
        """RECEIPT: the final record — what was decided and why."""
        v = self.verify(plan_id)
        v["law"] = "Cybrus alone handles money."
        v["ts"] = _utcnow()
        return v

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
