"""Act one — intake, consent-first.

We only walk into sites we're invited into. An invitation names the
owner, the business, the site/app, and the scope bounds (URL prefixes
the walk may touch). A walk-in requires the owner's acceptance on the
record. ``require_consent()`` is the gate every later act calls first.
"""

from __future__ import annotations

import json
import urllib.parse
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import ensure_home, rescue_home
from . import ledger as stone


class ConsentRefusedError(RuntimeError):
    """Raised when a walk-in is attempted without the owner's consent."""


#: Cost categories for the owner's stated operating spend. Every figure
#: is labeled "owner-stated" — the owner's own declaration, never a
#: measurement we invented.
COST_CATEGORIES = ("hosting", "saas", "tooling", "fees", "other")


def validate_costs(costs) -> List[Dict[str, Any]]:
    """Normalize owner-stated monthly cost line items.

    Each item: {name, category, amount_usd_monthly, note=""}.
    Raises ValueError on anything malformed — cost figures are never
    silently invented or repaired.
    """
    if costs is None:
        return []
    if not isinstance(costs, (list, tuple)):
        raise ValueError("validate_costs: costs must be a list of line items")
    out = []
    for n, item in enumerate(costs, 1):
        if not isinstance(item, dict):
            raise ValueError("validate_costs: item %d is not a mapping" % n)
        name = str(item.get("name") or "").strip()
        category = str(item.get("category") or "").strip().lower()
        amount = item.get("amount_usd_monthly", item.get("amount", 0))
        if not name:
            raise ValueError("validate_costs: item %d has no name" % n)
        if category not in COST_CATEGORIES:
            raise ValueError(
                "validate_costs: item %r category %r not in %s"
                % (name, category, "/".join(COST_CATEGORIES))
            )
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            raise ValueError(
                "validate_costs: item %r amount %r is not a number"
                % (name, item.get("amount_usd_monthly"))
            ) from None
        if amount < 0:
            raise ValueError(
                "validate_costs: item %r amount may not be negative" % name
            )
        out.append(
            {
                "name": name,
                "category": category,
                "amount_usd_monthly": round(amount, 2),
                "note": str(item.get("note") or ""),
                "provenance": "owner-stated",
            }
        )
    return out


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _next_id(home) -> str:
    state_path = rescue_home(home) / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        state = {}
    n = int(state.get("invitation_counter", 0)) + 1
    state["invitation_counter"] = n
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return "inv-%04d" % n


def _normalize_scope(site_url: str, scope: Optional[List[str]]) -> List[str]:
    prefixes = [s.rstrip("/") + "/" for s in (scope or [site_url])]
    out = []
    for p in prefixes:
        parsed = urllib.parse.urlparse(p)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("scope prefix must be an http(s) URL: %r" % p)
        out.append(p)
    # The site itself is always in scope.
    site_prefix = site_url.rstrip("/") + "/"
    if site_prefix not in out:
        out.insert(0, site_prefix)
    return out


@dataclass
class Invitation:
    """The owner's invitation: the only lawful way in.

    ``costs`` is the owner's stated monthly operating spend
    (hosting, SaaS, tooling, fees) — the cost baseline for the
    cost-cutting pillar. Every figure stays labeled "owner-stated".
    """

    id: str
    owner: str
    business: str
    site_url: str
    scope: List[str] = field(default_factory=list)
    note: str = ""
    issued_at: str = ""
    accepted_at: str = ""
    owner_note: str = ""
    costs: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return bool(self.accepted_at)

    def allows(self, url: str) -> bool:
        """True if the URL falls inside the invited scope bounds."""
        bare = url.rstrip("/")
        return any(
            url.startswith(prefix) or bare == prefix.rstrip("/")
            for prefix in self.scope
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Invitation":
        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in data.items() if k in known}
        clean.setdefault("scope", [])
        return cls(**clean)


def _inv_path(home, invitation_id: str):
    return ensure_home(home) / "invitations" / ("%s.json" % invitation_id)


def issue_invitation(
    home,
    *,
    owner: str,
    business: str,
    site_url: str,
    scope: Optional[List[str]] = None,
    note: str = "",
    costs: Optional[List[Dict[str, Any]]] = None,
) -> Invitation:
    """Record the invitation. Nothing fetches yet — this is only the invite.

    ``costs`` is the owner's stated monthly operating spend; validated
    and labeled owner-stated, never invented.
    """
    owner = (owner or "").strip()
    business = (business or "").strip()
    site_url = (site_url or "").strip().rstrip("/")
    if not owner:
        raise ValueError("issue_invitation: owner is required")
    if not business:
        raise ValueError("issue_invitation: business is required")
    parsed = urllib.parse.urlparse(site_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("issue_invitation: site_url must be an http(s) URL")
    inv = Invitation(
        id=_next_id(home),
        owner=owner,
        business=business,
        site_url=site_url,
        scope=_normalize_scope(site_url, scope),
        note=note,
        issued_at=_now(),
        costs=validate_costs(costs),
    )
    _inv_path(home, inv.id).write_text(
        json.dumps(inv.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    stone.record(
        home,
        "intake.invited",
        inv.id,
        {
            "owner": owner,
            "business": business,
            "site_url": site_url,
            "scope": inv.scope,
            "cost_items": len(inv.costs),
            "stated_monthly_usd": round(
                sum(c["amount_usd_monthly"] for c in inv.costs), 2
            ),
        },
    )
    return inv


def get_invitation(home, invitation_id: str) -> Invitation:
    path = _inv_path(home, invitation_id)
    try:
        return Invitation.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        raise ConsentRefusedError("no such invitation: %r" % invitation_id) from None


def accept_invitation(home, invitation_id: str, owner_note: str = "") -> Invitation:
    """The owner accepts: consent is now on the record."""
    inv = get_invitation(home, invitation_id)
    if inv.accepted:
        return inv
    inv.accepted_at = _now()
    inv.owner_note = owner_note or ""
    _inv_path(home, inv.id).write_text(
        json.dumps(inv.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    stone.record(
        home,
        "intake.accepted",
        inv.id,
        {
            "owner": inv.owner,
            "owner_note": inv.owner_note,
        },
    )
    return inv


def require_consent(home, invitation_id: str) -> Invitation:
    """The consent gate. Raises ConsentRefusedError unless the owner accepted."""
    inv = get_invitation(home, invitation_id)
    if not inv.accepted:
        raise ConsentRefusedError(
            "walk-in refused: invitation %r was issued to %s but never accepted — "
            "we only walk into sites we're invited into" % (inv.id, inv.owner)
        )
    return inv


__all__ = [
    "COST_CATEGORIES",
    "ConsentRefusedError",
    "Invitation",
    "accept_invitation",
    "get_invitation",
    "issue_invitation",
    "require_consent",
    "validate_costs",
]
