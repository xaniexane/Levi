"""Cybrus founder gateway — the authenticated path for provisioning.

Where :class:`~levi.cybrus.broker.CredentialBroker` refuses caller-asserted
founder identities because it cannot verify them (``_actor_identity``), this
module provides the authenticated alternative: a :class:`FounderSession`
bound to a live :class:`~levi.cybrus.gateway.CybrusGateway` session.

LAW FL1 — AUTHENTICATED-FOUNDER-PATH
------------------------------------
Every provisioning forward transition on
:class:`~levi.cybrus.broker_founder.FounderBroker`
(``provision_plan``, ``mint_credential``, ``begin_execution``,
``run_to_checkpoint`` / ``report_step``, ``human_input``,
``issue_contact`` / ``issue_checkpoint_secret``, ``complete_execution``,
``fail_plan``) requires a live ``FounderSession``. The owning identity is
derived from the session — never from a caller-asserted string — and the
session's liveness is re-checked on every transition, so an expired or
restart-cleared session fails closed.

Founder-tier identities are refused at session creation: the founder's own
name must never ride the provisioning path. The founder provisions through
their service identity (``chauncey-ops``), exactly as the broker's
``_actor_identity`` refusal prescribes. Remedy is printed in the error.

Sessions are in-memory on the gateway (a restart requires
re-authentication); the broker therefore re-validates liveness on every
transition rather than trusting a stale handle.

HONEST BOUNDARIES
-----------------
- This module performs authentication against the local identity store —
  it does not create trust, it checks the password the founder set.
- The plaintext session token issued by ``auth()`` is discarded
  immediately; the session handle carries only the token id and identity.
- stdlib-only, like the rest of Cybrus.
"""

from __future__ import annotations

import time
from typing import Dict, Optional


class FounderSessionError(Exception):
    """The founder session is missing, expired, or not permitted here."""


class FounderSession:
    """An authenticated provisioning session for a service identity.

    Create with :meth:`authenticate`; pass the resulting handle as
    ``session=`` to every provisioning transition on
    :class:`~levi.cybrus.broker_founder.FounderBroker`.
    """

    def __init__(
        self,
        identity: str,
        token_id: str,
        gateway,
        created_at: Optional[float] = None,
    ):
        self._identity = identity
        self._token_id = token_id
        self._gateway = gateway
        self._created_at = created_at if created_at is not None else time.time()

    # -- construction ----------------------------------------------------

    @classmethod
    def authenticate(
        cls, identity: str, credential: str, gateway=None
    ) -> "FounderSession":
        """Authenticate ``identity`` with its password and open a session.

        Raises :class:`FounderSessionError` when ``identity`` is a
        founder-tier name (provision through the service identity instead)
        or when authentication fails (the reason is never distinguished).
        The plaintext session token is discarded — only the token id is
        kept on the handle.
        """
        from levi.cybrus.identity import is_founder_identity

        name = str(identity or "").strip()
        if not name:
            raise FounderSessionError("identity is required")
        if is_founder_identity(name):
            raise FounderSessionError(
                f"identity {name!r} is a founder identity: provisioning "
                "sessions are for service identities. Remedy: authenticate "
                "as the founder's service identity (chauncey-ops) and "
                "provision under it — the founder's name never rides the "
                "provisioning path."
            )
        if gateway is None:
            from levi.cybrus.gateway import CybrusGateway

            gateway = CybrusGateway()
        try:
            token_id, _plaintext = gateway.auth(name, credential)
        except Exception as exc:
            raise FounderSessionError("authentication failed") from exc
        # The plaintext session token is deliberately dropped here: the
        # handle proves authentication happened; it is not a bearer token.
        return cls(identity=name, token_id=token_id, gateway=gateway)

    # -- use -------------------------------------------------------------

    @property
    def identity(self) -> str:
        """The authenticated service identity that owns this session."""
        return self._identity

    @property
    def token_id(self) -> str:
        """The gateway session token id (metadata only, not a secret)."""
        return self._token_id

    @property
    def created_at(self) -> float:
        return self._created_at

    def assert_live(self) -> str:
        """Re-check liveness against the gateway and return the identity.

        Raises :class:`FounderSessionError` when the session has expired
        or the gateway restarted (sessions are in-memory). Fail closed:
        a dead session authorizes nothing.
        """
        live = self._gateway.session_live(self._identity)
        if not live:
            raise FounderSessionError(
                f"session for {self._identity!r} is not live (expired or "
                "gateway restarted): authenticate again"
            )
        return self._identity

    def describe(self) -> Dict:
        """Metadata about the session (never secrets)."""
        return {
            "identity": self._identity,
            "token_id": self._token_id[:8],
            "created_at": self._created_at,
            "live": bool(self._gateway.session_live(self._identity)),
        }


def provisioning_session(
    identity: str, credential: str, gateway=None
) -> FounderSession:
    """Open an authenticated provisioning session (FL1 entry point)."""
    return FounderSession.authenticate(identity, credential, gateway=gateway)
