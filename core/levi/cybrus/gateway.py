"""Cybrus gateway — the Founder-Grade Identity Vault's internal API surface.

Canonical surface:
- :meth:`CybrusGateway.auth` — authenticate an identity → session token
  (token-engine ``kind="session"``).
- :meth:`CybrusGateway.generate_account` — thin wrapper over the account
  factory (returns the secret exactly once).
- :meth:`CybrusGateway.create_api_key` / :meth:`get_api_key` /
  :meth:`validate_api_key` / :meth:`list_api_keys` / :meth:`revoke_api_key`
  — named API keys whose secrets live in the encrypted vault (service
  ``cybrus.apikeys``), distinct from session tokens.
- :meth:`CybrusGateway.route_internal` — internal routing decision, logged
  (metadata only, never full payloads).
- :meth:`CybrusGateway.route_external` — the SOLE external gateway.
- :meth:`CybrusGateway.authorize_execution` — the execution-authorization
  path: policy → approval → audit → decision.

Governing rule, enforced by design: **Omega never touches external APIs
directly — Cybrus does.**

``route_external`` is the authorization / routing-control plane, NOT an
HTTP client: this build is stdlib-only with no network, so it performs no
network calls. A grant requires ALL of: (a) an authenticated identity
(live session from :meth:`auth`), (b) a policy-engine ``allow``, (c) a
human-approved HITL record when the decision is high-risk — then it issues
a short-lived signed routing grant (token binding: actor, destination
pattern, scope, expiry, purpose) and writes a full audit record. No grant
without all four. Policy ``deny`` always wins, even with an approval in
hand — there is no bypass path.

Token kinds used here: ``session`` (auth sessions), ``api`` (API keys are
vault-stored bearer secrets; routing grants are short-lived ``api``
tokens), ``revenue`` (paper-only value-tracking tokens carrying ``memo`` +
``basis``; no real money, labeled ``paper=True``).
"""

from __future__ import annotations

import hmac
import secrets
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _paths():  # noqa: D103 - private helper, same rationale as policy.py
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


#: Session lifetime after auth (12 hours).
SESSION_TTL_SECONDS = 12 * 3600
#: Default routing-grant lifetime (5 minutes — short-lived by design).
GRANT_TTL_SECONDS = 300
#: Vault service under which named API-key secrets are stored.
APIKEY_VAULT_SERVICE = "cybrus.apikeys"

_APIKEY_STORE = "apikeys"
_GRANTS_STORE = "grants"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GatewayError(Exception):
    """Base class for gateway failures."""


class GatewayAuthError(GatewayError):
    """Authentication failed, or no live session for the actor."""


class PolicyDenied(GatewayError):
    """The policy engine denied the request. Carries the ``Decision``."""

    def __init__(self, decision, message: str):
        super().__init__(message)
        self.decision = decision


class ApprovalRequired(GatewayError):
    """High-risk request blocked pending human approval. Carries the
    pending ``approval_id`` — a verified human approves it with
    ``levi cybrus approve <id> --identity <name>`` (password prompted)
    and then the request is retried."""

    def __init__(self, approval_id: str, message: str):
        super().__init__(message)
        self.approval_id = approval_id


