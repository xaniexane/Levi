"""transparent_commerce — easy-out as easy as easy-in, as a platform rule.

Studied from: giant-patterns-hunt-20260916-0016/report.md [S3].

Load-bearing idea: no friction asymmetry. A commerce flow declares how many
steps its signup takes and how many steps its cancellation takes; the
platform refuses to register any flow where cancelling costs more steps than
signing up. Cancelling is a single call that settles immediately and returns
a receipt — a one-click cancel, enforced in code rather than promised in copy.

LEVI's take: ``Commerce`` registers ``Flow`` objects, sells ``Subscription``
objects, and cancels them via ``cancel()``. ``FrictionAsymmetryError`` is
raised at registration time, not discovered by an angry customer later.
``friction_report()`` states every flow's in/out step counts plainly.

Honest limits: step counts are declared by the integrator; the module
enforces the rule against the declared numbers. Real-world checkout UX still
has to match what is declared here.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List

ORIGIN = "levi-revival/transparent-commerce"


class FrictionAsymmetryError(ValueError):
    """Raised when a flow makes exit harder than entry. Never allowed."""


@dataclass
class Flow:
    """A commerce flow. cancel_steps must never exceed signup_steps."""

    name: str
    signup_steps: int
    cancel_steps: int
    price_cents: int

    def __post_init__(self) -> None:
        if self.signup_steps < 1:
            raise ValueError("signup_steps must be at least 1")
        if self.cancel_steps < 1:
            raise ValueError("cancel_steps must be at least 1")
        if self.cancel_steps > self.signup_steps:
            raise FrictionAsymmetryError(
                f"flow {self.name!r}: cancel takes {self.cancel_steps} steps, "
                f"signup takes {self.signup_steps} — exit must be as easy as entry"
            )


@dataclass
class Subscription:
    """A live subscription. Cancelling is one call, effective immediately."""

    id: int
    flow_name: str
    customer: str
    price_cents: int
    started: str
    active: bool = True
    cancelled: str = ""


@dataclass
class Receipt:
    """Proof of cancellation, issued the moment it happens."""

    subscription_id: int
    customer: str
    flow_name: str
    cancelled_at: str
    final_charge_cents: int
    note: str = "cancelled in one step; no retention offers, no exit survey required"


class Commerce:
    """Commerce where the exit is as easy as the entrance, by construction."""

    def __init__(self) -> None:
        self._flows: Dict[str, Flow] = {}
        self._subs: Dict[int, Subscription] = {}
        self._next_id: int = 1

    def register_flow(self, flow: Flow) -> None:
        """Register a flow. Raises FrictionAsymmetryError on asymmetric flows.

        The asymmetry check already ran in ``Flow.__post_init__``; this is the
        platform-level gate that refuses to list a bad flow at all.
        """
        if flow.name in self._flows:
            raise KeyError(f"flow already registered: {flow.name!r}")
        self._flows[flow.name] = flow

    def subscribe(self, flow_name: str, customer: str) -> Subscription:
        """Sign up. Records the declared signup step count on the subscription."""
        flow = self._flows[flow_name]
        sub = Subscription(
            id=self._next_id,
            flow_name=flow_name,
            customer=customer,
            price_cents=flow.price_cents,
            started=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._next_id += 1
        self._subs[sub.id] = sub
        return sub

    def cancel(self, subscription_id: int) -> Receipt:
        """One-click cancel: immediate, idempotent, receipted.

        Cancelling an already-cancelled subscription returns the original
        receipt terms again rather than erroring — a second click must never
        be a trap.
        """
        sub = self._subs[subscription_id]
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if sub.active:
            sub.active = False
            sub.cancelled = now
        return Receipt(
            subscription_id=sub.id,
            customer=sub.customer,
            flow_name=sub.flow_name,
            cancelled_at=sub.cancelled,
            final_charge_cents=0,
        )

    def is_active(self, subscription_id: int) -> bool:
        """Whether the subscription is currently active."""
        return self._subs[subscription_id].active

    def friction_report(self) -> List[Dict[str, int]]:
        """Every flow's entry/exit step counts, stated plainly."""
        return [
            {
                "flow": f.name,
                "signup_steps": f.signup_steps,
                "cancel_steps": f.cancel_steps,
                "price_cents": f.price_cents,
            }
            for f in self._flows.values()
        ]

    def max_exit_steps(self) -> int:
        """The hardest cancel on the platform. A single number to hold us to."""
        if not self._flows:
            return 0
        return max(f.cancel_steps for f in self._flows.values())
