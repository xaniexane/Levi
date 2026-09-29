"""Cybrus broker — bloodline metering + broker-as-a-service.

Bloodline distribution law (Chauncey, 2026-09-27): the founder holds the
original source with UNLIMITED third-party credential creation; every
other instance spawns off it as a LIMITED bloodline derivative. The
unlimited capability is offered as a metered SERVICE the founder
provides. This module is the metering hooks:

- usage accounting (append-only meter ledger per identity),
- entitlement checks (read-only "may I?", distinct from quota consumption),
- the request-through-founder path: a limited instance files a service
  request; the founder fulfills it through an authenticated session; the
  limited instance can never mint unlimited itself.

METER LAWS (machine-checked in tests/test_cybrus_broker_meter.py)
----------------------------------------------------------------
- **M1 NO-SELF-MINT.** :func:`request_service` files a ticket; it never
  creates credentials, vault entries, or passwords.
- **M2 FOUNDER-FULFILL.** :func:`fulfill_service_request` and
  :func:`deny_service_request` require a live authenticated
  :class:`~levi.cybrus.founder_gateway.FounderSession`
  (``assert_live``); any other ``session=`` value is refused.
- **M3 METERED.** Every fulfillment records meter usage for the
  requestor and a service-ledger entry for the founder; readings are
  queryable via :func:`meter_reading`.
- **M4 ENTITLEMENT-BEFORE-USE.** :func:`entitlement_check` is read-only
  and never consumes quota; consumption happens exactly once inside the
  brokered action itself.
- **M5 AUDIT.** Request/fulfill/deny/meter events are audit-logged,
  metadata only — no secrets, no passwords, no tokens.
- **M6 SINGLE-FULFILL.** A request transitions to a terminal state
  (fulfilled/denied) exactly once; a second terminal transition fails.

His-words vs my-fill
---------------------
- His: founder unlimited; others limited; unlimited offered as a
  metered service he provides; spawned instances request through him.
- My fill: the ticket shape, the read-only entitlement check, and the
  rule that a founder-fulfilled service bypasses the *requestor's* tier
  quota (the founder's unlimited capability performs the mint) while
  still charging the requestor's meter and requiring the founder's
  human approval on the provision. If he wants requestor quotas to
  apply to fulfilled services too, that is a one-line change.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

_METER_STORE = "broker_meter"
_REQUESTS_STORE = "broker_service_requests"

_HOUR = 3600.0
_DAY = 86400.0


class MeterError(Exception):
    """Metering / broker-service failures (validation, state, gate)."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short(value: str) -> str:
    return str(value)[:8]


def _paths():
    from levi.cybrus import _paths as p

    return p


def _audit(event: str, actor: str, details: Optional[Dict] = None) -> None:
    from levi.cybrus.audit import AuditEngine

    AuditEngine().append(event, str(actor), dict(details or {}))


def _is_founder(identity: str) -> bool:
    from levi.cybrus.identity import is_founder_identity

    return is_founder_identity(identity)


def _clean_name(value: str, what: str) -> str:
    from levi.cybrus.broker import _clean_name as _cn

    return _cn(value, what)


def _clean_url(value: str) -> str:
    from levi.cybrus.broker import _clean_url as _cu

    return _cu(value)


# -- usage accounting ----------------------------------------------------------


def _load_ledger() -> List[Dict]:
    p = _paths()
    data = p.load_json_store(p.store_path(_METER_STORE))
    return data if isinstance(data, list) else []


def _save_ledger(entries: List[Dict]) -> None:
    p = _paths()
    path = p.store_path(_METER_STORE)
    with p.store_lock(path):
        p.save_json_store(path, entries)


def record_use(
    identity: str, action: str, units: int = 1, note: str = ""
) -> Dict[str, Any]:
    """Append usage to the meter ledger (accounting; does not gate).

    Every brokered mint — direct or service-fulfilled — lands here, so the
    founder can meter what was provided and to whom.
    """
    identity = _clean_name(identity, "identity")
    if not isinstance(units, int) or units < 1:
        raise MeterError("units must be a positive int")
    entry = {
        "id": uuid.uuid4().hex,
        "identity": identity,
        "action": str(action),
        "units": units,
        "note": str(note or ""),
        "ts": time.time(),
        "at": _utcnow_iso(),
    }
    ledger = _load_ledger()
    ledger.append(entry)
    _save_ledger(ledger)
    _audit(
        "broker.meter.recorded",
        identity,
        {"action": action, "units": units, "note": entry["note"]},
    )
    return dict(entry)


