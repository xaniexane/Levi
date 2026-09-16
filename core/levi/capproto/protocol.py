"""capproto/1 wire protocol: messages, validation, service dispatch.

The protocol spec is defined here in code and narrated in
``docs/CAPPROTO.md``. Framing: newline-delimited UTF-8 JSON, one message
per line, UTF-8, max line 1 MiB (fail-closed against resource abuse).

Messages (``v`` is always ``"capproto/1"``):

- client -> server ``{"v","id","op":"hello","agent":str}``
- client -> server ``{"v","id","op":"call","svc":str,"verb":str,
    "token":str,"args":object}``
- client -> server ``{"v","id","op":"revoke","token":str}``
- client -> server ``{"v","id","op":"bye"}``
- server -> client ``{"v","id","ok":true,"result":any}``
- server -> client ``{"v","id","ok":false,"error":str,"error_type":str}``

``error_type`` is one of: ``protocol`` ``auth`` ``refused`` ``unknown_verb``
``bad_args`` ``server``. The token on a ``call`` is verified with
:mod:`levi.revival.telescript`; the *action* checked is
``"<svc>.<verb>"`` against the token's patterns. Anything failing that —
malformed, tampered, expired, revoked, wrong grantee, or simply not
permitted — is REFUSED without invoking the verb. Deny-closed: unknown
verbs and missing args are errors, never guessed.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from levi.revival.telescript import (
    ActionRefused,
    CapabilityError,
    RevocationList,
    guarded_call,
)

from .tokens import MintLedger

__all__ = [
    "SPEC_VERSION",
    "MAX_LINE_BYTES",
    "ProtocolError",
    "ERROR_TYPES",
    "msg_hello",
    "msg_call",
    "msg_revoke",
    "msg_bye",
    "ok_response",
    "error_response",
    "validate_message",
    "ServiceSpec",
    "Verb",
]

SPEC_VERSION = "capproto/1"
MAX_LINE_BYTES = 1 << 20  # 1 MiB per framed line

ERROR_TYPES = ("protocol", "auth", "refused", "unknown_verb", "bad_args", "server")


class ProtocolError(Exception):
    """A wire message violates the capproto/1 spec."""


def _base(op: str, msg_id: Optional[str] = None) -> Dict[str, Any]:
    return {"v": SPEC_VERSION, "id": msg_id or uuid.uuid4().hex, "op": op}


def msg_hello(agent: str, msg_id: Optional[str] = None) -> Dict[str, Any]:
    if not isinstance(agent, str) or not agent:
        raise ProtocolError("hello: agent must be a non-empty string")
    m = _base("hello", msg_id)
    m["agent"] = agent
    return m


def msg_call(
    svc: str,
    verb: str,
    token: str,
    args: Optional[Dict[str, Any]] = None,
    msg_id: Optional[str] = None,
) -> Dict[str, Any]:
    for name, value in (("svc", svc), ("verb", verb), ("token", token)):
        if not isinstance(value, str) or not value:
            raise ProtocolError(f"call: {name} must be a non-empty string")
    if args is not None and not isinstance(args, dict):
        raise ProtocolError("call: args must be an object")
    m = _base("call", msg_id)
    m.update({"svc": svc, "verb": verb, "token": token, "args": args or {}})
    return m


def msg_revoke(token: str, msg_id: Optional[str] = None) -> Dict[str, Any]:
    if not isinstance(token, str) or not token:
        raise ProtocolError("revoke: token must be a non-empty string")
    m = _base("revoke", msg_id)
    m["token"] = token
    return m


def msg_bye(msg_id: Optional[str] = None) -> Dict[str, Any]:
    return _base("bye", msg_id)


def ok_response(msg_id: str, result: Any) -> Dict[str, Any]:
    return {"v": SPEC_VERSION, "id": msg_id, "ok": True, "result": result}


def error_response(msg_id: str, error_type: str, error: str) -> Dict[str, Any]:
    if error_type not in ERROR_TYPES:
        error_type = "server"
    return {
        "v": SPEC_VERSION,
        "id": msg_id,
        "ok": False,
        "error": str(error),
        "error_type": error_type,
    }


def validate_message(raw: Any) -> Dict[str, Any]:
    """Validate an inbound message; return it typed or raise ProtocolError."""
    if not isinstance(raw, dict):
        raise ProtocolError("message must be a JSON object")
    if raw.get("v") != SPEC_VERSION:
        raise ProtocolError(f"unsupported protocol version {raw.get('v')!r}")
    op = raw.get("op")
    if op not in ("hello", "call", "revoke", "bye"):
        raise ProtocolError(f"unknown op {op!r}")
    if not isinstance(raw.get("id"), str) or not raw["id"]:
        raise ProtocolError("message id must be a non-empty string")
    if op == "call":
        for key in ("svc", "verb", "token"):
            if not isinstance(raw.get(key), str) or not raw[key]:
                raise ProtocolError(f"call: {key} must be a non-empty string")
        if "args" in raw and not isinstance(raw["args"], dict):
            raise ProtocolError("call: args must be an object")
    if op == "revoke" and (
        not isinstance(raw.get("token"), str) or not raw["token"]
    ):
        raise ProtocolError("revoke: token must be a non-empty string")
    if op == "hello" and (
        not isinstance(raw.get("agent"), str) or not raw["agent"]
    ):
        raise ProtocolError("hello: agent must be a non-empty string")
    return raw


# ---------------------------------------------------------------------------
# ServiceSpec — a named service whose verbs are gated by capabilities
# ---------------------------------------------------------------------------


@dataclass
class Verb:
    """One callable verb on a service."""

    name: str
    handler: Callable[..., Any]
    required_args: List[str] = field(default_factory=list)
    summary: str = ""


class ServiceSpec:
    """A named capability-gated service.

    ``name`` is the service id (e.g. ``"kvnote"``); capability actions are
    checked as ``"<name>.<verb>"``. Verbs are deny-closed: dispatching an
    unregistered verb raises, never guesses.
    """

    def __init__(self, name: str):
        if not isinstance(name, str) or not name:
            raise ValueError("ServiceSpec: name must be a non-empty string")
        self.name = name
        self.verbs: Dict[str, Verb] = {}
        self.revocations = RevocationList()
        self.ledger: Optional[MintLedger] = None

    def add_verb(
        self,
        name: str,
        handler: Callable[..., Any],
        required_args: Optional[List[str]] = None,
        summary: str = "",
    ) -> "ServiceSpec":
        if name in self.verbs:
            raise ValueError(f"ServiceSpec: verb {name!r} already registered")
        self.verbs[name] = Verb(
            name=name,
            handler=handler,
            required_args=list(required_args or []),
            summary=summary,
        )
        return self

    def action_for(self, verb: str) -> str:
        return f"{self.name}.{verb}"

    def describe(self) -> Dict[str, Any]:
        return {
            "service": self.name,
            "protocol": SPEC_VERSION,
            "verbs": {
                name: {
                    "action": self.action_for(name),
                    "required_args": v.required_args,
                    "summary": v.summary,
                }
                for name, v in self.verbs.items()
            },
        }

    def dispatch(
        self,
        verb: str,
        token: str,
        args: Dict[str, Any],
        expected_grantee: Optional[str] = None,
    ) -> Any:
        """Verify the token, check the capability, then run the verb.

        Raises :class:`ProtocolError` for unknown verbs / missing args,
        and the original telescript refusal types for token problems —
        never wrapped into vagueness.
        """
        spec = self.verbs.get(verb)
        if spec is None:
            raise ProtocolError(
                f"unknown_verb: {self.name!r} has no verb {verb!r} "
                f"(known: {sorted(self.verbs)})"
            )
        args = dict(args or {})
        missing = [a for a in spec.required_args if a not in args]
        if missing:
            raise ProtocolError(
                f"bad_args: verb {verb!r} requires args {missing}"
            )
        action = self.action_for(verb)
        return guarded_call(
            token,
            action,
            spec.handler,
            expected_grantee=expected_grantee,
            revocations=self.revocations,
            **args,
        )

    def revoke_token(self, token: str) -> None:
        self.revocations.revoke(token)
        if self.ledger is not None:
            self.ledger.record_revoked(token)
