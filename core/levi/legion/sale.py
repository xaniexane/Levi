"""Legion money seam — paper only.

Flow: price-advisor quote -> Cybrus checkout record (PLAN + PREVIEW
only) -> lifetime one-copy license record (unpaid). The 70/30 split is
computed as a paper ledger line.

Hard rules, enforced here:
  * NEVER invent a payment rail. The checkout record names rail
    "paper" — a label, not a rail. Cybrus money.execute() would refuse
    it; we never call execute anyway.
  * NEVER invent income. split_paper() computes the 70/30 split on a
    quoted amount as a ledger line labeled PAPER — not a recorded event.
  * NEVER mark anything paid. Licenses are issued "paper-unpaid" and
    only ever become paid through a real Chauncey-authorized Cybrus
    settlement, which does not exist yet.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .packs import get_pack
from .product import LegionError

# Lifetime pricing: the advisor speaks monthly (doctrine), so a
# lifetime one-copy buy is stated as recommended-monthly x N months.
# N is plain in the quote rationale — no hidden math.
LIFETIME_MONTHS = 24
PACK_ADDON_FRACTION = 0.25  # each add-on pack: 25% of the base, stated plainly


class SaleError(ValueError):
    """Raised when a sale step violates the paper-money rules."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _home() -> Path:
    base = os.environ.get("LEVI_HOME") or str(Path.home() / ".levi")
    return Path(base).expanduser()


def _licenses_path(home: Optional[Path] = None) -> Path:
    d = (home or _home()) / "legion"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    p = d / "licenses.jsonl"
    if not p.exists():
        fd = os.open(str(p), os.O_WRONLY | os.O_CREAT, 0o600)
        os.close(fd)
    else:
        os.chmod(p, 0o600)
    return p


# ---------------------------------------------------------------------------
# Quote — through the founder price advisor
# ---------------------------------------------------------------------------


@dataclass
class LegionQuote:
    """A paper quote for one Legion install + optional add-on packs."""

    quote_id: str
    business_type: str
    packs: List[str]
    base_monthly: float
    base_lifetime: float
    pack_addons: Dict[str, float]
    total_usd: float
    seat_cap: int
    rationale: List[str]
    tier: str = "standard"  # standard | nephilim — paper tier line item
    created_at: str = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if self.total_usd <= 0:
            raise SaleError(
                "no free core: a Legion quote must be a positive price"
            )
        if self.tier not in ("standard", "nephilim"):
            raise SaleError(
                f"unknown tier {self.tier!r} — choose standard|nephilim"
            )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "LegionQuote":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in known})


def quote_legion(
    *,
    business_type: str = "generic",
    packs: Optional[List[str]] = None,
    giant_price: Optional[float] = None,
    strategy: str = "volume",
    tier: str = "standard",
) -> LegionQuote:
    """Quote a Legion install via the founder price advisor.

    Tier "flagship": the Legion install is the full legion-crew product
    (roster law: legion seats). A quote, never a charge — the advisor
    moves nothing. giant_price, when known, anchors ~30-60% below the
    giant; never invented here.

    tier: "standard" (base price) or "nephilim" (Nephilim grade —
    premium, base x 3.0, stated plainly as a PAPER line item).
    """
    from levi.advisor.pricing import PricePlan, advise_price
    from .tiers import get_tier

    pack_list = [p.lower() for p in (packs or [])]
    for p in pack_list:
        get_pack(p)  # deny-open on pack names
    spec = get_tier(tier)  # deny-open on tier names
    advice = advise_price(
        PricePlan(tier="flagship", giant_price=giant_price, strategy=strategy)
    )
    base_monthly = round(advice.recommended, 2)
    base_lifetime = round(
        base_monthly * LIFETIME_MONTHS * spec.price_multiplier, 2
    )
    addons = {
        p: round(base_lifetime * PACK_ADDON_FRACTION, 2) for p in pack_list
    }
    total = round(base_lifetime + sum(addons.values()), 2)
    rationale = list(advice.rationale)
    rationale.append(
        "legion product: flagship tier (the full crew is the product), "
        f"lifetime one-copy = recommended monthly x {LIFETIME_MONTHS} months, "
        "stated plainly — not a subscription"
    )
    rationale.append(
        f"PAPER tier line item: {spec.name} (grade: {spec.key}) — "
        f"price multiplier x{spec.price_multiplier}, stated plainly; "
        "the tier changes the operator seat, not the subscription math"
    )
    if addons:
        rationale.append(
            f"add-on packs ({', '.join(pack_list)}): "
            f"{int(PACK_ADDON_FRACTION * 100)}% of base each, labeled"
        )
    rationale.append("this is a QUOTE, not a charge — no money moves on a quote")
    return LegionQuote(
        quote_id="lgq_" + uuid.uuid4().hex[:10],
        business_type=business_type,
        packs=pack_list,
        base_monthly=base_monthly,
        base_lifetime=base_lifetime,
        pack_addons=addons,
        total_usd=total,
        seat_cap=advice.seat_cap,
        rationale=rationale,
        tier=spec.key,
    )


