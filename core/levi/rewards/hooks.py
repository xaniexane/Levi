"""Wiring seam — hooks that turn real events into rewards.

Two entry points, both living on the rewards side so the money layer is
never touched:

  reward_for_income_event(event, account=...)  — consumes a confirmed
      income event dict exactly as levi.income.engine.record_income()
      returns it (id, at, generator_id, kind, amount, ...).
  reward_for_usage(report)                     — consumes a usage report
      dict {"report_id", "account", "actions", "window_days", "at"}.

Both validate their input and REFUSE to invent: a malformed or empty
backing event raises ValueError (income) or earns nothing (a zero-action
usage report is a real report that simply qualifies for nothing).

See WIRING_NOTES.md for the one-line patch that calls
reward_for_income_event() from inside record_income().
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.rewards import ledger
from levi.rewards.rules import INCOME_KINDS, rules_for

_INCOME_REQUIRED = ("id", "at", "generator_id", "kind", "amount")
_USAGE_REQUIRED = ("report_id", "account", "actions", "window_days", "at")


def _month_of(at: str) -> str:
    """Calendar month "YYYY-MM" of an ISO timestamp."""
    try:
        # Handles "2026-09-18T10:00:00Z" and offset forms.
        stamp = at.replace("Z", "+00:00")
        return datetime.fromisoformat(stamp).strftime("%Y-%m")
    except (ValueError, AttributeError):
        raise ValueError(f"cannot derive month from timestamp {at!r}") from None


def _validate_income_event(event: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(event, dict):
        raise ValueError("income event must be a dict, as returned by record_income()")
    missing = [k for k in _INCOME_REQUIRED if k not in event]
    if missing:
        raise ValueError(f"income event missing fields {missing} — refusing to invent a basis")
    if event["kind"] not in INCOME_KINDS:
        raise ValueError(f"income event kind must be one of {INCOME_KINDS}, got {event['kind']!r}")
    try:
        amount = float(event["amount"])
    except (TypeError, ValueError):
        raise ValueError(f"income event amount must be numeric, got {event['amount']!r}") from None
    if amount <= 0:
        raise ValueError("income event amount must be positive — refusing to reward a non-event")
    return event


def _validate_usage_report(report: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(report, dict):
        raise ValueError("usage report must be a dict")
    missing = [k for k in _USAGE_REQUIRED if k not in report]
    if missing:
        raise ValueError(f"usage report missing fields {missing} — refusing to invent a basis")
    if not report["account"] or not isinstance(report["account"], str):
        raise ValueError("usage report account must be a non-empty string")
    try:
        actions = int(report["actions"])
    except (TypeError, ValueError):
        raise ValueError(f"usage report actions must be an integer, got {report['actions']!r}") from None
    if actions < 0:
        raise ValueError("usage report actions cannot be negative")
    try:
        window = int(report["window_days"])
    except (TypeError, ValueError):
        raise ValueError(
            f"usage report window_days must be an integer, got {report['window_days']!r}"
        ) from None
    if window <= 0:
        raise ValueError("usage report window_days must be positive")
    return report


def _income_rule_matches(rule: Dict[str, Any], event: Dict[str, Any]) -> bool:
    crit = rule["criteria"]
    if event["kind"] not in crit.get("kinds", ()):
        return False
    return float(event["amount"]) >= float(crit.get("min_amount_usd", 0.0))


def _usage_rule_matches(rule: Dict[str, Any], report: Dict[str, Any]) -> bool:
    crit = rule["criteria"]
    return (
        int(report["actions"]) >= int(crit.get("min_actions", 0))
        and int(report["window_days"]) >= int(crit.get("window_days", 0))
    )


def _already_earned(account: str, rule: Dict[str, Any], basis_id: str, home) -> bool:
    if ledger.has_earn_for_basis(account, rule["id"], basis_id, home):
        return True  # same backing event never pays twice
    if rule["per"] == "once" and ledger.earns_for(account, rule["id"], home):
        return True  # "once" rules fire a single time per account
    return False


def reward_for_income_event(
    event: Dict[str, Any],
    *,
    account: str,
    home: Optional[Path] = None,
    at: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Evaluate income-triggered rules against one CONFIRMED income event.

    Returns the earn entries created (possibly empty). Raises ValueError
    on a malformed event rather than inventing rewards.
    """
    event = _validate_income_event(event)
    if not account or not isinstance(account, str):
        raise ValueError("account must be a non-empty string")

    earned: List[Dict[str, Any]] = []
    for rule in rules_for("income"):
        if not _income_rule_matches(rule, event):
            continue
        if _already_earned(account, rule, str(event["id"]), home):
            continue
        detail = dict(rule["grant"])
        if rule["reward_type"] == "tier_reduction":
            detail["month"] = _month_of(str(event["at"]))
        entry = ledger.append(
            "earn",
            account,
            rule["reward_type"],
            reward_id=rule["id"],
            detail=detail,
            basis_ref={"kind": "income_event", "id": str(event["id"])},
            rule_id=rule["id"],
            at=at,
            home=home,
        )
        earned.append(entry)
    return earned


def reward_for_usage(
    report: Dict[str, Any],
    *,
    home: Optional[Path] = None,
    at: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Evaluate usage-triggered rules against one attention/use report.

    A report with zero actions is valid but earns nothing. Returns the
    earn entries created (possibly empty).
    """
    report = _validate_usage_report(report)
    account = str(report["account"])

    earned: List[Dict[str, Any]] = []
    for rule in rules_for("usage"):
        if not _usage_rule_matches(rule, report):
            continue
        if _already_earned(account, rule, str(report["report_id"]), home):
            continue
        detail = dict(rule["grant"])
        if rule["reward_type"] == "tier_reduction":
            detail["month"] = _month_of(str(report["at"]))
        entry = ledger.append(
            "earn",
            account,
            rule["reward_type"],
            reward_id=rule["id"],
            detail=detail,
            basis_ref={"kind": "usage_report", "id": str(report["report_id"])},
            rule_id=rule["id"],
            at=at,
            home=home,
        )
        earned.append(entry)
    return earned
