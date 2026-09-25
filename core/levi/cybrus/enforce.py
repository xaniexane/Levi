"""Cybrus enforce — the choke point for ALL platform API traffic.

Every internal service-to-service call and every external API egress
crosses Cybrus HERE. Products never roll their own auth, rate limiting,
policy checks, or HTTP egress: they call :func:`route_service_call` /
:func:`request_egress`, or guard a function with :func:`cybrus_guarded`.

LAWS (binding — what must always hold):
  L1  Every internal service call is authenticated, rate-limited,
      policy-checked, and audit-logged. An unauthenticated, over-limit,
      or policy-denied call NEVER reaches the callee — fail closed.
  L2  External egress happens ONLY under a signed, short-lived Cybrus
      routing grant. Products must never perform their own HTTP egress;
      they call ``request_egress()`` and use the returned grant.
  L3  Policy deny always wins. No approval, no grant, no session, no
      tier, no founder exemption bypasses a deny. There is no bypass
      path.
  L4  Audit records carry metadata only — caller, callee, action,
      payload_ref, ticket, decision, risk. Never payloads, never
      secrets, never credentials.
  L5  Routing grants are bound (actor, destination, scope, expiry,
      purpose) and expire; single-use approvals are consumed atomically
      — one approval authorizes at most one call and mints at most one
      grant.
  L6  (keeper's law / anticipation) Every refusal arrives with its
      remedy: the next step is named in the error — which credential to
      present, which approval id to approve, which command retries.
      Problems are answered before they are asked twice.
  L7  (originals-first) Nothing is invented here: every decision
      resolves against the registered originals — the router's table,
      the policy engine's rules, the approval ledger, the grants
      store. No silent defaults, no auto-discovery, no default-allow.
  L8  (law→guard→prove) The laws are declared first, enforced by the
      guards in this module, and machine-checked by
      tests/test_cybrus_enforce.py — invariant tests, honestly named
      (nothing here is formally proven).
  L9  (no-cancellation) This module never removes or disables another
      organ's registrations, routes, rules, keys, or grants. It revokes
      nothing it did not issue; it deletes nothing, ever.
  L10 (nothing-thrown-away) State only ever grows: audit appends,
      approvals are marked consumed (never deleted), grants expire but
      their records remain. Removal is not a tool this module uses.
  L11 (forward-motion) The choke point never blocks waiting on a human:
      a gated call raises immediately carrying a resumable approval id
      — the caller moves on and retries. Progress is the default state.
  L12 (honesty over polish) Every decision reports the backend posture
      honestly: why it was refused, what limit bound it, what would
      change the answer. See :func:`describe_posture`.

ONE ORGANISM: this module is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him. The choke point does not
serve products the way a vendor serves customers; it serves the
organism's own traffic the way an immune system serves a body: every
crossing checked, nothing foreign smuggled in, nothing of the body's
own thrown away.

Relationship to the router and gateway:
  - ``levi.cybrus.router`` is the route / address table (control plane).
  - ``levi.cybrus.gateway`` mints routing grants — ``route_external``
    is the sole external gateway (stdlib-only, no network: it issues
    signed grants, performs no HTTP).
  - THIS module is the choke point on top of both: ``route_service_call``
    gates every internal call, ``request_egress`` is the single
    sanctioned path for external egress (it wraps the gateway's grant
    flow: auth + router resolve + rate-limit + policy + HITL approval
    when high-risk + signed short-lived grant + audit).

Stdlib-only, no network. All state under ``~/.levi/cybrus/``
(``LEVI_HOME`` override honored).

Proof: tests/test_cybrus_enforce.py — invariant tests (the honest name
for the proof gate; nothing here is formally proven, only
machine-checked against the laws above).
"""

from __future__ import annotations

import functools
import uuid
from pathlib import Path
from typing import Dict, Optional, Tuple


# --- standalone-safe import of the sibling _paths helper -------------------
# Same rationale as policy.py: must work even while the package __init__
# is mid-flight on sibling engine modules.
def _paths():  # noqa: D103 - private helper
    try:
        from levi.cybrus import _paths as _p

        return _p
    except ImportError:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "levi.cybrus._paths.standalone",
            Path(__file__).resolve().parent / "_paths.py",
        )
        if spec is None or spec.loader is None:  # pragma: no cover
            raise ImportError("cybrus _paths helper unavailable") from None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def _utcnow_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


