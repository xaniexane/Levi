"""Telescript-style capability-bounded agent execution.

Inspired by the historical Telescript idea of mobile agents carrying
*permits* that bound what they may do on a host. This is an original,
from-scratch reimplementation for LEVI — no Telescript code is used.

Model: a ``Capability`` is a signed, expiring, deny-closed token granting a
*grantee* (an agent or tool executor identity) a set of *actions*. An
executor that holds only granted capabilities cannot perform anything else:
every tool invocation goes through :func:`guarded_call`, which verifies the
token and refuses anything not explicitly permitted. Anything unverifiable
— malformed, tampered, expired, revoked, wrong grantee — is REFUSED
(fail-closed), never executed.

Token format (compact, ASCII-safe):
    base64url(JSON claims) + "." + base64url(HMAC-SHA256(secret, payload))

Claims: ``{"v":1,"iss":issuer,"sub":grantee,"act":[patterns],"exp":epoch,"n":nonce}``

Action patterns:
- exact: ``"memory.store"`` matches only that action
- wildcard: ``"memory.*"`` matches any action with that prefix
- regex: ``"re:^memory\\.(store|recall)$"`` — fullmatch on the remainder

The HMAC secret comes from the ``LEVI_TELESCRIPT_SECRET`` environment
variable when set, otherwise a random per-process secret is generated. A
per-process secret means tokens cannot be verified after a restart — that
is deliberate and documented: capabilities are session-scoped by default.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

_TOKEN_VERSION = 1
_ENV_SECRET = "LEVI_TELESCRIPT_SECRET"


# ---------------------------------------------------------------------------
# Secret management
# ---------------------------------------------------------------------------

_process_secret: Optional[bytes] = None


def _get_secret() -> bytes:
    """Return the HMAC secret: env var if set, else a per-process secret."""
    env = os.environ.get(_ENV_SECRET)
    if env:
        return env.encode("utf-8")
    global _process_secret
    if _process_secret is None:
        _process_secret = secrets.token_bytes(32)
    return _process_secret


def reset_process_secret() -> None:
    """Regenerate the per-process secret (test support; invalidates tokens)."""
    global _process_secret
    _process_secret = secrets.token_bytes(32)


# ---------------------------------------------------------------------------
# Errors — all refusals are explicit and fail-closed
# ---------------------------------------------------------------------------


class CapabilityError(Exception):
    """Base class for every capability refusal."""


class MalformedToken(CapabilityError):
    """The token could not be parsed."""


class InvalidSignature(CapabilityError):
    """The token's HMAC did not verify (tampered or wrong secret)."""


class ExpiredToken(CapabilityError):
    """The token's expiry time has passed."""


class WrongGrantee(CapabilityError):
    """The token was issued to a different grantee."""


class RevokedToken(CapabilityError):
    """The token's nonce is on the revocation list."""


class ActionRefused(CapabilityError):
    """The action is not covered by any granted pattern (deny-closed)."""


# ---------------------------------------------------------------------------
# Capability
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Capability:
    """A verified capability permit.

    ``actions`` holds the raw pattern strings; use :func:`permits` to test.
    """

    issuer: str
    grantee: str
    actions: tuple[str, ...]
    expires_at: float
    nonce: str

    def is_expired(self, now: Optional[float] = None) -> bool:
        return self.expires_at <= (time.time() if now is None else now)

    def to_dict(self) -> dict:
        return {
            "issuer": self.issuer,
            "grantee": self.grantee,
            "actions": list(self.actions),
            "expires_at": self.expires_at,
            "nonce": self.nonce,
        }


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _validate_pattern(pattern: str) -> None:
    """Fail-closed at grant time: reject unusable patterns."""
    if not isinstance(pattern, str) or not pattern:
        raise ValueError(f"invalid action pattern: {pattern!r}")
    if pattern.startswith("re:"):
        try:
            re.compile(pattern[3:])
        except re.error as exc:
            raise ValueError(f"invalid regex pattern {pattern!r}: {exc}") from exc


