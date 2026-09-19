"""honest_subscriptions — stated prices, no roach motels, no forced migrations.

Studied from: giant-patterns-hunt-20260916-0016/report.md [S7].

Load-bearing idea: the price on the tin is the price you pay, locked at
signup (grandfathered against later price rises). Tier changes only happen
with explicit, recorded consent — there is no code path for a forced
migration. Cancellation is immediate with a receipt. A subscription always
knows both the currently advertised price and the price its holder actually
pays, and can show the difference.

LEVI's take: ``Billing`` defines ``Plan`` objects, sells ``Subscription``
objects with a locked price, requires an explicit ``consent=True`` keyword
for any tier change, and cancels in one call. ``MigrationRefused`` is raised
whenever consent is missing — the roach motel has no back door.

Honest limits: this is billing logic, not payment processing; no money moves
here. Price changes to the advertised card do not rewrite existing locks.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

ORIGIN = "levi-revival/honest-subscriptions"


class MigrationRefused(Exception):
    """Raised when a tier change is attempted without explicit consent."""


@dataclass
class Plan:
    """A subscription plan with a stated price. The stated price is the truth."""

    name: str
    price_cents: int
    billing: str = "monthly"
    blurb: str = ""

    def stated_price(self) -> Dict[str, object]:
        """The advertised terms, exactly as a customer would read them."""
        return {
            "plan": self.name,
            "price_cents": self.price_cents,
            "billing": self.billing,
            "blurb": self.blurb,
        }


@dataclass
class Subscription:
    """A subscription with its price locked at signup."""

    id: int
    holder: str
    plan_name: str
    locked_price_cents: int
    billing: str
    started: str
    active: bool = True
    consent_log: List[Dict[str, str]] = field(default_factory=list)


class Billing:
    """Subscriptions where the price is stated, locked, and never migrated by force."""

    def __init__(self) -> None:
        self._plans: Dict[str, Plan] = {}
        self._subs: Dict[int, Subscription] = {}
        self._next_id: int = 1

    def define_plan(self, plan: Plan) -> None:
        """Publish a plan. Republishing the same name updates the advertised
        price for NEW signups only — existing locks are untouched."""
        self._plans[plan.name] = plan

    def plans(self) -> List[Dict[str, object]]:
        """Every currently advertised plan, stated plainly."""
        return [p.stated_price() for p in self._plans.values()]

    def subscribe(self, plan_name: str, holder: str) -> Subscription:
        """Sign up. The advertised price becomes your locked price, forever."""
        plan = self._plans[plan_name]
        sub = Subscription(
            id=self._next_id,
            holder=holder,
            plan_name=plan_name,
            locked_price_cents=plan.price_cents,
            billing=plan.billing,
            started=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._next_id += 1
        self._subs[sub.id] = sub
        return sub

    def my_price(self, subscription_id: int) -> int:
        """The price this subscription actually pays — the locked price."""
        return self._subs[subscription_id].locked_price_cents

    def change_tier(
        self, subscription_id: int, new_plan: str, consent: bool = False
    ) -> Subscription:
        """Change tier. Requires explicit consent=True, which is logged.

        Without consent this raises MigrationRefused — there is deliberately
        no code path that migrates a subscriber silently.
        """
        if not consent:
            raise MigrationRefused(
                "tier change refused: explicit consent=True is required; "
                "forced migrations do not exist in this system"
            )
        sub = self._subs[subscription_id]
        plan = self._plans[new_plan]
        sub.plan_name = new_plan
        sub.locked_price_cents = plan.price_cents
        sub.billing = plan.billing
        sub.consent_log.append(
            {
                "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "action": f"tier change to {new_plan}",
                "consent": "explicit",
            }
        )
        return sub

    def cancel(self, subscription_id: int) -> Dict[str, object]:
        """Cancel immediately. Effective now, receipted, no retention maze."""
        sub = self._subs[subscription_id]
        sub.active = False
        return {
            "subscription_id": sub.id,
            "holder": sub.holder,
            "cancelled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "final_bill_cents": 0,
            "note": "no exit survey, no retention offers, no dark patterns",
        }

    def is_active(self, subscription_id: int) -> bool:
        """Whether the subscription is currently active."""
        return self._subs[subscription_id].active