#: The declared laws, machine-readable (L8: law→guard→prove — the laws
#: live in code, not just prose; tests assert every id is declared).
LAWS = (
    ("L1", "Every internal service call is authenticated, rate-limited, policy-checked, and audit-logged; failures never reach the callee."),
    ("L2", "External egress happens only under a signed, short-lived Cybrus routing grant; products never do their own HTTP egress."),
    ("L3", "Policy deny always wins; there is no bypass path."),
    ("L4", "Audit records carry metadata only — never payloads, secrets, or credentials."),
    ("L5", "Grants are bound and expire; approvals are single-use and consumed atomically."),
    ("L6", "Every refusal arrives with its remedy named (keeper's law / anticipation)."),
    ("L7", "Nothing is invented: every decision resolves against the registered originals (originals-first)."),
    ("L8", "Laws declared first, enforced by guards, machine-checked by invariant tests (law->guard->prove)."),
    ("L9", "This module never removes or disables another organ's registrations, routes, rules, keys, or grants (no-cancellation)."),
    ("L10", "State only ever grows; removal is not a tool this module uses (nothing-thrown-away)."),
    ("L11", "The choke point never blocks on a human; gated calls raise immediately with a resumable id (forward-motion)."),
    ("L12", "Every decision reports the backend posture honestly (honesty over polish)."),
)


def describe_posture() -> Dict:
    """Honest backend posture (L12: honesty over polish).

    What this choke point is, what it is not, and what it will never
    do — queryable at runtime so no caller has to take it on faith.
    """
    return {
        "organism": "levi",
        "organ": "levi.cybrus.enforce",
        "role": "choke point: every internal service call and every external egress crosses here",
        "network": "none — stdlib only; this module performs no HTTP and opens no sockets",
        "grant_transport": "control-plane only: Cybrus mints signed routing grants; the transport is separate and never here",
        "state_dir": str(_paths().cybrus_dir()),
        "deletes_data": False,   # L10: nothing-thrown-away
        "cancels_others": False,  # L9: no-cancellation
        "default_allow": False,  # L7: originals-first — no invented allows
        "deny_wins": True,       # L3
        "blocks_on_human": False,  # L11: forward-motion
        "laws": [lid for lid, _ in LAWS],
    }


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class EnforceError(Exception):
    """Base class for choke-point failures."""


class NotAuthenticated(EnforceError):
    """No usable credential was presented, or it did not validate."""


class CallDenied(EnforceError):
    """The policy engine denied the call. Carries the ``Decision``."""

    def __init__(self, decision, message: str):
        super().__init__(message)
        self.decision = decision


class DeviceDenied(EnforceError):
    """The calling device failed the device-bound session check (LEFT-GUARD).

    Unknown device → auto-enrolled ``untrusted`` + alert raised, call
    refused. Untrusted device → refused. Fingerprint mismatch → demoted to
    ``untrusted`` + re-alert, refused. High-risk calls additionally require
    ``trusted``. Every refusal names its remedy (L6) and is audited (L1).
    """


# ---------------------------------------------------------------------------
# Device-bound session checks (LEFT-GUARD)
# ---------------------------------------------------------------------------


