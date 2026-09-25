"""ARexx-style named application command ports.

Inspired by ARexx's named message ports, which let scripts send textual
commands ("verbs") to running applications. Original, from-scratch
reimplementation for LEVI — no ARexx code is used.

A :class:`PortRegistry` lets LEVI modules register named verbs on named
ports::

    registry.register_port("memory", {"store": store_fn, "recall": recall_fn})
    registry.send_command("memory", "store", args=["fact", "..."])

Verbs are resolved by name. Unknown ports and unknown verbs are refused
with clear, typed errors — never silently ignored. Ports may carry an
optional deny-closed allowlist ACL: when present, only listed callers may
invoke; everyone else (including an unnamed caller) is refused.

Ports can also be served over a 9P-style channel (see ``revival.plan9``,
imported lazily) so a script can drive modules in another thread via
:class:`RemoteRegistry`. And :func:`run_script` executes a list of
port/verb commands sequentially with per-step result capture.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

__all__ = [
    "PortError",
    "UnknownPort",
    "UnknownVerb",
    "AccessDenied",
    "PortRegistry",
    "StepResult",
    "run_script",
    "serve_registry",
    "RemoteRegistry",
]


# ---------------------------------------------------------------------------
# Errors — refusals are explicit and typed
# ---------------------------------------------------------------------------


class PortError(Exception):
    """Base class for port command failures."""


class UnknownPort(PortError):
    """No port is registered under that name."""


class UnknownVerb(PortError):
    """The port exists but has no such verb."""


class AccessDenied(PortError):
    """The caller is not on the port's allowlist (deny-closed)."""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@dataclass
class _Port:
    name: str
    verbs: dict[str, Callable[..., Any]]
    acl: Optional[frozenset[str]] = None  # allowlist of caller names; None = open


class PortRegistry:
    """In-process registry of named application command ports."""

    def __init__(self) -> None:
        self._ports: dict[str, _Port] = {}

    # -- registration ------------------------------------------------------
    def register_port(
        self,
        name: str,
        verbs: dict[str, Callable[..., Any]],
        acl: Optional[list[str]] = None,
    ) -> None:
        """Register ``name`` with a mapping of verb name -> callable.

        ``acl`` is an optional deny-closed allowlist of caller names.
        """
        if not isinstance(name, str) or not name:
            raise ValueError("port name must be a non-empty string")
        if not isinstance(verbs, dict) or not verbs:
            raise ValueError("verbs must be a non-empty dict of name -> callable")
        for verb, fn in verbs.items():
            if not isinstance(verb, str) or not verb:
                raise ValueError(f"invalid verb name: {verb!r}")
            if not callable(fn):
                raise ValueError(f"verb {verb!r} is not callable")
        self._ports[name] = _Port(
            name=name,
            verbs=dict(verbs),
            acl=frozenset(acl) if acl is not None else None,
        )

    def unregister_port(self, name: str) -> None:
        try:
            del self._ports[name]
        except KeyError:
            raise UnknownPort(f"unknown port: {name!r}") from None

    def has_port(self, name: str) -> bool:
        return name in self._ports

    def list_ports(self) -> dict[str, list[str]]:
        """Map port name -> sorted verb names (introspection, no callables)."""
        return {name: sorted(port.verbs) for name, port in self._ports.items()}

    # -- dispatch ------------------------------------------------------------
    def _resolve(
        self, port: str, verb: str, caller: Optional[str]
    ) -> Callable[..., Any]:
        try:
            entry = self._ports[port]
        except KeyError:
            raise UnknownPort(f"unknown port: {port!r}") from None
        if entry.acl is not None and caller not in entry.acl:
            raise AccessDenied(
                f"caller {caller!r} is not allowed on port {port!r} (deny-closed allowlist)"
            )
        try:
            return entry.verbs[verb]
        except KeyError:
            raise UnknownVerb(f"port {port!r} has no verb {verb!r}") from None

    def send_command(
        self,
        port: str,
        verb: str,
        args: Optional[list[Any]] = None,
        kwargs: Optional[dict[str, Any]] = None,
        caller: Optional[str] = None,
    ) -> Any:
        """Resolve ``port``/``verb`` and invoke it. Refusals raise typed errors."""
        fn = self._resolve(port, verb, caller)
        return fn(*(args or []), **(kwargs or {}))


# ---------------------------------------------------------------------------
# Script runner
# ---------------------------------------------------------------------------


@dataclass
class StepResult:
    """Outcome of one scripted port/verb command."""

    index: int
    port: str
    verb: str
    ok: bool
    result: Any = None
    error: Optional[str] = None


