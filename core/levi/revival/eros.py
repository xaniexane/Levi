"""LEVI's least-privilege delegation: capability factories, attenuation,
sealing, and meters (built on telescript).

Inspired by two pure-capability systems: KeyKOS (Tymshare, mid-1970s as
GNOSIS; Norm Hardy et al. — ran production VISA transaction processing
from 1983) with its factories, meters, and "start keys" letting users hand
programs exactly the authority they need; and EROS (Jonathan Shapiro,
SOSP 1999) — a pure capability microkernel with a single-level persistent
store, where capabilities are the only naming and addressing. EROS
research ended and Coyotos stalled ~2010 when the formal-verification
ambition outran resources (CapROS continues in the community); Key Logic
closed ~1991.

Remix delta: KeyKOS/EROS pure-capability discipline reimagined for *agent
delegation* — not a microkernel clone. A factory mints attenuated
capabilities for sub-agents from a root authority ("research flights and
book one" spawns a sub-agent that literally cannot touch email); sealed
tokens are invoke-only; meters bound invocations. The token carrier is
revival.telescript's signed capability tokens — no new crypto invented,
the improvement is the factory/attenuation discipline layered on top.

This is an original, from-scratch reimplementation for LEVI — and it is
deliberately built ON TOP OF :mod:`levi.revival.telescript` rather than
duplicating it:

- telescript is the *carrier*: signed, expiring, deny-closed capability
  tokens (HMAC), ``verify`` / ``permits`` / ``guarded_call``.
- eros adds the *KeyKOS discipline*: **factories** (a root authority that
  mints attenuated capabilities — every minted action must be covered by
  the root authority, checked conservatively), **attenuation/delegation**
  (derive a strictly weaker capability for a sub-agent, optionally for a
  different grantee), **sealing** (invoke-only capabilities that no
  factory will re-derive), and **meters** (capabilities with a bounded
  number of invocations).

The LEVI application: "research flights and book one" spawns a sub-agent
holding only flight-search and calendar-read capabilities — it literally
cannot touch email, because its capability was attenuated from a root
that never granted email. Delegation is least-privilege by construction.

Honesty: LOAD-BEARING — with two stated limits. (1) Sealing is enforced
by the minting authority (the factory), like KeyKOS start keys mediated
by the kernel — it is not cryptographic; a factory that never saw the
token cannot enforce its sealed bit. (2) Tokens are session-scoped via
telescript's secret model; there is no persistent single-level store
here — "persistence is transparent" is EROS's property, not this
module's. Both limits are documented, not hidden.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from levi.revival import telescript


# ---------------------------------------------------------------------------
# Errors — all refusals are explicit and fail-closed
# ---------------------------------------------------------------------------


class AttenuationRefused(telescript.CapabilityError):
    """A minted/derived action is not covered by the granting authority."""


class SealedCapability(telescript.CapabilityError):
    """The capability is sealed: invokable, but no factory will re-derive it."""


class MeterExhausted(telescript.CapabilityError):
    """The meter's invocation budget is spent."""


# ---------------------------------------------------------------------------
# Pattern coverage: does granted pattern P cover requested pattern Q?
# Conservative by design: anything uncertain is NOT covered.
# ---------------------------------------------------------------------------


def pattern_covers(granted: str, requested: str) -> bool:
    """True iff every action matching ``requested`` also matches ``granted``."""
    if granted == requested:
        return True
    if granted.endswith("*"):
        prefix = granted[:-1]
        if requested.startswith("re:"):
            return False  # conservative: regex vs wildcard is unknowable here
        if requested.endswith("*"):
            return requested[:-1].startswith(prefix)
        return requested.startswith(prefix)
    # granted is exact or regex: only identical patterns are covered
    return False


def _check_coverage(
    granted_actions: tuple[str, ...] | list[str], requested: list[str]
) -> None:
    for req in requested:
        if not any(pattern_covers(g, req) for g in granted_actions):
            raise AttenuationRefused(
                f"action pattern {req!r} is not covered by the granting authority"
            )


# ---------------------------------------------------------------------------
# Factory — the minting authority
# ---------------------------------------------------------------------------


