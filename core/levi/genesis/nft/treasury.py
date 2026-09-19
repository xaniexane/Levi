"""The buyback treasury: the exit door, as paper math.

Keeper's canon (2026-09-18): he or any generous holder must be able to opt
out their weight in the company and product, and the design must make value
rise for them.

CUSTODY (decided 2026-09-18): the treasury belongs to the HOLDERS
collectively. The treasury holds all funds and there is NO owner/admin
withdrawal function — not for the keeper, not for anyone. Funds move ONLY
via (a) the defined funding inflows (primary cut, royalties, receipted
keeper top-ups) and (b) the buyback settlement path (floor bids to exiting
holders, token burned on exit). The keeper's own exit settles only through
the same FIFO queue at identical prices — no backdoor. Even the keeper
cannot withdraw. His rationale: the floor is a mechanism, not a promise —
if he held the keys, buyers would have to trust him not to drain their
exit door, and trust is not a mechanism.

How it works, per series:

- FUNDING. 20% of gross primary revenue (``TREASURY_CUT``) lands here,
  carved from the keeper's share — the keeper funds the exit door himself.
  100% of secondary royalties (7.5%) land here too. Discretionary top-ups
  from the keeper are allowed and receipted; nothing else may add funds.
- THE FLOOR. Standing bid per token::

      floor = max(mint_price, treasury_balance / outstanding_supply)

  The invariant that makes it honest: when the floor equals full backing
  (``treasury_balance / outstanding``), every buyback at the floor leaves
  backing-per-token *unchanged* — the bid is exactly solvent by
  construction. When backing sits below mint price (early, thin treasury),
  the floor rests on mint price and buybacks drain faster than the
  invariant — fresh primary revenue and royalties must refill it. The
  simulator proves both regimes.
- BOUNDED LIQUIDITY. At most ``EPOCH_BUDGET_SHARE`` (5%) of a series'
  treasury may leave through buybacks in one settlement epoch. Requests
  beyond the budget wait in a FIFO queue. The floor is a standing bid with
  bounded liquidity — never a redemption guarantee, never a promise of any
  price. The securities-safe framing lives in ``economics``; the bound is
  its mechanical teeth.
- BURN. Every buyback burns the token: supply shrinks, the remaining
  tokens' backing is untouched (full-backing regime) or improved (royalty
  inflow with no new supply). Scarcity does the rising.
- FOUNDER PARITY. The keeper's reserve tokens are ordinary tokens: same
  floor, same queue, no priority. Parity is structural, not promised.

PAPER ONLY. Integer cents throughout; receipts are hash-chained.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from typing import Any, Dict, List, Optional

from .economics import (
    EPOCH_BUDGET_SHARE,
    TREASURY_CUT,
    NftEconomicsError,
    round_half_up_cents,
    split_primary_revenue,
    usd,
)

FORM_NAME = "genesis.nft.treasury"

#: Substrings that mark an attribute as an attempted admin drain. The
#: treasury has no withdrawal function; calling one refuses by law.
_DRAIN_SUBSTRINGS = ("withdraw", "sweep", "drain")


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _year_of_series(series_id: str) -> int:
    """Parse the year out of a series id like ``GENESIS-2027``."""
    try:
        return int(str(series_id).rsplit("-", 1)[1])
    except (ValueError, IndexError, AttributeError):
        raise NftEconomicsError(
            "series_id must look like GENESIS-<year>: %r" % (series_id,)
        )


class Treasury:
    """Paper buyback treasury with per-series accounts."""

    def __init__(self) -> None:
        self._series: Dict[str, Dict[str, Any]] = {}
        self._receipts: List[Dict[str, Any]] = []
        self._seq = 0
        self._prev_hash = "0" * 64

    def __getattr__(self, name: str) -> Any:
        # Custody law, enforced at the model level: there is no owner/admin
        # withdrawal function on the treasury. Any call shaped like a drain
        # (withdraw / sweep / drain) is refused, whoever asks — including
        # the keeper. Funds leave only through request_buyback/settle_epoch.
        if any(part in name.lower() for part in _DRAIN_SUBSTRINGS):
            raise NftEconomicsError(
                "custody law: the treasury has no withdrawal function — "
                "funds move only through buyback settlement. "
                "Even the keeper cannot withdraw."
            )
        raise AttributeError(
            "%r object has no attribute %r" % (type(self).__name__, name)
        )

    # -- receipts ------------------------------------------------------

    def _receipt(self, series_id: str, kind: str, detail: Dict[str, Any]) -> Dict[str, Any]:
        self._seq += 1
        body = {
            "seq": self._seq,
            "form": FORM_NAME,
            "series": series_id,
            "kind": kind,
            "detail": detail,
            "prev": self._prev_hash,
        }
        digest = hashlib.sha256(
            (self._prev_hash + _canonical(body)).encode("utf-8")
        ).hexdigest()
        receipt = dict(body, hash=digest)
        self._prev_hash = digest
        self._receipts.append(receipt)
        return receipt

    def verify_receipts(self) -> bool:
        """Re-walk the hash chain. True iff every link is intact."""
        prev = "0" * 64
        for r in self._receipts:
            body = {k: v for k, v in r.items() if k != "hash"}
            if body.get("prev") != prev:
                return False
            digest = hashlib.sha256((prev + _canonical(body)).encode("utf-8")).hexdigest()
            if digest != r["hash"]:
                return False
            prev = digest
        return True

    # -- series ----------------------------------------------------------

    def _get(self, series_id: str) -> Dict[str, Any]:
        try:
            return self._series[series_id]
        except KeyError:
            raise NftEconomicsError("unknown series: %r" % (series_id,))

    def create_series(
        self,
        series_id: str,
        cap: int,
        mint_price_cents: int,
        ledger=None,
    ) -> Dict[str, Any]:
        """Open a series. The cap is published here and never raised after.

        When a ``ledger`` (``levi.genesis.nft.ledger.SeriesLedger``) is
        given, the gate applies: the series' year must have its N banked in
        writing, and the cap must EQUAL that banked N — the published cap IS
        the keeper's written N. No N on the books, no mint. (Pre-mint cap
        *lowering* stays available through ``lower_cap``.)
        """
        if series_id in self._series:
            raise NftEconomicsError("series already exists: %r" % (series_id,))
        cap = int(cap)
        mint_price_cents = int(mint_price_cents)
        if cap <= 0:
            raise NftEconomicsError("cap must be positive")
        if mint_price_cents <= 0:
            raise NftEconomicsError("mint price must be positive")
        if ledger is not None:
            banked_n = ledger.require_n(_year_of_series(series_id))
            if cap != banked_n:
                raise NftEconomicsError(
                    "series cap %d does not match the banked N (%d) for %s"
                    % (cap, banked_n, series_id)
                )
        self._series[series_id] = {
            "cap": cap,
            "cap_history": [cap],
            "mint_price_cents": mint_price_cents,
            "minted": 0,
            "burned": 0,
            "balance_cents": 0,
            "queue": [],  # FIFO buyback requests: {"holder", "token_id"}
            "epoch": 0,
            "floor_log": [],  # [(epoch, floor_cents)]
            "founder_reserve": 0,  # reporting only — ordinary tokens
        }
        return self._receipt(series_id, "series-created", {
            "cap": cap,
            "mint_price": usd(mint_price_cents),
        })

    def lower_cap(self, series_id: str, new_cap: int) -> Dict[str, Any]:
        """Lower a cap before the first mint. Raising is refused, always."""
        s = self._get(series_id)
        new_cap = int(new_cap)
        if new_cap > s["cap_history"][0]:
            raise NftEconomicsError("caps are never raised after publication")
        if s["minted"] > 0:
            raise NftEconomicsError("cap is frozen once minting begins")
        if new_cap <= 0 or new_cap < s["minted"]:
            raise NftEconomicsError("invalid new cap")
        s["cap"] = new_cap
        s["cap_history"].append(new_cap)
        return self._receipt(series_id, "cap-lowered", {"cap": new_cap})

    # -- funding ---------------------------------------------------------

    def fund_primary(
        self, series_id: str, price_cents: int, count: int = 1
    ) -> Dict[str, Any]:
        """Record primary sales: mint ``count`` tokens, split the revenue.

        Returns the keeper/pool/treasury split. The treasury's cut is the
        only automatic inflow besides royalties.
        """
        s = self._get(series_id)
        count = int(count)
        if count <= 0:
            raise NftEconomicsError("count must be positive")
        if s["minted"] + count > s["cap"]:
            raise NftEconomicsError(
                "mint would breach the published cap (%d + %d > %d)"
                % (s["minted"], count, s["cap"])
            )
        split = split_primary_revenue(price_cents, count)
        s["minted"] += count
        s["balance_cents"] += split["treasury"]
        return dict(
            self._receipt(series_id, "primary-sale", {
                "count": count,
                "price": usd(price_cents),
                "gross": usd(split["keeper"] + split["pool"] + split["treasury"]),
                "keeper": usd(split["keeper"]),
                "pool": usd(split["pool"]),
                "treasury": usd(split["treasury"]),
                "treasury_cut": TREASURY_CUT,
            }),
            split_cents=split,
        )

    def fund_royalty(self, series_id: str, royalty_cents: int) -> Dict[str, Any]:
        """Route a secondary-sale royalty into the series treasury."""
        s = self._get(series_id)
        royalty_cents = int(royalty_cents)
        if royalty_cents < 0:
            raise NftEconomicsError("royalty cannot be negative")
        s["balance_cents"] += royalty_cents
        return self._receipt(series_id, "royalty", {"amount": usd(royalty_cents)})

    def top_up(
        self, series_id: str, amount_cents: int, source: str = "keeper"
    ) -> Dict[str, Any]:
        """Discretionary keeper top-up. Receipted, sourced, never silent."""
        s = self._get(series_id)
        amount_cents = int(amount_cents)
        if amount_cents <= 0:
            raise NftEconomicsError("top-up must be positive")
        s["balance_cents"] += amount_cents
        return self._receipt(series_id, "top-up", {
            "amount": usd(amount_cents),
            "source": source,
        })

    def note_founder_reserve(self, series_id: str, count: int) -> Dict[str, Any]:
        """Record how many of the series' tokens the keeper holds.

        Reporting only. Reserve tokens exit through the same queue at the
        same floor — parity is structural: the treasury cannot tell a
        founder's token from any holder's.
        """
        s = self._get(series_id)
        count = int(count)
        if count < 0:
            raise NftEconomicsError("invalid reserve count")
        s["founder_reserve"] = count
        return self._receipt(series_id, "founder-reserve-noted", {"count": count})

    def mint_keeper_reserve(self, series_id: str, pack_id: str = "") -> Dict[str, Any]:
        """Mint the keeper's copy: one token per series, no sale, no revenue.

        The reserve comes OUT of the published cap, not on top of it — it
        counts toward ``minted``/``outstanding`` like any token but adds
        nothing to the treasury (no primary split on a token never sold).
        Exactly one per series; the buyback queue treats it like any
        holder's token — no priority, no separate exit.
        """
        s = self._get(series_id)
        if s["founder_reserve"] >= 1:
            raise NftEconomicsError(
                "keeper's reserve for %s is already minted — one per series"
                % series_id
            )
        if s["minted"] + 1 > s["cap"]:
            raise NftEconomicsError(
                "reserve mint would breach the published cap — "
                "the keeper's copy comes out of N, never on top of it"
            )
        s["minted"] += 1
        s["founder_reserve"] += 1
        return self._receipt(series_id, "keeper-reserve-minted", {
            "pack_id": pack_id,
            "treasury_inflow_cents": 0,
        })

    # -- the floor ---------------------------------------------------------

    def outstanding(self, series_id: str) -> int:
        s = self._get(series_id)
        return s["minted"] - s["burned"]

    def backing_per_token(self, series_id: str) -> Optional[Fraction]:
        """Exact backing per outstanding token, as a rational of cents."""
        s = self._get(series_id)
        n = self.outstanding(series_id)
        if n <= 0:
            return None
        return Fraction(s["balance_cents"], n)

    def floor_price_cents(self, series_id: str) -> int:
        """The standing floor bid: max(mint_price, backing per token)."""
        s = self._get(series_id)
        n = self.outstanding(series_id)
        if n <= 0:
            return s["mint_price_cents"]
        backing = round_half_up_cents(s["balance_cents"], n)
        return max(s["mint_price_cents"], backing)

    # -- buybacks ------------------------------------------------------------

    def request_buyback(
        self, series_id: str, holder: str, token_id: int
    ) -> Dict[str, Any]:
        """Queue a holder's exit request. FIFO; founder or stranger alike.

        Custody: this queue is the keeper's ONLY exit path. There is no
        keeper-specific settlement, no priority lane, no backdoor — his
        reserve tokens leave through the same queue at the identical floor
        as any holder's, in the order they were queued.
        """
        s = self._get(series_id)
        if not holder:
            raise NftEconomicsError("holder is required")
        s["queue"].append({"holder": holder, "token_id": int(token_id)})
        return self._receipt(series_id, "buyback-requested", {
            "holder": holder,
            "token_id": int(token_id),
            "queue_depth": len(s["queue"]),
        })

    def settle_epoch(self, series_id: str) -> Dict[str, Any]:
        """Settle one epoch: pay the queue FIFO within the liquidity bound.

        Each buyback pays the *current* floor and burns the token. The epoch
        budget is 5% of the series treasury at settlement; requests beyond
        it stay queued. The treasury never pays what it does not hold.
        This is the ONLY outflow path in existence: no admin withdrawal,
        no sweep, no drain — even the keeper's exit is just a request in
        this queue.
        """
        s = self._get(series_id)
        s["epoch"] += 1
        # Bounded liquidity with a one-bid minimum: the exit door always
        # opens, but a run can never drain the treasury in one epoch.
        floor_now = self.floor_price_cents(series_id)
        budget = max(
            (s["balance_cents"] * int(EPOCH_BUDGET_SHARE * 100)) // 100,
            floor_now,
        )
        spent = 0
        settled: List[Dict[str, Any]] = []
        while s["queue"]:
            floor = self.floor_price_cents(series_id)
            if spent + floor > budget:
                break  # bounded liquidity — the rest wait
            if floor > s["balance_cents"]:
                break  # never pay what the treasury does not hold
            req = s["queue"].pop(0)
            s["balance_cents"] -= floor
            s["burned"] += 1
            spent += floor
            settled.append({
                "holder": req["holder"],
                "token_id": req["token_id"],
                "paid_cents": floor,
                "paid": usd(floor),
            })
        floor_now = self.floor_price_cents(series_id)
        s["floor_log"].append((s["epoch"], floor_now))
        return dict(
            self._receipt(series_id, "epoch-settled", {
                "epoch": s["epoch"],
                "settled": len(settled),
                "spent": usd(spent),
                "budget": usd(budget),
                "still_queued": len(s["queue"]),
                "floor_now": usd(floor_now),
                "outstanding": self.outstanding(series_id),
                "balance": usd(s["balance_cents"]),
            }),
            settled=settled,
            floor_cents=floor_now,
        )

    # -- views ---------------------------------------------------------------

    def series_view(self, series_id: str) -> Dict[str, Any]:
        """Full paper state of a series, for reports and tests."""
        s = self._get(series_id)
        backing = self.backing_per_token(series_id)
        return {
            "series": series_id,
            "cap": s["cap"],
            "cap_history": list(s["cap_history"]),
            "mint_price": usd(s["mint_price_cents"]),
            "mint_price_cents": s["mint_price_cents"],
            "minted": s["minted"],
            "burned": s["burned"],
            "outstanding": self.outstanding(series_id),
            "balance": usd(s["balance_cents"]),
            "balance_cents": s["balance_cents"],
            "backing_per_token": usd(round_half_up_cents(
                s["balance_cents"], self.outstanding(series_id)
            )) if self.outstanding(series_id) else 0,
            "floor": usd(self.floor_price_cents(series_id)),
            "floor_cents": self.floor_price_cents(series_id),
            "queued": len(s["queue"]),
            "epoch": s["epoch"],
            "floor_log": [(e, usd(f)) for e, f in s["floor_log"]],
            "founder_reserve": s["founder_reserve"],
            "_backing_exact": backing,
        }

    def check_solvency(self, series_id: str) -> bool:
        """The treasury never owes more than it holds."""
        return self._get(series_id)["balance_cents"] >= 0