def meter_reading(identity: str, action: str) -> Dict[str, Any]:
    """Queryable meter reading for ``identity``/``action``.

    Returns used/remaining units across hour/day windows plus the tier.
    The founder reads unlimited (still fully logged).
    """
    from levi.cybrus import rate_limits as _rate_limits

    identity = _clean_name(identity, "identity")
    now = time.time()
    used_hour = used_day = used_lifetime = 0
    for e in _load_ledger():
        if e.get("identity") != identity or e.get("action") != action:
            continue
        units = int(e.get("units", 0))
        used_lifetime += units
        age = now - float(e.get("ts", 0))
        if age < _HOUR:
            used_hour += units
        if age < _DAY:
            used_day += units
    if _is_founder(identity):
        return {
            "identity": identity,
            "action": action,
            "tier": "founder",
            "unlimited": True,
            "used_hour": used_hour,
            "used_day": used_day,
            "used_lifetime": used_lifetime,
            "remaining_hour": None,
            "remaining_day": None,
        }
    tier = _rate_limits.get_tier(identity)
    limits = _rate_limits.TIERS.get(tier, {})
    window = limits.get(action)
    if window is None:  # uncapped tier (platform)
        rem_h = rem_d = None
    else:
        per_hour, per_day = window
        rem_h = max(0, per_hour - used_hour)
        rem_d = max(0, per_day - used_day)
    return {
        "identity": identity,
        "action": action,
        "tier": tier,
        "unlimited": False,
        "used_hour": used_hour,
        "used_day": used_day,
        "used_lifetime": used_lifetime,
        "remaining_hour": rem_h,
        "remaining_day": rem_d,
    }


def entitlement_check(
    identity: str, action: str, units: int = 1
) -> Tuple[bool, str, Optional[int]]:
    """Read-only entitlement probe: may ``identity`` perform ``units`` of
    ``action`` right now? Returns ``(entitled, reason, remaining_day)``.

    Never consumes quota and never writes — the "may I?" before the
    "I did". The founder is always entitled (unlimited, logged).
    """
    identity = _clean_name(identity, "identity")
    if not isinstance(units, int) or units < 1:
        raise MeterError("units must be a positive int")
    if _is_founder(identity):
        _audit(
            "broker.meter.entitlement",
            identity,
            {"action": action, "entitled": True, "reason": "founder-unlimited"},
        )
        return True, "founder-unlimited", None
    reading = meter_reading(identity, action)
    rem = reading["remaining_day"]
    entitled = rem is None or rem >= units
    reason = "entitled" if entitled else f"quota-exhausted(tier={reading['tier']})"
    _audit(
        "broker.meter.entitlement",
        identity,
        {"action": action, "entitled": entitled, "reason": reason},
    )
    return entitled, reason, rem


# -- broker-as-a-service: request through the founder ---------------------------


def _load_requests() -> List[Dict]:
    p = _paths()
    data = p.load_json_store(p.store_path(_REQUESTS_STORE))
    return data if isinstance(data, list) else []


def _save_requests(requests: List[Dict]) -> None:
    p = _paths()
    path = p.store_path(_REQUESTS_STORE)
    with p.store_lock(path):
        p.save_json_store(path, requests)


def _find_request(request_id: str) -> Dict:
    for req in _load_requests():
        if req["id"] == request_id:
            return req
    raise MeterError(f"unknown broker service request: {_short(request_id)}")


def get_service_request(request_id: str) -> Dict[str, Any]:
    """Fetch a service-request ticket; raises unless it exists and is pending.

    Used by the broker to verify a ``service_request_id`` before a
    founder-fulfilled mint.
    """
    req = _find_request(str(request_id or ""))
    if req["status"] != "pending":
        raise MeterError(
            f"service request {_short(req['id'])} is {req['status']!r}, not pending"
        )
    return dict(req)


def _require_live_session(session) -> str:
    """Return the authenticated service identity, or refuse.

    Anything that is not a live FounderSession fails closed here — this
    is the M2 gate.
    """
    from levi.cybrus.founder_gateway import FounderSession, FounderSessionError

    if not isinstance(session, FounderSession):
        raise MeterError(
            "fulfillment requires a live authenticated FounderSession "
            f"(got {type(session).__name__})"
        )
    try:
        return session.assert_live()
    except FounderSessionError as exc:
        raise MeterError(f"founder session is not live: {exc}") from exc


