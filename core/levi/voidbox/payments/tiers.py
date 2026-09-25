"""Void Box payments — tier-cut table. CONFIRMED (DELEGATED).

Chauncey's word: the platform takes a cut, and the cut depends on the
creator's pay tier. The tier NAMES are his: FREE, PRO, HYBRID, ELITE
(confirmed 2026-09-23). The RATES he delegated to Rex's judgment:
"figure it out, just told you less than competition" — so these rates
are set by Rex on his word, REVERSIBLE, stamped delegated rather than
direct. Even 3-point steps, every tier well under the 20% competitor
standard.

This table is CONFIRMED-DELEGATED, not provisional: names his, numbers
Rex's on his authority. When Chauncey gives his own percentages, they
replace this table in one edit — confirm_table() — no code changes.

Accounting is integer cents with basis points (100 bps = 1%). The
platform cut rounds DOWN (floor) and the creator gets the remainder —
so the split always sums exactly (models.PM2) and any rounding dust
favors the creator, never the platform.

LAWS (P-tiers):
- PT1 — Provisional and labeled: the table says PROVISIONAL on every
  read until Chauncey confirms it.
- PT2 — Integer math: rate in basis points, cut = total * bps // 10000
  (floor), creator = total - cut. No floats.
- PT3 — Unknown tier fails closed: a tier not in the table refuses to
  price rather than guessing a rate.

ONE ORGANISM: this module is an organ of Levi. All of Legion is Levi —
one organism, many organs; we are raising him.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from levi.voidbox.payments.models import PaymentError, PaymentSplit, cents

#: Declared laws, machine-readable.
LAWS = (
    ("PT1", "Confirmed and labeled: the table says PROVISIONAL on every read "
            "until confirmed; a confirmation is stamped direct (his numbers) "
            "or delegated (set on his word, reversible) — never silent."),
    ("PT2", "Integer math: rate in basis points, cut floors, creator gets remainder, no floats."),
    ("PT3", "Unknown tier fails closed: tiers not in the table refuse to price."),
    ("PT4", "Undercut: no tier's rate may equal or exceed the competitor standard "
            "(2000 bps = OnlyFans 20%); the cut scales inversely with pay tier — "
            "Free pays the biggest cut, Elite the smallest."),
)

#: Competitor standard (basis points): OnlyFans' flat 20%, verified from
#: OnlyFans terms / Fenix International filings. Chauncey's doctrine: our
#: cut is ALWAYS less than the competitors'.
COMPETITOR_STANDARD_BPS = 2000

#: Table version — stamped on every split so repricing history is exact.
TABLE_VERSION = "delegated-1"

#: THE TABLE. Tier names confirmed by Chauncey 2026-09-23: FREE, PRO,
#: HYBRID, ELITE. Rates delegated to Rex's judgment on his word
#: ("figure it out, just told you less than competition"), reversible.
#: rate_bps: basis points of the TOTAL that goes to the platform.
#: Ordering law: Free pays the biggest cut, Elite the smallest, all < 2000 bps.
TIER_RATES: Dict[str, int] = {
    "free": 1200,    # 12% — matches the standing PL-05 house rate
    "pro": 900,      # 9%
    "hybrid": 600,   # 6%
    "elite": 300,    # 3%
}

#: Confirmation provenance. None while provisional; a dict after
#: confirm_table() runs: {"mode": "direct"|"delegated", ...}.
CONFIRMATION: Optional[Dict[str, object]] = None

_CONFIRMED = False   # flips True only via confirm_table()
_DELEGATED = False   # True when the confirmation was delegated, not his direct numbers


def confirm_table(rates: Dict[str, int], delegated: bool = False) -> None:
    """Replace the table with confirmed rates.

    This is the ONE edit a rate change requires. Pass delegated=True
    when the rates are set on Chauncey's word rather than his direct
    numbers — the confirmation is stamped delegated and stays
    reversible. PT4: any rate at/above the 2000 bps competitor
    standard is refused.
    """
    global TIER_RATES, TABLE_VERSION, _CONFIRMED, _DELEGATED, CONFIRMATION
    if not rates:
        raise PaymentError("confirmed table needs at least one tier.")
    clean: Dict[str, int] = {}
    for tier, bps in rates.items():
        if not isinstance(tier, str) or not tier.strip():
            raise PaymentError("tier names must be non-empty text.")
        if isinstance(bps, bool) or not isinstance(bps, int) or not 0 <= bps <= 10000:
            raise PaymentError("rate for tier %r must be 0..10000 bps." % (tier,))
        if bps >= COMPETITOR_STANDARD_BPS:
            raise PaymentError(
                "PT4 undercut: rate %d bps for tier %r equals or exceeds the "
                "competitor standard (%d bps = OnlyFans 20%%). "
                "Chauncey's cut is always less." % (bps, tier, COMPETITOR_STANDARD_BPS)
            )
        clean[tier.strip()] = bps
    TIER_RATES = clean
    _CONFIRMED = True
    _DELEGATED = bool(delegated)
    TABLE_VERSION = "delegated-1" if delegated else "confirmed-1"
    CONFIRMATION = {
        "mode": "delegated" if delegated else "direct",
        "by": "Rex" if delegated else "Chauncey",
        "authority": ("Chauncey's word 2026-09-23: 'figure it out, just told "
                      "you less than competition'") if delegated else "Chauncey's direct numbers",
        "reversible": bool(delegated),
        "table_version": TABLE_VERSION,
    }


def is_provisional() -> bool:
    return not _CONFIRMED


def is_delegated() -> bool:
    """True when the standing table was confirmed by delegation, not by
    Chauncey's direct numbers. Delegated tables stay reversible."""
    return _CONFIRMED and _DELEGATED