# ---------------------------------------------------------------------------
# Checkout record — Cybrus PLAN + PREVIEW only
# ---------------------------------------------------------------------------


@dataclass
class CheckoutRecord:
    """The paper checkout: a Cybrus money PLAN and its PREVIEW.

    No authorization is requested here, no rail exists, and execute()
    is never called — the gateway is fail-closed and stays that way.
    """

    record_id: str
    quote_id: str
    plan_id: str
    preview: str
    amount_minor: int
    currency: str
    buyer: str  # blank until a real buyer exists
    status: str = "paper-quote"
    created_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def plan_checkout(quote: LegionQuote, *, buyer: str = "") -> CheckoutRecord:
    """Record a paper checkout for a quote.

    Creates the Cybrus MoneyPlan (audit-trail only) and its human-
    readable preview. Stops there: PLAN -> PREVIEW, never PERMISSION,
    never EXECUTE. The rail is labeled "paper" — a label, not a rail.
    """
    from levi.cybrus.money import MoneyGateway, MoneyOperation

    if not isinstance(quote, LegionQuote):
        raise SaleError("plan_checkout needs a LegionQuote")
    gw = MoneyGateway()
    amount_minor = int(round(quote.total_usd * 100))
    plan = gw.plan(
        MoneyOperation.CHARGE,
        amount_minor,
        "USD",
        rail="paper",  # label, not a rail — execute() would refuse, and is never called
        purpose=f"Legion bot lifetime one-copy license ({quote.quote_id})",
        identity=buyer or "pending-buyer",
    )
    return CheckoutRecord(
        record_id="lgc_" + uuid.uuid4().hex[:10],
        quote_id=quote.quote_id,
        plan_id=plan.plan_id,
        preview=gw.preview(plan),
        amount_minor=amount_minor,
        currency="USD",
        buyer=buyer,
    )


# ---------------------------------------------------------------------------
# 70/30 split — paper ledger line, never recorded income
# ---------------------------------------------------------------------------


def split_paper(amount_usd: float) -> Dict[str, Any]:
    """Compute the 70/30 split on a quoted amount as a PAPER ledger line.

    Uses income.engine.split_income (the canonical split) but labels
    the result honestly: a quote split is not an income event and is
    never recorded as one. Money law holds: nothing moves until
    Chauncey registers a rail.
    """
    from levi.income.engine import split_income

    if amount_usd <= 0:
        raise SaleError("split needs a positive quoted amount")
    split = split_income(round(amount_usd, 2))
    return {
        "kind": "paper-split",
        "quoted_usd": round(amount_usd, 2),
        "keeper_usd": round(split["keeper"], 2),
        "pool_usd": round(split["pool"], 2),
        "law": "70/30: 70% keeper, 30% reinvest pool — "
               "paper only, never recorded income, moves nothing",
    }


# ---------------------------------------------------------------------------
# Lifetime one-copy license — always unpaid on paper
# ---------------------------------------------------------------------------


@dataclass
class LicenseRecord:
    """One lifetime one-copy Legion license.

    Buyer stays blank until a real sale. Status is ALWAYS
    "paper-unpaid" through this seam — nothing here can mark a license
    paid; only a real Chauncey-authorized Cybrus settlement can, and no
    rail exists for that.
    """

    license_id: str
    product: str
    business_name: str
    buyer: str  # blank until a real sale
    price_usd: float
    packs: List[str]
    terms: Dict[str, Any]
    quote_id: str
    checkout_record_id: str
    status: str = "paper-unpaid"
    issued_at: str = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if self.status != "paper-unpaid":
            raise SaleError(
                "license status is paper-unpaid, always — this seam "
                "cannot mark a license paid"
            )
        if not self.business_name or not self.business_name.strip():
            raise SaleError("license needs a business name")
        if self.price_usd <= 0:
            raise SaleError("no free core: license price must be positive")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "LicenseRecord":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in known})


def issue_license(
    quote: LegionQuote,
    checkout: CheckoutRecord,
    *,
    business_name: str,
    buyer: str = "",
    home: Optional[Path] = None,
) -> LicenseRecord:
    """Issue a paper-unpaid lifetime one-copy license and persist it.

    Refuses to mismatch quote and checkout. Persisted to the owner-only
    legion licenses ledger — a record of the paper offer, not a sale.
    """
    if checkout.quote_id != quote.quote_id:
        raise SaleError("checkout does not belong to this quote")
    lic = LicenseRecord(
        license_id="lgl_" + uuid.uuid4().hex[:10],
        product="Legion bot",
        business_name=business_name,
        buyer=buyer,
        price_usd=quote.total_usd,
        packs=list(quote.packs),
        terms={"lifetime": True, "copies": 1, "transferable": False},
        quote_id=quote.quote_id,
        checkout_record_id=checkout.record_id,
    )
    p = _licenses_path(home)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(lic.to_dict()) + "\n")
    os.chmod(p, 0o600)
    return lic


def list_licenses(home: Optional[Path] = None) -> List[LicenseRecord]:
    """List paper license records (owner-only ledger)."""
    p = _licenses_path(home)
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(LicenseRecord.from_dict(json.loads(line)))
        except Exception:
            continue
    return out
