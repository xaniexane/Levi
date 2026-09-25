"""Plan 9 interface discipline — one verb set, per-task namespaces.

WORKING TITLE only — naming is Chauncey's, never canon.

B10: five verbs (read/write/list/run/watch) over per-task namespaces.
Every operation resolves through the namespace via longest-prefix
mount matching; faults are receipted; every operation renders one
uniform audit entry: ``{namespace, verb, target, args}``.

Stdlib-only. Zero network. No sentience or subjective-experience
claims: a namespace is a fence, not a mind.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

VERBS: Tuple[str, ...] = ("read", "write", "list", "run", "watch")


class Plan9Fault(Exception):
    """A receipted namespace fault.  The receipt is on ``.receipt``."""

    def __init__(self, receipt: Dict[str, Any]):
        self.receipt = receipt
        super().__init__(str(receipt.get("reason", "plan9 fault")))


def _now() -> str:
    # Timestamps live ONLY inside receipts; logic never reads them.
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Audit log (uniform by construction)
# ---------------------------------------------------------------------------

_AUDIT: List[Dict[str, Any]] = []


def audit_log() -> List[Dict[str, Any]]:
    """Deep copy of the uniform audit log."""
    return copy.deepcopy(_AUDIT)


def clear_audit_log() -> None:
    _AUDIT.clear()


def _audit(entry: Dict[str, Any]) -> None:
    _AUDIT.append(entry)


# ---------------------------------------------------------------------------
# Capabilities, mounts, namespaces
# ---------------------------------------------------------------------------


@dataclass
class Capability:
    """What a mount grants: a target prefix, allowed verbs, op budget."""

    target_prefix: str
    verbs: Tuple[str, ...]
    budget: Optional[int] = None  # None = unlimited


@dataclass
class Mount:
    path: str
    capability: Capability
    used: int = 0
    revoked: bool = False


def _norm_path(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/") or "/"


class Namespace:
    """A task's private view: ``{task_id, mounts}``."""

    def __init__(self, task_id: str, mounts: Dict[str, Mount]):
        self.task_id = task_id
        self._mounts: Dict[str, Mount] = {_norm_path(p): m for p, m in mounts.items()}
        for p, m in self._mounts.items():
            m.path = p
        self.destroyed = False
        self._seq = 0

    def _receipt(self, op: str, **kw: Any) -> Dict[str, Any]:
        self._seq += 1
        receipt: Dict[str, Any] = {
            "seq": self._seq,
            "op": op,
            "namespace": self.task_id,
            "ts": _now(),
        }
        receipt.update(kw)
        return receipt

    def mount_points(self) -> List[str]:
        return sorted(self._mounts)

    def revoke(self, path: str) -> Dict[str, Any]:
        """Rung-0 semantics: shrink the namespace mid-task, immediately."""
        path = _norm_path(path)
        mount = self._mounts.get(path)
        if mount is None:
            raise Plan9Fault(
                self._receipt("revoke", reason="no such mount", path=path, ok=False)
            )
        mount.revoked = True
        return self._receipt("revoke", path=path, ok=True)

    def close(self) -> Dict[str, Any]:
        """Destroy the namespace at task end; mounts revoked."""
        self.destroyed = True
        self._mounts.clear()
        return self._receipt("close", ok=True)


def compose_namespace(
    task_id: str, grants: List[Dict[str, Any]]
) -> Tuple[Namespace, Dict[str, Any]]:
    """Build a namespace from declared grants.  The composition itself is
    a receipted, reviewable artifact."""
    mounts: Dict[str, Mount] = {}
    for grant in grants:
        path = _norm_path(grant["mount"])
        verbs = tuple(grant.get("verbs", ()))
        unknown = [v for v in verbs if v not in VERBS]
        if unknown:
            raise Plan9Fault(
                {
                    "op": "compose",
                    "namespace": task_id,
                    "reason": "unknown verbs in grant",
                    "verbs": unknown,
                    "ts": _now(),
                }
            )
        mounts[path] = Mount(
            path=path,
            capability=Capability(
                target_prefix=_norm_path(grant.get("prefix", path)),
                verbs=verbs,
                budget=grant.get("budget"),
            ),
        )
    ns = Namespace(task_id, mounts)
    receipt = ns._receipt(  # noqa: SLF001 - composition receipt is namespace-scoped
        "compose",
        grants=[
            {
                "mount": p,
                "prefix": m.capability.target_prefix,
                "verbs": list(m.capability.verbs),
                "budget": m.capability.budget,
            }
            for p, m in sorted(ns._mounts.items())
        ],
        ok=True,
    )
    return ns, receipt


