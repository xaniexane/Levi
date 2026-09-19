"""NFT economics: the lifetime one-copy buy as a token.

One token, one pack. The token's metadata certifies the pack's exact bytes
through the hash-chained manifest (``pack_id`` + ``final_hash``) that the
genesis assemblers already bank — counterfeits cannot exist because there
is exactly one token per pack hash per series.

PAPER ONLY. No chain, no testnet, no funds. Money here is integer cents;
every split is exact — no dust is ever lost to rounding.

Securities-safe framing is a design constraint, not a footnote: these are
sold as scarce lifetime licenses. The company promises no profit and no
rising value. Any appreciation is pure market scarcity. A lawyer clears the
first real mint before it happens — see ``NFT_LICENSE_TERMS`` and
``DESIGN.md``.

Keeper's decisions (2026-09-18, recorded): annual mint cap = 1,000 copies
per year MINIMUM; chain = Base; rates confirmed at 50/30/20 primary and
7.5% royalties. Each year's N is banked in writing in the series ledger
(``ledger.py``) before mint; money stays paper until he orders the rail.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

FORM_NAME = "genesis.nft.economics"

# ---------------------------------------------------------------------------
# Rates — CONFIRMED by the keeper 2026-09-18. These are no longer
# recommendations; they are the law until he changes them in writing.
# ---------------------------------------------------------------------------

#: EIP-2981-style royalty on every secondary sale, in basis points.
#: 7.5%: inside the 5-10% market norm — heavy enough to feed the treasury
#: meaningfully, light enough not to chill the secondary market.
ROYALTY_BPS = 750

#: Fixed cut of gross PRIMARY revenue routed to the buyback treasury.
#: Enforced in code the way the 70/30 split is enforced in
#: ``levi.income.engine``. The cut comes from the keeper's share — the
#: keeper funds the exit door himself, which is what makes buyers trust it.
#:
#: Why 20%: a primary cut can never lift backing above mint price on its
#: own (each token adds only cut x mint to the treasury while adding one
#: to supply), so the cut's job is to make the mint-price floor *credible*
#: from primary revenue alone in year one, before secondary volume exists.
#: The RISE comes from royalty compounding against a capped, shrinking
#: supply — the simulator proves the crossing.
TREASURY_CUT = 0.20
KEEPER_SHARE = 0.50
POOL_SHARE = 0.30

#: The keeper's floor on every annual mint: 1,000 copies per year MINIMUM
#: (decided 2026-09-18). His reasoning, in his words: billions of people
#: worldwide, so a thousand copies stay scarce enough to be valuable and
#: still sell enough to be very profitable.
#:
#: The keeper may set a HIGHER N for any year, in writing, before mint
#: (banked in ``ledger.SeriesLedger``). N below this floor is refused
#: unless his explicit override is flagged on the ledger record itself —
#: a sub-floor year is never silent.
ANNUAL_SERIES_CAP_MIN = 1000

#: Per-epoch buyback liquidity bound: at most this share of a series'
#: treasury may leave through buybacks in one settlement epoch — with a
#: minimum of one floor bid, so the exit door always opens even on a thin
#: treasury. The floor is a standing bid with bounded liquidity, never a
#: redemption guarantee.
EPOCH_BUDGET_SHARE = 0.05

BPS_DENOMINATOR = 10_000


# ---------------------------------------------------------------------------
# Money helpers — integer cents, exact.
# ---------------------------------------------------------------------------

def usd(cents: int) -> str:
    """Render integer cents as a dollar string."""
    sign = "-" if cents < 0 else ""
    c = abs(int(cents))
    return "%s$%d.%02d" % (sign, c // 100, c % 100)


def round_half_up_cents(numerator: int, denominator: int) -> int:
    """Round a positive rational to whole cents, half up."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    if numerator < 0:
        raise ValueError("numerator must be non-negative")
    return (2 * numerator + denominator) // (2 * denominator)


