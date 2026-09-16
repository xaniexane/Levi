"""Capability token attenuation + audit ledger, over telescript.

:mod:`levi.revival.telescript` mints and verifies bearer capability
tokens. This module adds the two operations the giants refuse to sell
you because they kill the toll booth:

- :func:`attenuate` — macaroon-style narrowing. Take a token you hold and
  mint a strictly *less* powerful one: a subset of its action patterns
  and/or an earlier expiry. The attenuated token keeps the same issuer
  and grantee, gets a fresh nonce, and can itself be attenuated further.
  Attenuation can NEVER widen: asking for a pattern the parent token does
  not carry, or an expiry past the parent's, is refused (fail-closed).
- :class:`MintLedger` — append-only, owner-only JSONL audit trail of
  every issuance, attenuation, and revocation on this machine.

Tokens are bearer instruments signed with the telescript HMAC secret
(``LEVI_TELESCRIPT_SECRET`` env var, else a per-process secret — see
:mod:`levi.revival.telescript`). Cross-process use requires the env var.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.revival.telescript import (
    Capability,
    RevocationList,
    issue,
    verify,
)

__all__ = [
    "AttenuationError",
    "attenuate",
    "decode",
    "MintLedger",
    "default_home",
]


class AttenuationError(Exception):
    """An attenuation request tried to widen (or was otherwise invalid)."""


def default_home() -> Path:
    """Resolve ~/.levi at CALL time (hermetic: HOME/LEVI_HOME respected)."""
    override = os.environ.get("LEVI_HOME")
    base = Path(override) if override else Path(os.path.expanduser("~/.levi"))
    return base / "capproto"


def _require_patterns(actions: Optional[List[str]], parent: Capability) -> tuple[str, ...]:
    if actions is None:
        return parent.actions
    if not isinstance(actions, (list, tuple)):
        raise AttenuationError("attenuate: actions must be a list of patterns or None")
    parent_set = set(parent.actions)
    for pattern in actions:
        if not isinstance(pattern, str) or not pattern:
            raise AttenuationError(f"attenuate: invalid action pattern {pattern!r}")
        if pattern not in parent_set:
            # Fail-closed: the new token must grant strictly less than the
            # parent. Patterns are matched by telescript's own deny-closed
            # matcher, so subset-at-string-level is the honest check.
            raise AttenuationError(
                f"attenuate: pattern {pattern!r} is not covered by the parent "
                f"token (parent grants {sorted(parent_set)}); refusing to widen"
            )
    return tuple(actions)


def attenuate(
    token: str,
    *,
    actions: Optional[List[str]] = None,
    ttl_seconds: Optional[float] = None,
    now: Optional[float] = None,
    ledger: Optional["MintLedger"] = None,
) -> str:
    """Mint a strictly narrower token from one you hold.

    Verifies the parent token first (expired/tampered/revoked parents
    refuse). ``actions`` must be a subset of the parent's patterns;
    ``ttl_seconds`` (from now) must not push expiry past the parent's.
    Returns the new token string.

    When ``ledger`` is given, the attenuation is recorded with the parent
    nonce for audit.
    """
    current = time.time() if now is None else now
    parent = verify(token, now=current)  # raises on any problem
    new_actions = _require_patterns(actions, parent)
    if ttl_seconds is not None:
        try:
            ttl = float(ttl_seconds)
        except (TypeError, ValueError):
            raise AttenuationError(
                "attenuate: ttl_seconds must be a number"
            ) from None
        if ttl <= 0:
            raise AttenuationError("attenuate: ttl_seconds must be positive")
        if current + ttl > parent.expires_at:
            raise AttenuationError(
                f"attenuate: requested expiry ({current + ttl:.0f}) exceeds the "
                f"parent token's expiry ({parent.expires_at:.0f}); refusing to widen"
            )
        child_ttl = ttl
    else:
        child_ttl = max(1.0, parent.expires_at - current)
    child = issue(
        parent.issuer,
        parent.grantee,
        list(new_actions),
        ttl_seconds=child_ttl,
        now=current,
    )
    if ledger is not None:
        ledger.record_attenuated(parent, child, current=current)
    return child


def decode(token: str) -> Dict[str, Any]:
    """Decode a token's claims WITHOUT verifying the signature.

    This is an inspection aid (debugging, ``capproto verify`` display).
    The returned claims are UNTRUSTED — never authorize from them. Use
    :func:`verify` (via :mod:`levi.revival.telescript`) for decisions.
    """
    if not isinstance(token, str) or token.count(".") != 1:
        raise AttenuationError("decode: token must be 'payload.signature'")
    import base64

    payload_b64 = token.split(".", 1)[0]
    pad = "=" * (-len(payload_b64) % 4)
    try:
        claims = json.loads(
            base64.urlsafe_b64decode(payload_b64 + pad).decode("utf-8")
        )
    except Exception as exc:
        raise AttenuationError(f"decode: token payload is not JSON ({exc})") from exc
    if not isinstance(claims, dict):
        raise AttenuationError("decode: token payload must be a JSON object")
    return claims


class MintLedger:
    """Append-only audit trail of token issuance/attenuation/revocation.

    Stored at ``<home>/mints.jsonl``; home is created owner-only (0700).
    """

    def __init__(self, home: Optional[Path] = None):
        self.home = Path(home) if home else default_home()
        self.home.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.home, 0o700)
        except OSError:
            pass
        self._path = self.home / "mints.jsonl"

    @staticmethod
    def _nonce(token: str) -> str:
        try:
            return str(decode(token).get("n", "?"))
        except AttenuationError:
            return "?"

    def _record(self, event: str, token: str, **extra: Any) -> None:
        claims = decode(token)
        record = {
            "ts": time.time(),
            "event": event,
            "nonce": claims.get("n"),
            "issuer": claims.get("iss"),
            "grantee": claims.get("sub"),
            "actions": claims.get("act"),
            "exp": claims.get("exp"),
        }
        record.update(extra)
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, separators=(",", ":")) + "\n")

    def record_issued(self, token: str) -> None:
        self._record("issued", token)

    def record_attenuated(self, parent: Capability, child_token: str, current: Optional[float] = None) -> None:
        self._record(
            "attenuated",
            child_token,
            parent_nonce=parent.nonce,
            parent_actions=list(parent.actions),
        )

    def record_revoked(self, token: str) -> None:
        self._record("revoked", token)

    def entries(self) -> List[Dict[str, Any]]:
        """Read the ledger (newest last). Corrupt lines are skipped, not fatal."""
        out: List[Dict[str, Any]] = []
        if not self._path.exists():
            return out
        with open(self._path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
        return out

    def revocation_list(self) -> RevocationList:
        """Rebuild a RevocationList from ledger 'revoked' events."""
        rl = RevocationList()
        for rec in self.entries():
            if rec.get("event") == "revoked" and rec.get("nonce"):
                rl.revoke(str(rec["nonce"]))
        return rl
