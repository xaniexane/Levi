"""Chain-agnostic contract interface spec for the genesis NFTs.

PAPER ONLY. No deployment, no testnet, no funds. This module specifies the
contract a real deployment must implement — the function surface, the
invariants it must hold, and the reference rule implementations it must
match — without naming a chain's SDK or wiring anything.

CHAIN DECIDED 2026-09-18: the keeper approved Base. The interface spec
below is the law any Base deployment must implement; nothing here
deploys, signs, or spends until he orders the rail.

CUSTODY DECIDED 2026-09-18 (the keeper's custody law): the buyback
treasury belongs to the HOLDERS collectively. The treasury contract holds
all funds and there is NO owner/admin withdrawal function — not for the
keeper, not for anyone. Funds move ONLY via (a) the defined funding
inflows (primary cut, royalties, receipted keeper top-ups) and (b) the
buyback settlement path (floor bids to exiting holders, burned on exit).
The keeper's own exit settles only through the same FIFO queue at
identical prices — no backdoor, no separate path. Even the keeper cannot
withdraw. His rationale: the floor is a mechanism, not a promise — if he
held the keys, buyers would have to trust him not to drain their exit
door, and trust is not a mechanism.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from .economics import EPOCH_BUDGET_SHARE, ROYALTY_BPS, reference_royalty

FORM_NAME = "genesis.nft.contract"

#: Token standard the deployment implements.
TOKEN_STANDARD = "ERC-721"
ROYALTY_STANDARD = "EIP-2981"

# ---------------------------------------------------------------------------
# The custody law — what may touch the money, and what may not.
# ---------------------------------------------------------------------------

#: Custody law for the series treasury, in data. A conforming deployment
#: must satisfy every entry; invariant no-owner-withdrawal enforces it.
CUSTODY_LAW: Dict[str, Any] = {
    "owner": "the holders, collectively",
    "principle": (
        "The treasury contract holds all funds. No owner/admin withdrawal "
        "function exists — not for the keeper, not for anyone. Even the "
        "keeper cannot withdraw."
    ),
    "inflows": [  # the ONLY ways funds enter
        "primary-cut",        # 20% of gross primary, carved from the keeper's share
        "royalty",            # 100% of secondary royalties (7.5% EIP-2981)
        "keeper-top-up",      # discretionary, receipted, sourced — never silent
    ],
    "outflows": [  # the ONLY ways funds leave
        "buyback-settlement",  # floor bids to exiting holders, token burned on exit
    ],
    "founder_exit": (
        "The keeper's own exit settles only through the same FIFO queue at "
        "identical prices — no backdoor, no separate path, no priority."
    ),
    "rationale": (
        "The floor is a mechanism, not a promise. If the keeper held the "
        "keys, buyers would have to trust him not to drain their exit door "
        "— and trust is not a mechanism."
    ),
}

#: Substrings that mark a function as an admin drain path. Any function
#: whose name contains one of these is a custody violation — it is a door
#: in the treasury that the buyback path does not own.
FORBIDDEN_DRAIN_PATTERNS = ("withdraw", "sweep", "drain")


def _looks_like_drain(function_name: str) -> bool:
    name = str(function_name).lower()
    return any(pattern in name for pattern in FORBIDDEN_DRAIN_PATTERNS)


def interface_function_names(interface: List[Dict[str, str]] = None) -> List[str]:
    """The function names declared by an interface spec (default: ours)."""
    return [fn["name"] for fn in (INTERFACE if interface is None else interface)]


def invariant_interface_has_no_drain(
    interface: List[Dict[str, str]] = None,
) -> bool:
    """The declared function surface contains no withdrawal/sweep function.

    The ABSENCE is itself the law: a conforming deployment must not
    declare a door the buyback path does not own — even one named for
    the keeper.
    """
    return not any(_looks_like_drain(n) for n in interface_function_names(interface))

#: The function surface a conforming deployment MUST expose. Types are
#: written in Solidity idiom because that is what the EVM L2s speak; a
#: non-EVM deployment must expose the same semantics under its own idiom.
#: This surface contains NO withdrawal or sweep function — the absence is
#: itself the custody law: the treasury contract holds all funds and funds
#: move only via the funding inflows and the buyback settlement path.
#: invariant no-owner-withdrawal FAILS any deployment whose spec declares
#: a drain door (ownerSweep, emergencyWithdraw, or any like-named path).
INTERFACE: List[Dict[str, str]] = [
    {
        "name": "createSeries",
        "signature": "createSeries(string seriesId, uint256 maxSupply, "
                     "uint256 mintPriceWei, address treasury)",
        "semantics": (
            "Opens an annual series. maxSupply is written once and can "
            "never be raised afterwards. Emits SeriesCreated."
        ),
    },
    {
        "name": "mint",
        "signature": "mint(address to, string seriesId, string tokenURI)",
        "semantics": (
            "Mints only while series minted count < maxSupply. tokenURI "
            "carries the metadata built by economics.build_token_metadata — "
            "pack_id + pack_final_hash. Only the minter role (the keeper's "
            "sale contract) may call. Emits Transfer(0x0 -> to)."
        ),
    },
    {
        "name": "burn",
        "signature": "burn(uint256 tokenId)",
        "semantics": (
            "Called by the treasury on buyback. Destroys the token and "
            "decrements the series supply. Burned ids are never re-minted."
        ),
    },
    {
        "name": "royaltyInfo",
        "signature": "royaltyInfo(uint256 tokenId, uint256 salePrice) "
                     "-> (address receiver, uint256 royaltyAmount)",
        "semantics": (
            "EIP-2981. receiver is always the series treasury; "
            "royaltyAmount is exactly ROYALTY_BPS of salePrice, rounded "
            "half up. Marketplaces that honor 2981 route it automatically."
        ),
    },
    {
        "name": "seriesOf",
        "signature": "seriesOf(uint256 tokenId) -> string seriesId",
        "semantics": "The series a token was minted into. Immutable.",
    },
    {
        "name": "seriesSupply",
        "signature": "seriesSupply(string seriesId) -> uint256",
        "semantics": "Live supply: minted minus burned. Never exceeds cap.",
    },
    {
        "name": "seriesCap",
        "signature": "seriesCap(string seriesId) -> uint256",
        "semantics": "The published cap. Set once at creation; immutable upward.",
    },
    {
        "name": "seriesFloor",
        "signature": "seriesFloor(string seriesId) -> uint256",
        "semantics": (
            "Read-only view of the treasury's current standing floor bid "
            "for the series, in wei. Computed off-chain by the treasury; "
            "published on-chain so holders can verify the bid they sell into."
        ),
    },
]


# ---------------------------------------------------------------------------
# Invariants — conformance predicates over a model ledger.
#
# A model ledger is a plain dict:
#   {"series": {series_id: {"cap": int, "minted": int, "burned": int,
#                           "cap_history": [int, ...],
#                           "treasury": "0x...",
#                           "royalty_events": [(sale_price, paid, receiver), ...],
#                           "admin_drain_paths": ["ownerSweep", ...],       # any entry -> FAIL
#                           "interface_functions": ["createSeries", ...],  # scanned for drain names
#                           "outflow_events": [{"kind": "buyback-settlement",
#                                               "receiver": "0x..."}, ...]}}}  # other kinds -> FAIL
# ---------------------------------------------------------------------------

def _series(ledger: Dict[str, Any], series_id: str) -> Dict[str, Any]:
    try:
        return ledger["series"][series_id]
    except KeyError:
        raise AssertionError("unknown series: %r" % (series_id,))


def invariant_cap_never_raised(ledger: Dict[str, Any], series_id: str) -> bool:
    """A published cap is never raised after creation."""
    hist = _series(ledger, series_id)["cap_history"]
    return all(later <= hist[0] for later in hist[1:])


def invariant_supply_within_cap(ledger: Dict[str, Any], series_id: str) -> bool:
    """Live supply (minted - burned) never exceeds the cap."""
    s = _series(ledger, series_id)
    return 0 <= s["minted"] - s["burned"] <= s["cap"]


def invariant_burned_never_reminted(
    ledger: Dict[str, Any], series_id: str, burned_ids: List[int], live_ids: List[int]
) -> bool:
    """Burned token ids never reappear among live tokens."""
    return not (set(burned_ids) & set(live_ids))


def invariant_royalty_exact(ledger: Dict[str, Any], series_id: str) -> bool:
    """Every recorded royalty equals the reference rule, to the treasury."""
    s = _series(ledger, series_id)
    for sale_price, paid, receiver in s.get("royalty_events", []):
        if receiver != s["treasury"]:
            return False
        if paid != reference_royalty(sale_price):
            return False
    return True


def invariant_no_owner_withdrawal(ledger: Dict[str, Any], series_id: str) -> bool:
    """The custody law, as a predicate: no admin drain path exists.

    FAILS when the model ledger/spec shows any of:
      - ``admin_drain_paths``: a declared withdrawal/sweep/drain function,
        an owner sweep, or any treasury receiver other than the buyback
        path;
      - ``interface_functions``: a declared function whose name looks like
        a drain (``withdraw`` / ``sweep`` / ``drain``);
      - ``outflow_events``: any outflow whose kind is not
        ``buyback-settlement`` — the ONLY allowed outflow.
    Absent fields pass: a ledger that declares nothing declares no drain.
    """
    s = _series(ledger, series_id)

    drain_paths = s.get("admin_drain_paths") or []
    if drain_paths:
        return False  # a drain door is declared — refused, always

    declared_functions = s.get("interface_functions") or []
    if any(_looks_like_drain(fn) for fn in declared_functions):
        return False  # the surface carries a withdrawal function

    for event in s.get("outflow_events") or []:
        if event.get("kind") != "buyback-settlement":
            return False  # the only outflow the law knows is the buyback

    return True


def invariant_floor_liquidity_bounded(
    ledger: Dict[str, Any],
    series_id: str,
    epoch_outflow: int,
    treasury_balance: int,
    floor_price: int,
) -> bool:
    """One epoch's buyback outflow never exceeds the bounded share.

    The bound is max(EPOCH_BUDGET_SHARE of the treasury, one floor bid) —
    the door always opens, a run never drains it in one epoch.
    """
    pct = (treasury_balance * int(EPOCH_BUDGET_SHARE * 100)) // 100
    bound = max(pct, floor_price)
    return 0 <= epoch_outflow <= bound


CONFORMANCE_SUITE: List[Tuple[str, Callable[..., bool]]] = [
    ("cap-never-raised", invariant_cap_never_raised),
    ("supply-within-cap", invariant_supply_within_cap),
    ("royalty-exact", invariant_royalty_exact),
    ("no-owner-withdrawal", invariant_no_owner_withdrawal),
]


def check_conformance(ledger: Dict[str, Any]) -> Dict[str, Any]:
    """Run the conformance suite over every series in a model ledger."""
    results: Dict[str, Any] = {}
    ok = True
    for series_id in ledger.get("series", {}):
        series_results: Dict[str, bool] = {}
        for name, predicate in CONFORMANCE_SUITE:
            try:
                passed = bool(predicate(ledger, series_id))
            except AssertionError:
                passed = False
            series_results[name] = passed
            ok = ok and passed
        results[series_id] = series_results
    return {"ok": ok, "series": results}


# ---------------------------------------------------------------------------
# Chain recommendation — data, not a decision.
# ---------------------------------------------------------------------------

CHAIN_RECOMMENDATION: Dict[str, Any] = {
    "recommended": "Base",
    "why": [
        "Fees: mints and transfers cost cents, not dollars — the keeper's "
        "law is dollar-scale entry, volume over margin, and L1 fees would "
        "eat a low-tier mint whole.",
        "EVM: ERC-721 + EIP-2981 are native idioms; marketplace royalty "
        "support (OpenSea et al.) is mature on EVM L2s.",
        "On-ramps: Coinbase-adjacent fiat rails lower buyer friction for "
        "the small-business lane Legion sells into.",
        "Tooling: standard wallets, block explorers, and indexers — no "
        "exotic stack for the keeper to maintain.",
    ],
    "alternatives": {
        "Polygon PoS": "Cheaper history, larger existing NFT market, but a "
                       "sidechain security model rather than L2 settlement.",
        "Solana": "Lowest fees and fast settlement, but non-EVM — the "
                   "interface spec above would need re-idioming and EIP-2981 "
                   "has no direct equivalent.",
    },
    "decision": (
        "DECIDED 2026-09-18 — the keeper approved Base. The interface spec "
        "above is the law any Base deployment must implement; nothing here "
        "deploys, signs, or spends until he orders the rail."
    ),
}
