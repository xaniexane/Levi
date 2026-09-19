"""Act five — the reveal (before/after receipt).

``build_reveal`` assembles the episode's receipt: per item the before and
after hashes, whether the fix verified, and a human change summary —
plus the audit score before and after (the after-state is re-audited
with the same checks and the same evidence law).

The completeness law is binding: every approved plan item must have a
result carrying BOTH hashes, or ``build_reveal`` raises
``IncompleteReceiptError`` — a reveal never ships half-built.
``approve_reveal`` is the owner's second gate; it closes the episode.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import ensure_home, rescue_home
from . import ledger as stone
from . import analytics
from .audit import DEFAULT_CHECKS, Check, get_audit, run_audit
from .intake import validate_costs
from .plan import require_approved
from .remodel import RemodelResult, get_results


class IncompleteReceiptError(RuntimeError):
    """A reveal was attempted without a complete before/after record."""


STATUS_OPEN = "open"
STATUS_ACCEPTED = "accepted"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class RevealItem:
    item_id: str
    check_id: str
    url: str
    before_sha256: str
    after_sha256: str
    verified: bool
    change_summary: str
    note: str = ""

    def changed(self) -> bool:
        return self.before_sha256 != self.after_sha256

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Reveal:
    id: str
    plan_id: str
    invitation_id: str
    business: str
    audit_id: str
    score_before: int
    score_after: int
    items: List[RevealItem] = field(default_factory=list)
    status: str = STATUS_OPEN
    owner: str = ""
    accepted_at: str = ""
    created_at: str = ""
    # Analytics: measured before/after per metric, with deltas.
    # Every metric ships — moved or not. When the audit predates
    # analytics there is no baseline; metrics_note says so honestly.
    metrics_before: Optional[Dict[str, float]] = None
    metrics_after: Optional[Dict[str, float]] = None
    metric_deltas: List[Dict[str, Any]] = field(default_factory=list)
    metrics_note: str = ""
    # Cost pillar: owner-stated before/after monthly spend and the
    # verified savings receipt. Verified = the math checks on figures
    # the owner put on the record, labeled owner-stated throughout.
    # Hosting is broken out as its own first-class line: hosting_savings
    # carries the hosting-only receipt ($/mo and $/yr) alongside the
    # total — the keeper's word is that even hosting cost rates get cut.
    cost_before: Optional[Dict[str, Any]] = None
    cost_after: Optional[Dict[str, Any]] = None
    savings: Dict[str, Any] = field(default_factory=dict)
    hosting_savings: Dict[str, Any] = field(default_factory=dict)
    cost_note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["items"] = [i.to_dict() for i in self.items]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reveal":
        from dataclasses import fields as _fields

        data = dict(data)
        data["items"] = [
            RevealItem(
                **{
                    k: v
                    for k, v in i.items()
                    if k in {f.name for f in _fields(RevealItem)}
                }
            )
            for i in data.get("items", [])
        ]
        known = {f.name for f in _fields(cls)}
        clean = {k: v for k, v in data.items() if k in known}
        clean.setdefault("items", [])
        return cls(**clean)


def _next_id(home) -> str:
    state_path = rescue_home(home) / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        state = {}
    n = int(state.get("reveal_counter", 0)) + 1
    state["reveal_counter"] = n
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return "reveal-%04d" % n


def build_reveal(
    home,
    plan_id: str,
    results: Optional[List[RemodelResult]] = None,
    after_walk: Optional[Dict[str, Dict[str, Any]]] = None,
    checks: Optional[List[Check]] = None,
    after_baseline: Optional[Dict[str, Any]] = None,
) -> Reveal:
    """Assemble the reveal receipt. Raises IncompleteReceiptError if half-built.

    ``after_baseline`` is an optional analytics baseline dict for the
    after-state; when ``after_walk`` is given without one, the
    after-state is measured with the same consent-gated measurement as
    the baseline. The reveal carries before/after numbers per metric —
    what moved and what didn't, honestly.
    """
    plan = require_approved(home, plan_id)
    results = results if results is not None else get_results(home, plan.invitation_id)
    by_item = {r.item_id: r for r in results}

    # Completeness law: every approved item needs a result with both hashes.
    missing = [i.id for i in plan.items if i.id not in by_item]
    if missing:
        raise IncompleteReceiptError(
            "reveal refused: no remodel result for approved item(s) %s"
            % ", ".join(missing)
        )
    hashless = [
        i.id
        for i in plan.items
        if not by_item[i.id].before_sha256 or not by_item[i.id].after_sha256
    ]
    if hashless:
        raise IncompleteReceiptError(
            "reveal refused: result(s) %s lack a before/after hash"
            % ", ".join(hashless)
        )

    audit = get_audit(home, plan.audit_id)
    score_before = audit.score
    # Re-audit the after-state with the same checks and the same evidence law.
    metrics_before: Optional[Dict[str, float]] = None
    metrics_after: Optional[Dict[str, float]] = None
    metric_deltas: List[Dict[str, Any]] = []
    metrics_note = ""
    if audit.baseline:
        metrics_before = dict((audit.baseline or {}).get("values", {}))
    if after_walk:
        reaudit = run_audit(
            home,
            plan.invitation_id,
            checks or DEFAULT_CHECKS,
            after_walk,
            receipts=[{"reveal": "re-audit of after-state"}],
        )
        score_after = reaudit.score
        # Measure the after-state with the same consent-gated measurement.
        # tag="after" so the before-baseline on disk is never overwritten.
        after = after_baseline
        if after is None:
            after = analytics.baseline_from_walk(
                home, plan.invitation_id, after_walk, tag="after"
            ).to_dict()
        elif hasattr(after, "to_dict"):
            after = after.to_dict()
        metrics_after = dict(after.get("values", {}))
    else:
        score_after = score_before

    if metrics_before is not None and metrics_after is not None:
        metric_deltas = analytics.metric_deltas(metrics_before, metrics_after)
        met = sum(1 for d in metric_deltas if d["target_met"])
        metrics_note = (
            "%d of %d metrics at healthy target; deltas measured "
            "from the site's own served content" % (met, len(metric_deltas))
        )
    elif metrics_before is None:
        metrics_note = (
            "no baseline on file — this audit predates analytics; "
            "metric deltas unavailable, score delta only"
        )

    # Cost pillar: baseline spend vs. owner-attested after spend.
    cost_before: Optional[Dict[str, Any]] = None
    cost_after: Optional[Dict[str, Any]] = None
    savings: Dict[str, Any] = {}
    hosting: Dict[str, Any] = {}
    cost_note = ""
    if audit.baseline and (audit.baseline or {}).get("cost"):
        cost_before = dict(audit.baseline["cost"])
    after_costs = _read_attested_costs(home, plan.invitation_id)
    if after_costs is not None:
        cost_after = after_costs
    if cost_before is not None and cost_after is not None:
        savings = analytics.cost_savings(cost_before, cost_after)
        cost_note = (
            "baseline vs. attested monthly spend, both owner-stated; "
            "savings $%.2f/mo ($%.2f/yr)"
            % (savings["savings_monthly_usd"], savings["savings_annual_usd"])
        )
        # Hosting broken out: the keeper's word is that even hosting
        # cost rates get cut, so the receipt shows hosting separately.
        hosting = analytics.hosting_savings(cost_before, cost_after)
        if hosting:
            cost_note += "; hosting $%.2f/mo → $%.2f/mo, saving $%.2f/mo ($%.2f/yr)" % (
                hosting["before_monthly_usd"],
                hosting["after_monthly_usd"],
                hosting["savings_monthly_usd"],
                hosting["savings_annual_usd"],
            )
        else:
            cost_note += "; no hosting spend on the record — hosting savings n/a"
    elif cost_before is None:
        cost_note = (
            "no cost baseline on file — the invitation carried no "
            "stated spend; savings unavailable"
        )
    else:
        cost_note = (
            "after-spend not yet attested — the owner states the "
            "post-remodel monthly spend via attest_costs()"
        )

    items = [
        RevealItem(
            item_id=i.id,
            check_id=i.check_id,
            url=by_item[i.id].url,
            before_sha256=by_item[i.id].before_sha256,
            after_sha256=by_item[i.id].after_sha256,
            verified=by_item[i.id].verified,
            change_summary=by_item[i.id].change_summary or i.action,
            note=by_item[i.id].note,
        )
        for i in plan.items
    ]
    reveal = Reveal(
        id=_next_id(home),
        plan_id=plan.id,
        invitation_id=plan.invitation_id,
        business=plan.business,
        audit_id=plan.audit_id,
        score_before=score_before,
        score_after=score_after,
        items=items,
        created_at=_now(),
        metrics_before=metrics_before,
        metrics_after=metrics_after,
        metric_deltas=metric_deltas,
        metrics_note=metrics_note,
        cost_before=cost_before,
        cost_after=cost_after,
        savings=savings,
        hosting_savings=hosting,
        cost_note=cost_note,
    )
    path = ensure_home(home) / "reveals" / ("%s.json" % reveal.id)
    path.write_text(
        json.dumps(reveal.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    stone.record(
        home,
        "reveal.built",
        plan.invitation_id,
        {
            "reveal_id": reveal.id,
            "plan_id": plan.id,
            "score_before": score_before,
            "score_after": score_after,
            "items": len(items),
            "verified": sum(1 for it in items if it.verified),
            "metrics": len(metric_deltas),
            "metrics_met": sum(1 for d in metric_deltas if d["target_met"]),
            "savings_monthly_usd": savings.get("savings_monthly_usd"),
            "hosting_savings_monthly_usd": hosting.get("savings_monthly_usd"),
        },
    )
    return reveal


def get_reveal(home, reveal_id: str) -> Reveal:
    path = ensure_home(home) / "reveals" / ("%s.json" % reveal_id)
    return Reveal.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _attested_costs_path(home, invitation_id: str):
    return ensure_home(home) / "episodes" / invitation_id / "costs_after.json"


def _read_attested_costs(home, invitation_id: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(
            _attested_costs_path(home, invitation_id).read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ValueError, OSError):
        return None


def attest_costs(
    home, plan_id: str, owner: str, costs: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """The owner states the post-remodel monthly spend.

    Only the owner who approved the plan may attest, and only on an
    approved plan. Figures are validated + labeled owner-stated —
    attested means the owner put them on the record, not that we
    metered the spend.
    """
    plan = require_approved(home, plan_id)
    if owner != plan.owner:
        raise ValueError(
            "attest_costs: only the approving owner (%r) may attest costs" % plan.owner
        )
    items = validate_costs(costs)
    record = analytics.cost_baseline(items)
    record["attested_by"] = owner
    record["attested_at"] = _now()
    record["plan_id"] = plan.id
    path = _attested_costs_path(home, plan.invitation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    stone.record(
        home,
        "costs.attested",
        plan.invitation_id,
        {
            "plan_id": plan.id,
            "owner": owner,
            "attested_monthly_usd": record["total_monthly_usd"],
            "items": record["item_count"],
        },
    )
    return record


def approve_reveal(home, reveal_id: str, owner: str, note: str = "") -> Reveal:
    """The owner's second gate: accept the reveal, close the episode."""
    reveal = get_reveal(home, reveal_id)
    if reveal.status != STATUS_OPEN:
        raise ValueError("approve_reveal: reveal %r is %s" % (reveal.id, reveal.status))
    reveal.status = STATUS_ACCEPTED
    reveal.owner = owner
    reveal.accepted_at = _now()
    path = ensure_home(home) / "reveals" / ("%s.json" % reveal.id)
    path.write_text(
        json.dumps(reveal.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    stone.record(
        home,
        "reveal.accepted",
        reveal.invitation_id,
        {
            "reveal_id": reveal.id,
            "owner": owner,
            "note": note,
            "score_before": reveal.score_before,
            "score_after": reveal.score_after,
        },
    )
    return reveal


__all__ = [
    "IncompleteReceiptError",
    "Reveal",
    "RevealItem",
    "STATUS_ACCEPTED",
    "STATUS_OPEN",
    "approve_reveal",
    "attest_costs",
    "build_reveal",
    "get_reveal",
]