def request_service(
    requestor: str,
    platform: str,
    signup_url: str,
    username: Optional[str] = None,
) -> Dict[str, Any]:
    """File a broker-service request (M1: files a ticket, mints nothing).

    A limited bloodline instance calls this to ask the founder's
    instance for a brokered third-party account. The request waits in
    ``pending`` until the founder fulfills or denies it. Filing is
    logged and audited; it creates no credentials.
    """
    requestor = _clean_name(requestor, "requestor")
    if _is_founder(requestor):
        raise MeterError(
            f"identity {requestor!r} is a founder identity: the founder "
            "provisions directly, never through a service request."
        )
    platform = _clean_name(platform, "platform")
    signup_url = _clean_url(signup_url)
    username = _clean_name(username, "username") if username else requestor
    record = {
        "id": uuid.uuid4().hex,
        "requestor": requestor,
        "platform": platform,
        "signup_url": signup_url,
        "username": username,
        "status": "pending",
        "created_at": _utcnow_iso(),
        "decided_at": None,
        "decided_by": None,
        "account_id": None,
    }
    requests = _load_requests()
    requests.append(record)
    _save_requests(requests)
    _audit(
        "broker.service.requested",
        requestor,
        {
            "request_id": _short(record["id"]),
            "platform": platform,
            "username": username,
        },
    )
    return dict(record)


def list_service_requests(status: Optional[str] = None) -> List[Dict]:
    """Service-request tickets, metadata only (never secrets)."""
    requests = _load_requests()
    if status is not None:
        requests = [r for r in requests if r["status"] == status]
    return [dict(r) for r in sorted(requests, key=lambda r: r["created_at"])]


def fulfill_service_request(
    request_id: str, session, vault_passphrase: str
) -> Tuple[Dict[str, Any], str]:
    """Fulfill a pending service request as the founder (M2/M3/M6).

    Requires a live FounderSession. Provisions the brokered account
    under the *requestor's* identity via the founder's unlimited
    capability (the requestor's tier quota does not gate a
    founder-performed service — the founder's human approval on the
    provision is the anti-abuse gate), charges the requestor's meter,
    and returns ``(account_record, password)`` exactly once to the
    founder's operator for delivery to the requestor.
    """
    fulfiller = _require_live_session(session)
    req = get_service_request(request_id)  # raises unless pending (M6)
    from levi.cybrus.broker import CredentialBroker

    broker = CredentialBroker(vault_passphrase)
    # The provision's own human gate fires here; the founder approves it.
    # The provision verifies the ticket, skips the requestor's tier quota
    # (founder's unlimited capability), and charges the requestor's meter.
    record, password = broker.provision(
        req["platform"],
        req["signup_url"],
        identity=req["requestor"],
        username=req["username"],
        service_request_id=req["id"],
    )
    p = _paths()
    path = p.store_path(_REQUESTS_STORE)
    with p.store_lock(path):
        requests = _load_requests()
        for r in requests:
            if r["id"] == req["id"]:
                r["status"] = "fulfilled"
                r["decided_at"] = _utcnow_iso()
                r["decided_by"] = fulfiller
                r["account_id"] = record["id"]
                req = dict(r)
                break
        p.save_json_store(path, requests)
    _audit(
        "broker.service.fulfilled",
        fulfiller,
        {
            "request_id": _short(req["id"]),
            "requestor": req["requestor"],
            "platform": req["platform"],
            "account_id": _short(record["id"]),
        },
    )
    return record, password


def deny_service_request(request_id: str, session, reason: str) -> Dict[str, Any]:
    """Deny a pending service request as the founder (M2/M6)."""
    denier = _require_live_session(session)
    reason = str(reason or "").strip()[:280] or "no reason given"
    req = _find_request(request_id)
    if req["status"] != "pending":
        raise MeterError(
            f"service request {_short(request_id)} is {req['status']!r}, "
            "not pending (M6 single-decision)"
        )
    p = _paths()
    path = p.store_path(_REQUESTS_STORE)
    with p.store_lock(path):
        requests = _load_requests()
        for r in requests:
            if r["id"] == req["id"]:
                r["status"] = "denied"
                r["decided_at"] = _utcnow_iso()
                r["decided_by"] = denier
                req = dict(r)
                break
        p.save_json_store(path, requests)
    _audit(
        "broker.service.denied",
        denier,
        {"request_id": _short(req["id"]), "requestor": req["requestor"], "reason": reason},
    )
    return dict(req)
