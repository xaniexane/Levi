"""LEVI Fair Trade — honest generosity, audited.

The giants taught us the sly-generosity trade: a gift that looks generous
but is cunning — free internet that's actually a walled garden, a privacy
rule that binds everyone except the rule-maker, a subscription you can
enter in one click and leave in sixteen thousand steps, a friendship
score that manufactures daily obligation.

Fair Trade does not rebuild any of that. It inverts it:

- ``trades.py``  — a clean-room catalog of the patterns, what they refuse,
  and the honest rule that replaces them.
- ``audit.py``   — score an offer: how honest is the trade, really?
- ``ledger.py``  — LEVI's own honest-trade declarations. Every LEVI
  generosity lands here with its true cost written down.
- ``counterplay.py`` — the exploitation layer: aware of their trades,
  LEVI ships the opposite as strategy. Each inversion names its profit
  engine and its popularity engine, with proof LEVI already lives it.

stdlib-only, local-first, no network, no telemetry.
"""

from .trades import PATTERNS, get_pattern, pattern_ids
from .audit import audit_offer
from .ledger import declare_trade, read_ledger
from .counterplay import all_counterplays, brief, counterplay, playbook

__all__ = [
    "PATTERNS",
    "get_pattern",
    "pattern_ids",
    "audit_offer",
    "declare_trade",
    "read_ledger",
    "all_counterplays",
    "brief",
    "counterplay",
    "playbook",
]