def split_primary_revenue(price_cents: int, count: int = 1) -> Dict[str, int]:
    """Split gross primary revenue 50/30/20 (keeper/pool/treasury), exact.

    Integer tenths throughout — no float dust. Largest-remainder: every
    cent of the gross lands somewhere; the split never invents or destroys
    money.
    """
    gross = int(price_cents) * int(count)
    if gross <= 0:
        raise ValueError("gross must be positive")
    shares = (("keeper", 5), ("pool", 3), ("treasury", 2))  # tenths
    floored = {name: (gross * n) // 10 for name, n in shares}
    remainder = gross - sum(floored.values())
    order = sorted(
        range(len(shares)),
        key=lambda i: ((gross * shares[i][1]) % 10, -i),
        reverse=True,
    )
    out = dict(floored)
    for i in order[:remainder]:
        out[shares[i][0]] += 1
    assert sum(out.values()) == gross
    return out


def reference_royalty(sale_price_cents: int) -> int:
    """Royalty owed to the treasury on a secondary sale, in cents.

    ROYALTY_BPS of the sale price, rounded half up. 100% of the royalty
    flows to the buyback treasury of the token's series.
    """
    if sale_price_cents < 0:
        raise ValueError("sale price cannot be negative")
    return (sale_price_cents * ROYALTY_BPS + BPS_DENOMINATOR // 2) // BPS_DENOMINATOR


# ---------------------------------------------------------------------------
# White-label law — mirrors the odd-set assembler.
# ---------------------------------------------------------------------------

class NftEconomicsError(ValueError):
    """Fail-closed on any economics violation."""


def check_white_label(buyer_name: str) -> str:
    """Validate the white-label buyer name for a token's license descriptor.

    Every token's license descriptor carries the buyer's business name —
    the pack is white-labeled per business, so LEVI branding must not leak
    onto the customer-facing surface.
    """
    name = (buyer_name or "").strip()
    if not name:
        raise NftEconomicsError("buyer business name is required (white-label law)")
    if "levi" in name.lower():
        raise NftEconomicsError(
            "buyer name must not carry LEVI branding (white-label law)"
        )
    if len(name) > 120:
        raise NftEconomicsError("buyer name too long (max 120 chars)")
    return name


# ---------------------------------------------------------------------------
# Token design — one token, one pack hash.
# ---------------------------------------------------------------------------

def token_id_for(pack_id: str, series_id: str) -> int:
    """Deterministic token id: sha256(series:pack) as a uint256.

    One pack hash yields exactly one token id per series — the token IS the
    certificate of that pack's bytes.
    """
    if not pack_id or not series_id:
        raise NftEconomicsError("pack_id and series_id are required")
    digest = hashlib.sha256(("%s:%s" % (series_id, pack_id)).encode("utf-8")).digest()
    return int.from_bytes(digest, "big")


def series_id_for(year: int) -> str:
    """Annual series id, e.g. ``GENESIS-2026``."""
    year = int(year)
    if year < 2020 or year > 2100:
        raise NftEconomicsError("series year out of range: %r" % (year,))
    return "GENESIS-%d" % year


#: Domain separation for the master token's id preimage — a pack preimage
#: is ``"series:pack"`` so ``"NFT2:series"`` can never collide with one.
MASTER_TOKEN_DOMAIN = "NFT2"


def master_token_id_for(series_id: str) -> int:
    """Deterministic id for the year's NFT² master token.

    One per series, held by the keeper. Domain-separated from pack-token
    ids: ``sha256("NFT2:" + series_id)`` can never equal a
    ``sha256("series:pack")`` id.
    """
    if not series_id:
        raise NftEconomicsError("series_id is required")
    digest = hashlib.sha256(
        ("%s:%s" % (MASTER_TOKEN_DOMAIN, series_id)).encode("utf-8")
    ).digest()
    return int.from_bytes(digest, "big")


def build_token_metadata(
    *,
    pack_id: str,
    pack_final_hash: str,
    series_id: str,
    buyer_name: str,
    agent_count: int,
    grade_proofs: Optional[List[Dict[str, Any]]] = None,
    agent_roster: Optional[List[Dict[str, Any]]] = None,
    license_terms_version: str = "genesis-nft-terms-1",
) -> Dict[str, Any]:
    """Build the token metadata that certifies one pack's exact bytes.

    ``pack_id`` + ``pack_final_hash`` come straight from the hash-chained
    manifest banked by the genesis assemblers (``odd_sets`` /
    ``assemble``) — this function takes them as data and never re-derives
    them, so the certificate cannot drift from the banked manifest.

    ``agent_roster`` optionally carries each agent's reimagined identity —
    a list of ``{"name": ..., "theme": ...}`` dicts (extra keys pass
    through). When given, its length must equal ``agent_count`` and every
    entry must name its agent: the token then carries the pack's agents by
    name and theme, so per-pack tokenization never erases who is inside.
    """
    buyer = check_white_label(buyer_name)
    if not pack_id or not pack_final_hash:
        raise NftEconomicsError("pack_id and pack_final_hash are required")
    if len(pack_final_hash) != 64 or any(
        ch not in "0123456789abcdef" for ch in pack_final_hash.lower()
    ):
        raise NftEconomicsError("pack_final_hash must be a 64-char hex sha256")
    if int(agent_count) % 2 == 0 or int(agent_count) < 1:
        raise NftEconomicsError(
            "genesis packs hold odd agent counts only (keeper's odd law)"
        )
    roster = []
    if agent_roster is not None:
        if len(agent_roster) != int(agent_count):
            raise NftEconomicsError(
                "agent_roster length must equal agent_count"
            )
        for entry in agent_roster:
            name = (entry.get("name") or "").strip()
            if not name:
                raise NftEconomicsError("every rostered agent must have a name")
            rec = {"name": name}
            theme = (entry.get("theme") or "").strip()
            if theme:
                rec["theme"] = theme
            for key, value in entry.items():
                if key not in rec:
                    rec[key] = value
            roster.append(rec)
    token_id = token_id_for(pack_id, series_id)
    return {
        "token_id": token_id,
        "token_id_hex": "0x%064x" % token_id,
        "name": "%s — Genesis %s" % (buyer, series_id),
        "description": (
            "A scarce lifetime license: one token, one genesis pack. "
            "This token certifies the exact pack bytes hashed below. "
            "Lifetime single-copy buy — yours forever, transferable on the "
            "open market. Sold as a license, not an investment: the company "
            "promises no profit and no rising value."
        ),
        "series_id": series_id,
        "pack_id": pack_id,
        "pack_final_hash": pack_final_hash.lower(),
        "agent_count": int(agent_count),
        "agents": roster,
        "grade_proofs": list(grade_proofs or []),
        "license_terms": license_terms_version,
        "license_terms_ref": NFT_LICENSE_TERMS["version"],
        "royalty_bps": ROYALTY_BPS,
        "buyer_business": buyer,
    }


# ---------------------------------------------------------------------------
# NFT² — the series master token. The NFT of the NFTs.
# ---------------------------------------------------------------------------

def build_master_token_metadata(
    *,
    series_id: str,
    year: int,
    banked_n: int,
    draw_seed: str,
    keeper_pack_id: str,
    keeper_pack_hash: str,
    keeper_roster: Optional[List[Dict[str, Any]]] = None,
    mint_registry: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Build the NFT² master token metadata — one per year, held by the keeper.

    The master is the keeper's reserve token elevated: it certifies its own
    pack (the keeper's inverse pack — every agent in inverse form) AND the
    entire year's mint registry. The token's content is the other tokens.

    Law:
    - The master is minted LAST — only after all N pack tokens exist, so
      the registry it carries is complete. ``mint_registry`` must hold
      exactly ``banked_n`` token ids, including the keeper's own.
    - The master is still 1 of the N (out of N, never on top): it counts
      toward the cap and the outstanding supply like any token.
    - ``keeper_roster`` entries may carry ``"form": "inverse"`` — the
      inverse variant forms live in the keeper's pack alone.
    """
    series_id_for(year)  # validates the year
    if not series_id or not series_id.startswith("GENESIS-"):
        raise NftEconomicsError("series_id is required")
    n = int(banked_n)
    if n < 1:
        raise NftEconomicsError("banked_n must be positive")
    if not (draw_seed or "").strip():
        raise NftEconomicsError("draw_seed is required — the master certifies the draw")
    if not keeper_pack_id or not keeper_pack_hash:
        raise NftEconomicsError("keeper pack id and hash are required")
    if len(keeper_pack_hash) != 64 or any(
        ch not in "0123456789abcdef" for ch in keeper_pack_hash.lower()
    ):
        raise NftEconomicsError("keeper_pack_hash must be a 64-char hex sha256")
    registry = [int(t) for t in (mint_registry or [])]
    if len(registry) != n:
        raise NftEconomicsError(
            "the master is minted last: registry holds %d of %d tokens"
            % (len(registry), n)
        )
    if len(set(registry)) != len(registry):
        raise NftEconomicsError("mint registry contains duplicate token ids")
    keeper_token_id = token_id_for(keeper_pack_id, series_id)
    if keeper_token_id not in registry:
        raise NftEconomicsError("keeper's token is missing from the mint registry")
    token_id = master_token_id_for(series_id)
    if token_id in registry:
        raise NftEconomicsError("master id collides with the mint registry")
    registry_hex = ["0x%064x" % t for t in registry]
    roster = []
    for entry in keeper_roster or []:
        name = (entry.get("name") or "").strip()
        if not name:
            raise NftEconomicsError("every rostered agent must have a name")
        rec = {"name": name, "form": (entry.get("form") or "inverse").strip()}
        theme = (entry.get("theme") or "").strip()
        if theme:
            rec["theme"] = theme
        roster.append(rec)
    return {
        "token_id": token_id,
        "token_id_hex": "0x%064x" % token_id,
        "edition": "NFT2",
        "name": "NFT² — Master of %s" % series_id,
        "description": (
            "The series master token: the NFT of the NFTs. One per year, "
            "held by the keeper. It certifies the keeper's inverse pack "
            "below and carries the complete mint registry of its series — "
            "every token of %s, including the draw that chose them. "
            "Sold as a license, not an investment: the company promises "
            "no profit and no rising value." % series_id
        ),
        "series_id": series_id,
        "year": int(year),
        "banked_n": n,
        "draw_seed": draw_seed,
        "keeper_pack_id": keeper_pack_id,
        "keeper_pack_hash": keeper_pack_hash.lower(),
        "keeper_token_id": keeper_token_id,
        "keeper_token_id_hex": "0x%064x" % keeper_token_id,
        "keeper_roster": roster,
        "mint_registry": registry_hex,
        "mint_registry_count": len(registry_hex),
        "license_terms": "genesis-nft-terms-1",
        "license_terms_ref": NFT_LICENSE_TERMS["version"],
        "royalty_bps": ROYALTY_BPS,
    }


# ---------------------------------------------------------------------------
# The annual-N framework — N itself stays TBD by the keeper.
# ---------------------------------------------------------------------------

def framework_for_n(
    *,
    revenue_target_cents: int,
    mint_price_cents: int,
    max_primary_sell_through: float = 1.0,
) -> Dict[str, Any]:
    """The framework for setting a series' annual mint cap N.

    price x quantity = revenue target, so N = target / (price x sell-through).
    Guidance, not a decision — but the keeper's floor binds: the effective
    N for any year is never below ``ANNUAL_SERIES_CAP_MIN`` (1,000) unless
    he overrides it explicitly on the series ledger. The year's N is banked
    in writing (``ledger.SeriesLedger``) before mint, and the series mints
    at exactly that N.
    """
    if revenue_target_cents <= 0 or mint_price_cents <= 0:
        raise NftEconomicsError("revenue target and mint price must be positive")
    if not 0 < max_primary_sell_through <= 1.0:
        raise NftEconomicsError("sell-through must be in (0, 1]")
    raw = revenue_target_cents / (mint_price_cents * max_primary_sell_through)
    import math

    return {
        "revenue_target": usd(revenue_target_cents),
        "mint_price": usd(mint_price_cents),
        "assumed_sell_through": max_primary_sell_through,
        "implied_n_exact": round(raw, 2),
        "implied_n_rounded": math.ceil(raw),
        "keeper_floor_n": ANNUAL_SERIES_CAP_MIN,
        "effective_n": max(ANNUAL_SERIES_CAP_MIN, math.ceil(raw)),
        "guidance": [
            "The keeper's floor is 1,000 per year, minimum. Year one starts "
            "at the floor unless he banks a higher N in writing.",
            "Raise N only after the treasury has defended the floor through "
            "at least one full buyback epoch cycle.",
            "Earlier series stay scarcer forever — never re-mint a closed "
            "series, never raise a published cap.",
            "N is the keeper's call, every year, in writing, before mint — "
            "banked in the series ledger, and the series mints at that N.",
        ],
        "decision": "TBD per year — keeper sets N in writing (floor 1,000), before mint",
    }


# ---------------------------------------------------------------------------
# License terms — securities-safe by construction.
# ---------------------------------------------------------------------------

NFT_LICENSE_TERMS: Dict[str, Any] = {
    "version": "genesis-nft-terms-1",
    "sale": (
        "One token, one genesis pack: a scarce lifetime license. "
        "One-time purchase — the licensed copy is yours forever."
    ),
    "copy": "1 copy: install on machines you own or control.",
    "transfer": (
        "Transferable on the open market — the whole token, with its "
        "certified pack hash. Secondary sales pay the on-chain royalty to "
        "the buyback treasury."
    ),
    "buyback": (
        "The buyback treasury posts a standing floor bid per series with "
        "bounded per-epoch liquidity. The floor is a bid, not a redemption "
        "guarantee and not a promise of any price."
    ),
    "no_profit_promises": [
        "The company promises no profit, no yield, and no rising value.",
        "Any secondary-market appreciation is pure market scarcity — the "
        "company does not cause it, direct it, or guarantee it.",
        "Marketing must never claim the token will rise in value, pay "
        "returns, or share in company profits.",
    ],
    "legal": (
        "A lawyer clears the first real mint before it happens. Until then "
        "every figure in this package is paper."
    ),
    "forbidden": [
        "mint beyond a series' published cap",
        "raise a published cap, ever",
        "re-mint a closed series",
        "strip or alter the token metadata",
        "represent the pack as the full LEVI organism",
    ],
}


def license_summary() -> Dict[str, Any]:
    """The license terms as data, for embedding in descriptors."""
    return json.loads(json.dumps(NFT_LICENSE_TERMS))
