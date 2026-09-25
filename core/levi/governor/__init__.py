"""LEVI usage governor: metering, spike detection, cool-downs, budgets.

Every provider/model call can be wrapped so its token usage is metered with
cause attribution, spikes are detected against rolling baselines, breaches
trigger automatic cool-downs (circuit breaker), and per-session/per-day
budgets are enforced deny-closed.

The honest priority lane (priority.py): burst passes that reserve the
single half-open probe slot during genuine contention — transparently
labeled, never manufactured. Passes cannot create contention.

Entry points:
  python -m levi.governor status|top|cooldowns|budgets|why|passes|pass-issue
  from levi.governor import GovernedProvider, governed_call
"""

from levi.governor.budgets import BudgetEnforcer, DEFAULT_BUDGETS
from levi.governor.cooldown import CooldownManager, CircuitState
from levi.governor.diagnose import summarize, top_contributors
from levi.governor.governed import GovernedProvider, governed_call
from levi.governor.meter import Meter, UsageRecord, fingerprint_messages, governor_home
from levi.governor.priority import BurstPass, PassWallet
from levi.governor.spikes import SpikeAlert, SpikeDetector

__all__ = [
    "BudgetEnforcer",
    "BurstPass",
    "CircuitState",
    "CooldownManager",
    "DEFAULT_BUDGETS",
    "GovernedProvider",
    "Meter",
    "PassWallet",
    "SpikeAlert",
    "SpikeDetector",
    "UsageRecord",
    "fingerprint_messages",
    "governed_call",
    "governor_home",
    "summarize",
    "top_contributors",
]