class Factory:
    """A KeyKOS-style factory: holds a root authority, mints attenuated
    capabilities. Constructed from a root capability *token*; the root is
    verified fail-closed at construction and never leaves the factory."""

    def __init__(
        self,
        factory_id: str,
        root_token: str,
        expected_grantee: Optional[str] = None,
        revocations: Optional[telescript.RevocationList] = None,
    ):
        if not factory_id or not factory_id.strip():
            raise ValueError("factory_id must be non-empty")
        self.factory_id = factory_id.strip()
        self._revocations = revocations or telescript.RevocationList()
        # Fail-closed: an unverifiable root means no factory at all.
        self._root = telescript.verify(
            root_token, expected_grantee=expected_grantee, revocations=self._revocations
        )
        self._sealed: set[str] = set()  # sealed token nonces
        self._delegation_log: list[dict] = []

    @property
    def root_actions(self) -> tuple[str, ...]:
        return self._root.actions

    def mint(
        self,
        grantee: str,
        actions: list[str],
        ttl_seconds: float = 3600,
        sealed: bool = False,
    ) -> str:
        """Mint a new capability attenuated from the root authority.

        Every requested action pattern must be covered by the root's
        patterns, else :class:`AttenuationRefused`. ``sealed=True`` marks
        the token invoke-only: this factory will refuse to derive from it.
        """
        _check_coverage(self._root.actions, list(actions))
        token = telescript.issue(
            self.factory_id, grantee, list(actions), ttl_seconds=ttl_seconds
        )
        cap = telescript.verify(token)  # self-issued; must verify
        if sealed:
            self._sealed.add(cap.nonce)
        self._delegation_log.append(
            {
                "op": "mint",
                "grantee": grantee,
                "actions": list(actions),
                "sealed": sealed,
                "nonce": cap.nonce,
            }
        )
        return token

    def derive(
        self,
        token: str,
        new_grantee: str,
        actions: list[str],
        ttl_seconds: float = 3600,
        sealed: bool = False,
        expected_grantee: Optional[str] = None,
    ) -> str:
        """Attenuate/delegate: derive a strictly weaker capability from an
        existing one. The derived actions must be covered by the source
        token's actions; sealed source tokens are refused."""
        cap = telescript.verify(
            token, expected_grantee=expected_grantee, revocations=self._revocations
        )
        if cap.nonce in self._sealed:
            raise SealedCapability(
                "capability is sealed: it may be invoked but not re-derived"
            )
        _check_coverage(cap.actions, list(actions))
        new_token = telescript.issue(
            self.factory_id, new_grantee, list(actions), ttl_seconds=ttl_seconds
        )
        new_cap = telescript.verify(new_token)
        if sealed:
            self._sealed.add(new_cap.nonce)
        self._delegation_log.append(
            {
                "op": "derive",
                "from_nonce": cap.nonce,
                "grantee": new_grantee,
                "actions": list(actions),
                "sealed": sealed,
                "nonce": new_cap.nonce,
            }
        )
        return new_token

    def seal(self, token: str) -> None:
        """Seal a factory-minted token: invoke-only from now on.

        Honest limit: enforced by this factory (the minting authority),
        like KeyKOS start keys mediated by the kernel — not cryptographic.
        """
        cap = telescript.verify(token, revocations=self._revocations)
        self._sealed.add(cap.nonce)

    def is_sealed(self, token: str) -> bool:
        cap = telescript.verify(token, revocations=self._revocations)
        return cap.nonce in self._sealed

    def revoke(self, token_or_nonce: str) -> None:
        self._revocations.revoke(token_or_nonce)

    def delegation_log(self) -> list[dict]:
        """Provenance: every mint/derive this factory performed."""
        return [dict(entry) for entry in self._delegation_log]


# ---------------------------------------------------------------------------
# Meter — a KeyKOS meter: bounded invocations
# ---------------------------------------------------------------------------


class Meter:
    """Wraps a capability token with an invocation budget. Each successful
    guarded call spends one unit; at zero the meter refuses."""

    def __init__(
        self,
        token: str,
        budget: int,
        expected_grantee: Optional[str] = None,
        revocations: Optional[telescript.RevocationList] = None,
    ):
        if budget < 0:
            raise ValueError("budget must be non-negative")
        # Verify now: a meter over an invalid token is refused at birth.
        telescript.verify(
            token, expected_grantee=expected_grantee, revocations=revocations
        )
        self._token = token
        self._budget = budget
        self._grantee = expected_grantee
        self._revocations = revocations

    @property
    def remaining(self) -> int:
        return self._budget

    def call(
        self, action: str, fn: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        if self._budget <= 0:
            raise MeterExhausted("meter budget is spent")
        result = telescript.guarded_call(
            self._token,
            action,
            fn,
            *args,
            expected_grantee=self._grantee,
            revocations=self._revocations,
            **kwargs,
        )
        self._budget -= 1
        return result


def invoke(
    token: str,
    action: str,
    fn: Callable[..., Any],
    *args: Any,
    expected_grantee: Optional[str] = None,
    revocations: Optional[telescript.RevocationList] = None,
    **kwargs: Any,
) -> Any:
    """Invoke through a capability: verify, check the action, execute —
    or refuse. (Delegates to :func:`telescript.guarded_call`.)"""
    return telescript.guarded_call(
        token,
        action,
        fn,
        *args,
        expected_grantee=expected_grantee,
        revocations=revocations,
        **kwargs,
    )


__all__ = [
    "AttenuationRefused",
    "SealedCapability",
    "MeterExhausted",
    "pattern_covers",
    "Factory",
    "Meter",
    "invoke",
]
