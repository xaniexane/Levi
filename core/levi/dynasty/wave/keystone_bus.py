# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Keystone graft bus — contract, events, lifecycle.

Companion to :mod:`levi.dynasty.wave.keystone`'s :class:`GraftHost`.
Keystone owns the one-app shell, and these are its graft mechanics.

- :func:`validate_graft_manifest` is the third-party graft contract:
  it checks ``name``, semver ``version``, ``permissions`` against the
  known set, the ``entry_point``, and the required ``sandbox: true``.
  Every violation is collected and raised together as a typed
  :class:`ContractViolation` — it never fails fast on the first one.
- :class:`EventBus` is cross-graft automation: grafts subscribe to
  topics, publishes fan out to subscribers with per-subscriber
  delivery receipts, and every graft owns a drainable inbox.
  Publishing to a topic with no subscribers is a documented no-op
  returning empty receipts.
- Graft lifecycle rides a strict state machine:
  ``disabled -> enabled -> suspended -> enabled``. Only enabled grafts
  receive deliveries. Illegal transitions raise a typed
  :class:`LifecycleError`.
"""

from __future__ import annotations

import copy
import re
import threading
from typing import Any, Dict, FrozenSet, List, Sequence

from levi.dynasty.dna import AgentError

__all__ = [
    "ContractViolation",
    "LifecycleError",
    "KNOWN_PERMISSIONS",
    "validate_graft_manifest",
    "EventBus",
]


class ContractViolation(AgentError):
    """A graft manifest broke the third-party contract.

    Carries every violation at once in :attr:`violations`; the message
    joins them for humans.
    """

    def __init__(self, violations: Sequence[str]) -> None:
        self.violations: List[str] = list(violations)
        super().__init__("graft contract violations: " + "; ".join(self.violations))


class LifecycleError(AgentError):
    """An illegal graft lifecycle transition was attempted."""


# -- third-party graft contract ---------------------------------------

KNOWN_PERMISSIONS: FrozenSet[str] = frozenset(
    {"fs.read", "fs.write", "net", "clock", "shell.exec"}
)

_SEMVER_RE = re.compile(r"^\d+\.\d+(\.\d+)?$")


def validate_graft_manifest(manifest: Any) -> Dict[str, Any]:
    """Validate a third-party graft manifest against the contract.

    Required: ``name`` (non-empty string), ``version`` (semver
    ``x.y`` or ``x.y.z``), ``permissions`` (a subset of
    :data:`KNOWN_PERMISSIONS`), ``entry_point`` (non-empty string),
    and ``sandbox: true`` (third-party grafts run sandboxed, always).

    Returns the normalized manifest on success. Raises
    :class:`ContractViolation` carrying *all* violations at once —
    never just the first.
    """
    violations: List[str] = []
    if not isinstance(manifest, dict):
        raise ContractViolation(["manifest must be a dict"])

    name = manifest.get("name")
    if not isinstance(name, str) or not name.strip():
        violations.append("name: must be a non-empty string")
    else:
        name = name.strip()

    version = manifest.get("version")
    if not isinstance(version, str) or not _SEMVER_RE.match(version):
        violations.append(f"version: must be semver 'x.y' or 'x.y.z', got {version!r}")

    permissions = manifest.get("permissions")
    if not isinstance(permissions, (list, tuple, set, frozenset)) or any(
        not isinstance(p, str) for p in permissions
    ):
        violations.append("permissions: must be a list of strings")
        permissions = []
    unknown = sorted(p for p in permissions if p not in KNOWN_PERMISSIONS)
    for perm in unknown:
        violations.append(f"permissions: unknown permission {perm!r}")

    entry_point = manifest.get("entry_point")
    if not isinstance(entry_point, str) or not entry_point.strip():
        violations.append("entry_point: must be a non-empty string")

    if manifest.get("sandbox") is not True:
        violations.append("sandbox: must be true (third-party grafts run sandboxed)")

    if violations:
        raise ContractViolation(violations)
    return {
        "name": name,
        "version": version,
        "permissions": sorted(set(permissions)),
        "entry_point": entry_point.strip(),
        "sandbox": True,
    }


# -- cross-graft event bus ----------------------------------------------

_DISABLED = "disabled"
_ENABLED = "enabled"
_SUSPENDED = "suspended"

# Legal transitions: {from: {to, ...}}.
_TRANSITIONS = {
    _DISABLED: {_ENABLED},
    _ENABLED: {_SUSPENDED, _DISABLED},
    _SUSPENDED: {_ENABLED, _DISABLED},
}


def _check_ident(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentError(f"{what} must be a non-empty string")
    return value.strip()


class EventBus:
    """Cross-graft event bus with lifecycle-gated delivery.

    Grafts subscribe to topics; ``publish`` fans out to every
    subscriber and returns one delivery receipt per subscriber,
    in subscription order. Only *enabled* grafts receive deliveries —
    disabled or suspended grafts get a receipt with
    ``delivered: False`` and nothing lands in their inbox. Every graft
    owns an inbox drained with :meth:`drain`.

    Publishing to a topic with no subscribers is a no-op returning an
    empty receipt list. A graft's first subscription enables it; after
    that the lifecycle machine runs: disabled -> enabled ->
    suspended -> enabled. ``drain`` on an unknown graft returns ``[]``.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._topics: Dict[str, List[str]] = {}
        self._states: Dict[str, str] = {}
        self._inboxes: Dict[str, List[Dict[str, Any]]] = {}

    # -- subscription ---------------------------------------------------
    def subscribe(self, graft: str, topic: str) -> str:
        """Subscribe ``graft`` to ``topic``. Idempotent. A graft's
        first subscription enables it. Returns the graft's state."""
        graft = _check_ident(graft, "graft")
        topic = _check_ident(topic, "topic")
        with self._lock:
            subs = self._topics.setdefault(topic, [])
            if graft not in subs:
                subs.append(graft)
            if graft not in self._states:
                self._states[graft] = _ENABLED
            self._inboxes.setdefault(graft, [])
            return self._states[graft]

    def unsubscribe(self, graft: str, topic: str) -> None:
        """Drop a subscription. Silent no-op when there is nothing to
        drop; the graft's lifecycle state and inbox are untouched."""
        graft = _check_ident(graft, "graft")
        topic = _check_ident(topic, "topic")
        with self._lock:
            subs = self._topics.get(topic)
            if subs and graft in subs:
                subs.remove(graft)

    # -- publishing -----------------------------------------------------
    def publish(self, topic: str, payload: Any) -> List[Dict[str, Any]]:
        """Publish ``payload`` on ``topic``.

        Returns one receipt per subscriber — ``{"graft", "topic",
        "delivered"}`` — in subscription order. Topics with no
        subscribers are a no-op returning ``[]``. Payloads are
        deep-copied into inboxes so later mutation of the caller's
        object cannot rewrite delivered history.
        """
        topic = _check_ident(topic, "topic")
        with self._lock:
            subs = list(self._topics.get(topic, []))
            receipts: List[Dict[str, Any]] = []
            for graft in subs:
                enabled = self._states.get(graft, _DISABLED) == _ENABLED
                if enabled:
                    self._inboxes.setdefault(graft, []).append(
                        {"topic": topic, "payload": copy.deepcopy(payload)}
                    )
                receipts.append({"graft": graft, "topic": topic, "delivered": enabled})
            return receipts

    def drain(self, graft: str) -> List[Dict[str, Any]]:
        """Return and clear ``graft``'s inbox (oldest first).

        Unknown grafts return ``[]``.
        """
        graft = _check_ident(graft, "graft")
        with self._lock:
            inbox = self._inboxes.get(graft, [])
            self._inboxes[graft] = []
            return inbox

    # -- lifecycle ------------------------------------------------------
    def state(self, graft: str) -> str:
        """Current lifecycle state; unknown grafts read as disabled."""
        graft = _check_ident(graft, "graft")
        with self._lock:
            return self._states.get(graft, _DISABLED)

    def _transition(self, graft: str, to_state: str) -> str:
        graft = _check_ident(graft, "graft")
        with self._lock:
            current = self._states.get(graft, _DISABLED)
            if to_state not in _TRANSITIONS[current]:
                raise LifecycleError(
                    f"graft {graft!r}: illegal transition {current} -> {to_state}"
                )
            self._states[graft] = to_state
            self._inboxes.setdefault(graft, [])
            return to_state

    def enable(self, graft: str) -> str:
        """disabled -> enabled, or suspended -> enabled."""
        return self._transition(graft, _ENABLED)

    def suspend(self, graft: str) -> str:
        """enabled -> suspended."""
        return self._transition(graft, _SUSPENDED)

    def disable(self, graft: str) -> str:
        """enabled -> disabled, or suspended -> disabled."""
        return self._transition(graft, _DISABLED)

    # -- introspection ----------------------------------------------------
    def topics(self) -> List[str]:
        """Topics with at least one subscriber, sorted."""
        with self._lock:
            return sorted(t for t, subs in self._topics.items() if subs)

    def subscribers(self, topic: str) -> List[str]:
        """Subscriber grafts for ``topic``, in subscription order."""
        topic = _check_ident(topic, "topic")
        with self._lock:
            return list(self._topics.get(topic, []))
