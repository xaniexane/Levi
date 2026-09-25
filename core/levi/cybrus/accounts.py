"""Cybrus account-action gateway — RIGHT direction (accounts + money).

Chauncey's mandate: *Cybrus is his guard on all four sides. RIGHT is
accounts + money: Gmail, OneDrive, GitHub, financial accounts. Credential
use and money movements go through the gateway and the audit log. NOTHING
moves silently.*

RIGHT LAWS (binding — what must always hold):
  R1  Every credential use goes through this gateway. No credential
      leaves the vault without a grant receipt: ``use_credential()`` mints
      a bound, short-lived grant first, reads the vault second, and
      appends a metadata-only receipt to the hash-chained audit log.
      Account credentials live under the vault namespace
      ``cybrus.accounts.<account_id>`` — only this module reads them;
      any other reader is a silent-movement violation (see sentry.py).
  R2  Every external account action (email send, drive/github operations,
      financial account reads/writes) routes through
      ``request_account_action()`` / ``execute_account_action()`` under a
      per-account grant. There is no sanctioned path around the gateway.
  R3  Sensitive scopes (``email.send``, ``account.write``,
      ``account.delete``, ``financial.read``, ``financial.write``,
      ``money.move``) require a human approval: the request raises
      :class:`AccountApprovalRequired` immediately carrying a resumable
      approval id (L11 forward-motion — the choke point never blocks).
      Approvals are single-use and consumed atomically (L5); a consumed,
      expired, denied, or plan-rebound approval is refused, not retried.
  R4  Policy deny always wins (L3): a suspended account, an unknown scope,
      or a forged/expired grant is refused — no approval overrides a deny.
  R5  Grants are bound (account, scope, actor, purpose, expiry) and
      single-use: one grant authorizes at most one
      ``execute_account_action()`` call. Grants expire after
      ``GRANT_TTL_SECONDS``; expiry is fail-closed.
  R6  Audit records carry metadata only — account id, scope, actor,
      grant id, approval id, decision (L4). Never secrets, never
      credentials, never message bodies.
  R7  State only grows (L10): the registry is append-versioned, grants are
      marked consumed (never deleted), the audit log is append-only and
      hash-chained. This module revokes nothing it did not issue (L9).

Relationship to the other organs:
  - ``levi.cybrus.vault`` holds the secrets (encrypted at rest); this
    module is the only sanctioned *reader* of the ``cybrus.accounts.*``
    namespace.
  - ``levi.cybrus.approval.ApprovalEngine`` is the human gate (action
    ``"account.action"``); ``consume_approved`` is the single-use
    primitive.
  - ``levi.cybrus.audit.AuditEngine`` is the tamper-evident log; every
    grant, refusal, credential use, and violation lands there.
  - ``levi.cybrus.sentry`` detects silent movement — actions attempted
    outside this gateway are denied and logged as violations (R5 of the
    mandate), not warned.

Stdlib-only, no network. All state under ``~/.levi/cybrus/``
(``LEVI_HOME`` override honored).

Proof: tests/test_cybrus_right.py — invariant tests, honestly named
(nothing here is formally proven, only machine-checked against the laws
above).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


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


#: Vault namespace prefix for account credentials. ONLY this module reads
#: ``cybrus.accounts.<account_id>`` — any other reader is a silent-movement
#: violation (R1). The scanner in tests/test_cybrus_right.py enforces it.
CREDENTIAL_VAULT_PREFIX = "cybrus.accounts"

#: Grant lifetime (5 minutes — short-lived by design, mirrors gateway.py).
GRANT_TTL_SECONDS = 300

#: Scopes that require a human approval before a grant is minted (R3).
SENSITIVE_SCOPES = frozenset(
    {
        "email.send",
        "account.write",
        "account.delete",
        "financial.read",
        "financial.write",
        "money.move",
    }
)

#: Approval-engine action name for account-action approvals.
APPROVAL_ACTION = "account.action"

_ACCOUNTS_STORE = "cybrus_accounts"
_GRANTS_STORE = "cybrus_account_grants"
_GRANT_KEY_FILE = "account_grant.key"

#: Vault-safe name rule (mirrors levi.cybrus.vault): account ids and vault
#: usernames become part of the vault service namespace, so they obey the
#: same charset. The human-readable login (e.g. an email address) lives in
#: the registry's ``display_name``; the vault key stays machine-safe.
_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


def _check_name(value: str, what: str) -> str:
    if not isinstance(value, str) or not _NAME_RE.match(value):
        raise AccountError(
            f"invalid {what} {value!r}: use 1-64 chars of [A-Za-z0-9._-] "
            "(it becomes part of the vault service name)"
        )
    return value


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _audit(event: str, actor: str, details: Optional[Dict[str, Any]] = None) -> Dict:
    from levi.cybrus.audit import AuditEngine

    return AuditEngine().append(event, actor, details or {})


class AccountError(Exception):
    """Base class for account-gateway failures."""


class AccountNotRegistered(AccountError):
    """No such account in the registry. Remedy: register it (Chauncey)."""


class AccountSuspended(AccountError):
    """The account is suspended — policy deny wins (L3/R4)."""


class AccountApprovalRequired(AccountError):
    """A sensitive-scope action is blocked pending human approval.

    Carries the pending ``approval_id`` — a verified human approves it
    with ``levi cybrus approve <id>`` and the action is retried with
    ``approval_id=<id>``. Approvals are single-use (L5/R3).
    """

    def __init__(self, approval_id: str, message: str):
        super().__init__(message)
        self.approval_id = approval_id


class GrantRefused(AccountError):
    """A grant failed validation: forged, expired, consumed, or rebound."""


class CredentialRefused(AccountError):
    """Credential use was refused (no grant, unknown account, bad scope)."""


def _grant_key() -> bytes:
    """Per-cybrus-dir HMAC key for grant signatures (created once)."""
    p = _paths()
    key_path = p.cybrus_dir() / _GRANT_KEY_FILE
    if key_path.exists():
        return key_path.read_bytes()
    key = secrets.token_bytes(32)
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, key)
    finally:
        os.close(fd)
    return key


def _sign_grant(grant_id: str, account_id: str, scope: str, actor: str, expires_at: str) -> str:
    body = "|".join((grant_id, account_id, scope, actor, expires_at)).encode("utf-8")
    return hmac.new(_grant_key(), body, hashlib.sha256).hexdigest()


@dataclass
class AccountGrant:
    """A bound, short-lived, single-use grant for one account action."""

    grant_id: str
    account_id: str
    scope: str
    action: str
    actor: str
    purpose: str
    issued_at: str
    expires_at: str
    approval_id: Optional[str] = None


@dataclass
class CredentialReceipt:
    """Proof that a credential left the vault through the gate (R1).

    Carries the secret the caller needs (e.g. an SMTP login) PLUS the
    grant receipt. The receipt — never the secret — is what lands in the
    audit log.
    """

    secret: str
    receipt: Dict[str, Any]


class AccountActionGateway:
    """The choke point for credential use and external account actions.

    Accounts are registered by Chauncey alone. Every action needs a grant;
    sensitive scopes additionally need a human approval. Grants are
    single-use and bound; the audit log records every grant, refusal,
    credential use, and violation (metadata only).
    """

    KEEPER_IDENTITIES = frozenset({"chauncey", "keeper", "chauncey-logan"})

    def __init__(self, vault_passphrase: Optional[str] = None):
        self._vault_passphrase = vault_passphrase
        self._vault = None
        p = _paths()
        self._accounts_path = p.store_path(_ACCOUNTS_STORE)
        self._grants_path = p.store_path(_GRANTS_STORE)

    # -- vault (lazy) ----------------------------------------------------

    def _get_vault(self):
        if self._vault is None:
            if not self._vault_passphrase:
                raise CredentialRefused(
                    "credential use requires the vault passphrase: "
                    "construct AccountActionGateway(vault_passphrase=...)"
                )
            from levi.cybrus.vault import CredentialVault

            self._vault = CredentialVault(passphrase=self._vault_passphrase)
        return self._vault

    # -- registry --------------------------------------------------------

    def _load_accounts(self) -> Dict[str, Dict]:
        return _paths().load_json_store(self._accounts_path) or {}

    def register_account(
        self,
        account_id: str,
        platform: str,
        scopes: List[str],
        *,
        registered_by: str,
        username: str = "",
        display_name: str = "",
    ) -> Dict:
        """Register an external account. Chauncey only — deliberate.

        ``account_id`` and ``username`` become part of the vault service
        namespace, so they obey the vault-safe charset
        (``[A-Za-z0-9._-]``, 1-64 chars). The human-readable login (e.g.
        an email address) goes in ``display_name``.
        """
        if registered_by.strip().lower() not in self.KEEPER_IDENTITIES:
            _audit(
                "account.register_refused",
                registered_by,
                {"account_id": account_id, "reason": "not keeper"},
            )
            raise AccountError(
                "accounts are registered by Chauncey only "
                f"(registered_by={registered_by!r} refused)"
            )
        _check_name(account_id, "account_id")
        if username:
            _check_name(username, "username")
        # Every account can have its credential used through the gate;
        # credential.use is always registered (R1) but never approval-gated.
        scopes = sorted(set(scopes) | {"credential.use"})
        p = _paths()
        with p.store_lock(self._accounts_path):
            accounts = self._load_accounts()
            entry = {
                "account_id": account_id,
                "platform": platform,
                "scopes": scopes,
                "username": username,
                "display_name": display_name or username or account_id,
                "status": "active",
                "registered_by": registered_by,
                "registered_at": _iso(_utcnow()),
            }
            accounts[account_id] = entry
            p.save_json_store(self._accounts_path, accounts)
        _audit(
            "account.registered",
            registered_by,
            {"account_id": account_id, "platform": platform,
             "scopes": scopes},
        )
        return dict(entry)

    def suspend_account(self, account_id: str, *, by: str) -> None:
        """Suspend an account — policy deny from here on (L3/R4)."""
        if by.strip().lower() not in self.KEEPER_IDENTITIES:
            raise AccountError("only Chauncey suspends accounts")
        p = _paths()
        with p.store_lock(self._accounts_path):
            accounts = self._load_accounts()
            if account_id not in accounts:
                raise AccountNotRegistered(f"unknown account {account_id!r}")
            accounts[account_id]["status"] = "suspended"
            p.save_json_store(self._accounts_path, accounts)
        _audit("account.suspended", by, {"account_id": account_id})

    def get_account(self, account_id: str) -> Dict:
        accounts = self._load_accounts()
        if account_id not in accounts:
            raise AccountNotRegistered(
                f"unknown account {account_id!r}: register it first "
                "(Chauncey: AccountActionGateway.register_account)"
            )
        return dict(accounts[account_id])

    # -- grants ----------------------------------------------------------

    def _load_grants(self) -> Dict[str, Dict]:
        return _paths().load_json_store(self._grants_path) or {}

    def _save_grants(self, grants: Dict[str, Dict]) -> None:
        _paths().save_json_store(self._grants_path, grants)

    def request_account_action(
        self,
        account_id: str,
        scope: str,
        action: str,
        actor: str,
        purpose: str = "",
        approval_id: Optional[str] = None,
    ) -> AccountGrant:
        """Request a grant for one account action (R2).

        Routine scopes mint a grant immediately. Sensitive scopes (R3)
        raise :class:`AccountApprovalRequired` carrying a resumable
        approval id — retry with ``approval_id=<id>`` after a human
        approves. Policy deny (unknown/suspended account, unknown scope)
        always wins (L3/R4): no approval overrides it.
        """
        account = self.get_account(account_id)  # raises AccountNotRegistered
        if account.get("status") != "active":
            _audit(
                "account.action_refused", actor,
                {"account_id": account_id, "scope": scope, "action": action,
                 "reason": "account suspended"},
            )
            raise AccountSuspended(
                f"account {account_id!r} is suspended: policy deny wins "
                "(unsuspend via Chauncey before retrying)"
            )
        if scope not in account.get("scopes", []):
            _audit(
                "account.action_refused", actor,
                {"account_id": account_id, "scope": scope, "action": action,
                 "reason": "scope not granted to account"},
            )
            raise GrantRefused(
                f"scope {scope!r} is not registered for account "
                f"{account_id!r}: register the scope first (Chauncey)"
            )

        resolved_approval_id = approval_id
        if scope in SENSITIVE_SCOPES and approval_id is None:
            from levi.cybrus.approval import ApprovalEngine

            entry = ApprovalEngine().request_approval(
                action=APPROVAL_ACTION,
                subject=actor,
                resource=f"account:{account_id}",
                risk="high",
                details={
                    "account_id": account_id, "scope": scope,
                    "action": action, "actor": actor, "purpose": purpose,
                },
            )
            _audit(
                "account.approval_requested", actor,
                {"account_id": account_id, "scope": scope, "action": action,
                 "approval_id": entry["id"]},
            )
            raise AccountApprovalRequired(
                entry["id"],
                f"sensitive scope {scope!r} on account {account_id!r} needs "
                f"human approval: approve {entry['id'][:8]} "
                f"(levi cybrus approve {entry['id'][:8]}) then retry with "
                f"approval_id={entry['id'][:8]}",
            )
        if scope in SENSITIVE_SCOPES:
            # Verify + consume the human approval atomically (L5/R3): one
            # approval mints at most one grant. Rebound approvals (minted
            # for a different account/scope/action) are refused.
            from levi.cybrus.approval import ApprovalEngine

            # RED-1 exact-match law: the consume side must present EXACTLY
            # the fields the approval carries — including "purpose", or
            # the approved ceremony can never complete. The grant stays
            # bound to the approved purpose (a retry with a different
            # purpose fails closed).
            consumed = ApprovalEngine().consume_approved(
                APPROVAL_ACTION,
                {
                    "account_id": account_id, "scope": scope,
                    "action": action, "actor": actor, "purpose": purpose,
                },
            )
            if consumed is None or consumed["id"] != approval_id:
                _audit(
                    "account.action_refused", actor,
                    {"account_id": account_id, "scope": scope,
                     "action": action, "approval_id": approval_id,
                     "reason": "approval missing, consumed, or rebound"},
                )
                raise GrantRefused(
                    "approval invalid for this action: it is unknown, "
                    "already consumed, expired, denied, or was approved for "
                    "a different account/scope/action (rebinding refused). "
                    "Request a fresh approval."
                )
            resolved_approval_id = consumed["id"]

        now = _utcnow()
        expires = _iso(
            datetime.fromtimestamp(now.timestamp() + GRANT_TTL_SECONDS,
                                   tz=timezone.utc)
        )
        grant_id = "ag_" + uuid.uuid4().hex[:16]
        sig = _sign_grant(grant_id, account_id, scope, actor, expires)
        record = {
            "grant_id": grant_id, "account_id": account_id, "scope": scope,
            "action": action, "actor": actor, "purpose": purpose,
            "issued_at": _iso(now), "expires_at": expires,
            "consumed_at": None, "approval_id": resolved_approval_id,
            "sig": sig,
        }
        p = _paths()
        with p.store_lock(self._grants_path):
            grants = self._load_grants()
            grants[grant_id] = record
            self._save_grants(grants)
        _audit(
            "account.grant_issued", actor,
            {"grant_id": grant_id, "account_id": account_id, "scope": scope,
             "action": action,
             "approval_id": resolved_approval_id},
        )
        return AccountGrant(
            grant_id=grant_id, account_id=account_id, scope=scope,
            action=action, actor=actor, purpose=purpose,
            issued_at=_iso(now), expires_at=expires,
            approval_id=resolved_approval_id,
        )

    def _consume_grant(self, grant: AccountGrant, actor: str) -> Dict:
        """Validate and atomically consume a grant (R5: single-use).

        Raises :class:`GrantRefused` on forgery, expiry, rebinding, or
        replay. Validation happens under the store lock with a fresh
        reload so two concurrent consumers cannot both win one grant.
        """
        p = _paths()
        with p.store_lock(self._grants_path):
            grants = self._load_grants()
            rec = grants.get(grant.grant_id)
            if rec is None:
                raise GrantRefused(
                    f"unknown grant {grant.grant_id!r}: request a fresh one "
                    "via request_account_action"
                )
            want = _sign_grant(
                rec["grant_id"], rec["account_id"], rec["scope"],
                rec["actor"], rec["expires_at"],
            )
            if not hmac.compare_digest(want, rec.get("sig", "")):
                _audit("account.grant_refused", actor,
                       {"grant_id": grant.grant_id, "reason": "forged"})
                raise GrantRefused(
                    f"grant {grant.grant_id!r} failed signature check: "
                    "forgery refused"
                )
            if rec.get("actor") != actor:
                _audit("account.grant_refused", actor,
                       {"grant_id": grant.grant_id, "reason": "actor rebound"})
                raise GrantRefused(
                    f"grant {grant.grant_id!r} was issued to "
                    f"{rec.get('actor')!r}, not {actor!r}: rebinding refused"
                )
            try:
                expires = datetime.fromisoformat(rec["expires_at"])
            except (KeyError, ValueError, TypeError):
                expires = _utcnow()  # unparseable expiry -> expired
            if expires <= _utcnow():
                _audit("account.grant_refused", actor,
                       {"grant_id": grant.grant_id, "reason": "expired"})
                raise GrantRefused(
                    f"grant {grant.grant_id!r} expired: request a fresh one"
                )
            if rec.get("consumed_at"):
                _audit("account.grant_refused", actor,
                       {"grant_id": grant.grant_id, "reason": "replay"})
                raise GrantRefused(
                    f"grant {grant.grant_id!r} already consumed: grants are "
                    "single-use (replay refused)"
                )
            rec["consumed_at"] = _iso(_utcnow())
            self._save_grants(grants)
            return dict(rec)

    def execute_account_action(
        self,
        grant: AccountGrant,
        action_fn: Callable[[], Any],
        *,
        actor: str,
    ) -> Any:
        """Execute one account action under a grant (R2/R5).

        The grant is consumed atomically BEFORE the action runs: at most
        one execution per grant, even under concurrency. The action's
        result is returned; failures inside ``action_fn`` still consume
        the grant (the attempt is what the approval covered) and are
        audited.
        """
        rec = self._consume_grant(grant, actor)
        _audit(
            "account.action_executed", actor,
            {"grant_id": grant.grant_id, "account_id": rec["account_id"],
             "scope": rec["scope"], "action": rec["action"]},
        )
        try:
            return action_fn()
        except Exception as exc:
            _audit(
                "account.action_failed", actor,
                {"grant_id": grant.grant_id, "account_id": rec["account_id"],
                 "action": rec["action"],
                 "error": f"{type(exc).__name__}: {exc}"},
            )
            raise

    # -- credentials (R1) ------------------------------------------------

    def _service(self, account_id: str) -> str:
        return f"{CREDENTIAL_VAULT_PREFIX}.{account_id}"

    def store_credential(
        self, account_id: str, username: str, secret: str, *, by: str
    ) -> None:
        """Store an account credential in the vault. Chauncey only.

        ``username`` is the vault-safe login name registered for the
        account (same value passed as ``username=`` to
        :meth:`register_account`).
        """
        if by.strip().lower() not in self.KEEPER_IDENTITIES:
            raise CredentialRefused(
                "account credentials are stored by Chauncey only"
            )
        account = self.get_account(account_id)  # must be a registered account
        _check_name(username, "username")
        if username != (account.get("username") or account_id):
            raise CredentialRefused(
                f"username {username!r} does not match the registered "
                f"vault login for account {account_id!r}"
            )
        if not secret:
            raise CredentialRefused("refusing to store an empty secret")
        self._get_vault().store(self._service(account_id), username, secret)
        _audit(
            "account.credential_stored", by,
            {"account_id": account_id, "username": username},
        )

    def use_credential(
        self, account_id: str, scope: str, actor: str, purpose: str = ""
    ) -> CredentialReceipt:
        """Use an account credential through the gate (R1).

        Mints a bound, short-lived grant for scope ``credential.use``
        (routine — no human approval, but the grant + receipt are
        mandatory), reads the vault, and appends a metadata-only receipt
        to the hash-chained audit log. The secret is returned to the
        caller ONLY with the receipt; nothing about the secret lands in
        any log. Direct vault reads of the ``cybrus.accounts.*``
        namespace bypass this gate and are silent-movement violations.
        """
        account = self.get_account(account_id)  # raises AccountNotRegistered
        if scope not in account.get("scopes", []):
            raise CredentialRefused(
                f"scope {scope!r} is not registered for account "
                f"{account_id!r}: the credential cannot be used for it"
            )
        # request_account_action enforces suspension (AccountSuspended)
        grant, receipt = self._receipt_credential_use(
            account_id, scope, actor, purpose, source="vault",
        )
        username = account.get("username") or account_id
        secret = self._get_vault().get(self._service(account_id), username)
        return CredentialReceipt(secret=secret, receipt=receipt)

    def attest_credential_use(
        self,
        account_id: str,
        scope: str,
        actor: str,
        *,
        purpose: str = "",
        source: str = "config",
    ) -> Dict[str, Any]:
        """Receipt a credential use whose secret lives outside the vault.

        Migration cover for credentials not yet moved into the
        ``cybrus.accounts.*`` vault namespace (e.g. the oath daemon's
        SMTP password in mail.json). Mints and consumes the
        ``credential.use`` grant for the scope and appends the
        metadata-only receipt — the use is never silent. The secret
        itself is NEVER passed here and never logged; ``source`` names
        where it was read from. End state is vault storage via
        :meth:`use_credential`.
        """
        account = self.get_account(account_id)  # raises AccountNotRegistered
        if scope not in account.get("scopes", []):
            raise CredentialRefused(
                f"scope {scope!r} is not registered for account "
                f"{account_id!r}: the credential cannot be used for it"
            )
        _, receipt = self._receipt_credential_use(
            account_id, scope, actor, purpose, source=source,
        )
        return receipt

    def _receipt_credential_use(
        self,
        account_id: str,
        scope: str,
        actor: str,
        purpose: str,
        source: str,
    ) -> tuple:
        """Mint + consume the credential.use grant, audit the receipt.

        Returns ``(grant, receipt)``. The receipt is metadata-only (L4):
        grant id, account, scope, actor, source — never the secret.
        """
        # request_account_action enforces suspension (AccountSuspended)
        grant = self.request_account_action(
            account_id, "credential.use", "use_credential:" + scope,
            actor, purpose,
        )
        self._consume_grant(grant, actor)
        receipt = {
            "grant_id": grant.grant_id, "account_id": account_id,
            "scope": scope, "actor": actor, "source": source,
            "issued_at": grant.issued_at,
        }
        _audit("account.credential_used", actor, receipt)
        return grant, receipt


def status() -> Dict[str, Any]:
    """Gateway status: the law, account count, fail-closed posture."""
    gw = AccountActionGateway()
    accounts = gw._load_accounts()
    return {
        "law": "No credential leaves the vault without a grant receipt; "
               "no account action outside the gateway.",
        "accounts": len(accounts),
        "active": sum(1 for a in accounts.values()
                      if a.get("status") == "active"),
        "grant_ttl_seconds": GRANT_TTL_SECONDS,
        "sensitive_scopes": sorted(SENSITIVE_SCOPES),
    }