def issue(
    issuer: str,
    grantee: str,
    actions: list[str],
    ttl_seconds: float = 3600,
    now: Optional[float] = None,
) -> str:
    """Create a signed capability token. Deny-closed: ``actions=[]`` permits nothing."""
    if not issuer or not isinstance(issuer, str):
        raise ValueError("issuer must be a non-empty string")
    if not grantee or not isinstance(grantee, str):
        raise ValueError("grantee must be a non-empty string")
    if not isinstance(actions, (list, tuple)):
        raise ValueError("actions must be a list of patterns")
    for pattern in actions:
        _validate_pattern(pattern)

    issued_at = time.time() if now is None else now
    claims = {
        "v": _TOKEN_VERSION,
        "iss": issuer,
        "sub": grantee,
        "act": list(actions),
        "exp": issued_at + ttl_seconds,
        "n": secrets.token_hex(16),
    }
    payload = _b64e(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    sig = _b64e(hmac.new(_get_secret(), payload.encode("ascii"), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def verify(
    token: str,
    expected_grantee: Optional[str] = None,
    revocations: Optional["RevocationList"] = None,
    now: Optional[float] = None,
) -> Capability:
    """Verify a token and return the Capability. Raises on ANY problem (fail-closed)."""
    if not isinstance(token, str) or token.count(".") != 1:
        raise MalformedToken("token must be 'payload.signature'")

    payload_b64, sig_b64 = token.split(".", 1)
    try:
        payload_bytes = _b64d(payload_b64)
        sig_bytes = _b64d(sig_b64)
    except Exception as exc:
        raise MalformedToken(f"token is not valid base64url: {exc}") from exc

    expected = hmac.new(_get_secret(), payload_b64.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(sig_bytes, expected):
        raise InvalidSignature("HMAC verification failed")

    try:
        claims = json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:
        raise MalformedToken(f"payload is not JSON: {exc}") from exc
    if not isinstance(claims, dict):
        raise MalformedToken("payload must be a JSON object")

    if claims.get("v") != _TOKEN_VERSION:
        raise MalformedToken(f"unsupported token version: {claims.get('v')!r}")
    issuer = claims.get("iss")
    grantee = claims.get("sub")
    actions = claims.get("act")
    expires_at = claims.get("exp")
    nonce = claims.get("n")
    if not isinstance(issuer, str) or not issuer:
        raise MalformedToken("missing/invalid 'iss'")
    if not isinstance(grantee, str) or not grantee:
        raise MalformedToken("missing/invalid 'sub'")
    if not isinstance(actions, list) or not all(isinstance(a, str) for a in actions):
        raise MalformedToken("missing/invalid 'act'")
    if not isinstance(expires_at, (int, float)):
        raise MalformedToken("missing/invalid 'exp'")
    if not isinstance(nonce, str) or not nonce:
        raise MalformedToken("missing/invalid 'n'")

    current = time.time() if now is None else now
    if expires_at <= current:
        raise ExpiredToken("token has expired")

    if expected_grantee is not None and grantee != expected_grantee:
        raise WrongGrantee(f"token issued to {grantee!r}, not {expected_grantee!r}")

    if revocations is not None and revocations.is_revoked(nonce):
        raise RevokedToken("token has been revoked")

    return Capability(
        issuer=issuer,
        grantee=grantee,
        actions=tuple(actions),
        expires_at=float(expires_at),
        nonce=nonce,
    )


# ---------------------------------------------------------------------------
# Revocation
# ---------------------------------------------------------------------------


class RevocationList:
    """In-memory revocation list keyed by token nonce."""

    def __init__(self) -> None:
        self._revoked: set[str] = set()

    def revoke(self, token_or_nonce: str) -> None:
        """Revoke by full token (nonce extracted without full verification) or raw nonce."""
        nonce = token_or_nonce
        if "." in token_or_nonce:
            try:
                payload_b64 = token_or_nonce.split(".", 1)[0]
                claims = json.loads(_b64d(payload_b64).decode("utf-8"))
                maybe = claims.get("n")
                if isinstance(maybe, str):
                    nonce = maybe
            except Exception:
                pass  # fall through: revoke the raw string as-is
        self._revoked.add(nonce)

    def is_revoked(self, nonce: str) -> bool:
        return nonce in self._revoked

    def __len__(self) -> int:
        return len(self._revoked)


# ---------------------------------------------------------------------------
# Action matching (deny-closed)
# ---------------------------------------------------------------------------


def permits(cap: Capability, action: str) -> bool:
    """True iff any granted pattern covers ``action``. No pattern => no permission."""
    if not isinstance(action, str) or not action:
        return False
    for pattern in cap.actions:
        if pattern.startswith("re:"):
            try:
                if re.fullmatch(pattern[3:], action):
                    return True
            except re.error:
                continue  # fail-closed: bad pattern never grants
        elif pattern.endswith("*"):
            if action.startswith(pattern[:-1]):
                return True
        elif action == pattern:
            return True
    return False


# ---------------------------------------------------------------------------
# Guarded execution
# ---------------------------------------------------------------------------


def guarded_call(
    cap_token: str,
    action: str,
    fn: Callable[..., Any],
    *args: Any,
    expected_grantee: Optional[str] = None,
    revocations: Optional[RevocationList] = None,
    now: Optional[float] = None,
    **kwargs: Any,
) -> Any:
    """Verify the token, check the action, then execute ``fn`` — or refuse.

    The tool function is never invoked unless the token is valid, unexpired,
    unrevoked, issued to ``expected_grantee`` (when given), and one of its
    action patterns covers ``action``. Errors from ``fn`` itself propagate
    unchanged.
    """
    cap = verify(cap_token, expected_grantee=expected_grantee, revocations=revocations, now=now)
    if not permits(cap, action):
        raise ActionRefused(f"action {action!r} not permitted by capability for {cap.grantee!r}")
    return fn(*args, **kwargs)


# ---------------------------------------------------------------------------
# Small convenience: a grantee-bound executor holding one or more tokens
# ---------------------------------------------------------------------------


@dataclass
class GuardedExecutor:
    """An agent/tool executor that only holds the capabilities it was granted."""

    grantee: str
    tokens: list[str] = field(default_factory=list)
    revocations: Optional[RevocationList] = None

    def call(self, action: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Try each held token in order; raise ActionRefused if none permit."""
        last_error: Optional[CapabilityError] = None
        for token in self.tokens:
            try:
                return guarded_call(
                    token,
                    action,
                    fn,
                    *args,
                    expected_grantee=self.grantee,
                    revocations=self.revocations,
                    **kwargs,
                )
            except CapabilityError as exc:
                last_error = exc
                continue
        raise ActionRefused(
            f"no held capability permits {action!r} for {self.grantee!r}"
        ) from last_error
