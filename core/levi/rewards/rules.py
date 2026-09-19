"""Rewards engine — earn rules as data.

Canon (Chauncey, 2026-09-18): rewards are exactly three things —
  (a) extra usage grants (units of product usage),
  (b) tier pricing reductions for the month (month-scoped),
  (c) badges (named achievements with criteria).

Rules are DATA, not code. Each rule names a trigger (a confirmed income
event, or an attention/use report), honest earn criteria, and exactly one
reward. The hooks in :mod:`levi.rewards.hooks` evaluate these rules; this
module only declares them.

Honest rule: a rule can only fire on a real backing event. The catalog
never invents value — criteria are thresholds over observed events.
"""

from __future__ import annotations

from typing import Any, Dict, List

# Reward types, per canon. Nothing else may appear in a rule's grant.
REWARD_TYPES = ("usage_grant", "tier_reduction", "badge")

# Triggers a rule can listen to.
TRIGGERS = ("income", "usage")

# Income kinds a rule may match (subset of levi.income.engine.INCOME_KINDS).
INCOME_KINDS = ("sale", "recurring", "payout")


def _rule(
    rule_id: str,
    name: str,
    trigger: str,
    reward_type: str,
    criteria: Dict[str, Any],
    grant: Dict[str, Any],
    *,
    per: str = "every",
    description: str = "",
) -> Dict[str, Any]:
    """Build one catalog rule (validated)."""
    if trigger not in TRIGGERS:
        raise ValueError(f"trigger must be one of {TRIGGERS}, got {trigger!r}")
    if reward_type not in REWARD_TYPES:
        raise ValueError(
            f"reward_type must be one of {REWARD_TYPES}, got {reward_type!r}"
        )
    if per not in ("once", "every"):
        raise ValueError(f"per must be 'once' or 'every', got {per!r}")
    return {
        "id": rule_id,
        "name": name,
        "trigger": trigger,
        "reward_type": reward_type,
        "criteria": criteria,
        "grant": grant,
        "per": per,  # "once": at most one earn per account; "every": each qualifying event
        "description": description,
    }


REWARDS_CATALOG: List[Dict[str, Any]] = [
    # ---- income-triggered -------------------------------------------------
    _rule(
        "first-dollar",
        "First confirmed dollar",
        trigger="income",
        reward_type="badge",
        criteria={"kinds": ["sale"], "min_amount_usd": 0.01},
        grant={"badge": "first-dollar", "title": "First Dollar",
               "citation": "first confirmed sale on record"},
        per="once",
        description="The account's first confirmed sale mints the First Dollar badge.",
    ),
    _rule(
        "recurring-loyalty",
        "Recurring loyalty reduction",
        trigger="income",
        reward_type="tier_reduction",
        criteria={"kinds": ["recurring"], "min_amount_usd": 0.01},
        grant={"percent_off": 10, "scope": "month",
               "citation": "recurring income keeps the lights on — the month gets cheaper"},
        per="every",
        description="Every confirmed recurring billing event earns 10% off the account's "
                    "tier pricing for that calendar month.",
    ),
    _rule(
        "payout-celebration",
        "Big payout usage grant",
        trigger="income",
        reward_type="usage_grant",
        criteria={"kinds": ["payout"], "min_amount_usd": 500.0},
        grant={"units": 200, "unit": "usage-credit",
               "citation": "a $500+ payout funds 200 extra units of product usage"},
        per="every",
        description="Each confirmed payout of $500+ grants 200 extra usage credits.",
    ),
    _rule(
        "rainmaker",
        "Rainmaker",
        trigger="income",
        reward_type="badge",
        criteria={"kinds": ["payout"], "min_amount_usd": 500.0},
        grant={"badge": "rainmaker", "title": "Rainmaker",
               "citation": "single confirmed payout of $500+"},
        per="once",
        description="A single confirmed payout of $500+ mints the Rainmaker badge, once.",
    ),
    _rule(
        "sale-milestone-grant",
        "Strong sale usage grant",
        trigger="income",
        reward_type="usage_grant",
        criteria={"kinds": ["sale"], "min_amount_usd": 100.0},
        grant={"units": 25, "unit": "usage-credit",
               "citation": "a $100+ sale funds 25 extra units of product usage"},
        per="every",
        description="Each confirmed sale of $100+ grants 25 extra usage credits.",
    ),
    # ---- usage/attention-triggered ----------------------------------------
    _rule(
        "week-of-attention",
        "Week of attention",
        trigger="usage",
        reward_type="usage_grant",
        criteria={"min_actions": 100, "window_days": 7},
        grant={"units": 50, "unit": "usage-credit",
               "citation": "100+ recorded actions inside a 7-day window"},
        per="every",
        description="100+ real usage actions inside any 7-day window grants 50 extra usage credits.",
    ),
    _rule(
        "month-of-momentum",
        "Month of momentum",
        trigger="usage",
        reward_type="tier_reduction",
        criteria={"min_actions": 500, "window_days": 30},
        grant={"percent_off": 15, "scope": "month",
               "citation": "500+ recorded actions inside a 30-day window"},
        per="every",
        description="500+ real usage actions inside any 30-day window earns 15% off the "
                    "account's tier pricing for that calendar month.",
    ),
    _rule(
        "deep-focus",
        "Deep Focus",
        trigger="usage",
        reward_type="badge",
        criteria={"min_actions": 1000, "window_days": 30},
        grant={"badge": "deep-focus", "title": "Deep Focus",
               "citation": "1000+ recorded actions inside a 30-day window"},
        per="once",
        description="1000+ real usage actions inside any 30-day window mints the Deep Focus badge, once.",
    ),
]


def get_rule(rule_id: str) -> Dict[str, Any]:
    """Fetch one catalog rule by id (KeyError if unknown)."""
    for rule in REWARDS_CATALOG:
        if rule["id"] == rule_id:
            return rule
    raise KeyError(f"no reward rule {rule_id!r}")


def rules_for(trigger: str) -> List[Dict[str, Any]]:
    """All catalog rules listening to one trigger."""
    if trigger not in TRIGGERS:
        raise ValueError(f"trigger must be one of {TRIGGERS}, got {trigger!r}")
    return [r for r in REWARDS_CATALOG if r["trigger"] == trigger]