# ---------------------------------------------------------------------------
# DirectDispatch — verb -> plain python callable (tests / thin adapter)
# ---------------------------------------------------------------------------


class DispatchError(Exception):
    pass


class DirectDispatch:
    """Maps each verb to a plain callable ``fn(real_target, args)``.

    Until the middle team pins its tool-execution protocol, this is the
    adapter between ``operate()`` and current tool functions.
    """

    def __init__(self):
        self._handlers: Dict[str, Callable[[str, Any], Any]] = {}

    def register(self, verb: str, fn: Callable[[str, Any], Any]) -> None:
        if verb not in VERBS:
            raise ValueError("DirectDispatch: unknown verb %r" % verb)
        self._handlers[verb] = fn

    @property
    def verbs(self) -> Tuple[str, ...]:
        return tuple(self._handlers)

    def __call__(self, verb: str, real_target: str, args: Any) -> Any:
        try:
            handler = self._handlers[verb]
        except KeyError:
            raise DispatchError("no handler for verb %r" % verb) from None
        return handler(real_target, args)


_DEFAULT_DISPATCH = DirectDispatch()


@dataclass
class OpResult:
    value: Any
    receipt: Dict[str, Any]


def _longest_prefix_match(mounts: Dict[str, Mount], target: str) -> Optional[Mount]:
    best: Optional[Mount] = None
    for path, mount in mounts.items():
        if mount.revoked:
            continue
        if target == path or target.startswith(path + "/"):
            if best is None or len(path) > len(best.path):
                best = mount
    return best


def operate(
    namespace: Namespace,
    verb: str,
    target: str,
    args: Any,
    dispatch: Optional[Callable[[str, str, Any], Any]] = None,
) -> OpResult:
    """Resolve ``(namespace, verb, target, args)`` through the namespace.

    Returns :class:`OpResult`; every fault raises a receipted
    :class:`Plan9Fault` and is audited.
    """
    dispatch = dispatch or _DEFAULT_DISPATCH
    target = _norm_path(target)

    def fault(reason: str, **kw: Any) -> Plan9Fault:
        receipt = namespace._receipt(  # noqa: SLF001 - operate is namespace-scoped
            "fault", verb=verb, target=target, reason=reason, ok=False, **kw
        )
        _audit(
            {
                "namespace": namespace.task_id,
                "verb": verb,
                "target": target,
                "args": copy.deepcopy(args),
                "receipt_id": receipt["seq"],
                "ok": False,
                "reason": reason,
                "ts": receipt["ts"],
            }
        )
        return Plan9Fault(receipt)

    if namespace.destroyed:
        raise fault("namespace destroyed")
    if verb not in VERBS:
        raise fault("unknown verb")

    mount = _longest_prefix_match(namespace._mounts, target)
    if mount is None:
        raise fault("unnamed target")
    if verb not in mount.capability.verbs:
        raise fault("denied verb", mount=mount.path)

    real_target = mount.capability.target_prefix + target[len(mount.path) :]
    real_target = _norm_path(real_target)
    if not (
        real_target == mount.capability.target_prefix
        or real_target.startswith(mount.capability.target_prefix + "/")
    ):
        raise fault("target escapes capability prefix", mount=mount.path)

    budget = mount.capability.budget
    if budget is not None and mount.used >= budget:
        raise fault("budget exhausted", mount=mount.path, budget=budget)

    try:
        value = dispatch(verb, real_target, args)
    except DispatchError as exc:
        raise fault("dispatch failed: %s" % exc) from None
    except Exception as exc:  # tool errors are receipted, never silent
        raise fault("tool error: %s" % exc) from None

    mount.used += 1
    receipt = namespace._receipt(  # noqa: SLF001 - operate is namespace-scoped
        "op", verb=verb, target=target, real_target=real_target, ok=True
    )
    _audit(
        {
            "namespace": namespace.task_id,
            "verb": verb,
            "target": target,
            "args": copy.deepcopy(args),
            "receipt_id": receipt["seq"],
            "ok": True,
            "ts": receipt["ts"],
        }
    )
    return OpResult(value=value, receipt=receipt)
