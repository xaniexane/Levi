"""Cybrus credential broker — the automated Bitwarden against third-party platforms.

LEVI-original, founder-grade. Where the vault stores LEVI's *own* secrets and
the gateway mints LEVI's *own* API keys, the broker reaches *outward*: it
provisions and tracks credentials the founder holds on third-party platforms,
records API keys fetched from those platforms' developer consoles, and runs
the OAuth2 authorization-code state machine against them.

Three responsibilities, one law — **every secret encrypted at rest, every
high-risk action human-gated**:

1. **Third-party account provisioning** — a provisioning *record* per
   external account: platform, signup URL, username, owning identity,
   lifecycle status (``provisioned`` → ``active`` → ``retired``). The broker
   generates the password (CSPRNG, via the vault's ``generate_password``)
   and stores it encrypted; the actual signup click on the external site is
   the operator's job — the broker tracks, it does not browse.

2. **External API-key records** — keys the founder fetched from a
   platform's developer console (or CLI, or API) are stored encrypted in
   the vault with label, scopes, and retrieval method. Retrieval is
   owner-only (containment by identity) and audit-logged with metadata only.

3. **OAuth2 flow state machine** — pure logic, no network: ``initiated``
   (authorization URL + PKCE generated) → ``authorized`` (callback code
   captured, CSRF state verified) → ``active`` (tokens stored) →
   ``refreshed``. The HTTP exchanges themselves happen in the operator's
   browser; the broker owns the state, the PKCE verifier, the encrypted
   token storage (via the existing ``OAuthVault``), and the refresh
   scheduling data (``refresh_due_at``).

Approval + audit: provisioning, key store/retrieve, rotation, retirement,
OAuth start, token store, and refresh all pass through the
:class:`~levi.cybrus.approval.ApprovalEngine` human gate (single-use
consumption, same pattern as the gateway) and append metadata-only records
to the :class:`~levi.cybrus.audit.AuditEngine` tamper-evident log. No secret
— password, key, verifier, auth code, token — ever lands in a JSON store, an
audit record, or stdout, except the deliberate exactly-once issuance prints
the CLI performs for freshly generated passwords.

HONEST BOUNDARIES (read before wiring this to anything real):
- This module performs NO network calls and drives NO browser. The live
  signup, the console key copy, and the OAuth code exchange are the
  operator's hands; the broker is the memory and the gate around them.
- ``refresh_due_at`` is scheduling *data*, not a scheduler — something else
  must wake up and call :meth:`oauth_refresh` with freshly exchanged tokens.
- Like the rest of Cybrus, this is stdlib-only; PKCE uses SHA-256/S256 only.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


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


# --- vault service namespaces (encrypted at rest) ---------------------------
_ACCOUNTS_VAULT_PREFIX = "cybrus.broker.accounts"
_KEYS_VAULT_PREFIX = "cybrus.broker.keys"
_OAUTH_VAULT_PREFIX = "cybrus.broker.oauth"

# --- metadata stores (JSON, metadata only — never secrets) -------------------
_ACCOUNTS_STORE = "broker_accounts"
_APIKEYS_STORE = "broker_apikeys"
_FLOWS_STORE = "broker_oauth_flows"

#: How early (seconds) before token expiry a refresh is considered due.
REFRESH_SAFETY_MARGIN_SECONDS = 300

#: Allowed API-key retrieval methods (how the founder obtained the key).
KEY_RETRIEVAL_METHODS = ("console", "cli", "api", "import")

#: OAuth2 flow states and their legal transitions.
_FLOW_TRANSITIONS = {
    "initiated": ("authorized", "abandoned"),
    "authorized": ("active", "abandoned"),
    "active": ("refreshed", "abandoned"),
    "refreshed": ("refreshed", "abandoned"),
    "abandoned": (),
}


class BrokerError(Exception):
    """Base class for broker failures (validation, state, containment)."""


class BrokerApprovalRequired(BrokerError):
    """A high-risk broker action is blocked pending human approval.

    Carries the pending ``approval_id`` — a verified human approves it with
    ``levi cybrus approve <id> --identity <name>`` and the action is
    retried. Approvals are single-use: one approval completes at most one
    action.
    """

    def __init__(self, approval_id: str, message: str):
        super().__init__(message)
        self.approval_id = approval_id


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short(value: str) -> str:
    return value[:8]


def _clean_name(value: str, what: str) -> str:
    """Validate an identifier (platform / identity / label / username).

    Same character rule as the vault: 1-64 chars of [A-Za-z0-9._-].
    """
    from levi.cybrus.vault import VaultError, _sanitize

    try:
        return _sanitize(value, what)
    except VaultError as exc:
        raise BrokerError(str(exc)) from exc


def _clean_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BrokerError("signup_url must be a non-empty string")
    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise BrokerError(
            f"signup_url must be an http(s) URL, got {value!r}"
        )
    return value


def _audit(event: str, actor: str, details: Optional[Dict] = None) -> None:
    """Append a broker audit record. ``details`` must NEVER contain secret
    material — callers pass names, platforms, scopes, never values."""
    from levi.cybrus.audit import AuditEngine

    AuditEngine().append(event, str(actor), dict(details or {}))


def _pending_match(approvals, action: str, details: Dict) -> Optional[Dict]:
    """Find a still-pending entry matching ``action`` + ``details`` (same
    reuse-pending pattern the gateway uses before requesting a fresh one).

    BLUE (RED-1): EXACT detail match — subset matching would let a
    plainer request reuse a pending approval that carries human-added
    restriction metadata.
    """
    for entry in approvals.list_all():
        if entry.get("action") != action or entry.get("status") != "pending":
            continue
        entry_details = entry.get("details") or {}
        if entry_details != details:
            continue
        return entry
    return None


def _require_approval(action: str, subject: str, resource: str, details: Dict) -> Dict:
    """The human gate for broker actions: consume a matching approved entry
    (single-use, atomic), or raise :class:`BrokerApprovalRequired` carrying
    a pending approval id (reusing an existing pending entry when one
    matches, else requesting a fresh one)."""
    from levi.cybrus.approval import ApprovalEngine

    approvals = ApprovalEngine()
    approved = approvals.consume_approved(action, details)
    if approved is not None:
        return approved
    pending = _pending_match(approvals, action, details)
    entry = (
        pending
        if pending is not None
        else approvals.request_approval(action, subject, resource, "high", details=details)
    )
    _audit(
        "broker.approval_required",
        subject,
        {"action": action, "resource": resource, "approval_id": _short(entry["id"])},
    )
    raise BrokerApprovalRequired(
        entry["id"],
        f"high-risk broker action {action!r} needs a verified human: "
        f"approve {_short(entry['id'])} "
        f"(levi cybrus approve {_short(entry['id'])} --identity <you>), "
        "then retry",
    )


class CredentialBroker:
    """The third-party credential broker: provisioned external accounts,
    external API-key records, and the OAuth2 flow state machine.

    Construct with the vault master passphrase; the broker opens the
    encrypted vault lazily and keeps no secrets in its own attributes.
    ``identity`` is the default owning identity when callers do not pass
    one explicitly.
    """

    def __init__(self, vault_passphrase: str, identity: Optional[str] = None):
        if not isinstance(vault_passphrase, str) or not vault_passphrase:
            raise BrokerError("vault passphrase is required (non-empty string)")
        self._passphrase = vault_passphrase
        self._identity = _clean_name(identity, "identity") if identity else None
        self._vault = None
        self._oauth_vault = None

    # -- internals ---------------------------------------------------------

    def _vault_instance(self):
        if self._vault is None:
            from levi.cybrus.vault import CredentialVault

            self._vault = CredentialVault(self._passphrase)
        return self._vault

    def _oauth_vault_instance(self):
        if self._oauth_vault is None:
            from levi.cybrus.vault import OAuthVault

            self._oauth_vault = OAuthVault(self._passphrase)
        return self._oauth_vault

    def _actor_identity(self, identity: Optional[str]) -> str:
        # BLUE (RED-1, L1 — forged caller identity): the broker accepts
        # caller-asserted identities and cannot verify them, so a founder
        # name must never be asserted here — wearing it rides the
        # founder's quota exemption past the ACCOUNT_CREATE gate.
        # Founder work goes through the authenticated gateway path
        # (auth() session), not the broker.
        from levi.cybrus.identity import is_founder_identity

        if identity is not None:
            resolved = _clean_name(identity, "identity")
        elif self._identity is not None:
            resolved = self._identity
        else:
            raise BrokerError("identity is required (no default identity configured)")
        if is_founder_identity(resolved):
            raise BrokerError(
                f"identity {resolved!r} is a founder identity: the broker "
                "cannot verify asserted identities, so founder names are "
                "refused here. Remedy: provision under your own service "
                "identity, or act as the founder through the authenticated "
                "gateway path (auth() session)."
            )
        return resolved

    @staticmethod
    def _load_store(name: str) -> List[Dict]:
        data = _paths().load_json_store(_paths().store_path(name))
        return data if isinstance(data, list) else []

    @staticmethod
    def _save_store(name: str, payload: List[Dict]) -> None:
        # Lock-free: the caller must hold the store lock (same pattern as
        # the gateway) — flock() on an already-held lock file would block.
        p = _paths()
        p.save_json_store(p.store_path(name), payload)

    @staticmethod
    def _accounts_service(platform: str) -> str:
        return f"{_ACCOUNTS_VAULT_PREFIX}.{_clean_name(platform, 'platform')}"

    @staticmethod
    def _keys_service(platform: str) -> str:
        return f"{_KEYS_VAULT_PREFIX}.{_clean_name(platform, 'platform')}"

    @staticmethod
    def _oauth_service(platform: str) -> str:
        return f"{_OAUTH_VAULT_PREFIX}.{_clean_name(platform, 'platform')}"

    # -- third-party account provisioning ----------------------------------

    def provision(
        self,
        platform: str,
        signup_url: str,
        identity: Optional[str] = None,
        username: Optional[str] = None,
    ):
        """Provision a third-party account record.

        Human-gated (``broker.provision``). Generates a strong password via
        the vault's CSPRNG generator, stores it encrypted, and records the
        account metadata with status ``provisioned``. Returns
        ``(record, plaintext_password)`` — the password is shown exactly
        once by the caller and never logged.

        The actual signup on the external site is the operator's job (the
        broker does not browse); call :meth:`activate` once the signup is
        confirmed on the site.
        """
        from levi.cybrus.vault import generate_password

        platform = _clean_name(platform, "platform")
        signup_url = _clean_url(signup_url)
        identity = self._actor_identity(identity)
        username = _clean_name(username, "username") if username else identity

        details = {"identity": identity, "platform": platform, "username": username}
        _require_approval("broker.provision", identity, f"thirdparty.{platform}", details)
        # RQ-2026-09-21: tier-based anti-spam gate (after approval = point of
        # no return, so approval-pending attempts never consume quota)
        from levi.cybrus import rate_limits as _rate_limits
        _rate_limits.check(identity, _rate_limits.ACCOUNT_CREATE)

        p = _paths()
        with p.store_lock(p.store_path(_ACCOUNTS_STORE)):
            accounts = self._load_store(_ACCOUNTS_STORE)
            for acc in accounts:
                if (
                    acc["platform"] == platform
                    and acc["username"] == username
                    and acc["status"] in ("provisioned", "active")
                ):
                    raise BrokerError(
                        f"account already provisioned for {platform!r}/{username!r} "
                        f"(id {_short(acc['id'])}, status {acc['status']!r})"
                    )
            password = generate_password()
            self._vault_instance().store(
                self._accounts_service(platform), username, password
            )
            record = {
                "id": uuid.uuid4().hex,
                "platform": platform,
                "signup_url": signup_url,
                "username": username,
                "identity": identity,
                "status": "provisioned",
                "created_at": _utcnow_iso(),
                "activated_at": None,
                "retired_at": None,
                "password_rotated_at": None,
            }
            accounts.append(record)
            self._save_store(_ACCOUNTS_STORE, accounts)
        _audit(
            "broker.account.provisioned",
            identity,
            {
                "account_id": _short(record["id"]),
                "platform": platform,
                "username": username,
            },
        )
        return dict(record), password

    def _find_account(self, account_id: str) -> Dict:
        for acc in self._load_store(_ACCOUNTS_STORE):
            if acc["id"] == account_id:
                return acc
        raise BrokerError(f"unknown broker account id: {_short(account_id)}")

    def get_account(self, account_id: str) -> Dict:
        """Account metadata (never secrets — the store holds none)."""
        return dict(self._find_account(account_id))

    def list_accounts(self, identity: Optional[str] = None) -> List[Dict]:
        """Provisioning records, optionally filtered by owning identity.
        Metadata only."""
        if identity is not None:
            # BLUE (RED-1): route asserted identities through the founder
            # refusal in _actor_identity.
            identity = self._actor_identity(identity)
        return [
            dict(acc)
            for acc in sorted(
                self._load_store(_ACCOUNTS_STORE), key=lambda a: a["created_at"]
            )
            if identity is None or acc["identity"] == identity
        ]

    def activate(self, account_id: str, identity: Optional[str] = None) -> Dict:
        """Mark a provisioned account ``active`` — the operator's
        confirmation that the signup actually completed on the external
        site. Bookkeeping, not gated; audit-logged."""
        identity = self._actor_identity(identity)
        p = _paths()
        with p.store_lock(p.store_path(_ACCOUNTS_STORE)):
            accounts = self._load_store(_ACCOUNTS_STORE)
            record = next((a for a in accounts if a["id"] == account_id), None)
            if record is None:
                raise BrokerError(f"unknown broker account id: {_short(account_id)}")
            if record["identity"] != identity:
                raise BrokerError(
                    f"containment: {identity!r} may not activate "
                    f"{record['identity']!r}'s account"
                )
            if record["status"] != "provisioned":
                raise BrokerError(
                    f"cannot activate account {_short(account_id)}: status is "
                    f"{record['status']!r}, expected 'provisioned'"
                )
            record["status"] = "active"
            record["activated_at"] = _utcnow_iso()
            self._save_store(_ACCOUNTS_STORE, accounts)
        _audit(
            "broker.account.activated",
            identity,
            {"account_id": _short(account_id), "platform": record["platform"]},
        )
        return dict(record)

    def rotate(self, account_id: str, identity: Optional[str] = None):
        """Rotate an account's password. Human-gated (``broker.rotate``).
        Returns ``(record, new_plaintext_password)`` — shown exactly once,
        never logged."""
        from levi.cybrus.vault import generate_password

        identity = self._actor_identity(identity)
        record = self._find_account(account_id)
        if record["identity"] != identity:
            raise BrokerError(
                f"containment: {identity!r} may not rotate {record['identity']!r}'s account"
            )
        if record["status"] == "retired":
            raise BrokerError(
                f"cannot rotate retired account {_short(account_id)}"
            )
        details = {
            "identity": identity,
            "platform": record["platform"],
            "account_id": account_id,
        }
        _require_approval(
            "broker.rotate", identity, f"thirdparty.{record['platform']}", details
        )
        new_password = generate_password()
        self._vault_instance().store(
            self._accounts_service(record["platform"]), record["username"], new_password
        )
        p = _paths()
        with p.store_lock(p.store_path(_ACCOUNTS_STORE)):
            accounts = self._load_store(_ACCOUNTS_STORE)
            for acc in accounts:
                if acc["id"] == account_id:
                    acc["password_rotated_at"] = _utcnow_iso()
                    record = dict(acc)
                    break
            self._save_store(_ACCOUNTS_STORE, accounts)
        _audit(
            "broker.account.rotated",
            identity,
            {"account_id": _short(account_id), "platform": record["platform"]},
        )
        return record, new_password

    def retire(self, account_id: str, identity: Optional[str] = None) -> Dict:
        """Retire an account: delete its vault password, mark the record
        ``retired`` (the record itself is kept for the audit trail — nothing
        is thrown away). Human-gated (``broker.retire``)."""
        identity = self._actor_identity(identity)
        record = self._find_account(account_id)
        if record["identity"] != identity:
            raise BrokerError(
                f"containment: {identity!r} may not retire {record['identity']!r}'s account"
            )
        details = {
            "identity": identity,
            "platform": record["platform"],
            "account_id": account_id,
        }
        _require_approval(
            "broker.retire", identity, f"thirdparty.{record['platform']}", details
        )
        try:
            self._vault_instance().delete(
                self._accounts_service(record["platform"]), record["username"]
            )
        except KeyError:
            pass  # already gone from the vault; the record still retires
        p = _paths()
        with p.store_lock(p.store_path(_ACCOUNTS_STORE)):
            accounts = self._load_store(_ACCOUNTS_STORE)
            for acc in accounts:
                if acc["id"] == account_id:
                    acc["status"] = "retired"
                    acc["retired_at"] = _utcnow_iso()
                    record = dict(acc)
                    break
            self._save_store(_ACCOUNTS_STORE, accounts)
        _audit(
            "broker.account.retired",
            identity,
            {"account_id": _short(account_id), "platform": record["platform"]},
        )
        return record

    # -- external API-key records ------------------------------------------

    def store_key(
        self,
        platform: str,
        label: str,
        key_material: str,
        identity: Optional[str] = None,
        scopes=(),
        retrieval_method: str = "console",
    ) -> Dict:
        """Record an API key fetched from a third-party platform's developer
        console (or CLI/API/import). Human-gated (``broker.apikey.store``).
        The key is encrypted in the vault; the registry holds metadata only.
        Returns the metadata record."""
        platform = _clean_name(platform, "platform")
        label = _clean_name(label, "label")
        identity = self._actor_identity(identity)
        if not isinstance(key_material, str) or not key_material:
            raise BrokerError("key_material must be a non-empty string")
        if retrieval_method not in KEY_RETRIEVAL_METHODS:
            raise BrokerError(
                f"retrieval_method must be one of {KEY_RETRIEVAL_METHODS}, "
                f"got {retrieval_method!r}"
            )
        clean_scopes = self._clean_scopes(scopes)
        details = {"identity": identity, "platform": platform, "label": label}
        _require_approval(
            "broker.apikey.store", identity, f"thirdparty.{platform}", details
        )
        p = _paths()
        with p.store_lock(p.store_path(_APIKEYS_STORE)):
            registry = self._load_store(_APIKEYS_STORE)
            for entry in registry:
                if (
                    entry["platform"] == platform
                    and entry["label"] == label
                    and entry["identity"] == identity
                    and entry["status"] == "active"
                ):
                    raise BrokerError(
                        f"api key already recorded for {platform!r}/{label!r} "
                        f"(id {_short(entry['id'])})"
                    )
            self._vault_instance().store(
                self._keys_service(platform), label, key_material
            )
            record = {
                "id": uuid.uuid4().hex,
                "platform": platform,
                "label": label,
                "identity": identity,
                "scopes": clean_scopes,
                "retrieval_method": retrieval_method,
                "status": "active",
                "created_at": _utcnow_iso(),
                "revoked_at": None,
            }
            registry.append(record)
            self._save_store(_APIKEYS_STORE, registry)
        _audit(
            "broker.apikey.stored",
            identity,
            {
                "key_id": _short(record["id"]),
                "platform": platform,
                "label": label,
                "scopes": clean_scopes,
                "retrieval_method": retrieval_method,
            },
        )
        return dict(record)

    @staticmethod
    def _clean_scopes(scopes) -> List[str]:
        if scopes is None:
            return []
        if not isinstance(scopes, (list, tuple)):
            raise BrokerError("scopes must be a list of strings")
        clean = []
        for s in scopes:
            if not isinstance(s, str) or not s.strip():
                raise BrokerError("scopes must be non-empty strings")
            clean.append(s.strip())
        return clean

    def _find_key(self, label: str, identity: str) -> Dict:
        for entry in self._load_store(_APIKEYS_STORE):
            if (
                entry["label"] == label
                and entry["identity"] == identity
                and entry["status"] == "active"
            ):
                return entry
        raise BrokerError(
            f"unknown active api key {label!r} for identity {identity!r}"
        )

    def retrieve_key(
        self, label: str, identity: Optional[str] = None, requester: Optional[str] = None
    ) -> str:
        """Retrieve a recorded third-party API key. Human-gated
        (``broker.apikey.retrieve``) and containment-checked: ``requester``
        must equal the owning identity. Audit-logged with metadata only.
        Returns the key material (the owner's own secret — handle it like a
        password-manager reveal)."""
        label = _clean_name(label, "label")
        identity = self._actor_identity(identity)
        requester = _clean_name(requester, "requester") if requester else identity
        if requester != identity:
            raise BrokerError(
                f"containment: {requester!r} may not retrieve {identity!r}'s api keys"
            )
        record = self._find_key(label, identity)
        details = {"identity": identity, "platform": record["platform"], "label": label}
        _require_approval(
            "broker.apikey.retrieve", identity, f"thirdparty.{record['platform']}", details
        )
        # RQ-2026-09-21: tier-based anti-spam gate (after approval = point of no return)
        from levi.cybrus import rate_limits as _rate_limits
        _rate_limits.check(identity, _rate_limits.API_KEY_FETCH)
        key_material = self._vault_instance().get(
            self._keys_service(record["platform"]), label
        )
        _audit(
            "broker.apikey.retrieved",
            identity,
            {
                "key_id": _short(record["id"]),
                "platform": record["platform"],
                "label": label,
            },
        )
        return key_material

    def list_keys(self, identity: Optional[str] = None) -> List[Dict]:
        """API-key metadata — platforms, labels, scopes, methods. Key values
        are never listed."""
        if identity is not None:
            # BLUE (RED-1): route asserted identities through the founder
            # refusal in _actor_identity.
            identity = self._actor_identity(identity)
        return [
            dict(entry)
            for entry in sorted(
                self._load_store(_APIKEYS_STORE), key=lambda e: e["created_at"]
            )
            if identity is None or entry["identity"] == identity
        ]

    def revoke_key(self, label: str, identity: Optional[str] = None) -> Dict:
        """Revoke a recorded API key: delete the vault entry, mark the
        registry entry ``revoked`` (kept for the trail). Human-gated
        (``broker.apikey.revoke``)."""
        label = _clean_name(label, "label")
        identity = self._actor_identity(identity)
        record = self._find_key(label, identity)
        details = {"identity": identity, "platform": record["platform"], "label": label}
        _require_approval(
            "broker.apikey.revoke", identity, f"thirdparty.{record['platform']}", details
        )
        try:
            self._vault_instance().delete(self._keys_service(record["platform"]), label)
        except KeyError:
            pass
        p = _paths()
        with p.store_lock(p.store_path(_APIKEYS_STORE)):
            registry = self._load_store(_APIKEYS_STORE)
            for entry in registry:
                if entry["id"] == record["id"]:
                    entry["status"] = "revoked"
                    entry["revoked_at"] = _utcnow_iso()
                    record = dict(entry)
                    break
            self._save_store(_APIKEYS_STORE, registry)
        _audit(
            "broker.apikey.revoked",
            identity,
            {
                "key_id": _short(record["id"]),
                "platform": record["platform"],
                "label": label,
            },
        )
        return record

    # -- OAuth2 flow state machine ------------------------------------------

    @staticmethod
    def _pkce_pair():
        """(verifier, S256 challenge). The verifier is the secret — it lives
        in the encrypted vault, never in the flow store."""
        verifier = secrets.token_urlsafe(64)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("utf-8")).digest())
            .rstrip(b"=")
            .decode("ascii")
        )
        return verifier, challenge

    @staticmethod
    def _authorization_url(authorize_url: str, params: Dict[str, str]) -> str:
        if not isinstance(authorize_url, str) or not authorize_url.strip():
            raise BrokerError("authorize_url must be a non-empty string")
        parsed = urlparse(authorize_url.strip())
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise BrokerError(
                f"authorize_url must be an http(s) URL, got {authorize_url!r}"
            )
        query = dict(parse_qsl(parsed.query))
        query.update(params)
        return urlunparse(parsed._replace(query=urlencode(query)))

    def _find_flow(self, flow_id: str) -> Dict:
        for flow in self._load_store(_FLOWS_STORE):
            if flow["id"] == flow_id:
                return flow
        raise BrokerError(f"unknown oauth flow id: {_short(flow_id)}")

    @staticmethod
    def _transition(flow: Dict, to_state: str) -> None:
        allowed = _FLOW_TRANSITIONS.get(flow["status"], ())
        if to_state not in allowed:
            raise BrokerError(
                f"illegal oauth flow transition: {flow['status']!r} -> {to_state!r} "
                f"(flow {_short(flow['id'])})"
            )

    def _save_flow(self, updated: Dict) -> None:
        p = _paths()
        with p.store_lock(p.store_path(_FLOWS_STORE)):
            flows = self._load_store(_FLOWS_STORE)
            for i, flow in enumerate(flows):
                if flow["id"] == updated["id"]:
                    flows[i] = updated
                    break
            else:
                flows.append(updated)
            self._save_store(_FLOWS_STORE, flows)

    def _clear_flow_secrets(self, platform: str, short: str) -> None:
        """Single-use scratch secrets (verifier, auth code) are wiped from
        the vault once consumed. Best-effort: missing entries are ignored."""
        service = self._oauth_service(platform)
        for suffix in ("verifier", "code"):
            try:
                self._vault_instance().delete(service, f"{short}.{suffix}")
            except KeyError:
                pass

    def oauth_start(
        self,
        platform: str,
        client_id: str,
        authorize_url: str,
        redirect_uri: str,
        identity: Optional[str] = None,
        scopes=(),
    ) -> Dict:
        """Begin an OAuth2 authorization-code flow (PKCE/S256).

        Human-gated (``broker.oauth.start``). Generates the PKCE
        verifier/challenge pair and the CSRF ``state``; the verifier is
        stored encrypted in the vault (single-use scratch), the flow record
        holds metadata only. Returns ``{"flow_id", "authorization_url",
        "state"}`` — open ``authorization_url`` in the operator's browser
        and feed the redirect's ``code`` to :meth:`oauth_callback`.

        No network is touched here; this is the state machine, not an HTTP
        client.
        """
        platform = _clean_name(platform, "platform")
        identity = self._actor_identity(identity)
        if not isinstance(client_id, str) or not client_id.strip():
            raise BrokerError("client_id must be a non-empty string")
        redirect_uri = _clean_url(redirect_uri)
        clean_scopes = self._clean_scopes(scopes)

        details = {"identity": identity, "platform": platform}
        _require_approval(
            "broker.oauth.start", identity, f"thirdparty.{platform}", details
        )
        # RQ-2026-09-21: tier-based anti-spam gate + one in-flight OAuth flow
        # per user (after approval = point of no return)
        from levi.cybrus import rate_limits as _rate_limits
        _rate_limits.check(identity, _rate_limits.OAUTH_INITIATE)
        _rate_limits.acquire_flow(identity)

        flow_id = uuid.uuid4().hex
        short = _short(flow_id)
        verifier, challenge = self._pkce_pair()
        state = secrets.token_urlsafe(24)
        params = {
            "response_type": "code",
            "client_id": client_id.strip(),
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        if clean_scopes:
            params["scope"] = " ".join(clean_scopes)
        authorization_url = self._authorization_url(authorize_url, params)

        self._vault_instance().store(
            self._oauth_service(platform), f"{short}.verifier", verifier
        )
        flow = {
            "id": flow_id,
            "platform": platform,
            "identity": identity,
            "client_id": client_id.strip(),
            "redirect_uri": redirect_uri,
            "scopes": clean_scopes,
            "state": state,
            "status": "initiated",
            "created_at": _utcnow_iso(),
            "authorized_at": None,
            "tokenized_at": None,
            "refresh_due_at": None,
        }
        self._save_flow(flow)
        _audit(
            "broker.oauth.started",
            identity,
            {
                "flow_id": short,
                "platform": platform,
                "scopes": clean_scopes,
            },
        )
        return {
            "flow_id": flow_id,
            "authorization_url": authorization_url,
            "state": state,
        }

    def oauth_callback(
        self,
        flow_id: str,
        code: str,
        returned_state: str,
        identity: Optional[str] = None,
    ) -> Dict:
        """Capture the authorization ``code`` from the provider redirect.

        Verifies the CSRF ``state`` (fail closed on mismatch), stores the
        single-use code encrypted in the vault, and moves the flow
        ``initiated`` → ``authorized``. The code is never written to the
        flow store or the audit log. Next: the operator exchanges the code
        for tokens (in their browser / client) and calls
        :meth:`oauth_complete` with what the provider returned.
        """
        identity = self._actor_identity(identity)
        if not isinstance(code, str) or not code:
            raise BrokerError("code must be a non-empty string")
        flow = self._find_flow(flow_id)
        if flow["identity"] != identity:
            raise BrokerError(
                f"containment: {identity!r} may not drive {flow['identity']!r}'s flow"
            )
        self._transition(flow, "authorized")
        if not secrets.compare_digest(str(returned_state or ""), flow["state"]):
            raise BrokerError(
                f"oauth state mismatch on flow {_short(flow_id)}: possible CSRF — "
                "refusing to capture the code"
            )
        self._vault_instance().store(
            self._oauth_service(flow["platform"]), f"{_short(flow_id)}.code", code
        )
        flow["status"] = "authorized"
        flow["authorized_at"] = _utcnow_iso()
        self._save_flow(flow)
        _audit(
            "broker.oauth.callback",
            identity,
            {"flow_id": _short(flow_id), "platform": flow["platform"]},
        )
        return {
            "flow_id": flow_id,
            "status": flow["status"],
            "platform": flow["platform"],
        }

    def oauth_complete(
        self,
        flow_id: str,
        identity: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None,
        scopes=None,
    ) -> Dict:
        """Store the token set from a completed code exchange.

        Human-gated (``broker.oauth.token_store``). The operator performed
        the exchange against the provider elsewhere and hands the resulting
        tokens here; they are stored encrypted via the existing
        ``OAuthVault`` (the single token store of record), the single-use
        verifier + code are wiped from the vault, and the flow moves
        ``authorized`` → ``active`` with ``refresh_due_at`` scheduling data.
        Returns token metadata only — never token values.
        """
        from levi.cybrus.vault import OAuthError

        identity = self._actor_identity(identity)
        if not isinstance(access_token, str) or not access_token:
            raise BrokerError("access_token must be a non-empty string")
        if expires_in is not None and (
            not isinstance(expires_in, int)
            or isinstance(expires_in, bool)
            or expires_in <= 0
        ):
            raise BrokerError("expires_in must be a positive integer or None")
        flow = self._find_flow(flow_id)
        if flow["identity"] != identity:
            raise BrokerError(
                f"containment: {identity!r} may not complete {flow['identity']!r}'s flow"
            )
        self._transition(flow, "active")
        details = {"identity": identity, "platform": flow["platform"], "flow_id": flow_id}
        _require_approval(
            "broker.oauth.token_store",
            identity,
            f"thirdparty.{flow['platform']}",
            details,
        )
        granted_scopes = self._clean_scopes(scopes) if scopes is not None else flow["scopes"]
        try:
            meta = self._oauth_vault_instance().store_token(
                flow["platform"],
                identity,
                access_token,
                refresh_token=refresh_token,
                scopes=granted_scopes,
                expires_in=expires_in,
            )
        except OAuthError as exc:
            raise BrokerError(str(exc)) from exc
        self._clear_flow_secrets(flow["platform"], _short(flow_id))
        flow["status"] = "active"
        flow["tokenized_at"] = _utcnow_iso()
        flow["refresh_due_at"] = (
            time.time() + expires_in - REFRESH_SAFETY_MARGIN_SECONDS
            if expires_in is not None
            else None
        )
        self._save_flow(flow)
        _audit(
            "broker.oauth.token_stored",
            identity,
            {
                "flow_id": _short(flow_id),
                "platform": flow["platform"],
                "scopes": granted_scopes,
                "expires_in": expires_in,
                "has_refresh_token": refresh_token is not None,
            },
        )
        # RQ-2026-09-21: release the in-flight OAuth flow slot
        from levi.cybrus import rate_limits as _rate_limits
        _rate_limits.release_flow(identity)
        return {
            "flow_id": flow_id,
            "status": flow["status"],
            "platform": flow["platform"],
            "identity": identity,
            "scopes": meta["scopes"],
            "expires_at": meta["expires_at"],
            "refresh_due_at": flow["refresh_due_at"],
        }

    def oauth_refresh(
        self,
        flow_id: str,
        identity: Optional[str] = None,
        new_access_token: Optional[str] = None,
        new_refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None,
    ) -> Dict:
        """Record a token refresh the operator performed against the
        provider. Human-gated (``broker.oauth.refresh``). Moves the flow to
        ``refreshed`` (repeatable), bumps the refresh count in the token
        store, and recomputes ``refresh_due_at``. No network is touched —
        the exchange is the operator's job; this is the state + storage."""
        from levi.cybrus.vault import OAuthError

        identity = self._actor_identity(identity)
        if not isinstance(new_access_token, str) or not new_access_token:
            raise BrokerError("new_access_token must be a non-empty string")
        flow = self._find_flow(flow_id)
        if flow["identity"] != identity:
            raise BrokerError(
                f"containment: {identity!r} may not refresh {flow['identity']!r}'s flow"
            )
        self._transition(flow, "refreshed")
        details = {"identity": identity, "platform": flow["platform"], "flow_id": flow_id}
        _require_approval(
            "broker.oauth.refresh", identity, f"thirdparty.{flow['platform']}", details
        )
        # RQ-2026-09-21: tier-based anti-spam gate (after approval = point of no return)
        from levi.cybrus import rate_limits as _rate_limits
        _rate_limits.check(identity, _rate_limits.OAUTH_REFRESH)
        try:
            meta = self._oauth_vault_instance().record_refresh(
                flow["platform"],
                identity,
                requester=identity,
                new_access_token=new_access_token,
                new_refresh_token=new_refresh_token,
                expires_in=expires_in,
            )
        except OAuthError as exc:
            raise BrokerError(str(exc)) from exc
        flow["status"] = "refreshed"
        flow["refresh_due_at"] = (
            time.time() + expires_in - REFRESH_SAFETY_MARGIN_SECONDS
            if expires_in is not None
            else None
        )
        self._save_flow(flow)
        _audit(
            "broker.oauth.refreshed",
            identity,
            {
                "flow_id": _short(flow_id),
                "platform": flow["platform"],
                "refresh_count": meta["refresh_count"],
            },
        )
        return {
            "flow_id": flow_id,
            "status": flow["status"],
            "platform": flow["platform"],
            "refresh_count": meta["refresh_count"],
            "refresh_due_at": flow["refresh_due_at"],
        }

    def oauth_abandon(self, flow_id: str, identity: Optional[str] = None) -> Dict:
        """Abandon an in-flight flow: wipe its scratch secrets from the
        vault and mark it ``abandoned``. The safe direction — ungated, but
        audit-logged."""
        identity = self._actor_identity(identity)
        flow = self._find_flow(flow_id)
        if flow["identity"] != identity:
            raise BrokerError(
                f"containment: {identity!r} may not abandon {flow['identity']!r}'s flow"
            )
        self._transition(flow, "abandoned")
        self._clear_flow_secrets(flow["platform"], _short(flow_id))
        flow["status"] = "abandoned"
        self._save_flow(flow)
        _audit(
            "broker.oauth.abandoned",
            identity,
            {"flow_id": _short(flow_id), "platform": flow["platform"]},
        )
        # RQ-2026-09-21: release the in-flight OAuth flow slot
        from levi.cybrus import rate_limits as _rate_limits
        _rate_limits.release_flow(identity)
        return {"flow_id": flow_id, "status": flow["status"]}

    def flow_needs_refresh(self, flow_id: str, identity: Optional[str] = None) -> bool:
        """True when the flow holds tokens whose ``refresh_due_at`` has
        passed — the scheduling predicate a refresh driver polls."""
        identity = self._actor_identity(identity)
        flow = self._find_flow(flow_id)
        if flow["identity"] != identity:
            raise BrokerError(
                f"containment: {identity!r} may not inspect {flow['identity']!r}'s flow"
            )
        due_at = flow.get("refresh_due_at")
        if due_at is None:
            return False
        return time.time() >= float(due_at)

    def oauth_status(self, identity: Optional[str] = None) -> List[Dict]:
        """Flow metadata — states, scopes, token expiry, refresh-due flags.
        Never token values."""
        if identity is not None:
            # BLUE (RED-1): route asserted identities through the founder
            # refusal in _actor_identity.
            identity = self._actor_identity(identity)
        out = []
        for flow in sorted(
            self._load_store(_FLOWS_STORE), key=lambda f: f["created_at"]
        ):
            if identity is not None and flow["identity"] != identity:
                continue
            out.append(
                {
                    "flow_id": flow["id"],
                    "platform": flow["platform"],
                    "identity": flow["identity"],
                    "status": flow["status"],
                    "scopes": list(flow["scopes"]),
                    "created_at": flow["created_at"],
                    "tokenized_at": flow["tokenized_at"],
                    "refresh_due_at": flow["refresh_due_at"],
                    "needs_refresh": self.flow_needs_refresh(flow["id"], flow["identity"]),
                }
            )
        return out

    # -- overview ----------------------------------------------------------

    def status(self, identity: Optional[str] = None) -> Dict:
        """Broker overview: counts of accounts / keys / flows and how many
        flows are refresh-due. Metadata only."""
        accounts = self.list_accounts(identity=identity)
        keys = self.list_keys(identity=identity)
        flows = self.oauth_status(identity=identity)
        by_status: Dict[str, int] = {}
        for flow in flows:
            by_status[flow["status"]] = by_status.get(flow["status"], 0) + 1
        return {
            "accounts": len(accounts),
            "api_keys": len(keys),
            "oauth_flows": len(flows),
            "oauth_by_status": by_status,
            "oauth_refresh_due": sum(1 for f in flows if f["needs_refresh"]),
        }
