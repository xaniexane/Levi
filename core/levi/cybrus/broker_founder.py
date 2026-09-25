"""Cybrus broker — founder edition: the live-provisioning skill.

The elevated tier above :mod:`levi.cybrus.broker`. Where the base broker is
the memory and the gate around third-party signups ("the broker tracks, it
does not browse"), the founder edition *drives* the signup through the
operator channel — preparing the plan, minting the credential into the
vault, walking the signup steps, and pausing at human checkpoints.

His words are the spec; the security laws are not relaxed. The founder
edition extends the skill, never the trust:

LAWS (machine-checked in tests/test_cybrus_broker_founder.py)
-------------------------------------------------------------
- **L1 SECRETS-SEALED.** No plaintext secret (password, contact handle,
  verification code) ever appears in a JSON store, an audit record, or
  stdout. Contacts and codes live encrypted in the vault as single-use
  scratch and are wiped after issue. The exactly-once issuance rule from
  the base broker applies: a minted password / provided code is revealed
  once, to the operator channel, then gone.
- **L2 GATE-EVERY-STEP.** Every forward state transition is human-gated
  through :class:`~levi.cybrus.approval.ApprovalEngine` with RED-1
  exact-match details and single-use consumption. Pausing
  (``executing`` → ``awaiting-human``) and failing (→ ``failed``) are the
  safe directions: ungated, audit-logged, always allowed.
- **L3 TERMS-ARE-HUMAN.** The broker NEVER accepts terms of service on the
  human's behalf. ``human_input`` on a ``terms_acceptance`` checkpoint
  requires an explicit ``human_attestation=True`` from the plan's owning
  identity; a machine attestation is refused even with a valid approval.
- **L4 NO-IDENTITY-DOCUMENTS.** The broker has no method that accepts
  identity documents or identity values. ``identity_kyc`` checkpoints
  record only ``{"provided": True}`` metadata — the human types their
  legal name / DOB into their own browser session; the values never touch
  the broker. Payloads carrying extra keys are refused.
- **L5 CHECKPOINT-PAUSE.** When execution reaches a human checkpoint the
  plan moves to ``awaiting-human`` and no further step executes until the
  human resumes it. The fake-signup end-to-end test proves the pauses fire.
- **L6 PLAN-FIDELITY.** Execution may only perform steps listed in the
  approved plan (the approval details carry a digest of the exact steps).
  An unknown step id fails the plan instead of running.
- **L7 METADATA-ONLY.** Plan stores and audit records carry names,
  platforms, checkpoint kinds, and digests — never secret values.

FULL-BUILD LAWS (machine-checked in tests/test_cybrus_founder_full.py)
---------------------------------------------------------------------
- **FL1 AUTHENTICATED-FOUNDER-PATH.** Every provisioning forward
  transition takes ``session=`` — a live
  :class:`~levi.cybrus.founder_gateway.FounderSession` — and derives the
  owning identity from it. Caller-asserted identity strings are refused
  on these transitions; founder-tier sessions are refused at session
  creation (the founder provisions through the service identity,
  ``chauncey-ops``). Liveness is re-checked against the gateway on every
  transition; an expired session fails closed.
- **FL6 OPERATOR-CHANNEL-BINDING.** The production channel
  (:class:`~levi.cybrus.broker_operator.BrowserTaskChannel`) performs
  steps only through an explicitly bound browser-task executor; unbound
  it raises instead of faking a signup.
- **FL7 PLAN-REGISTRY-FIDELITY.** The PayPal signup plan is registered
  beside Cash App under the same checkpoint laws (human terms, no
  identity values, single-use secrets); unknown platforms are refused.
- **FL8 CLI-COVERAGE.** The ``levi cybrus founder`` commands honor the
  same gates as the library calls — session auth, approvals, checkpoints.

State machine
-------------
``planned`` → ``credential-minted`` → ``executing`` ⇄ ``awaiting-human``
→ ``active``; any state → ``failed``. ``complete_execution`` additionally
requires every step consumed. On success the live account is registered
with the base broker's account machinery (status ``active``), so rotation,
retirement, and owner-only retrieval are inherited unchanged.

The operator channel
--------------------
Machine steps are performed by an *operator channel* — an object with
``perform(plan, step, context) -> {"ok": bool, "note": str}``. In
production this is the browser-task driver; in tests it is
``FakeOperatorChannel`` walking a fake signup page. The broker owns the
plan, the secrets, the gates, and the pauses — never the browser.

HONEST BOUNDARIES
-----------------
- The broker still performs no network calls itself. "Driving the signup"
  means orchestrating the operator channel step by step, holding the
  secrets, and enforcing the checkpoints — the HTTP still happens in the
  operator's browser.
- Verification codes and contacts are single-use scratch: issued exactly
  once to the operator channel, then wiped from the vault.
- Founder identities are refused here exactly as in the base broker
  (:meth:`CredentialBroker._actor_identity`) — the founder acts through
  their own service identity.
- stdlib-only, like the rest of Cybrus.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from levi.cybrus.broker import (
    BrokerApprovalRequired,
    BrokerError,
    CredentialBroker,
    _ACCOUNTS_STORE,
    _audit,
    _clean_name,
    _pending_match,
    _require_approval,
    _short,
    _utcnow_iso,
)

# --- metadata store (JSON, metadata only — never secrets) -------------------
_FOUNDER_PLANS_STORE = "broker_founder_plans"

#: Vault service namespace for founder-edition scratch secrets (passwords,
#: contacts, verification codes — all single-use, all wiped after issue).
_FOUNDER_VAULT_PREFIX = "cybrus.broker.founder"

#: Namespace for deterministic founder plan ids (uuid5). The id is derived
#: from (identity, platform, username, attempt) so that approve-then-retry
#: produces byte-identical RED-1 approval details; a fresh attempt number
#: keeps failed plans' records intact (nothing is thrown away).
_FOUNDER_PLAN_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "levi.cybrus.broker-founder.plan")


def _deterministic_plan_id(identity: str, platform: str, username: str, attempt: int) -> str:
    return uuid.uuid5(
        _FOUNDER_PLAN_NAMESPACE, f"{identity}:{platform}:{username}:{attempt}"
    ).hex


#: Legal founder-edition plan states and their transitions.
_FOUNDER_TRANSITIONS = {
    "planned": ("credential-minted", "failed"),
    "credential-minted": ("executing", "failed"),
    "executing": ("awaiting-human", "active", "failed"),
    "awaiting-human": ("executing", "failed"),
    "active": (),
    "failed": (),
}

#: Human checkpoint kinds. ``identity_document`` is deliberately absent —
#: the broker has no such checkpoint and no method that accepts documents.
CHECKPOINT_KINDS = (
    "verification_code",
    "terms_acceptance",
    "identity_kyc",
    "payment_link",
)


class FounderBrokerError(BrokerError):
    """Base class for founder-edition failures (validation, state, law)."""


class FounderTermsRefused(FounderBrokerError):
    """A terms-acceptance checkpoint was not satisfied by a verified human.

    The broker never accepts terms on anyone's behalf: the attestation must
    come from the plan's owning identity with ``human_attestation=True``.
    """


class FounderPlanFailed(FounderBrokerError):
    """A plan step reported failure (or plan fidelity was violated) and the
    plan was moved to ``failed``. Carries the plan id."""


def _step_digest(steps: List[Dict]) -> str:
    """Short digest of the exact approved step list (RED-1 plan fidelity)."""
    canonical = json.dumps(
        [{"id": s["id"], "kind": s["kind"]} for s in steps], sort_keys=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# --- signup plan registry ---------------------------------------------------
# Each platform declares its signup flow as data: the broker executes only
# what is declared here. Cash App is the reference platform.


def _cashapp_plan() -> Dict:
    return {
        "platform": "cashapp",
        "display": "Cash App",
        "signup_url": "https://cash.app/",
        "required_fields": [
            {
                "name": "contact",
                "kind": "human_contact",
                "sensitive": True,
                "stored": "vault-scratch-single-use",
                "description": (
                    "Phone number or email for verification. Provided by the "
                    "human at plan time, encrypted in the vault, issued "
                    "exactly once to the operator channel, then wiped."
                ),
            },
            {
                "name": "password",
                "kind": "minted",
                "sensitive": True,
                "stored": "vault-encrypted",
                "description": (
                    "Strong password minted by the broker (CSPRNG) at "
                    "credential-minting time."
                ),
            },
            {
                "name": "legal_identity",
                "kind": "human_identity",
                "sensitive": True,
                "stored": "never",
                "description": (
                    "Legal name + date of birth. Entered by the human in "
                    "their own browser session at the identity checkpoint. "
                    "The broker records only that the checkpoint was "
                    "satisfied — values never touch the broker."
                ),
            },
            {
                "name": "terms",
                "kind": "human_terms",
                "sensitive": False,
                "stored": "never",
                "description": (
                    "Cash App terms of service. Read and accepted by the "
                    "human, in person. The broker NEVER accepts terms on a "
                    "human's behalf (L3)."
                ),
            },
        ],
        "steps": [
            {
                "id": "open_signup",
                "kind": "action",
                "description": "Open the Cash App signup page in the operator browser.",
                "verify": "signup form visible",
            },
            {
                "id": "enter_contact",
                "kind": "action",
                "description": (
                    "Enter the human-provided phone/email (issued exactly "
                    "once to the operator channel)."
                ),
                "verify": "contact accepted; verification code requested",
            },
            {
                "id": "checkpoint_sms",
                "kind": "checkpoint",
                "checkpoint": "verification_code",
                "description": (
                    "SMS/email verification code. The human reads it from "
                    "their own device and provides it; the broker never "
                    "sees the device."
                ),
                "verify": "code provided by human",
            },
            {
                "id": "submit_code",
                "kind": "action",
                "description": "Submit the issued verification code exactly once.",
                "verify": "contact verified",
            },
            {
                "id": "checkpoint_identity",
                "kind": "checkpoint",
                "checkpoint": "identity_kyc",
                "description": (
                    "Legal name + date of birth, entered by the human in "
                    "their own browser session. Broker records satisfaction "
                    "only — never the values (L4)."
                ),
                "verify": "human confirms identity details entered",
            },
            {
                "id": "checkpoint_terms",
                "kind": "checkpoint",
                "checkpoint": "terms_acceptance",
                "description": (
                    "Cash App terms of service. The human reads and accepts "
                    "them personally. Machine attestation is refused (L3)."
                ),
                "verify": "human attestation recorded",
            },
            {
                "id": "link_card",
                "kind": "checkpoint",
                "checkpoint": "payment_link",
                "optional": True,
                "description": (
                    "Optional: the human links a debit card in their own "
                    "session. Broker records linked/skipped only."
                ),
                "verify": "human confirms linked or skipped",
            },
            {
                "id": "confirm_created",
                "kind": "action",
                "description": "Confirm the account dashboard / $cashtag is reachable.",
                "verify": "account identifier visible",
            },
        ],
    }


def _paypal_plan() -> Dict:
    return {
        "platform": "paypal",
        "display": "PayPal",
        "signup_url": "https://www.paypal.com/us/webapps/mpp/account-selection",
        "required_fields": [
            {
                "name": "contact",
                "kind": "human_contact",
                "sensitive": True,
                "stored": "vault-scratch-single-use",
                "description": (
                    "Email or mobile number for verification. Provided by "
                    "the human at plan time, encrypted in the vault, issued "
                    "exactly once to the operator channel, then wiped."
                ),
            },
            {
                "name": "password",
                "kind": "minted",
                "sensitive": True,
                "stored": "vault-encrypted",
                "description": (
                    "Strong password minted by the broker (CSPRNG) at "
                    "credential-minting time; entered into the PayPal "
                    "signup form by the operator channel."
                ),
            },
            {
                "name": "legal_identity",
                "kind": "human_identity",
                "sensitive": True,
                "stored": "never",
                "description": (
                    "Legal name, date of birth, address. Entered by the "
                    "human in their own browser session at the identity "
                    "checkpoint. The broker records only that the checkpoint "
                    "was satisfied — values never touch the broker."
                ),
            },
            {
                "name": "terms",
                "kind": "human_terms",
                "sensitive": False,
                "stored": "never",
                "description": (
                    "PayPal User Agreement. Read and accepted by the human, "
                    "in person. The broker NEVER accepts terms on a human's "
                    "behalf (L3)."
                ),
            },
        ],
        "steps": [
            {
                "id": "open_signup",
                "kind": "action",
                "description": "Open the PayPal account-selection page in the operator browser.",
                "verify": "account type selection visible",
            },
            {
                "id": "choose_personal",
                "kind": "action",
                "description": "Choose the Personal account type.",
                "verify": "personal signup form visible",
            },
            {
                "id": "enter_contact",
                "kind": "action",
                "description": (
                    "Enter the human-provided email/mobile (issued exactly "
                    "once to the operator channel)."
                ),
                "verify": "contact accepted; verification code requested",
            },
            {
                "id": "checkpoint_sms",
                "kind": "checkpoint",
                "checkpoint": "verification_code",
                "description": (
                    "Email/SMS verification code. The human reads it from "
                    "their own device and provides it; the broker never "
                    "sees the device."
                ),
                "verify": "code provided by human",
            },
            {
                "id": "submit_code",
                "kind": "action",
                "description": "Submit the issued verification code exactly once.",
                "verify": "contact verified",
            },
            {
                "id": "enter_password",
                "kind": "action",
                "description": (
                    "Enter the broker-minted password (issued exactly once "
                    "to the operator channel)."
                ),
                "verify": "password accepted",
            },
            {
                "id": "checkpoint_identity",
                "kind": "checkpoint",
                "checkpoint": "identity_kyc",
                "description": (
                    "Legal name, date of birth, address — entered by the "
                    "human in their own browser session. Broker records "
                    "satisfaction only — never the values (L4)."
                ),
                "verify": "human confirms identity details entered",
            },
            {
                "id": "checkpoint_terms",
                "kind": "checkpoint",
                "checkpoint": "terms_acceptance",
                "description": (
                    "PayPal User Agreement. The human reads and accepts it "
                    "personally. Machine attestation is refused (L3)."
                ),
                "verify": "human attestation recorded",
            },
            {
                "id": "link_card",
                "kind": "checkpoint",
                "checkpoint": "payment_link",
                "optional": True,
                "description": (
                    "Optional: the human links a bank/card in their own "
                    "session. Broker records linked/skipped only."
                ),
                "verify": "human confirms linked or skipped",
            },
            {
                "id": "confirm_created",
                "kind": "action",
                "description": "Confirm the PayPal account dashboard is reachable.",
                "verify": "account identifier visible",
            },
        ],
    }


#: Signup plan registry (FL7): every platform declares its flow as data;
#: unknown platforms are refused at plan time.
SIGNUP_PLANS: Dict[str, Dict] = {"cashapp": _cashapp_plan(), "paypal": _paypal_plan()}


class FounderBroker(CredentialBroker):
    """The founder edition of the credential broker: live provisioning.

    Subclasses :class:`CredentialBroker` to inherit the vault, the
    identity/containment rules, the approval gate, and the account/key
    machinery. Adds provisioning *plans* with per-platform signup flows,
    an operator-channel execution loop, human checkpoints, and the
    extended state machine.

    Construct with the vault master passphrase, exactly like the base
    broker. ``identity`` is the default owning identity.
    """

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _founder_service(platform: str) -> str:
        return f"{_FOUNDER_VAULT_PREFIX}.{_clean_name(platform, 'platform')}"

    @staticmethod
    def _load_plans() -> List[Dict]:
        from levi.cybrus import _paths as _p

        data = _p.load_json_store(_p.store_path(_FOUNDER_PLANS_STORE))
        return data if isinstance(data, list) else []

    def _save_plan_record(self, updated: Dict) -> None:
        from levi.cybrus import _paths as _p

        with _p.store_lock(_p.store_path(_FOUNDER_PLANS_STORE)):
            plans = self._load_plans()
            for i, plan in enumerate(plans):
                if plan["id"] == updated["id"]:
                    plans[i] = updated
                    break
            else:
                plans.append(updated)
            _p.save_json_store(_p.store_path(_FOUNDER_PLANS_STORE), plans)

    def _find_plan(self, plan_id: str) -> Dict:
        for plan in self._load_plans():
            if plan["id"] == plan_id:
                return plan
        raise FounderBrokerError(f"unknown founder plan id: {_short(plan_id)}")

    def _provisioning_identity(self, session) -> str:
        """FL1 — derive the provisioning identity from a live session.

        Every provisioning transition takes ``session=`` (a
        :class:`~levi.cybrus.founder_gateway.FounderSession`) instead of a
        caller-asserted identity string. The session's liveness is
        re-checked against the gateway on every call, so an expired or
        restart-cleared session fails closed. Founder-tier sessions are
        refused at session creation — the founder provisions through the
        service identity (chauncey-ops).
        """
        if session is None:
            raise FounderBrokerError(
                "authenticated founder session required: open one with "
                "FounderSession.authenticate(<service-identity>, <password>) "
                "and pass it as session=. Caller-asserted identity strings "
                "are refused on provisioning transitions (FL1)."
            )
        from levi.cybrus.founder_gateway import FounderSession

        if not isinstance(session, FounderSession):
            raise FounderBrokerError(
                f"session must be a FounderSession, not {type(session).__name__}"
            )
        return session.assert_live()

    @staticmethod
    def _check_transition(plan: Dict, to_state: str) -> None:
        """Validate a transition without mutating — the gate runs between
        validation and mutation, so a raised approval never leaves a
        half-moved plan behind."""
        allowed = _FOUNDER_TRANSITIONS.get(plan["status"], ())
        if to_state not in allowed:
            raise FounderBrokerError(
                f"illegal founder plan transition: {plan['status']!r} -> "
                f"{to_state!r} (plan {_short(plan['id'])})"
            )

    @staticmethod
    def _transition(plan: Dict, to_state: str) -> None:
        FounderBroker._check_transition(plan, to_state)
        plan["status"] = to_state

    def _wipe_scratch(self, plan: Dict) -> None:
        """Wipe single-use scratch secrets (password, contact, code) from
        the vault. Best-effort: missing entries are ignored."""
        service = self._founder_service(plan["platform"])
        short = _short(plan["id"])
        for suffix in ("password", "contact", "verify_code"):
            try:
                self._vault_instance().delete(service, f"{short}.{suffix}")
            except KeyError:
                pass

    def _plan_public(self, plan: Dict) -> Dict:
        """The plan as the operator channel sees it — metadata only."""
        return {
            "plan_id": plan["id"],
            "platform": plan["platform"],
            "display": plan["display"],
            "signup_url": plan["signup_url"],
            "username": plan["username"],
            "identity": plan["identity"],
            "status": plan["status"],
            "step_index": plan["step_index"],
            "step_count": len(plan["steps"]),
            "step_digest": plan.get("step_digest"),
            "steps": [
                {
                    "id": s["id"],
                    "kind": s["kind"],
                    "description": s["description"],
                    "verify": s.get("verify", ""),
                    "optional": bool(s.get("optional", False)),
                    "checkpoint": s.get("checkpoint"),
                }
                for s in plan["steps"]
            ],
        }

    def _current_step(self, plan: Dict) -> Dict:
        if plan["step_index"] >= len(plan["steps"]):
            raise FounderBrokerError(
                f"plan {_short(plan['id'])} has no remaining steps"
            )
        return plan["steps"][plan["step_index"]]

    def _live_plan_guard(self, plan: Dict, username: str) -> None:
        """Refuse a second live plan/account for the same platform+user."""
        for other in self._load_plans():
            if (
                other["id"] != plan.get("id")
                and other["platform"] == plan["platform"]
                and other["username"] == username
                and other["status"] not in ("failed",)
            ):
                raise FounderBrokerError(
                    f"a founder plan already exists for "
                    f"{plan['platform']!r}/{username!r} "
                    f"(id {_short(other['id'])}, status {other['status']!r})"
                )
        for acc in self._load_store(_ACCOUNTS_STORE):
            if (
                acc["platform"] == plan["platform"]
                and acc["username"] == username
                and acc["status"] in ("provisioned", "active")
            ):
                raise FounderBrokerError(
                    f"account already provisioned for {plan['platform']!r}/"
                    f"{username!r} (id {_short(acc['id'])}, status "
                    f"{acc['status']!r}) — use the base broker to manage it"
                )

    # -- plan ----------------------------------------------------------------

    def provision_plan(
        self,
        platform: str,
        session=None,
        username: Optional[str] = None,
        contact: Optional[str] = None,
    ) -> Dict:
        """Create a live-provisioning plan for a third-party platform.

        FL1: requires a live :class:`FounderSession` (``session=``) — the
        owning identity is derived from it, never asserted by the caller.
        Human-gated (``broker.founder.plan``). ``contact`` is the
        phone/email the human wants verified — it is encrypted into the
        vault as single-use scratch immediately and never lands in the
        plan store. Returns the public plan (metadata only).
        """
        platform_key = _clean_name(platform, "platform").lower()
        if platform_key not in SIGNUP_PLANS:
            raise FounderBrokerError(
                f"unknown platform {platform!r}: known plans: "
                f"{sorted(SIGNUP_PLANS)}"
            )
        spec = SIGNUP_PLANS[platform_key]
        identity = self._provisioning_identity(session)
        username = _clean_name(username, "username") if username else identity
        if not isinstance(contact, str) or not contact.strip():
            raise FounderBrokerError(
                "contact is required: the phone/email the human wants verified"
            )

        plan_id = uuid.uuid4().hex
        steps = [dict(s) for s in spec["steps"]]
        digest = _step_digest(steps)
        # Deterministic per-attempt id: approve-then-retry must reproduce
        # byte-identical RED-1 details, and a fresh attempt number keeps a
        # failed plan's record intact (nothing is thrown away).
        attempt = sum(
            1
            for p in self._load_plans()
            if p["platform"] == platform_key and p["username"] == username
        )
        plan_id = _deterministic_plan_id(identity, platform_key, username, attempt)
        # Duplicate guard BEFORE the gate (read-only): a duplicate must
        # never consume an approval or quota.
        self._live_plan_guard({"id": plan_id, "platform": platform_key}, username)
        details = {
            "identity": identity,
            "platform": platform_key,
            "username": username,
            "plan_id": plan_id,
            "step_digest": digest,
        }
        _require_approval(
            "broker.founder.plan", identity, f"thirdparty.{platform_key}", details
        )

        plan = {
            "id": plan_id,
            "platform": platform_key,
            "display": spec["display"],
            "signup_url": spec["signup_url"],
            "username": username,
            "identity": identity,
            "status": "planned",
            "steps": steps,
            "step_digest": digest,
            "step_index": 0,
            "has_contact": True,
            "checkpoint_secret_pending": False,
            "created_at": _utcnow_iso(),
            "completed_at": None,
            "failed_at": None,
            "fail_reason": None,
        }
        # Contact → encrypted scratch NOW (L1: never in the JSON store).
        self._vault_instance().store(
            self._founder_service(platform_key),
            f"{_short(plan_id)}.contact",
            contact.strip(),
        )
        self._save_plan_record(plan)
        _audit(
            "broker.founder.planned",
            identity,
            {
                "plan_id": _short(plan_id),
                "platform": platform_key,
                "username": username,
                "step_digest": digest,
                "step_count": len(steps),
            },
        )
        return self._plan_public(plan)

    def get_plan(self, plan_id: str, identity: Optional[str] = None) -> Dict:
        """Plan metadata (never secrets). Containment-checked."""
        identity = self._actor_identity(identity)
        plan = self._find_plan(plan_id)
        if plan["identity"] != identity:
            raise FounderBrokerError(
                f"containment: {identity!r} may not inspect "
                f"{plan['identity']!r}'s plan"
            )
        return self._plan_public(plan)

    def list_plans(self, identity: Optional[str] = None) -> List[Dict]:
        """Provisioning plans, optionally filtered by owning identity.
        Metadata only."""
        if identity is not None:
            identity = self._actor_identity(identity)
        return [
            self._plan_public(p)
            for p in sorted(self._load_plans(), key=lambda x: x["created_at"])
            if identity is None or p["identity"] == identity
        ]

    # -- credential minting ----------------------------------------------------

    def mint_credential(self, plan_id: str, session=None):
        """Mint the plan's password (CSPRNG) into the encrypted vault.

        Human-gated (``broker.founder.mint``). Moves the plan
        ``planned`` → ``credential-minted``. Returns ``(public_plan,
        plaintext_password)`` — the password is shown exactly once by the
        caller and never logged (L1).
        """
        from levi.cybrus.vault import generate_password

        identity = self._provisioning_identity(session)
        plan = self._find_plan(plan_id)
        if plan["identity"] != identity:
            raise FounderBrokerError(
                f"containment: {identity!r} may not mint for "
                f"{plan['identity']!r}'s plan"
            )
        self._check_transition(plan, "credential-minted")
        details = {
            "identity": identity,
            "platform": plan["platform"],
            "username": plan["username"],
            "plan_id": plan_id,
        }
        _require_approval(
            "broker.founder.mint",
            identity,
            f"thirdparty.{plan['platform']}",
            details,
        )
        self._transition(plan, "credential-minted")
        password = generate_password()
        self._vault_instance().store(
            self._founder_service(plan["platform"]),
            f"{_short(plan_id)}.password",
            password,
        )
        self._save_plan_record(plan)
        _audit(
            "broker.founder.credential_minted",
            identity,
            {"plan_id": _short(plan_id), "platform": plan["platform"]},
        )
        return self._plan_public(plan), password

    # -- execution ---------------------------------------------------------------

    def begin_execution(self, plan_id: str, session=None) -> Dict:
        """Start driving the signup through the operator channel.

        Human-gated (``broker.founder.execute``); the approval details
        carry the digest of the exact steps approved (L6 plan fidelity).
        The tier-based anti-spam gate runs here — this is the point of no
        return, so approval-pending attempts never consume quota. Moves
        the plan ``credential-minted`` → ``executing``.
        """
        identity = self._provisioning_identity(session)
        plan = self._find_plan(plan_id)
        if plan["identity"] != identity:
            raise FounderBrokerError(
                f"containment: {identity!r} may not execute "
                f"{plan['identity']!r}'s plan"
            )
        self._check_transition(plan, "executing")
        details = {
            "identity": identity,
            "platform": plan["platform"],
            "username": plan["username"],
            "plan_id": plan_id,
            "step_digest": plan["step_digest"],
        }
        _require_approval(
            "broker.founder.execute",
            identity,
            f"thirdparty.{plan['platform']}",
            details,
        )
        self._transition(plan, "executing")
        from levi.cybrus import rate_limits as _rate_limits

        _rate_limits.check(identity, _rate_limits.ACCOUNT_CREATE)
        self._save_plan_record(plan)
        _audit(
            "broker.founder.executing",
            identity,
            {
                "plan_id": _short(plan_id),
                "platform": plan["platform"],
                "step_digest": plan["step_digest"],
            },
        )
        return self._plan_public(plan)

    def next_step(self, plan_id: str, session=None) -> Dict:
        """Return the current step for the operator channel.

        Read-side; containment-checked. When the current step is a human
        checkpoint the plan pauses to ``awaiting-human`` (the safe
        direction — ungated, audit-logged) and the checkpoint descriptor
        is returned. No step executes past a checkpoint until the human
        resumes it (L5).
        """
        identity = self._provisioning_identity(session)
        plan = self._find_plan(plan_id)
        if plan["identity"] != identity:
            raise FounderBrokerError(
                f"containment: {identity!r} may not drive "
                f"{plan['identity']!r}'s plan"
            )
        if plan["status"] not in ("executing", "awaiting-human"):
            raise FounderBrokerError(
                f"plan {_short(plan_id)} is {plan['status']!r}: "
                "no steps to drive"
            )
        step = self._current_step(plan)
        public = self._plan_public(plan)
        current = {
            "id": step["id"],
            "kind": step["kind"],
            "description": step["description"],
            "verify": step.get("verify", ""),
            "optional": bool(step.get("optional", False)),
            "checkpoint": step.get("checkpoint"),
            "plan": public,
        }
        if step["kind"] == "checkpoint" and plan["status"] == "executing":
            self._transition(plan, "awaiting-human")
            self._save_plan_record(plan)
            _audit(
                "broker.founder.awaiting_human",
                identity,
                {
                    "plan_id": _short(plan_id),
                    "checkpoint": step["checkpoint"],
                    "step_id": step["id"],
                },
            )
        return current

    def report_step(
        self,
        plan_id: str,
        step_id: str,
        ok: bool,
        note: str = "",
        session=None,
    ) -> Dict:
        """The operator channel reports a machine step's outcome.

        Bookkeeping inside an already-approved execution (not a state
        transition): containment-checked and audit-logged. L6 plan
        fidelity — the step id must be the plan's current action step, or
        the plan fails instead of running something unapproved.
        """
        identity = self._provisioning_identity(session)
        plan = self._find_plan(plan_id)
        if plan["identity"] != identity:
            raise FounderBrokerError(
                f"containment: {identity!r} may not report for "
                f"{plan['identity']!r}'s plan"
            )
        if plan["status"] != "executing":
            raise FounderBrokerError(
                f"plan {_short(plan_id)} is {plan['status']!r}: "
                "not executing"
            )
        step = self._current_step(plan)
        if step["id"] != step_id or step["kind"] != "action":
            self._fail_locked(
                plan,
                identity,
                f"plan fidelity violated: reported step {step_id!r} is not "
                f"the current approved action step {step['id']!r}",
            )
            raise FounderPlanFailed(
                f"plan {_short(plan_id)} failed: unapproved step {step_id!r}"
            )
        if not ok:
            self._fail_locked(
                plan, identity, f"step {step_id!r} reported failure: {note}"
            )
            raise FounderPlanFailed(
                f"plan {_short(plan_id)} failed at step {step_id!r}"
            )
        plan["step_index"] += 1
        self._save_plan_record(plan)
        _audit(
            "broker.founder.step_ok",
            identity,
            {"plan_id": _short(plan_id), "step_id": step_id},
        )
        return self._plan_public(plan)

    def run_to_checkpoint(
        self, plan_id: str, channel, session=None
    ) -> Dict:
        """Drive machine steps through ``channel`` until a human checkpoint
        (or completion). ``channel`` implements
        ``perform(public_plan, step, context) -> {"ok": bool, "note": str}``.
        Returns the checkpoint descriptor, or ``{"done": True, ...}`` when
        every step is consumed (then call :meth:`complete_execution`).
        """
        identity = self._provisioning_identity(session)
        context: Dict = {}
        while True:
            plan = self._find_plan(plan_id)
            if plan["status"] == "awaiting-human":
                return self.next_step(plan_id, session=session)
            if plan["status"] != "executing":
                raise FounderBrokerError(
                    f"plan {_short(plan_id)} is {plan['status']!r}: "
                    "cannot drive"
                )
            try:
                step = self._current_step(plan)
            except FounderBrokerError:
                return {"done": True, "plan": self._plan_public(plan)}
            current = self.next_step(plan_id, session=session)
            if current["kind"] == "checkpoint":
                return current
            outcome = channel.perform(self._plan_public(plan), current, context)
            if not isinstance(outcome, dict) or "ok" not in outcome:
                raise FounderBrokerError(
                    "operator channel must return {'ok': bool, 'note': str}"
                )
            self.report_step(
                plan_id,
                current["id"],
                bool(outcome["ok"]),
                str(outcome.get("note", "")),
                session=session,
            )

    # -- human checkpoints ---------------------------------------------------------

    def human_input(
        self,
        plan_id: str,
        checkpoint_id: str,
        payload: Dict,
        session=None,
        human_attestation: bool = False,
    ) -> Dict:
        """Satisfy the current human checkpoint and resume execution.

        Human-gated (``broker.founder.checkpoint``): the human's input IS
        the gate — the approval is consumed here, moving the plan
        ``awaiting-human`` → ``executing``. Per checkpoint kind:

        - ``verification_code``: ``{"code": "<sms/email code>"}`` — the
          code is encrypted into the vault as single-use scratch and
          issued exactly once via :meth:`issue_checkpoint_secret`.
        - ``terms_acceptance``: requires ``human_attestation=True`` from
          the plan's owning identity, else :class:`FounderTermsRefused`
          (L3). The broker never accepts terms for the human.
        - ``identity_kyc``: exactly ``{"provided": True}`` — metadata
          only; any extra keys are refused (L4).
        - ``payment_link``: exactly ``{"linked": True}`` or
          ``{"skipped": True}`` — metadata only.
        """
        identity = self._provisioning_identity(session)
        plan = self._find_plan(plan_id)
        if plan["identity"] != identity:
            raise FounderBrokerError(
                f"containment: {identity!r} may not answer checkpoints for "
                f"{plan['identity']!r}'s plan"
            )
        if plan["status"] != "awaiting-human":
            raise FounderBrokerError(
                f"plan {_short(plan_id)} is {plan['status']!r}: "
                "no checkpoint awaiting input"
            )
        step = self._current_step(plan)
        if step["kind"] != "checkpoint" or step["id"] != checkpoint_id:
            raise FounderBrokerError(
                f"checkpoint {checkpoint_id!r} is not the current step of "
                f"plan {_short(plan_id)}"
            )
        kind = step["checkpoint"]
        if kind not in CHECKPOINT_KINDS:
            raise FounderBrokerError(
                f"unknown checkpoint kind {kind!r} — refusing"
            )
        if not isinstance(payload, dict):
            raise FounderBrokerError("checkpoint payload must be a dict")

        details = {
            "identity": identity,
            "platform": plan["platform"],
            "plan_id": plan_id,
            "checkpoint": kind,
            "checkpoint_id": checkpoint_id,
        }
        _require_approval(
            "broker.founder.checkpoint",
            identity,
            f"thirdparty.{plan['platform']}",
            details,
        )

        short = _short(plan_id)
        service = self._founder_service(plan["platform"])
        if kind == "verification_code":
            code = payload.get("code")
            if set(payload.keys()) != {"code"} or not isinstance(code, str) or not code:
                raise FounderBrokerError(
                    "verification_code payload must be exactly {'code': '<code>'}"
                )
            self._vault_instance().store(service, f"{short}.verify_code", code)
            plan["checkpoint_secret_pending"] = True
        elif kind == "terms_acceptance":
            # L3: the broker never accepts terms on the human's behalf.
            if not human_attestation or identity != plan["identity"]:
                raise FounderTermsRefused(
                    "terms acceptance requires the plan owner's explicit "
                    "human attestation (human_attestation=True); the broker "
                    "never accepts terms for the human"
                )
            if set(payload.keys()) != {"accepted"} or payload.get("accepted") is not True:
                raise FounderBrokerError(
                    "terms_acceptance payload must be exactly {'accepted': True}"
                )
        elif kind == "identity_kyc":
            # L4: metadata only — values never touch the broker.
            if set(payload.keys()) != {"provided"} or payload.get("provided") is not True:
                raise FounderBrokerError(
                    "identity_kyc payload must be exactly {'provided': True}: "
                    "the broker accepts no identity values or documents"
                )
        elif kind == "payment_link":
            keys = set(payload.keys())
            if keys != {"linked"} or payload.get("linked") not in (True, False):
                if keys != {"skipped"} or payload.get("skipped") is not True:
                    raise FounderBrokerError(
                        "payment_link payload must be exactly {'linked': bool} "
                        "or {'skipped': True}"
                    )
        else:  # pragma: no cover - guarded above
            raise FounderBrokerError(f"unknown checkpoint kind {kind!r}")

        self._transition(plan, "executing")
        plan["step_index"] += 1
        self._save_plan_record(plan)
        _audit(
            "broker.founder.checkpoint_satisfied",
            identity,
            {
                "plan_id": short,
                "checkpoint": kind,
                "checkpoint_id": checkpoint_id,
            },
        )
        return self._plan_public(plan)

    def issue_contact(self, plan_id: str, session=None) -> str:
        """Reveal the plan's contact handle (phone/email) exactly once.

        The operator channel calls this to fill the signup form, then the
        secret is wiped from the vault. Containment-checked; audit-logged
        with metadata only. The gate was consumed at plan creation — this
        is the issuance half of that approval.
        """
        identity = self._provisioning_identity(session)
        plan = self._find_plan(plan_id)
        if plan["identity"] != identity:
            raise FounderBrokerError(
                f"containment: {identity!r} may not take secrets from "
                f"{plan['identity']!r}'s plan"
            )
        if plan["status"] not in ("credential-minted", "executing"):
            raise FounderBrokerError(
                f"plan {_short(plan_id)} is {plan['status']!r}: "
                "contact is not issuable"
            )
        short = _short(plan_id)
        service = self._founder_service(plan["platform"])
        try:
            contact = self._vault_instance().get(service, f"{short}.contact")
        except KeyError:
            raise FounderBrokerError(
                f"contact for plan {short} is already spent"
            )
        try:
            self._vault_instance().delete(service, f"{short}.contact")
        except KeyError:
            pass
        plan["has_contact"] = False
        self._save_plan_record(plan)
        _audit(
            "broker.founder.contact_issued",
            identity,
            {"plan_id": short, "platform": plan["platform"]},
        )
        return contact

    def issue_checkpoint_secret(
        self, plan_id: str, session=None
    ) -> str:
        """Reveal a checkpoint secret (verification code) exactly once.

        The operator channel calls this after the human provides the code,
        types it into the signup page, and the secret is wiped from the
        vault. Containment-checked; audit-logged with metadata only. The
        gate was consumed at :meth:`human_input` — this is the issuance
        half of that approval.
        """
        identity = self._provisioning_identity(session)
        plan = self._find_plan(plan_id)
        if plan["identity"] != identity:
            raise FounderBrokerError(
                f"containment: {identity!r} may not take secrets from "
                f"{plan['identity']!r}'s plan"
            )
        if not plan.get("checkpoint_secret_pending"):
            raise FounderBrokerError(
                f"plan {_short(plan_id)} has no pending checkpoint secret"
            )
        short = _short(plan_id)
        service = self._founder_service(plan["platform"])
        try:
            secret = self._vault_instance().get(service, f"{short}.verify_code")
        except KeyError:
            plan["checkpoint_secret_pending"] = False
            self._save_plan_record(plan)
            raise FounderBrokerError(
                f"checkpoint secret for plan {short} is already spent"
            )
        try:
            self._vault_instance().delete(service, f"{short}.verify_code")
        except KeyError:
            pass
        plan["checkpoint_secret_pending"] = False
        self._save_plan_record(plan)
        _audit(
            "broker.founder.checkpoint_secret_issued",
            identity,
            {"plan_id": short, "kind": "verification_code"},
        )
        return secret

    # -- completion / failure ----------------------------------------------------------

    def complete_execution(self, plan_id: str, session=None) -> Dict:
        """Finish a fully-executed plan: register the live account.

        Human-gated (``broker.founder.complete``). Requires every step
        consumed. The minted password moves from founder scratch into the
        base broker's account vault service, a broker account record is
        written with status ``active``, and rotation / retirement /
        owner-only retrieval are inherited from the base broker unchanged.
        Moves the plan ``executing`` → ``active``.
        """
        identity = self._provisioning_identity(session)
        plan = self._find_plan(plan_id)
        if plan["identity"] != identity:
            raise FounderBrokerError(
                f"containment: {identity!r} may not complete "
                f"{plan['identity']!r}'s plan"
            )
        if plan["step_index"] < len(plan["steps"]):
            raise FounderBrokerError(
                f"plan {_short(plan_id)} has unconsumed steps: cannot complete"
            )
        self._check_transition(plan, "active")
        details = {
            "identity": identity,
            "platform": plan["platform"],
            "username": plan["username"],
            "plan_id": plan_id,
            "step_digest": plan["step_digest"],
        }
        _require_approval(
            "broker.founder.complete",
            identity,
            f"thirdparty.{plan['platform']}",
            details,
        )
        self._transition(plan, "active")
        short = _short(plan_id)
        founder_service = self._founder_service(plan["platform"])
        try:
            password = self._vault_instance().get(founder_service, f"{short}.password")
        except KeyError as exc:
            raise FounderBrokerError(
                f"plan {short} has no minted credential — cannot complete"
            ) from exc
        # Hand the credential to the base broker's account machinery.
        self._vault_instance().store(
            self._accounts_service(plan["platform"]), plan["username"], password
        )
        try:
            self._vault_instance().delete(founder_service, f"{short}.password")
        except KeyError:
            pass
        from levi.cybrus import _paths as _p

        with _p.store_lock(_p.store_path(_ACCOUNTS_STORE)):
            accounts = self._load_store(_ACCOUNTS_STORE)
            record = {
                "id": uuid.uuid4().hex,
                "platform": plan["platform"],
                "signup_url": plan["signup_url"],
                "username": plan["username"],
                "identity": identity,
                "status": "active",
                "created_at": plan["created_at"],
                "activated_at": _utcnow_iso(),
                "retired_at": None,
                "password_rotated_at": None,
                "founder_plan_id": plan_id,
            }
            accounts.append(record)
            self._save_store(_ACCOUNTS_STORE, accounts)
        # Contact scratch is spent — wipe it.
        try:
            self._vault_instance().delete(founder_service, f"{short}.contact")
        except KeyError:
            pass
        plan["completed_at"] = _utcnow_iso()
        self._save_plan_record(plan)
        _audit(
            "broker.founder.completed",
            identity,
            {
                "plan_id": short,
                "platform": plan["platform"],
                "username": plan["username"],
                "account_id": _short(record["id"]),
            },
        )
        return {"plan": self._plan_public(plan), "account": dict(record)}

    def _fail_locked(self, plan: Dict, identity: str, reason: str) -> None:
        """Move a plan to ``failed`` and wipe its scratch secrets. The safe
        direction — ungated, audit-logged. Never raises."""
        try:
            self._transition(plan, "failed")
        except FounderBrokerError:
            return  # already terminal; leave it
        self._wipe_scratch(plan)
        plan["failed_at"] = _utcnow_iso()
        plan["fail_reason"] = reason[:500]
        try:
            self._save_plan_record(plan)
        finally:
            _audit(
                "broker.founder.failed",
                identity,
                {"plan_id": _short(plan["id"]), "reason": reason[:200]},
            )

    def fail_plan(
        self, plan_id: str, reason: str, session=None
    ) -> Dict:
        """Abandon a plan: wipe scratch secrets, mark ``failed``. Ungated
        (the safe direction), audit-logged. Nothing is thrown away — the
        failed plan record stays for the trail."""
        identity = self._provisioning_identity(session)
        plan = self._find_plan(plan_id)
        if plan["identity"] != identity:
            raise FounderBrokerError(
                f"containment: {identity!r} may not fail "
                f"{plan['identity']!r}'s plan"
            )
        if not isinstance(reason, str) or not reason.strip():
            raise FounderBrokerError("a failure reason is required")
        self._fail_locked(plan, identity, reason.strip())
        return self._plan_public(plan)

    # -- overview ----------------------------------------------------------

    def status(self, identity: Optional[str] = None) -> Dict:
        """Founder-edition overview: plan counts by state. Metadata only."""
        if identity is not None:
            identity = self._actor_identity(identity)
        plans = self._load_plans()
        if identity is not None:
            plans = [p for p in plans if p["identity"] == identity]
        by_status: Dict[str, int] = {}
        for plan in plans:
            by_status[plan["status"]] = by_status.get(plan["status"], 0) + 1
        return {
            "plans": len(plans),
            "by_status": by_status,
            "platforms": sorted(SIGNUP_PLANS),
        }
