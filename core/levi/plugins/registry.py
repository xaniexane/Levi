"""Connector contract for external-service plugins (blueprint §3, §1.5).

A *connector* is the single honest gateway between LEVI and a
third-party account. Every connector declares:

* ``id`` / ``display_name`` — stable identifiers;
* ``credential_env_var`` — the one and only place its credential is read
  from (never logged, never printed, never written to disk);
* ``capabilities`` — what the connector can do;
* ``operations`` — the named actions ``execute()`` understands, each
  flagged as read or write.

Honesty rules (enforced here, not left to each connector):

1. ``execute()`` with no credential in the environment returns
   ``ok=False`` with status ``"missing_credential"`` and states exactly
   which env var is missing. Nothing is sent.
2. ``execute()`` with a credential but no transport wired returns
   ``ok=False`` with status ``"transport_not_wired"`` and says so
   plainly. Nothing is sent.
3. Any connector exposing at least one *write* capability or operation
   gets ``requires_confirmation=True`` forced at class-definition time —
   no per-feature override is possible. A write operation without an
   explicit ``confirm=True`` returns ``ok=False`` with status
   ``"confirmation_required"`` and never reaches the transport.
4. Success is never simulated: ``ok=True`` is returned only after the
   transport actually ran and reported success.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Capability:
    """Something a connector can do.

    ``write=True`` means the capability can change state on a third-party
    account (post, create, delete, move money, ...).
    """

    name: str
    description: str = ""
    write: bool = False


@dataclass(frozen=True)
class Operation:
    """A named action ``execute()`` understands."""

    name: str
    description: str
    write: bool = False
    params: tuple[str, ...] = ()


@dataclass
class ExecutionResult:
    """The honest outcome of an ``execute()`` call."""

    connector: str
    operation: str
    ok: bool
    status: str  # ok | missing_credential | transport_not_wired |
                 # confirmation_required | unknown_operation |
                 # invalid_params | api_error
    message: str
    data: dict[str, Any] | None = None
    request_made: bool = False


class TransportNotWired(Exception):
    """Raised by the default ``_call_api`` when a connector has not wired
    its transport. ``execute()`` converts this into an honest result."""


#: Fake-transport signature used by ``execute(..., transport=...)``:
#: ``transport(method, path, token, body) -> response payload``.
Transport = Callable[[str, str, str, Any], Any]


# ---------------------------------------------------------------------------
# Connector base
# ---------------------------------------------------------------------------


class Connector(ABC):
    """Base class for every third-party connector."""

    id: ClassVar[str] = ""
    display_name: ClassVar[str] = ""
    credential_env_var: ClassVar[str] = ""
    capabilities: ClassVar[tuple[Capability, ...]] = ()
    operations: ClassVar[tuple[Operation, ...]] = ()
    requires_confirmation: ClassVar[bool] = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Blueprint §1.5: anything that can write to a third-party account
        # or move money requires confirmation, with no per-feature
        # override. Enforce at class-definition time so a subclass cannot
        # silently opt out.
        writes = any(c.write for c in cls.capabilities) or any(
            o.write for o in cls.operations
        )
        if writes:
            cls.requires_confirmation = True

    # -- credential handling ----------------------------------------------

    def credential(self) -> str | None:
        """Read the credential from its declared env var.

        Returns ``None`` when the var is missing or blank. The value is
        returned to the caller only — never logged, printed, or stored.
        """
        if not self.credential_env_var:
            return None
        value = os.environ.get(self.credential_env_var, "")
        return value if value.strip() else None

    def missing_credential_message(self) -> str:
        return (
            f"missing credential: set {self.credential_env_var} "
            "— nothing was sent."
        )

    # -- operation lookup -------------------------------------------------

    def _operation(self, name: str) -> Operation | None:
        for op in self.operations:
            if op.name == name:
                return op
        return None

    # -- transport --------------------------------------------------------

    def _call_api(
        self, method: str, path: str, token: str, body: Any = None
    ) -> Any:
        """Perform one authenticated request. Subclasses wire this to a
        real transport (stdlib ``urllib`` for the kernel).

        The base implementation raises :class:`TransportNotWired` so a
        credential-bearing connector without a transport states that
        plainly instead of pretending to work.
        """
        raise TransportNotWired(
            f"connector '{self.id}' has a credential configured but no "
            "transport is wired — nothing was sent."
        )

    # -- execution --------------------------------------------------------

    def execute(
        self,
        operation: str,
        params: dict[str, Any] | None = None,
        *,
        confirm: bool = False,
        transport: Transport | None = None,
    ) -> ExecutionResult:
        """Run a named operation, honestly.

        Checks, in order: the operation exists → confirmation (writes) →
        credential present → transport wired → real call. Any failure
        returns an ``ExecutionResult`` with ``ok=False``; success is only
        reported after the transport actually ran.
        """
        params = dict(params or {})

        op = self._operation(operation)
        if op is None:
            known = ", ".join(o.name for o in self.operations) or "(none)"
            return ExecutionResult(
                connector=self.id,
                operation=operation,
                ok=False,
                status="unknown_operation",
                message=(
                    f"unknown operation {operation!r} for connector "
                    f"'{self.id}'. Known: {known} — nothing was sent."
                ),
            )

        if op.write and self.requires_confirmation and not confirm:
            return ExecutionResult(
                connector=self.id,
                operation=operation,
                ok=False,
                status="confirmation_required",
                message=(
                    f"operation {operation!r} can write to a third-party "
                    "account and requires explicit confirmation — nothing "
                    "was sent. Re-run with confirm=True (CLI: --yes)."
                ),
            )

        token = self.credential()
        if token is None:
            return ExecutionResult(
                connector=self.id,
                operation=operation,
                ok=False,
                status="missing_credential",
                message=self.missing_credential_message(),
            )

        try:
            payload = self.perform(operation, params, token, transport)
        except TransportNotWired as exc:
            return ExecutionResult(
                connector=self.id,
                operation=operation,
                ok=False,
                status="transport_not_wired",
                message=str(exc),
            )
        except ConnectorAPIError as exc:
            return ExecutionResult(
                connector=self.id,
                operation=operation,
                ok=False,
                status="api_error",
                message=str(exc),
            )
        except InvalidParams as exc:
            return ExecutionResult(
                connector=self.id,
                operation=operation,
                ok=False,
                status="invalid_params",
                message=str(exc),
            )
        return ExecutionResult(
            connector=self.id,
            operation=operation,
            ok=True,
            status="ok",
            message=f"operation {operation!r} completed.",
            data=payload if isinstance(payload, dict) else {"result": payload},
            request_made=True,
        )

    # -- per-connector logic ----------------------------------------------

    @abstractmethod
    def perform(
        self,
        operation: str,
        params: dict[str, Any],
        token: str,
        transport: Transport | None,
    ) -> Any:
        """Run ``operation`` against the real API using ``token``.

        Use ``transport(method, path, token, body)`` when provided (tests
        inject fakes here); otherwise call ``self._call_api(...)``.

        Raise :class:`InvalidParams` for bad input and
        :class:`ConnectorAPIError` for remote failures — both carry
        messages that must never include the credential.
        """


class ConnectorAPIError(Exception):
    """A remote call failed. Message must never contain the credential."""


class InvalidParams(Exception):
    """Caller-supplied params failed validation. Nothing was sent."""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


_REGISTRY: dict[str, type[Connector]] = {}


def register_connector(cls: type[Connector]) -> type[Connector]:
    """Register a connector class by its ``id``."""
    if not cls.id:
        raise ValueError(f"{cls.__name__} must define a non-empty id")
    if not cls.credential_env_var:
        raise ValueError(
            f"{cls.__name__} must declare credential_env_var"
        )
    _REGISTRY[cls.id] = cls
    return cls


def get_connector(connector_id: str) -> Connector | None:
    cls = _REGISTRY.get(connector_id)
    return cls() if cls is not None else None


def list_connectors() -> list[Connector]:
    return [cls() for _, cls in sorted(_REGISTRY.items())]


def describe(connector: Connector) -> str:
    """One human-readable summary line block per connector."""
    caps = ", ".join(
        f"{c.name}{'*' if c.write else ''}" for c in connector.capabilities
    )
    ops = ", ".join(
        f"{o.name}{'*' if o.write else ''}" for o in connector.operations
    )
    return (
        f"{connector.id} — {connector.display_name}\n"
        f"  credential: {connector.credential_env_var} "
        f"({'present' if connector.credential() else 'missing'})\n"
        f"  capabilities: {caps or '(none)'}\n"
        f"  operations: {ops or '(none)'}  (* = write)\n"
        f"  requires_confirmation: {connector.requires_confirmation}"
    )
