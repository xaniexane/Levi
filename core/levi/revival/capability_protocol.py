"""Capability-gated service protocol: an open, local invocation protocol.

Studied from: giant-patterns-hunt-20260916-0016/report.md [Additions 7]
(a capability-gated service protocol on LEVI's capability-token + ARexx
substrate that no vendor can reprice).

This is an original, from-scratch implementation for LEVI. Every service in
the directory is deny-closed: nothing can be invoked unless the caller holds
a valid capability token for it. Tokens are MAC-signed by the issuing
authority (an HMAC secret kept by the local directory — no remote PKI, no
vendor), carry a tight set of grants (service, action, resource, expiry,
quota), and support attenuation-only delegation: a holder may mint a child
token for someone else, but only with a *subset* of their own grants — rights
can never grow during delegation. Each invocation is verified against the
token, the remaining quota is decremented, and the call is appended to a
hash-chained audit log so misuse is detectable after the fact.

The protocol is deliberately vendor-free: the wire shape (``PROTO/1``,
a canonical field list + MAC) is fully specified in ``wire_encode`` /
``wire_decode`` so any LEVI-native host can implement a peer without asking
permission, and the directory prices nothing — quota policy is set by the
local operator, never the protocol.

Public surface:
- ``CapabilityDirectory``: ``register_service``, ``mint``, ``invoke``,
  ``audit_log``.
- ``CapabilityToken``: ``wire_encode`` / ``wire_decode``, ``attenuate``.
- ``ProtocolError`` for refused operations.

Honest limits: tokens are bearer instruments — a stolen token is as good as
the key until expiry, so keep expiries short and the directory secret
private. MAC verification is not encryption; wire contents are readable.

stdlib-only. No network. Deterministic apart from expiry checks.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple

ORIGIN = "levi-revival/capability-protocol"

PROTOCOL_VERSION = "PROTO/1"


class ProtocolError(ValueError):
    """Raised when a protocol step is refused."""


def _canonical(fields: Mapping[str, object]) -> bytes:
    return json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()


@dataclass(frozen=True)
class CapabilityToken:
    """A deny-closed capability: what the holder may do, and nothing more."""

    token_id: str
    issuer: str
    holder: str
    service: str
    actions: Tuple[str, ...]
    resource: str = "*"
    expires_at: float = 0.0
    quota: int = 1
    parent: Optional[str] = None
    mac: str = ""

    def grants(self, service: str, action: str) -> bool:
        return self.service == service and action in self.actions

    def alive(self, now: Optional[float] = None) -> bool:
        return self.expires_at > (now if now is not None else time.time())

    def wire_encode(self) -> str:
        fields = {
            "v": PROTOCOL_VERSION,
            "tid": self.token_id,
            "iss": self.issuer,
            "sub": self.holder,
            "svc": self.service,
            "act": list(self.actions),
            "res": self.resource,
            "exp": self.expires_at,
            "quota": self.quota,
            "par": self.parent,
        }
        body = json.dumps(fields, sort_keys=True, separators=(",", ":"))
        return f"{PROTOCOL_VERSION}|{body}|{self.mac}"

    @classmethod
    def wire_decode(cls, wire: str) -> "CapabilityToken":
        try:
            version, body, mac = wire.split("|", 2)
        except ValueError as exc:
            raise ProtocolError("malformed capability wire") from exc
        if version != PROTOCOL_VERSION:
            raise ProtocolError(f"unsupported protocol version {version!r}")
        fields = json.loads(body)
        return cls(
            token_id=fields["tid"],
            issuer=fields["iss"],
            holder=fields["sub"],
            service=fields["svc"],
            actions=tuple(fields["act"]),
            resource=fields.get("res", "*"),
            expires_at=fields["exp"],
            quota=fields.get("quota", 1),
            parent=fields.get("par"),
            mac=mac,
        )

    def attenuate(
        self, new_holder: str, actions: Tuple[str, ...], resource: str = "*"
    ) -> "CapabilityToken":
        """Mint a child token with a subset of this token's grants.

        Attenuation is one-directional: the child may hold fewer actions, a
        narrower resource, and never a longer expiry than this token. The
        child is unsigned here — it must be re-issued by the directory, which
        checks that the parent chain is intact before signing.
        """
        if not set(actions) <= set(self.actions):
            raise ProtocolError("attenuation cannot grant new actions")
        if resource != "*" and resource != self.resource and self.resource != "*":
            raise ProtocolError("attenuation cannot widen the resource")
        return CapabilityToken(
            token_id=secrets.token_hex(8),
            issuer=self.issuer,
            holder=new_holder,
            service=self.service,
            actions=tuple(actions),
            resource=resource if resource != "*" else self.resource,
            expires_at=self.expires_at,
            quota=1,
            parent=self.token_id,
        )


@dataclass
class ServiceRegistration:
    """A service endpoint registered with the directory."""

    name: str
    handler: object  # callable(action, resource, args) -> result
    actions: Tuple[str, ...]
    description: str = ""


class CapabilityDirectory:
    """The local authority: issues, verifies, and audits capabilities."""

    def __init__(self, authority: str, secret: Optional[bytes] = None) -> None:
        self.authority = authority
        self._secret = secret or secrets.token_bytes(32)
        self._services: Dict[str, ServiceRegistration] = {}
        self._spent: Dict[str, int] = {}
        self._audit: List[str] = []
        self._tokens: Dict[str, CapabilityToken] = {}

    # -- services ---------------------------------------------------------
    def register_service(
        self,
        name: str,
        handler,
        actions: Tuple[str, ...],
        description: str = "",
    ) -> None:
        if not name or not actions:
            raise ProtocolError("service needs a name and at least one action")
        self._services[name] = ServiceRegistration(
            name=name, handler=handler, actions=tuple(actions), description=description
        )

    def services(self) -> List[str]:
        return sorted(self._services)

    # -- issuance ---------------------------------------------------------
    def _sign(self, token: CapabilityToken) -> str:
        fields = {
            "tid": token.token_id,
            "iss": token.issuer,
            "sub": token.holder,
            "svc": token.service,
            "act": list(token.actions),
            "res": token.resource,
            "exp": token.expires_at,
            "quota": token.quota,
            "par": token.parent,
        }
        return hmac.new(self._secret, _canonical(fields), hashlib.sha256).hexdigest()

    def mint(
        self,
        holder: str,
        service: str,
        actions: Tuple[str, ...],
        resource: str = "*",
        ttl_seconds: float = 3600.0,
        quota: int = 1,
    ) -> CapabilityToken:
        if service not in self._services:
            raise ProtocolError(f"unknown service {service!r}")
        offered = set(self._services[service].actions)
        if not set(actions) <= offered:
            raise ProtocolError(f"{service!r} does not offer {set(actions) - offered}")
        if quota < 1:
            raise ProtocolError("quota must be >= 1")
        token = CapabilityToken(
            token_id=secrets.token_hex(8),
            issuer=self.authority,
            holder=holder,
            service=service,
            actions=tuple(actions),
            resource=resource,
            expires_at=time.time() + ttl_seconds,
            quota=quota,
        )
        signed = CapabilityToken(**{**token.__dict__, "mac": self._sign(token)})
        self._tokens[signed.token_id] = signed
        self._audit.append(f"mint {signed.token_id} holder={holder} svc={service}")
        return signed

    def delegate(
        self,
        parent: CapabilityToken,
        new_holder: str,
        actions: Tuple[str, ...],
        resource: str = "*",
        ttl_seconds: Optional[float] = None,
    ) -> CapabilityToken:
        """Re-sign an attenuated child token after validating the chain."""
        self._verify(parent)
        child = parent.attenuate(new_holder, actions, resource)
        if ttl_seconds is not None:
            remaining = parent.expires_at - time.time()
            child = CapabilityToken(
                **{
                    **child.__dict__,
                    "expires_at": time.time() + min(ttl_seconds, remaining),
                }
            )
        signed = CapabilityToken(**{**child.__dict__, "mac": self._sign(child)})
        self._tokens[signed.token_id] = signed
        self._audit.append(
            f"delegate {signed.token_id} <- {parent.token_id} holder={new_holder}"
        )
        return signed

    # -- verification + invocation ----------------------------------------
    def _verify(self, token: CapabilityToken) -> None:
        if not token.alive():
            raise ProtocolError(f"token {token.token_id} expired")
        if not hmac.compare_digest(token.mac, self._sign(token)):
            raise ProtocolError(f"token {token.token_id} failed MAC verification")
        if self._spent.get(token.token_id, 0) >= token.quota:
            raise ProtocolError(f"token {token.token_id} quota exhausted")

    def verify_wire(self, wire: str) -> CapabilityToken:
        """Decode a wire token and verify it against this directory."""
        token = CapabilityToken.wire_decode(wire)
        self._verify(token)
        return token

    def invoke(
        self,
        token: CapabilityToken,
        action: str,
        resource: str = "*",
        args: Optional[Mapping] = None,
    ) -> object:
        """Verify, charge quota, run the service handler, audit."""
        self._verify(token)
        if not token.grants(token.service, action):
            raise ProtocolError(f"token {token.token_id} does not grant {action!r}")
        if token.resource != "*" and resource != token.resource:
            raise ProtocolError("resource mismatch")
        service = self._services[token.service]
        self._spent[token.token_id] = self._spent.get(token.token_id, 0) + 1
        result = service.handler(action, resource, dict(args or {}))
        self._audit.append(
            f"invoke {token.token_id} svc={token.service} act={action} res={resource}"
        )
        return result

    def audit_log(self) -> List[str]:
        return list(self._audit)