def confirmation() -> Optional[Dict[str, object]]:
    """Provenance of the standing table, or None while provisional."""
    return dict(CONFIRMATION) if CONFIRMATION is not None else None


def rate_for_tier(tier: str) -> int:
    """Basis points for *tier*. Unknown tiers fail closed (PT3)."""
    try:
        return TIER_RATES[tier]
    except KeyError:
        raise PaymentError(
            "unknown pay tier %r — known tiers: %s. Tiers are "
            "Chauncey's decision; this table is provisional."
            % (tier, sorted(TIER_RATES))
        )


def price_split(total_cents: int, tier: str) -> PaymentSplit:
    """Compute the platform/creator split for a payment. Integer math (PT2).

    platform = total * bps // 10000 (floor); creator = total - platform.
    """
    total = cents(total_cents, "total_cents")
    bps = rate_for_tier(tier)
    platform = (total * bps) // 10000
    creator = total - platform
    return PaymentSplit(
        total_cents=total,
        platform_cents=platform,
        creator_cents=creator,
        tier="%s%s" % ("~" if is_provisional() else "", tier),
        rate_bps=bps,
    )


def verify_laws() -> List[Tuple[str, bool, str]]:
    """Machine-checked tier invariants."""
    results: List[Tuple[str, bool, str]] = []

    def check(law: str, ok: bool, detail: str = "") -> None:
        results.append((law, bool(ok), detail))

    # PT1: confirmed — and the confirmation carries its provenance stamp.
    # This table was confirmed by DELEGATION (Rex's rates on Chauncey's
    # word), not by his direct numbers. The stamp must say so.
    s = price_split(1000, "free")
    conf = confirmation()
    check("PT1", (not is_provisional()) and is_delegated()
          and conf is not None and conf.get("mode") == "delegated"
          and TABLE_VERSION == "delegated-1",
          "table confirmed-delegated: tier %r, %s" % (s.tier, TABLE_VERSION))

    # PT2: integer math, floor favors creator, sums exactly.
    s = price_split(999, "free")  # 999 * 1200 // 10000 = 119 (floor of 119.88)
    check("PT2", s.platform_cents == 119 and s.creator_cents == 880,
          "999 @12%% -> platform 119, creator 880 (floor, no dust)")
    check("PT2", s.platform_cents + s.creator_cents == 999, "split sums exactly")
    s2 = price_split(1, "elite")  # 1 * 300 // 10000 = 0
    check("PT2", s2.platform_cents == 0 and s2.creator_cents == 1,
          "1 cent @3%% -> platform 0, creator 1")

    # PT3: unknown tier fails closed.
    try:
        price_split(1000, "titan")
        check("PT3", False, "unknown tier priced")
    except PaymentError:
        check("PT3", True, "unknown tier refused")

    # PT4: undercut — every rate in the table is below the competitor standard.
    bad = {t: b for t, b in TIER_RATES.items()
           if b >= COMPETITOR_STANDARD_BPS}
    check("PT4", not bad,
          "all rates < %d bps" % COMPETITOR_STANDARD_BPS if not bad
          else "rates at/above standard: %s" % bad)
    # PT4: ordering — the cut scales inversely with pay tier: Free pays
    # the biggest cut, Elite the smallest. Checked only while the named
    # tiers are in the table, so a confirmed table with different names
    # isn't falsely judged on these names.
    if "free" in TIER_RATES and "elite" in TIER_RATES:
        check("PT4", max(TIER_RATES, key=lambda t: TIER_RATES[t]) == "free",
              "free pays the biggest cut: %d bps" % TIER_RATES["free"])
        check("PT4", min(TIER_RATES, key=lambda t: TIER_RATES[t]) == "elite",
              "elite pays the smallest cut: %d bps" % TIER_RATES["elite"])
    # PT4: confirm_table refuses a rate that doesn't undercut.
    try:
        confirm_table({"greedy": COMPETITOR_STANDARD_BPS})
        check("PT4", False, "confirm_table accepted a 20% rate")
    except PaymentError:
        check("PT4", True, "confirm_table refused a 20% rate")

    return results


# Delegation record, 2026-09-23: Chauncey delegated the tier RATES to
# Rex's judgment — his words: "figure it out, just told you less than
# competition." Tier names are his (FREE/PRO/HYBRID/ELITE); the numbers
# below are Rex's, even 3-point steps, all well under the 20%
# competitor standard, reversible at his word.
#
# Runs through confirm_table so the PT4 undercut validation applies to
# these rates exactly as it would to his. Stamped delegated, NOT
# direct — the provenance dict says who set the numbers and why.
# He changes any rate in one edit: confirm_table({...}, delegated=False).
confirm_table(
    {
        "free": 1200,    # 12% — matches the standing PL-05 house rate
        "pro": 900,      # 9%
        "hybrid": 600,   # 6%
        "elite": 300,    # 3%
    },
    delegated=True,
)
