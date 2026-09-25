"""Operator config loader for NeighborOS (spec §3 law 9: config, not code).

``load_policies(store)`` seeds ``~/.levi/neighbor/policies.json`` from the
package default on first use and returns the operator's live config.
Edits there take effect immediately — no code fork needed.

The floor is the law: ``worker_keep_floor = 0.90``. Any config that
lowers it below 0.90 is rejected with ``FloorViolation`` — the operator
can raise generosity, never lower it.
"""

from __future__ import annotations

import json
from typing import Any

from .store import Store


class FloorViolation(ValueError):
    """Raised when a config change would undercut the 90% worker floor."""


def load_policies(store: Store) -> dict[str, Any]:
    path = store.ensure_policies()
    policies = json.loads(path.read_text(encoding="utf-8"))
    floor = float(policies.get("worker_keep_floor", 0.90))
    if floor < 0.90:
        raise FloorViolation(
            f"worker_keep_floor={floor} is below the un-lowered floor 0.90"
        )
    return policies


def worker_keep_floor(policies: dict[str, Any]) -> float:
    return float(policies.get("worker_keep_floor", 0.90))


def fee_rate_for(amount: float, policies: dict[str, Any]) -> float:
    """Corpus band rate by job size (§11): <100: 12%, <500: 10%, <2000: 8%, else 6%."""
    for band in policies.get("commission_bands", []):
        ceiling = band.get("max_amount")
        if ceiling is None or amount <= float(ceiling):
            return float(band["fee_rate"])
    return 0.06
