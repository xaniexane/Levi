"""Dual-key consent gates.

A consequential act may run only when TWO keys turn together:

* the *standing key* -- a durable policy setting (e.g. the keeper allowed
  cloud escalation in config), and
* the *request key* -- an explicit per-action permission granted for this
  one act (e.g. the user ticked "allow cloud" on this request).

One key alone never opens the gate. Every decision, allow or deny, returns
a receipt: who asked, which keys were present, when, and why. Receipts are
plain dicts so they can be logged, audited, or shown to the keeper without
any special tooling.

This is the standing "Permission" step of Plan->Preview->Permission->
Execute->Verify->Receipt, formalized as a reusable mechanism. It is the
original LEVI-native descendant of the double opt-in pattern in the
consolidated offline-first upload (cloud_allowed / sync_allowed), which
expressed the same idea for exactly two actions. The registry form below
covers any number of consequential actions with one code path.

stdlib-only.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class GateVerdict:
    """Outcome of one gate check."""

    allowed: bool
    gate: str
    standing: bool
    requested: bool
    reason: str
    at: float = field(default_factory=time.time)

    def receipt(self) -> Dict[str, Any]:
        """Plain-dict receipt for logs and audits."""
        return {
            "gate": self.gate,
            "allowed": self.allowed,
            "standing_key": self.standing,
            "request_key": self.requested,
            "reason": self.reason,
            "at": self.at,
        }


class DualKeyGate:
    """One named gate: standing policy key AND per-action request key."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description

    def check(self, standing: bool, requested: bool) -> GateVerdict:
        """Decide. Never raises; a missing key is a denied gate."""
        standing_key = bool(standing)
        request_key = bool(requested)
        if standing_key and request_key:
            reason = "both keys turned"
        elif not standing_key and not request_key:
            reason = "denied: standing policy forbids it and no permission was granted"
        elif not standing_key:
            reason = (
                "denied: standing policy forbids it (permission alone is not enough)"
            )
        else:
            reason = (
                "denied: no per-action permission granted (policy alone is not enough)"
            )
        return GateVerdict(
            allowed=standing_key and request_key,
            gate=self.name,
            standing=standing_key,
            requested=request_key,
            reason=reason,
        )


class GateRegistry:
    """Named gates with one check path and an audit trail."""

    def __init__(self) -> None:
        self._gates: Dict[str, DualKeyGate] = {}
        self._audit: list = []

    def register(self, gate: DualKeyGate) -> DualKeyGate:
        if gate.name in self._gates:
            raise ValueError(f"gate already registered: {gate.name}")
        self._gates[gate.name] = gate
        return gate

    def check(self, name: str, standing: bool, requested: bool) -> GateVerdict:
        gate = self._gates.get(name)
        if gate is None:
            raise KeyError(f"unknown gate: {name}")
        verdict = gate.check(standing, requested)
        self._audit.append(verdict.receipt())
        return verdict

    def gates(self) -> Dict[str, str]:
        return {name: g.description for name, g in self._gates.items()}

    def audit_trail(self) -> list:
        return list(self._audit)


# The classic pair from the upload, pre-registered for convenience.
DEFAULT_REGISTRY = GateRegistry()
DEFAULT_REGISTRY.register(
    DualKeyGate("cloud-escalation", "send a redacted request to a cloud provider")
)
DEFAULT_REGISTRY.register(
    DualKeyGate("sync-export", "copy local records anywhere off this machine")
)


def check(
    name: str, standing: Mapping[str, Any] | bool, requested: bool = False
) -> GateVerdict:
    """One-call form over the default registry.

    `standing` may be a bool, or a config mapping whose truthiness of
    the gate's standing key is used (falls back to a top-level
    "allowed" entry). Missing anything is a denial, never an error.
    """
    if isinstance(standing, Mapping):
        value = standing.get(name, standing.get("allowed", False))
    else:
        value = standing
    return DEFAULT_REGISTRY.check(name, bool(value), requested)
