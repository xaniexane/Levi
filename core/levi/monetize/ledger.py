"""Shared income ledger for the 12 monetization projects.

Every earning action writes a receipt: one JSON object per line in
``~/.levi/monetize/income.jsonl`` (owner-only permissions, dir 0o700,
file 0o600). The ledger is append-only: corrections are new events
(``kind="adjustment"``), never rewrites.

Receipts are honest records of what Chauncey confirms — LEVI never
invents income. Event kinds:

  sale       one-off client payment received
  recurring  subscription/retainer billing event
  payout     platform payout (Etsy, KDP, YouTube, ad network...)
  expense    cost incurred (ad spend, platform fees, materials)
  refund     money returned to a client
  milestone  non-cash milestone (first order, 100th sale...) — amount 0
  adjustment correction to an earlier receipt — must reference it
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

KINDS = ("sale", "recurring", "payout", "expense", "refund", "milestone", "adjustment")

RISK_BANDS = ("low", "medium", "elevated")
"""low: paid-upfront client service; medium: recurring/operational exposure;
elevated: platform- or traffic-dependent income."""


def default_dir(home: Optional[Path] = None) -> Path:
    base = home if home is not None else Path.home()
    return base / ".levi" / "monetize"


def default_path(home: Optional[Path] = None) -> Path:
    return default_dir(home) / "income.jsonl"


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_event(
    project: str,
    kind: str,
    amount: float,
    currency: str = "USD",
    note: str = "",
    counterparty: str = "",
    risk_band: str = "low",
    home: Optional[Path] = None,
) -> Dict[str, Any]:
    """Append one income receipt to the ledger. Returns the receipt."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
    if risk_band not in RISK_BANDS:
        raise ValueError(f"risk_band must be one of {RISK_BANDS}, got {risk_band!r}")
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise ValueError(f"amount must be numeric, got {amount!r}") from None
    if not isinstance(project, str) or not project.strip():
        raise ValueError("project must be a non-empty slug")
    if amount < 0 and kind not in ("expense", "refund", "adjustment"):
        raise ValueError(
            "negative amounts are only valid for expense/refund/adjustment"
        )

    path = default_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    receipt = {
        "id": uuid.uuid4().hex[:12],
        "at": _utcnow(),
        "project": project.strip(),
        "kind": kind,
        "amount": round(amount, 2),
        "currency": currency,
        "counterparty": counterparty,
        "note": note,
        "risk_band": risk_band,
    }
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    os.chmod(path, 0o600)
    return receipt


def read_events(
    home: Optional[Path] = None,
    project: Optional[str] = None,
    kind: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Read receipts newest-first. Corrupt lines are skipped, not fatal."""
    path = default_path(home)
    events: List[Dict[str, Any]] = []
    if not path.exists():
        return events
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict):
            continue
        if project and rec.get("project") != project:
            continue
        if kind and rec.get("kind") != kind:
            continue
        events.append(rec)
    events.reverse()
    if limit is not None:
        events = events[:limit]
    return events


def summarize(
    home: Optional[Path] = None,
    project: Optional[str] = None,
) -> Dict[str, Any]:
    """Totals by project, by kind, and net. Expenses/refunds subtract."""
    events = read_events(home=home, project=project)
    inflow_kinds = ("sale", "recurring", "payout")
    outflow_kinds = ("expense", "refund")
    by_project: Dict[str, float] = {}
    by_kind: Dict[str, float] = {}
    net = 0.0
    for rec in events:
        amt = float(rec.get("amount", 0.0))
        kind = rec.get("kind", "")
        by_kind[kind] = round(by_kind.get(kind, 0.0) + amt, 2)
        if kind in inflow_kinds:
            net += amt
            by_project[rec["project"]] = round(
                by_project.get(rec["project"], 0.0) + amt, 2
            )
        elif kind in outflow_kinds:
            net -= amt
    return {
        "events": len(events),
        "gross_inflow": round(sum(by_kind.get(k, 0.0) for k in inflow_kinds), 2),
        "outflow": round(sum(by_kind.get(k, 0.0) for k in outflow_kinds), 2),
        "net": round(net, 2),
        "by_project": by_project,
        "by_kind": by_kind,
    }
