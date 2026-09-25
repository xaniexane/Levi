"""Dual-gate consent policy for cloud escalation.

The studied MVP gated cloud calls on two switches: a global server flag
and a per-request opt-in. LEVI's recreation names them honestly:

- ``keeper_allows_cloud`` — the keeper's standing policy (Chauncey).
  Flips only on his word; defaults to False.
- ``call_allows_cloud`` — consent for THIS call. Never inherited,
  never cached, never assumed from a previous yes.

The gate opens only when both are true. One gate alone never opens
the wire — that is the whole doctrine.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GatePolicy:
    """Standing offline-first policy. Immutable; the keeper replaces it."""

    keeper_allows_cloud: bool = False
    confidence_threshold: float = 0.72
    log_retention_days: int = 30

    def escalation_permitted(self, call_allows_cloud: bool) -> tuple[bool, str]:
        """Return (permitted, reason). The reason is always named."""
        if not self.keeper_allows_cloud:
            return False, "keeper policy forbids cloud (keeper_allows_cloud=False)"
        if not call_allows_cloud:
            return False, "no per-call consent (call_allows_cloud=False)"
        return True, "dual gate passed"


def default_policy() -> GatePolicy:
    """The standing policy: local only, confidence threshold 0.72."""
    return GatePolicy()


@dataclass
class MutablePolicy:
    """A policy the keeper can flip at runtime. Replaces, never mutates."""

    _policy: GatePolicy = field(default_factory=default_policy)

    def set(self, policy: GatePolicy) -> None:
        self._policy = policy

    def get(self) -> GatePolicy:
        return self._policy