def _check_device(
    device_id: str,
    device_fingerprint: Optional[str],
    *,
    min_level: str,
    caller: str,
    action: str,
    stage: str,
) -> Dict:
    """Device-bound session check for the service-call layer.

    - Unknown ``device_id`` → first sighting: auto-enroll ``untrusted`` +
      alert, then refuse (I1).
    - Fingerprint mismatch against the bound one → demote to
      ``untrusted`` + re-alert, then refuse (I6).
    - Trust below *min_level* → refuse (device compromise surface stays
      bounded: a trusted device's privileges never ride an untrusted
      device).

    Returns the device record when the check passes. Raises
    :class:`DeviceDenied`; the refusal is audited with metadata only (L4).
    """
    from levi.cybrus.device_guard import DeviceGuard

    guard = DeviceGuard()
    record = guard.trust.get(device_id)
    if record is None:
        # I1: first sighting — enroll untrusted, raise the alert, refuse.
        _, approval_id = guard.sighting(device_id, name=device_id)
        _audit(
            "call.device_refused",
            caller,
            {
                "stage": stage,
                "action": action,
                "device_id": device_id,
                "reason": "unknown device: enrolled untrusted, alert raised",
                "approval_id": approval_id[:8],
            },
        )
        raise DeviceDenied(
            f"unknown device {device_id!r}: enrolled as untrusted and an "
            f"approval was raised ({approval_id[:8]}). Remedy: have a human "
            f"run 'levi cybrus approve {approval_id[:8]}', then "
            f"'levi cybrus device trust {device_id} <level>', then retry."
        )
    seen = guard.seen(device_id, fingerprint=device_fingerprint or None)
    if seen["status"] == "spoof_suspect":
        _audit(
            "call.device_refused",
            caller,
            {
                "stage": stage,
                "action": action,
                "device_id": device_id,
                "reason": "fingerprint mismatch: demoted to untrusted",
                "approval_id": seen["approval_id"][:8],
            },
        )
        raise DeviceDenied(
            f"device {device_id!r} fingerprint mismatch: demoted to "
            "untrusted and a re-approval was raised. Remedy: verify the "
            "device physically, then re-approve it."
        )
    if not guard.trust.trust_at_least(device_id, min_level):
        actual = (guard.trust.get(device_id) or {}).get("trust")
        _audit(
            "call.device_refused",
            caller,
            {
                "stage": stage,
                "action": action,
                "device_id": device_id,
                "reason": f"trust {actual!r} below required {min_level!r}",
            },
        )
        raise DeviceDenied(
            f"device {device_id!r} trust is {actual!r}; this call requires "
            f"{min_level!r}. Remedy: raise 'levi cybrus device request "
            f"{device_id} --level {min_level}', have a human approve it, "
            "then retry."
        )
    return seen


# ---------------------------------------------------------------------------
# Small guards
# ---------------------------------------------------------------------------


