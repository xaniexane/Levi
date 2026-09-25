"""Rewards engine — extra usage, monthly tier reductions, badges.

Canon (Chauncey, 2026-09-18): rewards are exactly three things —
extra usage grants, tier pricing reductions for the month, and badges.
Every reward is ledgered (append-only, hash-chained) against a real
backing event — a confirmed income event or a real usage report. The
engine never invents value, and it moves no money: rewards are
ledgered benefits, paper until the rail is real.
"""

from levi.rewards.hooks import reward_for_income_event, reward_for_usage
from levi.rewards.ledger import append, earns_for, ledger_path, read, verify
from levi.rewards.redeem import (
    active_reductions,
    balances,
    list_badges,
    month_reduction,
    redeem_usage,
    sweep_expiry,
    usage_balance,
)
from levi.rewards.rules import REWARDS_CATALOG, REWARD_TYPES, get_rule, rules_for

__all__ = [
    "REWARDS_CATALOG",
    "REWARD_TYPES",
    "get_rule",
    "rules_for",
    "reward_for_income_event",
    "reward_for_usage",
    "append",
    "earns_for",
    "ledger_path",
    "read",
    "verify",
    "active_reductions",
    "balances",
    "list_badges",
    "month_reduction",
    "redeem_usage",
    "sweep_expiry",
    "usage_balance",
]