class CybrusGateway:
    """The canonical internal API surface of the Cybrus identity vault."""

    def __init__(self, vault_passphrase: Optional[str] = None):
        self._vault_passphrase = vault_passphrase
        self._vault_instance = None
        # identity name -> {"token_id": ..., "expires_at": ...}; in-memory
        # only — a restart requires re-authentication.
        self._sessions: Dict[str, Dict] = {}

    # -- internal helpers ------------------------------------------------

    def _audit(self, event: str, actor: str, details: Optional[Dict] = None):
        from levi.cybrus.audit import AuditEngine

        return AuditEngine().append(event, actor, details or {})

    def _vault(self):
        if self._vault_instance is None:
            if not self._vault_passphrase:
                raise GatewayError(
                    "vault is not unlocked: construct CybrusGateway with "
                    "vault_passphrase=<master password>"
                )
            from levi.cybrus.vault import CredentialVault

            self._vault_instance = CredentialVault(self._vault_passphrase)
        return self._vault_instance

    def _load_store(self, name: str) -> List[Dict]:
        data = _paths().load_json_store(_paths().store_path(name))
        return data if isinstance(data, list) else []

    def _save_store(self, name: str, payload: List[Dict]) -> None:
        _paths().save_json_store(_paths().store_path(name), payload)

    def _require_session(self, actor: str) -> Dict:
        sess = self._sessions.get(actor)
        if not sess or sess["expires_at"] <= time.time():
            self._sessions.pop(actor, None)
            raise GatewayAuthError(f"no live session for {actor!r}: call auth() first")
        return sess

    @staticmethod
    def _match_approval(
        entries: List[Dict], action: str, details: Dict, status: str
    ) -> Optional[Dict]:
        for entry in entries:
            if entry.get("action") != action or entry.get("status") != status:
                continue
            entry_details = entry.get("details") or {}
            if all(entry_details.get(k) == v for k, v in details.items()):
                if status == "approved" and entry_details.get("consumed_at"):
                    continue  # single-use: already consumed
                return entry
        return None

    # -- auth ------------------------------------------------------------

    def auth(self, identity: str, credential: str) -> Tuple[str, str]:
        """Authenticate an identity with its password. Returns
        ``(session_token_id, plaintext_session_token)`` — the plaintext is
        shown exactly once. Raises :class:`GatewayAuthError` on failure
        (the reason is never distinguished to callers)."""
        from levi.cybrus.factory import verify_password
        from levi.cybrus.identity import IdentityStore
        from levi.cybrus.tokens import TokenEngine

        store = IdentityStore()
        rec = store.get(identity)
        if rec is None or rec.get("status") != "active":
            self._audit("auth.failed", str(identity), {"reason": "unknown_or_inactive"})
            raise GatewayAuthError("authentication failed")
        cred_ref = store.get_credential(rec["id"])
        if not cred_ref or not verify_password(credential, cred_ref):
            self._audit("auth.failed", rec["name"], {"reason": "bad_credential"})
            raise GatewayAuthError("authentication failed")
        token_id, plaintext = TokenEngine().issue(
            scopes=["cybrus.session"],
            ttl_seconds=SESSION_TTL_SECONDS,
            kind="session",
            label=f"session:{rec['name']}",
        )
        self._sessions[rec["name"]] = {
            "token_id": token_id,
            "expires_at": time.time() + SESSION_TTL_SECONDS,
        }
        self._audit("auth.success", rec["name"], {"token_id": token_id[:8]})
        return token_id, plaintext

    # -- accounts --------------------------------------------------------

    def generate_account(self, name: str, tier: str = "starter") -> Tuple[Dict, str]:
        """Create an identity account via the account factory. Returns
        ``(record, plaintext_password)`` — the password exists in plaintext
        only in this return value (never in the audit log)."""
        from levi.cybrus.factory import AccountFactory

        record, password = AccountFactory().generate(name, tier=tier)
        self._audit(
            "account.generated",
            record["name"],
            {"id": record["id"][:8], "tier": record["tier"]},
        )
        return record, password

    # -- named API keys (vault-stored, distinct from session tokens) ------

    def create_api_key(self, name: str, scopes: List[str]) -> Tuple[str, str]:
        """Create a named API key. The secret is stored in the encrypted
        vault and returned exactly once. ``scopes`` must be a non-empty
        list of non-empty strings.

        The name-uniqueness check and the registry append run under the
        store lock, so two concurrent creates cannot both claim the same
        name.
        """
        if not isinstance(name, str) or not name.strip():
            raise GatewayError("api key name must be a non-empty string")
        name = name.strip()
        if (
            not isinstance(scopes, (list, tuple))
            or not scopes
            or any(not isinstance(s, str) or not s.strip() for s in scopes)
        ):
            raise GatewayError("scopes must be a non-empty list of strings")
        p = _paths()
        with p.store_lock(p.store_path(_APIKEY_STORE)):
            registry = self._load_store(_APIKEY_STORE)
            if any(entry["name"] == name for entry in registry):
                raise GatewayError(f"api key name already taken: {name!r}")
            secret = secrets.token_urlsafe(32)
            self._vault().store(APIKEY_VAULT_SERVICE, name, secret)
            registry.append(
                {
                    "name": name,
                    "scopes": [s.strip() for s in scopes],
                    "created_at": _utcnow_iso(),
                }
            )
            self._save_store(_APIKEY_STORE, registry)
        self._audit("apikey.created", "gateway", {"name": name})
        return name, secret

    def get_api_key(self, name: str) -> str:
        """Return the stored API-key secret. Raises :class:`KeyError` when
        no such key exists."""
        registry = self._load_store(_APIKEY_STORE)
        if not any(entry["name"] == name for entry in registry):
            raise KeyError(f"unknown api key: {name!r}")
        return self._vault().get(APIKEY_VAULT_SERVICE, name)

    def validate_api_key(self, name: str, presented: str) -> Optional[Dict]:
        """Validate a presented API key. Returns ``{"name", "scopes"}`` on
        success, ``None`` otherwise (constant-time comparison)."""
        try:
            stored = self.get_api_key(name)
        except (KeyError, GatewayError):
            return None
        if not isinstance(presented, str) or not hmac.compare_digest(stored, presented):
            return None
        registry = self._load_store(_APIKEY_STORE)
        meta = next(entry for entry in registry if entry["name"] == name)
        return {"name": name, "scopes": list(meta["scopes"])}

    def list_api_keys(self) -> List[Dict]:
        """API-key metadata — names and scopes only, never secrets."""
        return [
            {
                "name": entry["name"],
                "scopes": list(entry["scopes"]),
                "created_at": entry["created_at"],
            }
            for entry in self._load_store(_APIKEY_STORE)
        ]

    def revoke_api_key(self, name: str) -> None:
        """Revoke (delete) a named API key. Raises :class:`KeyError` when
        unknown."""
        p = _paths()
        with p.store_lock(p.store_path(_APIKEY_STORE)):
            registry = self._load_store(_APIKEY_STORE)
            remaining = [entry for entry in registry if entry["name"] != name]
            if len(remaining) == len(registry):
                raise KeyError(f"unknown api key: {name!r}")
            self._vault().delete(APIKEY_VAULT_SERVICE, name)
            self._save_store(_APIKEY_STORE, remaining)
        self._audit("apikey.revoked", "gateway", {"name": name})

    # -- internal routing -------------------------------------------------

    def route_internal(
        self, qid_or_target, payload_meta: Optional[Dict] = None
    ) -> Dict:
        """Internal routing decision. Accepts a :class:`QID` (``QID =
        address of thought``) or a named internal target string. The
        decision is audit-logged with metadata only — never full payloads."""
        from levi.cybrus.qid import QID

        qid = None
        if isinstance(qid_or_target, str):
            text = qid_or_target.strip()
            if not text:
                raise GatewayError("internal route target must be non-empty")
            try:
                qid = QID.parse(text)
            except ValueError:
                qid = None  # a named internal target, not a QID
            target = str(qid) if qid is not None else text
        else:
            # A QID instance — normalized through its canonical string form
            # so QIDs from any copy of the module are accepted.
            try:
                qid = QID.parse(str(qid_or_target))
            except (ValueError, TypeError):
                raise GatewayError(
                    "route target must be a QID or a target string, "
                    f"got {type(qid_or_target).__name__}"
                ) from None
            target = str(qid)
        self._audit(
            "route.internal",
            "gateway",
            {"target": target, "meta": dict(payload_meta or {})},
        )
        return {
            "target": target,
            "qid": str(qid) if qid else None,
            "allowed": True,
            "ts": _utcnow_iso(),
        }

    # -- execution authorization ------------------------------------------

    def authorize_execution(self, actor: str, action: str, resource: str) -> Dict:
        """The execution-authorization path: policy check → approval check
        (high-risk requires an approved HITL record) → audit append →
        returns the authorization outcome.

        Returns ``{"decision", "authorized", "approval_id", "reason"}``.
        Policy ``deny`` always wins — even with an approval in hand.
        Approvals are single-use: a consumed approval cannot authorize
        twice.
        """
        from levi.cybrus.approval import ApprovalEngine
        from levi.cybrus.policy import PolicyEngine

        policy = PolicyEngine()
        approvals = ApprovalEngine()
        decision = policy.evaluate(actor, resource, action)

        if decision.decision == "deny":
            self._audit(
                "execution.denied",
                actor,
                {
                    "action": action,
                    "resource": resource,
                    "risk": decision.risk,
                    "reason": decision.reason,
                },
            )
            return {
                "decision": decision,
                "authorized": False,
                "approval_id": None,
                "reason": decision.reason,
            }

        details = {"actor": actor, "action": action, "resource": resource}
        if policy.needs_approval(decision):
            # Atomic match-and-consume: exactly one concurrent caller can
            # win an approval — single-use holds even across processes.
            approved = approvals.consume_approved("execute", details)
            if approved is None:
                pending = self._match_approval(
                    approvals.list_all(), "execute", details, "pending"
                )
                entry = (
                    pending
                    if pending is not None
                    else approvals.request_approval(
                        "execute", actor, resource, decision.risk, details=details
                    )
                )
                self._audit(
                    "execution.approval_required",
                    actor,
                    {
                        "action": action,
                        "resource": resource,
                        "risk": decision.risk,
                        "approval_id": entry["id"][:8],
                    },
                )
                return {
                    "decision": decision,
                    "authorized": False,
                    "approval_id": entry["id"],
                    "reason": (
                        "high-risk execution requires explicit human approval: "
                        f"{entry['id'][:8]}"
                    ),
                }
            self._audit(
                "execution.authorized",
                actor,
                {
                    "action": action,
                    "resource": resource,
                    "risk": decision.risk,
                    "approval_id": approved["id"][:8],
                },
            )
            return {
                "decision": decision,
                "authorized": True,
                "approval_id": approved["id"],
                "reason": "authorized: human approval on record",
            }

        self._audit(
            "execution.authorized",
            actor,
            {"action": action, "resource": resource, "risk": decision.risk},
        )
        return {
            "decision": decision,
            "authorized": True,
            "approval_id": None,
            "reason": "authorized: low-risk policy allow",
        }

    # -- the sole external gateway ----------------------------------------

    def route_external(
        self,
        destination: str,
        actor: str,
        purpose: str,
        grant_ttl_seconds: int = GRANT_TTL_SECONDS,
    ) -> Dict:
        """The SOLE external gateway — control plane only (no network calls
        in this build).

        Requires ALL of: (a) a live authenticated session for ``actor``,
        (b) a policy-engine ``allow`` for the route, (c) a human-approved
        HITL record when the decision is high-risk. Then issues a
        short-lived signed routing grant bound to (actor, destination
        pattern, scope, expiry, purpose) and writes a full audit record.

        Raises :class:`GatewayAuthError` without a session,
        :class:`PolicyDenied` on policy deny (wins over any approval), and
        :class:`ApprovalRequired` (carrying the pending ``approval_id``)
        when a high-risk route still needs a human.
        """
        if not isinstance(destination, str) or not destination.strip():
            raise GatewayError("destination must be a non-empty string")
        if not isinstance(purpose, str) or not purpose.strip():
            raise GatewayError("purpose is required (non-empty string)")
        destination = destination.strip()
        purpose = purpose.strip()
        if not isinstance(grant_ttl_seconds, int) or grant_ttl_seconds <= 0:
            raise GatewayError("grant_ttl_seconds must be a positive integer")

        self._require_session(actor)

        from levi.cybrus.approval import ApprovalEngine
        from levi.cybrus.policy import PolicyEngine
        from levi.cybrus.tokens import TokenEngine

        policy = PolicyEngine()
        approvals = ApprovalEngine()
        decision = policy.evaluate(actor, f"external.{destination}", "route")

        if decision.decision == "deny":
            self._audit(
                "route.external.denied",
                actor,
                {
                    "destination": destination,
                    "purpose": purpose,
                    "risk": decision.risk,
                    "reason": decision.reason,
                },
            )
            raise PolicyDenied(
                decision,
                f"policy denied route to {destination!r}: {decision.reason}",
            )

        details = {"actor": actor, "destination": destination, "purpose": purpose}
        if policy.needs_approval(decision):
            # Atomic match-and-consume: exactly one concurrent caller can
            # win an approval — one approval mints at most one grant.
            approved = approvals.consume_approved("route.external", details)
            if approved is None:
                pending = self._match_approval(
                    approvals.list_all(), "route.external", details, "pending"
                )
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
                self._audit(
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
                    f"high-risk external route requires explicit human approval: "
                    f"{entry['id'][:8]} "
                    f"(approve with: levi cybrus approve {entry['id'][:8]} "
                    f"--identity <name>, then retry)",
                )

        token_id, plaintext = TokenEngine().issue(
            scopes=["route.external", f"destination:{destination}"],
            ttl_seconds=grant_ttl_seconds,
            kind="api",
            label=f"grant:{actor}->{destination}",
        )
        grant_id = uuid.uuid4().hex
        now = time.time()
        p = _paths()
        with p.store_lock(p.store_path(_GRANTS_STORE)):
            grants = self._load_store(_GRANTS_STORE)
            grants.append(
                {
                    "grant_id": grant_id,
                    "token_id": token_id,
                    "actor": actor,
                    "destination": destination,
                    "purpose": purpose,
                    "scopes": ["route.external", f"destination:{destination}"],
                    "issued_at": now,
                    "expires_at": now + grant_ttl_seconds,
                }
            )
            self._save_store(_GRANTS_STORE, grants)
        self._audit(
            "route.external.granted",
            actor,
            {
                "destination": destination,
                "purpose": purpose,
                "grant_id": grant_id[:8],
                "token_id": token_id[:8],
                "risk": decision.risk,
                "expires_in": grant_ttl_seconds,
            },
        )
        return {
            "grant_id": grant_id,
            "token": plaintext,
            "token_id": token_id,
            "actor": actor,
            "destination": destination,
            "purpose": purpose,
            "expires_at": now + grant_ttl_seconds,
        }

    def validate_grant(self, token: str) -> Optional[Dict]:
        """Validate a presented routing-grant token. Returns the binding
        ``{"grant_id", "actor", "destination", "purpose", "scopes",
        "expires_at"}`` or ``None`` when unknown / revoked / expired."""
        from levi.cybrus.tokens import TokenEngine

        payload = TokenEngine().validate(token)
        if payload is None:
            return None
        now = time.time()
        for grant in self._load_store(_GRANTS_STORE):
            if grant["token_id"] != payload["id"]:
                continue
            if grant["expires_at"] <= now:
                return None
            return {
                "grant_id": grant["grant_id"],
                "actor": grant["actor"],
                "destination": grant["destination"],
                "purpose": grant["purpose"],
                "scopes": list(grant["scopes"]),
                "expires_at": grant["expires_at"],
            }
        return None

    # -- HITL passthrough --------------------------------------------------

    def approve(self, approval_id: str, by: str = "owner") -> Dict:
        """Approve a pending HITL entry (the human gate)."""
        from levi.cybrus.approval import ApprovalEngine

        return ApprovalEngine().approve(approval_id, by=by)

    def deny(self, approval_id: str, reason: str = "", by: str = "owner") -> Dict:
        """Deny a pending HITL entry."""
        from levi.cybrus.approval import ApprovalEngine

        return ApprovalEngine().deny(approval_id, reason=reason, by=by)
