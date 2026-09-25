"""Void Box enforcement layer — Cybrus thrown on top of the Void Box product.

CANON (Chauncey): Void Box = the product, created FIRST. Cybrus = thrown
on top for extra security. This module IS that enforcement layer: every
consequential Void Box action passes through Cybrus grants / policy /
audit before the product primitive runs. SI side — every public entry
point calls ``levi.plaiground.gate.require_adult()`` FIRST. Money moves
ONLY through ``levi.cybrus.money.MoneyGateway`` — fail-closed; this
module holds no rail references, no keys, no payment data.

LAWS (machine-readable in :data:`LAWS`):
- E1  SI gate first: every public entry point calls ``require_adult()``
      before any other work. ``GateLockedError`` means the action never
      starts.
- E2  Consequential actions (room create, member add/remove/leave,
      device revoke, listing publish, money charge) run ONLY under a
      consumed Cybrus approval. No approval, no action.
- E3  RED-1 exact match: the raise site and the consume site build
      approval details from ONE canonical builder
      (:func:`_approval_details`). ``consume_approved`` refuses anything
      that is not exactly what the approval carries — no more, no fewer
      fields. A tampered or rebound approval is refused, never silently
      honored.
- E4  Policy gate: ``PolicyEngine.evaluate(subject, resource, action)``
      must ALLOW; a deny (including default-deny) refuses the action.
      Approval never overrides a policy deny — the policy check runs
      BEFORE consumption, so a denied action never consumes the grant.
- E5  Money moves ONLY through ``MoneyGateway``'s six-gate flow
      (plan -> preview -> permission -> execute -> verify -> receipt).
      The platform NEVER holds money logic itself: no rails, no keys,
      no amounts outside the gateway's plan objects.
- E6  Every action — allowed or refused — writes ONE tamper-evident
      audit record via ``AuditEngine.append``. Records are metadata
      only: never keys, never plaintext, never payment data.
- E7  Fail-closed: any enforcement error (gate locked, no approval,
      policy deny, consume mismatch, audit failure) refuses the action
      BEFORE the underlying product operation is invoked. Nothing
      half-applies — the rooms/money call is the last step, reached
      only after every gate passed.
- E8  Approvals are single-use: ``consume_approved`` marks them consumed
      atomically. Replays are refused.
- E9  Read-only actions (open_message, get_room, relay poll) are NOT
      approval-gated — they are read-only — but they are still
      gate-checked by ``require_adult()``.
- E10 Errors are typed (``GateLockedError``, ``ApprovalNeeded``,
      ``PolicyRefused``, ``MoneyApprovalRequired``,
      ``EnforcementError``) — an enforcement failure never degrades
      into a bare pass.

The raise -> approve -> consume ceremony (the pattern fixed by the
Cybrus formation worker, commit 65918d06):
    request:  ApprovalEngine().request_approval(action, actor, resource,
              "high", details=_approval_details(...))
    approve:  human runs ``levi cybrus approve <id>``
    consume:  ApprovalEngine().consume_approved(action,
              _approval_details(...))   # EXACTLY the same details

Both the raise and the consume build from :func:`_approval_details` —
one source of truth, so the ceremony cannot drift apart again.

stdlib-only. ``enforce.py`` is the Void Box organ's enforcement layer;
``levi.cybrus.enforce`` is a different module (Cybrus's own internal
gate) — same family, different organ.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# LAWS — machine-readable canon
# ---------------------------------------------------------------------------

LAWS: Tuple[Tuple[str, str], ...] = (
    ("E1", "SI gate first: every public entry point calls require_adult() "
           "before any other work; GateLockedError means the action never starts."),
    ("E2", "Consequential actions (room create, member add/remove/leave, "
           "device revoke, listing publish, money charge) run only under a "
           "consumed Cybrus approval — no approval, no action."),
    ("E3", "RED-1 exact match: raise and consume sites build approval "
           "details from one canonical builder; consume_approved refuses "
           "any detail mismatch or tamper."),
    ("E4", "Policy gate: PolicyEngine.evaluate(subject, resource, action) "
           "must allow; deny (incl. default-deny) refuses. Approval never "
           "overrides a policy deny; policy is checked before consumption."),
    ("E5", "Money moves only through MoneyGateway's six-gate flow; the "
           "platform holds no rail references, keys, or payment data."),
    ("E6", "Every action — allowed or refused — writes one tamper-evident "
           "audit record via AuditEngine; records are metadata only."),
    ("E7", "Fail-closed: any enforcement error refuses the action BEFORE "
           "the underlying product operation is invoked; nothing half-applies."),
    ("E8", "Approvals are single-use: consumed atomically by "
           "consume_approved; replays refused."),
    ("E9", "Read-only actions (open_message, get_room, relay poll) are "
           "unenforced but still gate-checked by require_adult()."),
    ("E10", "Enforcement errors are typed — a failure never degrades "
            "into a bare pass."),
)


# ---------------------------------------------------------------------------
# Typed enforcement errors (E10)
# ---------------------------------------------------------------------------


class EnforcementError(ValueError):
    """Base refusal: an enforced Void Box action was not permitted."""


class ApprovalNeeded(EnforcementError):
    """A consequential action is blocked pending human approval.

    Carries the pending ``approval_id`` — a human approves it with
    ``levi cybrus approve <id>`` and the caller retries the SAME guarded
    call (same actor, same fields), which then consumes the approval.
    """

    def __init__(self, approval_id: str, action: str, message: str):
        super().__init__(message)
        self.approval_id = approval_id
        self.action = action


class PolicyRefused(EnforcementError):
    """Fail-closed: the Cybrus policy engine denied the action."""


# ---------------------------------------------------------------------------
# Approval action names — the contract between raise and consume sites
# ---------------------------------------------------------------------------

ACTION_ROOM_CREATE = "voidbox.room.create"
ACTION_MEMBER_ADD = "voidbox.room.member_add"
ACTION_MEMBER_REMOVE = "voidbox.room.member_remove"
ACTION_MEMBER_LEAVE = "voidbox.room.member_leave"
ACTION_DEVICE_REVOKE = "voidbox.room.device_revoke"
ACTION_LISTING_PUBLISH = "voidbox.listing.publish"

#: (approval_action, policy_resource, policy_action) per guarded op.
_ACTION_TABLE: Dict[str, Tuple[str, str, str]] = {
    "room.create": (ACTION_ROOM_CREATE, "voidbox.room", "create"),
    "room.member_add": (ACTION_MEMBER_ADD, "voidbox.room", "member_add"),
    "room.member_remove": (ACTION_MEMBER_REMOVE, "voidbox.room", "member_remove"),
    "room.member_leave": (ACTION_MEMBER_LEAVE, "voidbox.room", "member_leave"),
    "room.device_revoke": (ACTION_DEVICE_REVOKE, "voidbox.room", "device_revoke"),
    "listing.publish": (ACTION_LISTING_PUBLISH, "voidbox.listing", "publish"),
}

#: Money operations supported by charge_guarded (MoneyGateway ops).
MONEY_OPERATIONS = ("charge", "refund", "payout", "transfer", "deposit", "withdraw")

_APPROVAL_RISK = "high"  # consequential Void Box actions gate at high


# ---------------------------------------------------------------------------
# Canonical approval-details builder (E3, RED-1 single source of truth)
# ---------------------------------------------------------------------------


def _approval_details(action_name: str, actor: str, **fields: Any) -> Dict[str, Any]:
    """Build the EXACT approval-details dict for a Void Box action.

    Both the raise site (:func:`request_enforcement_approval`) and the
    consume site (:func:`_run_guarded`) call this with the same
    arguments — one source of truth, so the RED-1 ceremony cannot drift
    apart. The caller must pass exactly the bound fields: a plainer
    consume must never silently drop a restriction the approver saw.
    """
    details: Dict[str, Any] = {
        "voidbox_action": action_name,
        "actor": actor,
    }
    details.update(fields)
    return details


# ---------------------------------------------------------------------------
# Cybrus engines (constructed per call — stores are read fresh each time)
# ---------------------------------------------------------------------------


def _approval_engine():
    from levi.cybrus.approval import ApprovalEngine

    return ApprovalEngine()


def _policy_engine():
    from levi.cybrus.policy import PolicyEngine

    return PolicyEngine()


def _audit_engine():
    from levi.cybrus.audit import AuditEngine

    return AuditEngine()


def _audit(event: str, actor: str, details: Optional[Dict[str, Any]] = None) -> Dict:
    """One tamper-evident record per enforcement event (E6)."""
    return _audit_engine().append(event, actor, details or {})


# ---------------------------------------------------------------------------
# The raise side of the ceremony
# ---------------------------------------------------------------------------


def request_enforcement_approval(
    table_key: str,
    approval_action: str,
    actor: str,
    details: Dict[str, Any],
    *,
    risk: str = _APPROVAL_RISK,
) -> Dict:
    """Raise a pending Cybrus approval for a Void Box action (E2).

    *details* must be the dict built by :func:`_approval_details` — the
    consume side will present the identical dict (RED-1). Returns the
    pending entry; a human approves it with
    ``levi cybrus approve <id>``.
    """
    _, policy_resource, _ = _ACTION_TABLE[table_key]
    entry = _approval_engine().request_approval(
        action=approval_action,
        subject=actor,
        resource=policy_resource,
        risk=risk,
        details=details,
    )
    _audit(
        "voidbox.enforce.approval_requested",
        actor,
        {"voidbox_action": approval_action, "approval_id": entry["id"][:8]},
    )
    return entry


def _find_pending_approval(action_name: str, details: Dict[str, Any]) -> Optional[Dict]:
    """A pending entry matching (action, EXACT details), or None.

    Reusing a pending entry keeps the human from approving the same
    ceremony twice; the exact-detail match keeps RED-1 honest even on
    the reuse path.
    """
    for entry in _approval_engine().list_all():
        if entry.get("status") != "pending":
            continue
        if entry.get("action") != action_name:
            continue
        entry_details = entry.get("details")
        if isinstance(entry_details, dict) and entry_details == details:
            return dict(entry)
    return None


# ---------------------------------------------------------------------------
# The guarded runner — gate -> policy -> consume -> execute -> audit (E7)
# ---------------------------------------------------------------------------


def _run_guarded(
    action_name: str,
    actor: str,
    details_fields: Dict[str, Any],
    operation: Callable[[], Any],
    *,
    gate_home: Optional[Path] = None,
) -> Any:
    """Run one consequential Void Box action through full enforcement.

    Order is law (E7): (1) require_adult, (2) policy evaluate,
    (3) consume approval, (4) execute the product operation — reached
    only after every gate passed, (5) audit. Any failure in (1)-(3)
    refuses BEFORE the operation is invoked: nothing half-applies.
    """
    from levi.plaiground.gate import require_adult

    # (1) SI gate first — nothing else runs when the gate is locked (E1).
    require_adult(gate_home)

    approval_action, policy_resource, policy_action = _ACTION_TABLE[action_name]
    details = _approval_details(approval_action, actor, **details_fields)

    # (2) Policy: deny (incl. default-deny) refuses BEFORE consumption —
    # a denied action never spends the human's approval (E4).
    decision = _policy_engine().evaluate(actor, policy_resource, policy_action)
    if not decision.allowed:
        _audit(
            "voidbox.enforce.policy_refused",
            actor,
            {
                "voidbox_action": approval_action,
                "resource": policy_resource,
                "action": policy_action,
                "reason": decision.reason,
            },
        )
        raise PolicyRefused(
            "Cybrus policy refused %s for %r: %s — no grant consumed, "
            "no operation performed." % (approval_action, actor, decision.reason)
        )

    # (3) Consume the approval — RED-1 exact match (E2/E3/E8).
    consumed = _approval_engine().consume_approved(approval_action, details)
    if consumed is None:
        pending = _find_pending_approval(approval_action, details)
        entry = (
            pending
            if pending is not None
            else request_enforcement_approval(action_name, approval_action, actor, details)
        )
        _audit(
            "voidbox.enforce.approval_needed",
            actor,
            {
                "voidbox_action": approval_action,
                "approval_id": entry["id"][:8],
            },
        )
        raise ApprovalNeeded(
            entry["id"],
            approval_action,
            "voidbox action %s needs a consumed Cybrus approval: approve %s "
            "with `levi cybrus approve %s` then retry the same call with "
            "identical fields." % (approval_action, entry["id"][:8], entry["id"][:8]),
        )

    # (4) All gates passed — the product operation runs now, and only now.
    try:
        result = operation()
    except Exception as exc:
        _audit(
            "voidbox.enforce.operation_failed",
            actor,
            {
                "voidbox_action": approval_action,
                "approval_id": consumed["id"][:8],
                "error": "%s: %s" % (type(exc).__name__, str(exc)[:120]),
            },
        )
        raise

    # (5) Tamper-evident record of the allowed action (E6).
    _audit(
        "voidbox.enforce.executed",
        actor,
        {
            "voidbox_action": approval_action,
            "approval_id": consumed["id"][:8],
            "consumed_at": consumed["details"].get("consumed_at"),
        },
    )
    return result


# ---------------------------------------------------------------------------
# Guarded room operations — thin wrappers over levi.voidbox.rooms
# ---------------------------------------------------------------------------


def create_room_guarded(
    store,
    name: str,
    creator_id: str,
    *,
    actor: str,
    public: bool = False,
    device_id: Optional[str] = None,
    gate_home: Optional[Path] = None,
) -> dict:
    """Create a room through Cybrus enforcement (E1-E4, E6-E8, E10)."""
    return _run_guarded(
        "room.create",
        actor,
        {
            "name": name,
            "creator_id": creator_id,
            "public": bool(public),
            "device_id": device_id,
        },
        lambda: store.create_room(
            name, creator_id, public=public, device_id=device_id
        ),
        gate_home=gate_home,
    )


def add_member_guarded(
    store,
    room_id: str,
    member_id: str,
    by_admin: str,
    *,
    actor: str,
    gate_home: Optional[Path] = None,
) -> dict:
    """Admin adds a member through Cybrus enforcement (re-keys on success)."""
    return _run_guarded(
        "room.member_add",
        actor,
        {"room_id": room_id, "member_id": member_id, "by_admin": by_admin},
        lambda: store.add_member(room_id, member_id, by_admin),
        gate_home=gate_home,
    )


def remove_member_guarded(
    store,
    room_id: str,
    member_id: str,
    by_admin: str,
    *,
    actor: str,
    gate_home: Optional[Path] = None,
) -> dict:
    """Admin removes a member through Cybrus enforcement (re-keys on success)."""
    return _run_guarded(
        "room.member_remove",
        actor,
        {"room_id": room_id, "member_id": member_id, "by_admin": by_admin},
        lambda: store.remove_member(room_id, member_id, by_admin),
        gate_home=gate_home,
    )


def leave_room_guarded(
    store,
    room_id: str,
    member_id: str,
    *,
    actor: str,
    gate_home: Optional[Path] = None,
) -> dict:
    """A member leaves through Cybrus enforcement (self-removal, re-keys)."""
    return _run_guarded(
        "room.member_leave",
        actor,
        {"room_id": room_id, "member_id": member_id},
        lambda: store.leave_room(room_id, member_id),
        gate_home=gate_home,
    )


def revoke_device_guarded(
    store,
    room_id: str,
    member_id: str,
    device_id: str,
    by_admin: str,
    *,
    actor: str,
    gate_home: Optional[Path] = None,
) -> dict:
    """Admin revokes a member device through Cybrus enforcement (re-keys)."""
    return _run_guarded(
        "room.device_revoke",
        actor,
        {
            "room_id": room_id,
            "member_id": member_id,
            "device_id": device_id,
            "by_admin": by_admin,
        },
        lambda: store.revoke_member_device(room_id, member_id, device_id, by_admin),
        gate_home=gate_home,
    )


# ---------------------------------------------------------------------------
# Guarded listing publish — the product's "classifieds" surface
# ---------------------------------------------------------------------------

_LISTINGS_FILE = "listings.jsonl"


def _listings_path(gate_home: Optional[Path]) -> Path:
    """Append-only platform listing registry (metadata only — room_id,
    name, public flag, lister; never keys, never member lists)."""
    from levi.voidbox.rooms import voidbox_rooms_dir

    base = voidbox_rooms_dir(gate_home).parent
    return base / _LISTINGS_FILE


def publish_listing_guarded(
    store,
    room_id: str,
    *,
    actor: str,
    blurb: str = "",
    gate_home: Optional[Path] = None,
) -> dict:
    """Publish a room listing (classifieds surface) through enforcement.

    The listing advertises a room's EXISTENCE (id, name, public flag,
    lister, short blurb) — it carries no keys, no member lists, no
    message content. Written to an append-only registry; never deleted
    (nothing-thrown-away law).
    """
    if not isinstance(blurb, str) or len(blurb) > 140:
        raise EnforcementError("listing blurb must be a string of <= 140 chars.")

    def _op() -> dict:
        meta = store.get_room(room_id)
        listing = {
            "room_id": room_id,
            "name": meta.get("name"),
            "public": bool(meta.get("public")),
            "listed_by": actor,
            "blurb": blurb,
            "listed_at": datetime.now(timezone.utc).isoformat(),
        }
        path = _listings_path(gate_home)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(listing, sort_keys=True) + "\n")
        os.chmod(path, 0o600)
        return listing

    return _run_guarded(
        "listing.publish",
        actor,
        {"room_id": room_id, "blurb": blurb},
        _op,
        gate_home=gate_home,
    )


def list_listings(*, gate_home: Optional[Path] = None) -> List[dict]:
    """Read-only: the published listings. Unenforced (read), gate-checked."""
    from levi.plaiground.gate import require_adult

    require_adult(gate_home)  # E9: read-only, still gated
    path = _listings_path(gate_home)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# ---------------------------------------------------------------------------
# Guarded money — the ONLY path for Void Box payments (E5)
# ---------------------------------------------------------------------------


def charge_guarded(
    *,
    operation: str,
    amount_minor: int,
    currency: str,
    rail: str,
    purpose: str,
    identity: str,
    actor: str,
    approval_id: Optional[str] = None,
    authorized_by: str = "chauncey",
    gate_home: Optional[Path] = None,
) -> dict:
    """Charge (or refund/payout/...) through Cybrus money, fail-closed.

    The platform NEVER holds money logic: the movement runs entirely
    through ``MoneyGateway``'s six-gate flow (E5). Ceremony:

    1. First call WITHOUT ``approval_id``: plans the movement, requests
       the human approval, and raises ``MoneyApprovalRequired`` carrying
       the pending ``approval_id``. Nothing moves.
    2. A human approves: ``levi cybrus approve <id>``.
    3. Retry WITH ``approval_id``: rebuilds the EXACT plan the approval
       was minted for (``plan_from_approval`` — a rebound approval is
       refused), authorizes (Chauncey keeper identity), and executes.
       The approval is consumed atomically inside the gateway (RED-1);
       with no registered rail the movement refuses (fail-closed) — the
       honest current posture.

    Policy is evaluated on (actor, "voidbox.money", operation) BEFORE
    the gateway runs; a deny refuses up front (E4).
    """
    from levi.plaiground.gate import require_adult

    require_adult(gate_home)  # E1: first, before any other work

    if operation not in MONEY_OPERATIONS:
        raise EnforcementError(
            "unknown money operation %r (valid: %s)" % (operation, ", ".join(MONEY_OPERATIONS))
        )
    if not isinstance(amount_minor, int) or amount_minor <= 0:
        raise EnforcementError("amount_minor must be a positive integer (minor units — no float money).")

    from levi.cybrus.money import (
        MoneyApprovalRequired,
        MoneyAuthorization,
        MoneyGateway,
    )

    decision = _policy_engine().evaluate(actor, "voidbox.money", operation)
    if not decision.allowed:
        _audit(
            "voidbox.enforce.charge.policy_refused",
            actor,
            {
                "operation": operation,
                "amount_minor": amount_minor,
                "currency": currency,
                "rail": rail,
                "reason": decision.reason,
            },
        )
        raise PolicyRefused(
            "Cybrus policy refused money operation %r for %r: %s"
            % (operation, actor, decision.reason)
        )

    gateway = MoneyGateway()

    if approval_id is None:
        # Raise side: plan -> request approval -> raise, nothing moves.
        plan = gateway.plan(
            operation=operation,
            amount_minor=amount_minor,
            currency=currency,
            rail=rail,
            purpose=purpose,
            identity=identity,
        )
        entry = gateway.request_execution_approval(plan, subject=identity)
        _audit(
            "voidbox.enforce.charge.approval_needed",
            actor,
            {
                "operation": operation,
                "amount_minor": amount_minor,
                "currency": currency,
                "rail": rail,
                "plan_id": plan.plan_id,
                "approval_id": entry["id"][:8],
            },
        )
        raise MoneyApprovalRequired(
            entry["id"],
            "money operation %r needs human approval: approve %s with "
            "`levi cybrus approve %s` then retry charge_guarded with "
            "approval_id=%s." % (operation, entry["id"][:8], entry["id"][:8], entry["id"][:8]),
        )

    # Consume side: rebuild the EXACT plan the approval was minted for
    # (a rebound approval is refused here), then execute through the
    # gateway's RED-1 consume + fail-closed rail checks.
    plan = gateway.plan_from_approval(approval_id, expected_operation=operation)
    try:
        gateway.execute(
            plan,
            MoneyAuthorization(
                authorized_by=authorized_by,
                plan_id=plan.plan_id,
                operation=operation,
                approval_id=approval_id,
            ),
        )
    except Exception as exc:
        _audit(
            "voidbox.enforce.charge.refused",
            actor,
            {
                "operation": operation,
                "plan_id": plan.plan_id,
                "approval_id": approval_id[:8],
                "error": "%s: %s" % (type(exc).__name__, str(exc)[:160]),
            },
        )
        raise
    _audit(
        "voidbox.enforce.charge.executed",
        actor,
        {
            "operation": operation,
            "plan_id": plan.plan_id,
            "approval_id": approval_id[:8],
        },
    )
    return gateway.receipt(plan.plan_id)


# ---------------------------------------------------------------------------
# Read-only-but-gated actions (E9): open_message, get_room, relay poll
# ---------------------------------------------------------------------------


def open_message_gated(store, room_id: str, member_id: str, envelope: dict,
                       *, gate_home: Optional[Path] = None) -> dict:
    """Open a sealed envelope. Read-only: unenforced, still gate-checked."""
    from levi.plaiground.gate import require_adult

    require_adult(gate_home)
    return store.open_message(room_id, member_id, envelope)


def get_room_gated(store, room_id: str, *, gate_home: Optional[Path] = None) -> dict:
    """Read room metadata. Read-only: unenforced, still gate-checked."""
    from levi.plaiground.gate import require_adult

    require_adult(gate_home)
    return store.get_room(room_id)


def poll_gated(mailbox_store, recipient: str, limit: int = 50,
               *, gate_home: Optional[Path] = None) -> list:
    """Poll the relay mailbox. Read-only: unenforced, still gate-checked.

    ``mailbox_store`` is a ``levi.voidbox.relay.MailboxStore``; the relay
    moves ciphertext only and never opens envelopes.
    """
    from levi.plaiground.gate import require_adult

    require_adult(gate_home)
    return mailbox_store.poll(recipient, limit)


# ---------------------------------------------------------------------------
# Owner policy bootstrap (convenience — rules live in Cybrus, not here)
# ---------------------------------------------------------------------------


def grant_owner_rules(actor: str) -> List[dict]:
    """Register the standard Void Box enforcement rules for *actor*.

    Convenience for owner onboarding — the rules themselves live in
    Cybrus's policy store (``levi.cybrus.policy``), not here. All
    consequential actions gate at ``high`` risk (approval required);
    money gates at ``critical``. Without these rules the policy engine
    default-denies (E4/E7) — that is the honest, fail-closed default.
    """
    engine = _policy_engine()
    rules = []
    for action_name in _ACTION_TABLE:
        _, resource, action = _ACTION_TABLE[action_name]
        rules.append(engine.add_rule(actor, resource, action, "allow", "high"))
    for op in MONEY_OPERATIONS:
        rules.append(engine.add_rule(actor, "voidbox.money", op, "allow", "critical"))
    return rules


# ---------------------------------------------------------------------------
# Law verification — machine-checkable (the "prove" half of law-guard-prove)
# ---------------------------------------------------------------------------


def verify_laws() -> List[Tuple[str, bool, str]]:
    """Machine-checkable enforcement invariants. Each returns
    ``(law_id, ok, detail)``. Named after the rooms.py convention."""
    results: List[Tuple[str, bool, str]] = []

    def check(law: str, ok: bool, detail: str = "") -> None:
        results.append((law, bool(ok), detail))

    # E3: the canonical builder is deterministic — raise and consume
    # sites can never drift apart.
    d1 = _approval_details(ACTION_ROOM_CREATE, "alice", name="x", creator_id="alice",
                           public=False, device_id=None)
    d2 = _approval_details(ACTION_ROOM_CREATE, "alice", name="x", creator_id="alice",
                           public=False, device_id=None)
    check("E3", d1 == d2, "canonical details builder deterministic")

    # Approval action names are distinct — no cross-action grant reuse.
    names = [ACTION_ROOM_CREATE, ACTION_MEMBER_ADD, ACTION_MEMBER_REMOVE,
             ACTION_MEMBER_LEAVE, ACTION_DEVICE_REVOKE, ACTION_LISTING_PUBLISH]
    check("E3", len(set(names)) == len(names), "approval action names distinct")

    # The action table covers every guarded op exactly once.
    check("E2", set(_ACTION_TABLE) == {
        "room.create", "room.member_add", "room.member_remove",
        "room.member_leave", "room.device_revoke", "listing.publish",
    }, "action table covers all guarded ops")

    # E6: the audit chain verifies (tamper-evident).
    try:
        ok, bad = _audit_engine().verify()
        check("E6", ok, "audit chain verifies" if ok else "broken at index %r" % (bad,))
    except Exception as exc:  # fail closed on any audit fault
        check("E6", False, "audit verify raised: %s" % exc)

    # E5: this module holds no money logic — money.py owns it.
    import levi.cybrus.money as _money

    check("E5", hasattr(_money, "MoneyGateway")
          and hasattr(_money, "MONEY_APPROVAL_ACTION"),
          "money flows through levi.cybrus.money.MoneyGateway")

    # E1: the gate is the single entry check.
    from levi.plaiground import gate as _gate

    check("E1", callable(_gate.require_adult), "require_adult available")

    # LAWS registry itself is well-formed.
    ids = [law_id for law_id, _ in LAWS]
    check("LAWS", len(LAWS) >= 10 and len(set(ids)) == len(ids),
          "%d laws, ids distinct" % len(LAWS))

    return results


def check_invariants() -> List[Tuple[str, bool, str]]:
    """Alias matching the rooms.py/relay.py convention."""
    return verify_laws()