def _check_name(value: str, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EnforceError(f"{what} must be a non-empty string")
    value = value.strip()
    if len(value) > 128:
        raise EnforceError(f"{what} must be at most 128 chars")
    return value


def _check_payload_ref(value: Optional[str]) -> Optional[str]:
    """``payload_ref`` is a REFERENCE (id / hash), never content. Metadata
    only — the choke point never accepts, sees, or logs a payload."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise EnforceError("payload_ref must be a non-empty string reference")
    value = value.strip()
    if len(value) > 256:
        raise EnforceError("payload_ref must be at most 256 chars")
    return value


def _audit(event: str, actor: str, details: Optional[Dict] = None) -> Dict:
    from levi.cybrus.audit import AuditEngine

    return AuditEngine().append(event, str(actor), dict(details or {}))


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def _authenticate(
    caller: str,
    *,
    credential: Optional[str] = None,
    api_key: Optional[Tuple[str, str]] = None,
    gateway=None,
) -> Dict:
    """Authenticate ``caller``. Returns ``{"method", "subject"}``.

    Two credential forms (exactly one):
      - ``credential=<bearer token>`` — a Cybrus-issued token validated
        with :class:`TokenEngine` (the token itself is never logged).
        ``session`` tokens must be label-bound to the caller
        (``session:<caller>``); ``api`` tokens must carry the
        ``service.call`` scope. BLUE (RED-1, L1): a bearer ``api`` token
        authenticates an ordinary caller, but it can NEVER act as a
        founder identity — the founder name confers quota exemption, so
        wearing it is privilege escalation. Founder identities require a
        bound credential (session token or named api key); an ``api``
        token whose label IS the caller is honored.
      - ``api_key=(name, secret)`` — a named vault-stored API key; the
        key name must equal ``caller``, the secret must validate, and
        the key must carry the ``service.call`` scope. Requires
        ``gateway=CybrusGateway(vault_passphrase=...)`` (the vault must
        be unlocked to read the stored secret).

    Raises :class:`NotAuthenticated` on anything else — fail closed.
    """
    if credential is not None and api_key is not None:
        raise EnforceError("pass exactly one of credential= / api_key=, not both")

    if credential is not None:
        from levi.cybrus.tokens import TokenEngine

        payload = TokenEngine().validate(credential)
        if payload is None:
            raise NotAuthenticated("credential did not validate (unknown / revoked / expired)")
        kind = payload.get("kind")
        if kind == "session":
            if payload.get("label") != f"session:{caller}":
                raise NotAuthenticated(
                    "session token is not bound to this caller identity"
                )
            return {"method": "session", "subject": caller}
        if kind == "api":
            scopes = payload.get("scopes") or []
            if "service.call" not in scopes:
                raise NotAuthenticated("api token lacks the 'service.call' scope")
            # BLUE (RED-1, L1 — forged caller identity): a bearer service
            # token is not bound to anyone, so it must never authenticate
            # AS a founder identity — the founder name rides quota
            # exemption (rate_limits._is_admin), and wearing it is
            # privilege escalation. Founder callers need a bound
            # credential: a session token (label session:<name>) or a
            # named api key. An api token whose label IS the caller is
            # honored as explicitly bound.
            from levi.cybrus.identity import is_founder_identity

            if is_founder_identity(caller) and payload.get("label") != caller:
                raise NotAuthenticated(
                    f"bearer service token cannot act as founder identity "
                    f"{caller!r}: the token is not bound to that identity. "
                    "Remedy: authenticate as the founder through auth() and "
                    "present the bound session token, or use an api key "
                    "named for the identity — then retry."
                )
            return {"method": "service_token", "subject": caller}
        raise NotAuthenticated(f"token kind {kind!r} cannot authorize service calls")

    if api_key is not None:
        if gateway is None:
            raise EnforceError(
                "api_key= auth requires gateway=CybrusGateway(vault_passphrase=...) "
                "so the vault-stored secret can be checked"
            )
        if (
            not isinstance(api_key, (tuple, list))
            or len(api_key) != 2
            or not all(isinstance(v, str) and v for v in api_key)
        ):
            raise EnforceError("api_key must be a (name, secret) pair of non-empty strings")
        name, secret = api_key
        meta = gateway.validate_api_key(name, secret)
        if meta is None:
            raise NotAuthenticated("api key did not validate")
        if name != caller:
            raise NotAuthenticated("api key name does not match the caller identity")
        if "service.call" not in (meta.get("scopes") or []):
            raise NotAuthenticated("api key lacks the 'service.call' scope")
        return {"method": "api_key", "subject": caller}

    raise NotAuthenticated(
        "no credential: pass credential=<bearer token> or api_key=(name, secret)"
    )


# ---------------------------------------------------------------------------
# Target resolution (internal address space only)
# ---------------------------------------------------------------------------


def _resolve_service_target(callee) -> Dict:
    """Resolve ``callee`` inside the internal address space.

    QID-addressed targets (``QID = address of thought``) are internal by
    construction. Named targets resolve through the route table and must
    be first-class internal routes — external destinations are refused
    here (use :func:`request_egress` for those).
    """
    text = callee if isinstance(callee, str) else str(callee)
    try:
        from levi.cybrus.qid import QID

        qid = QID.parse(text)
        return {"kind": "internal", "route": str(qid), "address": "qid"}
    except (ValueError, TypeError):
        pass
    from levi.cybrus.router import RouteRegistry

    decision = RouteRegistry().resolve(text)  # raises RouteRefused
    if decision["kind"] != "internal":
        raise EnforceError(
            f"{text!r} is an external route — internal calls cannot cross "
            "it; use request_egress() for external destinations"
        )
    return {"kind": "internal", "route": decision["route"], "address": "named"}


def _policy_resource(target: Dict) -> str:
    if target["address"] == "qid":
        return f"qid.{target['route']}"
    return f"service.{target['route']}"


def _match_approval(entries, action: str, details: Dict):
    from levi.cybrus import gateway as gateway_mod

    return gateway_mod.CybrusGateway._match_approval(
        entries, action, details, "pending"
    )


# ---------------------------------------------------------------------------
# The choke point: internal service calls
# ---------------------------------------------------------------------------


def route_service_call(
    caller: str,
    callee,
    action: str,
    payload_ref: Optional[str] = None,
    *,
    credential: Optional[str] = None,
    api_key: Optional[Tuple[str, str]] = None,
    gateway=None,
    device_id: Optional[str] = None,
    device_fingerprint: Optional[str] = None,
) -> Dict:
    """Route one internal service-to-service call through the choke point.

    Path: authenticate caller → device-bound session check (when
    ``device_id`` is given: unknown → enroll untrusted + alert + refuse;
    untrusted → refuse; fingerprint mismatch → demote + refuse) →
    resolve callee (internal only) → rate-limit → policy evaluate →
    device trust escalation for high-risk (requires ``trusted``) →
    HITL approval when high-risk allow → audit (metadata only) →
    return the routing ticket.

    ``payload_ref`` is an opaque reference (id / hash), never content —
    there is deliberately no ``payload`` parameter (L4).

    Raises :class:`NotAuthenticated` (no/invalid credential),
    :class:`DeviceDenied` (device-bound session check failed),
    :class:`RateLimitDenied` (over quota — from ``levi.cybrus.rate_limits``),
    :class:`CallDenied` (policy deny — deny always wins, L3),
    :class:`ApprovalRequired` (high-risk allow pending human approval —
    carries ``approval_id``; approve, then retry),
    :class:`RouteRefused` (unknown / external destination).
    """
    ticket = uuid.uuid4().hex
    caller = _check_name(caller, "caller")
    callee_text = callee if isinstance(callee, str) else str(callee)
    callee_text = _check_name(callee_text, "callee")
    action = _check_name(action, "action")
    payload_ref = _check_payload_ref(payload_ref)

    def refused(stage: str, reason: str) -> Dict:
        return {
            "callee": callee_text,
            "action": action,
            "payload_ref": payload_ref,
            "ticket": ticket[:8],
            "stage": stage,
            "reason": reason,
        }

    try:
        authn = _authenticate(
            caller, credential=credential, api_key=api_key, gateway=gateway
        )
    except EnforceError as exc:
        _audit("call.refused", caller, refused("auth", str(exc)))
        raise

    # LEFT-GUARD phase 1: device-bound session check. An unknown device is
    # sighted (enrolled untrusted + alert) and the call refused — it never
    # rides a caller credential (I1). A bound device below "known" is
    # refused; high-risk escalation to "trusted" happens after policy
    # evaluation (phase 2), once the risk is known.
    if device_id is not None:
        _check_device(
            device_id,
            device_fingerprint,
            min_level="known",
            caller=caller,
            action=action,
            stage="device",
        )

    try:
        target = _resolve_service_target(callee_text)
    except EnforceError as exc:
        _audit("call.refused", caller, refused("route", str(exc)))
        raise

    from levi.cybrus import rate_limits

    # Over-limit: rate_limits.check() audits the denial itself and raises
    # RateLimitDenied — the call never proceeds (fail closed, L1).
    rate_limits.check(caller, rate_limits.SERVICE_CALL)

    from levi.cybrus.approval import ApprovalEngine
    from levi.cybrus.policy import PolicyEngine

    policy = PolicyEngine()
    resource = _policy_resource(target)
    decision = policy.evaluate(caller, resource, action)

    if decision.decision == "deny":
        _audit(
            "call.refused",
            caller,
            {
                **refused("policy", decision.reason),
                "risk": decision.risk,
            },
        )
        # L3: deny always wins — even with an approval in hand. The
        # approval ledger is never consulted on a deny.
        raise CallDenied(
            decision,
            f"policy denied {caller} -> {callee_text} ({action}): {decision.reason}",
        )

    details = {"caller": caller, "callee": target["route"], "action": action}

    # LEFT-GUARD phase 2: high-risk calls need a TRUSTED device. Phase 1
    # already guaranteed >= "known"; now the risk is known, escalate.
    if device_id is not None and decision.risk in ("high", "critical"):
        _check_device(
            device_id,
            device_fingerprint,
            min_level="trusted",
            caller=caller,
            action=action,
            stage="device.high_risk",
        )

    approval_id = None
    if policy.needs_approval(decision):
        from levi.cybrus.gateway import ApprovalRequired

        approvals = ApprovalEngine()
        # Atomic match-and-consume: one approval authorizes at most one
        # call, even across processes (L5).
        approved = approvals.consume_approved("service.call", details)
        if approved is None:
            pending = _match_approval(approvals.list_all(), "service.call", details)
            entry = (
                pending
                if pending is not None
                else approvals.request_approval(
                    "service.call", caller, resource, decision.risk, details=details
                )
            )
            _audit(
                "call.approval_required",
                caller,
                {
                    **refused("approval", "high-risk call needs human approval"),
                    "risk": decision.risk,
                    "approval_id": entry["id"][:8],
                },
            )
            raise ApprovalRequired(
                entry["id"],
                "high-risk internal call requires explicit human approval: "
                f"{entry['id'][:8]} (levi cybrus approve {entry['id'][:8]} "
                "--identity <name>, then retry)",
            )
        approval_id = approved["id"]

    _audit(
        "call.routed",
        caller,
        {
            "callee": target["route"],
            "action": action,
            "payload_ref": payload_ref,
            "ticket": ticket[:8],
            "risk": decision.risk,
            "auth": authn["method"],
            "device_id": device_id,
            "approval_id": approval_id[:8] if approval_id else None,
        },
    )
    return {
        "allowed": True,
        "ticket": ticket,
        "caller": caller,
        "callee": target["route"],
        "action": action,
        "payload_ref": payload_ref,
        "risk": decision.risk,
        "ts": _utcnow_iso(),
    }


# ---------------------------------------------------------------------------
# The decorator: one-line choke-point guard for product code
# ---------------------------------------------------------------------------


def cybrus_guarded(*, service: str, callee: str, action: Optional[str] = None):
    """Guard a product function so its internal calls cross the choke point.

    One line on the function::

        @cybrus_guarded(service="levi.jobs", callee="levi.knowledge")
        def search_jobs(query, *, cybrus_credential=None):
            ...

    At call time the wrapper pops the ``cybrus_*`` kwargs
    (``cybrus_credential``, ``cybrus_api_key``, ``cybrus_gateway``,
    ``cybrus_payload_ref``, ``cybrus_device_id``,
    ``cybrus_device_fingerprint``), routes through :func:`route_service_call`,
    and only then invokes the function — a refused call means the body
    never runs. Function arguments are never audited (L4); only the
    ``cybrus_payload_ref`` reference is logged.
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            credential = kwargs.pop("cybrus_credential", None)
            api_key = kwargs.pop("cybrus_api_key", None)
            gw = kwargs.pop("cybrus_gateway", None)
            payload_ref = kwargs.pop("cybrus_payload_ref", None)
            device_id = kwargs.pop("cybrus_device_id", None)
            device_fingerprint = kwargs.pop("cybrus_device_fingerprint", None)
            route_service_call(
                service,
                callee,
                action or fn.__name__,
                payload_ref=payload_ref,
                credential=credential,
                api_key=api_key,
                gateway=gw,
                device_id=device_id,
                device_fingerprint=device_fingerprint,
            )
            return fn(*args, **kwargs)

        wrapper._cybrus_guarded = {
            "service": service,
            "callee": callee,
            "action": action or fn.__name__,
        }
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# The choke point: external egress (the single sanctioned path)
# ---------------------------------------------------------------------------


def request_egress(
    actor: str,
    destination: str,
    purpose: str,
    *,
    credential: Optional[str] = None,
    api_key: Optional[Tuple[str, str]] = None,
    gateway=None,
    grant_ttl_seconds: Optional[int] = None,
) -> Dict:
    """The single sanctioned path for external API egress (L2).

    Products must NOT do their own HTTP egress — they request a routing
    grant here and hand the grant to the (separately authorized) transport.

    Path: authenticate actor → router resolve (must be a registered
    external route) → rate-limit → policy evaluate → HITL approval when
    high-risk allow → signed short-lived grant (bound to actor,
    destination, scope, expiry, purpose) → audit (metadata only).

    This wraps the gateway's grant flow (``route_external`` requires ALL
    of the same: policy allow + human approval when high-risk, then a
    signed grant) — the difference is the auth step: here the actor
    authenticates with a Cybrus bearer token / API key instead of a live
    password session.

    Returns the grant dict (same shape as ``route_external``):
    ``grant_id``, ``token`` (plaintext, shown once), ``token_id``,
    ``actor``, ``destination``, ``purpose``, ``expires_at``.

    Raises :class:`NotAuthenticated`, :class:`RateLimitDenied`,
    :class:`PolicyDenied` (from the gateway — deny always wins, L3),
    :class:`ApprovalRequired` (carries ``approval_id``), :class:`RouteRefused`
    (destination not a registered external route).
    """
    from levi.cybrus.gateway import GRANT_TTL_SECONDS

    actor = _check_name(actor, "actor")
    destination = _check_name(destination, "destination")
    if not isinstance(purpose, str) or not purpose.strip():
        raise EnforceError("purpose is required (non-empty string)")
    purpose = purpose.strip()
    if grant_ttl_seconds is None:
        grant_ttl_seconds = GRANT_TTL_SECONDS
    if not isinstance(grant_ttl_seconds, int) or grant_ttl_seconds <= 0:
        raise EnforceError("grant_ttl_seconds must be a positive integer")

    def refused(stage: str, reason: str) -> Dict:
        return {
            "destination": destination,
            "purpose": purpose,
            "stage": stage,
            "reason": reason,
        }

    try:
        _authenticate(actor, credential=credential, api_key=api_key, gateway=gateway)
    except EnforceError as exc:
        _audit("egress.refused", actor, refused("auth", str(exc)))
        raise

    from levi.cybrus.router import RouteRegistry

    try:
        route = RouteRegistry().resolve(destination)
    except EnforceError as exc:
        _audit("egress.refused", actor, refused("route", str(exc)))
        raise
    if route["kind"] != "external":
        reason = (
            f"{destination!r} is an internal route — external egress grants "
            "are for registered external destinations only; use "
            "route_service_call() for internal calls"
        )
        _audit("egress.refused", actor, refused("route", reason))
        raise EnforceError(reason)

    from levi.cybrus import rate_limits

    rate_limits.check(actor, rate_limits.SERVICE_CALL)

    from levi.cybrus.approval import ApprovalEngine
    from levi.cybrus.gateway import ApprovalRequired, PolicyDenied
    from levi.cybrus.policy import PolicyEngine

    policy = PolicyEngine()
    approvals = ApprovalEngine()
    decision = policy.evaluate(actor, f"external.{destination}", "route")

    if decision.decision == "deny":
        _audit(
            "route.external.denied",
            actor,
            {
                "destination": destination,
                "purpose": purpose,
                "risk": decision.risk,
                "reason": decision.reason,
            },
        )
        # L3: deny wins even with an approval in hand — same guarantee as
        # the gateway's own route_external.
        raise PolicyDenied(
            decision,
            f"policy denied egress to {destination!r}: {decision.reason}",
        )

    details = {"actor": actor, "destination": destination, "purpose": purpose}
    if policy.needs_approval(decision):
        # Same action + details shape as gateway.route_external, so an
        # approval granted for one path is consumable by the other — and
        # single-use still holds (L5).
        approved = approvals.consume_approved("route.external", details)
        if approved is None:
            pending = _match_approval(approvals.list_all(), "route.external", details)
            entry = (
                pending
                if pending is not None
                else approvals.request_approval(
                    "route.external",
                    actor,
                    f"external.{destination}",
                    decision.risk,
                    details=details,
                )
            )
            _audit(
                "route.external.approval_required",
                actor,
                {
                    "destination": destination,
                    "purpose": purpose,
                    "risk": decision.risk,
                    "approval_id": entry["id"][:8],
                },
            )
            raise ApprovalRequired(
                entry["id"],
                "high-risk external egress requires explicit human approval: "
                f"{entry['id'][:8]} (levi cybrus approve {entry['id'][:8]} "
                "--identity <name>, then retry)",
            )

    if gateway is None:
        from levi.cybrus.gateway import CybrusGateway

        gateway = CybrusGateway()
    # The grant mint itself is the gateway's machinery (signed token,
    # grants-store record, full audit) — the choke point adds the auth /
    # routing / policy path above it, never its own minting.
    return gateway._issue_routing_grant(
        actor, destination, purpose, decision, grant_ttl_seconds
    )