def _normalize_step(
    step: Any, index: int
) -> tuple[str, str, list[Any], dict[str, Any]]:
    if isinstance(step, dict):
        port = step.get("port")
        verb = step.get("verb")
        args = step.get("args") or []
        kwargs = step.get("kwargs") or {}
    elif isinstance(step, (list, tuple)):
        if len(step) < 2:
            raise ValueError(f"step {index}: need at least (port, verb)")
        port, verb = step[0], step[1]
        args = list(step[2]) if len(step) > 2 and step[2] is not None else []
        kwargs = dict(step[3]) if len(step) > 3 and step[3] is not None else {}
    else:
        raise ValueError(f"step {index}: must be a dict or (port, verb, ...) tuple")
    if not isinstance(port, str) or not isinstance(verb, str):
        raise ValueError(f"step {index}: port and verb must be strings")
    return port, verb, list(args), dict(kwargs)


def run_script(
    registry: PortRegistry,
    steps: list[Any],
    caller: Optional[str] = None,
    stop_on_error: bool = True,
) -> list[StepResult]:
    """Execute scripted port/verb commands sequentially, capturing results.

    Each step is ``{"port", "verb", "args", "kwargs"}`` or
    ``(port, verb, args, kwargs)``. With ``stop_on_error=True`` (default),
    the first failed step ends the run; otherwise every step runs and each
    result records its own ok/error.
    """
    results: list[StepResult] = []
    for index, raw in enumerate(steps):
        try:
            port, verb, args, kwargs = _normalize_step(raw, index)
        except ValueError as exc:
            results.append(StepResult(index, "", "", False, None, str(exc)))
            if stop_on_error:
                break
            continue
        try:
            outcome = registry.send_command(
                port, verb, args=args, kwargs=kwargs, caller=caller
            )
            results.append(StepResult(index, port, verb, True, outcome, None))
        except PortError as exc:
            results.append(
                StepResult(
                    index, port, verb, False, None, f"{type(exc).__name__}: {exc}"
                )
            )
            if stop_on_error:
                break
        except Exception as exc:  # verb implementation errors are captured, not hidden
            results.append(
                StepResult(
                    index, port, verb, False, None, f"{type(exc).__name__}: {exc}"
                )
            )
            if stop_on_error:
                break
    return results


# ---------------------------------------------------------------------------
# Optional socketpair-backed serving (lazy import: plan9 is a sibling module)
# ---------------------------------------------------------------------------


def _plan9():
    from . import plan9 as _p9

    return _p9


def serve_registry(
    registry: PortRegistry, channel: Any, request_types: Optional[set[str]] = None
) -> None:
    """Serve ``registry`` over a 9P-style channel (blocking).

    Accepted message type: ``"command"`` with payload
    ``{"port", "verb", "args", "kwargs", "caller"}``. Replies carry
    ``{"ok": True, "result": ...}`` or ``{"ok": False, "error": ...}`` with
    the refusal's error type preserved in the message.
    """
    allowed = {"command"} if request_types is None else request_types

    def handler(msg_type: str, payload: Any) -> Any:
        if not isinstance(payload, dict):
            raise PortError("command payload must be an object")
        try:
            result = registry.send_command(
                payload.get("port"),
                payload.get("verb"),
                args=payload.get("args") or [],
                kwargs=payload.get("kwargs") or {},
                caller=payload.get("caller"),
            )
        except PortError as exc:
            return {"ok": False, "error_type": type(exc).__name__, "error": str(exc)}
        except Exception as exc:
            return {"ok": False, "error_type": type(exc).__name__, "error": str(exc)}
        return {"ok": True, "error_type": None, "error": None, "result": result}

    _plan9().serve(channel, handler, request_types=allowed)


class RemoteRegistry:
    """Client-side view of a registry served over a 9P-style channel."""

    def __init__(self, channel: Any) -> None:
        self._channel = channel

    def send_command(
        self,
        port: str,
        verb: str,
        args: Optional[list[Any]] = None,
        kwargs: Optional[dict[str, Any]] = None,
        caller: Optional[str] = None,
        timeout: float = 5.0,
    ) -> Any:
        reply = self._channel.request(
            "command",
            {
                "port": port,
                "verb": verb,
                "args": args or [],
                "kwargs": kwargs or {},
                "caller": caller,
            },
            timeout=timeout,
        )
        if not isinstance(reply, dict):
            raise PortError(f"malformed reply: {reply!r}")
        if not reply.get("ok"):
            error_type = reply.get("error_type") or "PortError"
            error_cls = {
                "UnknownPort": UnknownPort,
                "UnknownVerb": UnknownVerb,
                "AccessDenied": AccessDenied,
            }.get(error_type, PortError)
            raise error_cls(str(reply.get("error")))
        return reply.get("result")

    def close(self) -> None:
        try:
            self._channel.close()
        except Exception:
            pass
