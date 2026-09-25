"""Act four — the remodel (Extreme Makeover).

``run_remodel`` takes an owner-approved plan and, for each rescue item:

  before snapshot → rail plan → preview (before/after diff) → permission
  (under the owner's plan approval) → execute the transform → verify by
  re-running the item's audit check against the after-state → receipt.

Transforms are operator-supplied callables ``(item, page) -> new_page``;
the engine applies, verifies, and receipts them — it never invents
fixes. A transform that fails, or an after-state that still trips the
check, is receipted honestly as a miss: the stone records misses too.

Versioned changes: the episode dir is committed via the code-forge seam.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import ensure_home, episode_rail
from . import ledger as stone
from .audit import DEFAULT_CHECKS, Check
from .plan import RescueItem, RescuePlan, require_approved

try:
    from ..forge.rail import Rail
    from ..policy.gates import RiskLevel
except Exception:  # pragma: no cover
    Rail = None  # type: ignore
    RiskLevel = None  # type: ignore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _page_sha(page: Dict[str, Any]) -> str:
    """Content hash of the whole page record — title, text, links, forms."""
    canonical = json.dumps(page, sort_keys=True, ensure_ascii=False, default=str)
    return _sha(canonical)


@dataclass
class RemodelResult:
    item_id: str
    check_id: str
    url: str
    before_sha256: str = ""
    after_sha256: str = ""
    before_path: str = ""
    after_path: str = ""
    verified: bool = False
    note: str = ""
    change_summary: str = ""
    proposal_id: str = ""
    receipt: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RemodelResult":
        from dataclasses import fields as _fields

        known = {f.name for f in _fields(cls)}
        clean = {k: v for k, v in data.items() if k in known}
        clean.setdefault("receipt", {})
        return cls(**clean)


def _rail(home) -> "Rail":
    return episode_rail(home)


def _risk(name: str):
    return getattr(RiskLevel, name, name) if RiskLevel is not None else name


def run_remodel(
    home,
    plan_id: str,
    walk: Dict[str, Dict[str, Any]],
    transforms: Dict[str, Callable[[RescueItem, Dict[str, Any]], Dict[str, Any]]],
    checks: Optional[List[Check]] = None,
    rail: Optional["Rail"] = None,
    surfaces: Optional[Any] = None,
) -> List[RemodelResult]:
    """Remodel every item of an owner-approved plan. Returns per-item results.

    ``walk`` is the audit's WalkContext (url → page record);
    ``transforms`` maps item id → ``(item, page) -> new_page``.
    """
    plan = require_approved(home, plan_id)  # the gate: owner-approved or refused
    rail = rail or _rail(home)
    checks = checks if checks is not None else DEFAULT_CHECKS
    check_by_id = {c.id: c for c in checks}

    root = ensure_home(home)
    episode_dir = root / "episodes" / plan.invitation_id
    before_dir = episode_dir / "before"
    after_dir = episode_dir / "after"
    for d in (before_dir, after_dir):
        d.mkdir(parents=True, exist_ok=True)

    results: List[RemodelResult] = []
    for item in plan.items:
        result = _remodel_item(
            home=home,
            plan=plan,
            item=item,
            walk=walk,
            transform=transforms.get(item.id),
            check=check_by_id.get(item.check_id),
            rail=rail,
            episode_dir=episode_dir,
            before_dir=before_dir,
            after_dir=after_dir,
        )
        results.append(result)
        stone.record(
            home,
            "remodel.item_done" if result.verified else "remodel.item_failed",
            plan.invitation_id,
            {
                "plan_id": plan.id,
                "item_id": item.id,
                "verified": result.verified,
                "note": result.note,
            },
        )
    (episode_dir / "results.json").write_text(
        json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    # Versioned changes via the code-forge seam (honest if git is missing).
    from . import seams

    version = seams.version_episode(episode_dir, "rescue remodel: %s" % plan.id)
    stone.record(
        home,
        "remodel.completed",
        plan.invitation_id,
        {
            "plan_id": plan.id,
            "items": len(results),
            "verified": sum(1 for r in results if r.verified),
            "version": version,
        },
    )
    return results


def _remodel_item(
    home,
    plan: RescuePlan,
    item: RescueItem,
    walk: Dict[str, Dict[str, Any]],
    transform,
    check: Optional[Check],
    rail: "Rail",
    episode_dir: Path,
    before_dir: Path,
    after_dir: Path,
) -> RemodelResult:
    url = item.affected[0] if item.affected else next(iter(walk), "")
    page = dict(walk.get(url, {"url": url, "text": "", "status": 200}))
    result = RemodelResult(
        item_id=item.id, check_id=item.check_id, url=url, before_sha256=_page_sha(page)
    )
    (before_dir / ("%s.json" % item.id)).write_text(
        json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    result.before_path = str(before_dir / ("%s.json" % item.id))

    if transform is None:
        result.note = "no transform supplied for item — nothing changed"
        result.after_sha256 = result.before_sha256
        (after_dir / ("%s.json" % item.id)).write_text(
            json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        result.after_path = str(after_dir / ("%s.json" % item.id))
        result.receipt = {"status": "skipped", "note": result.note}
        return result

    # Plan the execution on the rail; preview carries the before-state so
    # the operator sees exactly what is about to change.
    proposal_id = rail.plan(
        tool="rescue-remodel",
        description="remodel %s: %s" % (item.id, item.action),
        risk=_risk(item.risk),
        reason="executing owner-approved rescue item %s of plan %s"
        % (item.id, plan.id),
        affected=[url],
        impact=item.preview,
        reversible=item.reversible,
        artifacts={"item": item.to_dict(), "before_sha256": result.before_sha256},
    )
    result.proposal_id = proposal_id
    rail.preview(proposal_id)
    # Permission rides on the owner's plan approval — recorded, not skipped.
    rail.approve(
        proposal_id, note="under owner plan approval %s by %s" % (plan.id, plan.owner)
    )

    def _fn():
        new_page = transform(item, dict(page))
        if not isinstance(new_page, dict):
            raise TypeError("transform must return a page dict")
        new_page.setdefault("url", url)
        return (
            "remodeled %s" % item.id,
            {
                "before_sha256": result.before_sha256,
                "after_sha256": _page_sha(new_page),
                "page": new_page,
            },
        )

    def _verify(details):
        if check is None:
            return (False, "no audit check named %r to verify against" % item.check_id)
        leftover = check.run({url: details["page"]})
        if leftover is None:
            return (True, "audit check %r now passes" % check.id)
        return (False, "still failing: %s" % leftover.get("title"))

    receipt = rail.execute(proposal_id, _fn, verify=_verify)
    from dataclasses import asdict as _asdict, is_dataclass as _isdc

    details = receipt.details if hasattr(receipt, "details") else {}
    result.receipt = _asdict(receipt) if _isdc(receipt) else dict(details)
    result.verified = bool(getattr(receipt, "verified", False))
    if result.verified and details:
        after_page = details.get("page", page)
        result.after_sha256 = details.get("after_sha256", _page_sha(after_page))
        (after_dir / ("%s.json" % item.id)).write_text(
            json.dumps(after_page, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        result.after_path = str(after_dir / ("%s.json" % item.id))
        result.change_summary = "%s → fixed (%s)" % (item.finding_title, item.action)
        result.note = "verified: %s" % _verify(details)[1]
    else:
        result.after_sha256 = result.before_sha256
        (after_dir / ("%s.json" % item.id)).write_text(
            json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        result.after_path = str(after_dir / ("%s.json" % item.id))
        result.note = "not verified: %s" % (
            getattr(receipt, "note", "") or "transform or verify failed"
        )
    return result


def get_results(home, episode_id: str) -> List[RemodelResult]:
    path = ensure_home(home) / "episodes" / episode_id / "results.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    return [RemodelResult.from_dict(r) for r in data]


__all__ = ["RemodelResult", "get_results", "run_remodel"]
