"""Paper market simulator: prove the treasury math before real money exists.

PAPER ONLY. No chain, no funds, no payments. The simulator runs scripted
scenarios — mints, primary sales, secondary sales with royalties, buyback
requests, epoch settlements, burns — through ``treasury.Treasury`` and
prints each series' floor-price trajectory.

Three scenarios ship:

- ``first_light`` — the healthy path: a 100-cap series mints at $50,
  sells 60 primary, sees secondary volume, a few holders exit. The floor
  should never fall below mint price and should rise as royalties compound
  against a shrinking supply.
- ``bank_run`` — the stress path: a thin early treasury faces 40% of
  holders requesting exit at once. The epoch budget must hold, the queue
  must stay FIFO, the treasury must never go negative.
- ``founder_parity`` — the trust path: the keeper's reserve exits through
  the identical queue at the identical floor. No priority, no discount.

Every scenario is deterministic: same script, same trajectory, every run.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .economics import reference_royalty, series_id_for, usd
from .ledger import SeriesLedger
from .treasury import Treasury

FORM_NAME = "genesis.nft.simulate"


class PaperMarket:
    """A paper market: holders, tokens, and one treasury."""

    def __init__(self) -> None:
        self.treasury = Treasury()
        # holder -> {series_id: [token_ids]} (paper token registry)
        self.holdings: Dict[str, Dict[str, List[int]]] = {}
        self._next_token = 1

    # -- setup -----------------------------------------------------------

    def open_series(
        self, year: int, cap: int, mint_price_cents: int, ledger=None
    ) -> str:
        """Open a series, optionally through the ledger gate (no N, no mint)."""
        series_id = series_id_for(year)
        self.treasury.create_series(series_id, cap, mint_price_cents, ledger=ledger)
        return series_id

    # -- events ----------------------------------------------------------

    def primary_sale(
        self, series_id: str, buyer: str, count: int = 1, price_cents: int = 0
    ) -> Dict[str, Any]:
        """Buyer takes ``count`` fresh tokens at the series mint price."""
        s = self.treasury.series_view(series_id)
        price = price_cents or s["mint_price_cents"]
        receipt = self.treasury.fund_primary(series_id, price, count)
        ids = []
        for _ in range(count):
            tid = self._next_token
            self._next_token += 1
            ids.append(tid)
        self.holdings.setdefault(buyer, {}).setdefault(series_id, []).extend(ids)
        return {"buyer": buyer, "token_ids": ids, "receipt": receipt["hash"]}

    def secondary_sale(
        self, series_id: str, seller: str, buyer: str, price_cents: int
    ) -> Dict[str, Any]:
        """A resale: royalty to the treasury, token changes hands."""
        held = self.holdings.get(seller, {}).get(series_id, [])
        if not held:
            raise ValueError("%s holds no %s tokens" % (seller, series_id))
        token_id = held.pop(0)
        royalty = reference_royalty(price_cents)
        self.treasury.fund_royalty(series_id, royalty)
        self.holdings.setdefault(buyer, {}).setdefault(series_id, []).append(token_id)
        return {
            "token_id": token_id,
            "price": usd(price_cents),
            "royalty": usd(royalty),
            "seller": seller,
            "buyer": buyer,
        }

    def request_exit(self, series_id: str, holder: str) -> Dict[str, Any]:
        """A holder queues one token for buyback at the standing floor."""
        held = self.holdings.get(holder, {}).get(series_id, [])
        if not held:
            raise ValueError("%s holds no %s tokens" % (holder, series_id))
        token_id = held.pop(0)
        receipt = self.treasury.request_buyback(series_id, holder, token_id)
        return {"holder": holder, "token_id": token_id, "receipt": receipt["hash"]}

    def settle(self, series_id: str) -> Dict[str, Any]:
        """Run one settlement epoch and return the paper state."""
        result = self.treasury.settle_epoch(series_id)
        return result

    def snapshot(self, series_id: str) -> Dict[str, Any]:
        return self.treasury.series_view(series_id)


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

def scenario_first_light() -> Dict[str, Any]:
    """Healthy path: 100-cap series, $50 mint, sellout, heavy secondary.

    The claim under test: royalty compounding against a capped, shrinking
    supply lifts the floor *above* mint price — the value-raise mechanism,
    proven on paper. This is a mechanism proof, not a volume projection.
    """
    m = PaperMarket()
    sid = m.open_series(2026, cap=100, mint_price_cents=5_000)
    log: List[str] = []

    # Primary: full sellout. 20% of gross -> treasury.
    for i in range(100):
        m.primary_sale(sid, "holder-%02d" % i)
    s = m.snapshot(sid)
    log.append("after primary sellout 100/100: floor %s, treasury %s, backing %s"
               % (s["floor"], s["balance"], s["backing_per_token"]))

    # Secondary: 600 resales at $100 — 7.5% royalties compound.
    # Any current holder may sell; the royalty accrues per sale regardless.
    for i in range(600):
        m.secondary_sale(sid, _any_holder(m, sid), "trader-%03d" % i, 10_000)
    s = m.snapshot(sid)
    log.append("after 600 resales @ $100: floor %s, treasury %s, backing %s"
               % (s["floor"], s["balance"], s["backing_per_token"]))

    # Five holders exit at the standing floor (now above mint).
    exited = [h for h in list(m.holdings) if m.holdings[h].get(sid)][:5]
    for h in exited:
        m.request_exit(sid, h)
    r = m.settle(sid)
    s = m.snapshot(sid)
    log.append(
        "after 5 exits + settle: floor %s, outstanding %d, treasury %s, receipts %s"
        % (s["floor"], s["outstanding"], s["balance"], m.treasury.verify_receipts())
    )

    # More secondary volume on the shrunken supply — the ratchet tightens.
    for i in range(100):
        m.secondary_sale(sid, _any_holder(m, sid), "late-%03d" % i, 10_000)
    m.settle(sid)
    s = m.snapshot(sid)
    log.append("after 100 more resales: floor %s, treasury %s, backing %s"
               % (s["floor"], s["balance"], s["backing_per_token"]))

    return {
        "name": "first-light",
        "series": sid,
        "log": log,
        "floor_log": s["floor_log"],
        "final": s,
        "receipts_ok": m.treasury.verify_receipts(),
        "solvent": m.treasury.check_solvency(sid),
    }


def _any_holder(m: PaperMarket, series_id: str) -> str:
    """Any holder currently holding a token of the series (deterministic)."""
    for holder in sorted(m.holdings):
        if m.holdings[holder].get(series_id):
            return holder
    raise ValueError("no holder with tokens")


def scenario_bank_run() -> Dict[str, Any]:
    """Stress path: thin treasury, 40% of holders exit at once.

    The claim under test: bounded liquidity + FIFO + never-pay-what-you-
    don't-hold keeps the treasury solvent and orderly under a run. Honest
    boundary: a mint-price floor over a thin backing is NOT fully fundable
    for every holder at once — the queue drains until the treasury is
    empty, then waits for new inflow. That limit is the design, not a bug.
    """
    m = PaperMarket()
    sid = m.open_series(2026, cap=100, mint_price_cents=5_000)
    log: List[str] = []

    for i in range(20):
        m.primary_sale(sid, "holder-%02d" % i)
    s = m.snapshot(sid)
    log.append("after primary 20/100: floor %s, treasury %s, backing %s"
               % (s["floor"], s["balance"], s["backing_per_token"]))

    # 8 of 20 holders (40%) request exit in the same epoch.
    for i in range(8):
        m.request_exit(sid, "holder-%02d" % i)
    r = m.settle(sid)
    s = m.snapshot(sid)
    log.append(
        "epoch 1: settled %d, still queued %d, floor %s, treasury %s"
        % (len(r["settled"]), s["queued"], s["floor"], s["balance"])
    )

    # Keep settling: the queue drains FIFO until the treasury is empty.
    epochs = 1
    while m.snapshot(sid)["queued"] and epochs < 12:
        before = m.snapshot(sid)["balance_cents"]
        m.settle(sid)
        epochs += 1
        if m.snapshot(sid)["balance_cents"] == before == 0:
            break  # treasury empty — the honest boundary, no fake progress
    s = m.snapshot(sid)
    log.append(
        "settled %d epochs: floor %s, outstanding %d, treasury %s, "
        "still queued %d, solvent %s, receipts %s"
        % (epochs, s["floor"], s["outstanding"], s["balance"], s["queued"],
           m.treasury.check_solvency(sid), m.treasury.verify_receipts())
    )

    return {
        "name": "bank-run",
        "series": sid,
        "log": log,
        "floor_log": s["floor_log"],
        "final": s,
        "receipts_ok": m.treasury.verify_receipts(),
        "solvent": m.treasury.check_solvency(sid),
    }


def scenario_founder_parity() -> Dict[str, Any]:
    """Trust path: the keeper's reserve exits through the identical queue.

    The claim under test: founder tokens are ordinary tokens — same floor,
    same FIFO queue, no priority. The keeper queues BEHIND ordinary
    holders and the settlement order proves it.
    """
    m = PaperMarket()
    sid = m.open_series(2026, cap=100, mint_price_cents=5_000)
    log: List[str] = []

    for i in range(60):
        m.primary_sale(sid, "holder-%02d" % i)
    for i in range(40):
        m.secondary_sale(sid, _any_holder(m, sid), "trader-%02d" % i, 8_000)
    # The keeper keeps a 10-token reserve — ordinary tokens, noted only.
    for _ in range(10):
        m.primary_sale(sid, "keeper")
    m.treasury.note_founder_reserve(sid, 10)
    s = m.snapshot(sid)
    log.append("treasury deepened: floor %s, treasury %s, backing %s"
               % (s["floor"], s["balance"], s["backing_per_token"]))

    # Two ordinary holders queue first; the keeper queues behind them.
    first = _any_holder(m, sid)
    m.request_exit(sid, first)
    second = _any_holder(m, sid)
    m.request_exit(sid, second)
    m.request_exit(sid, "keeper")
    m.request_exit(sid, "keeper")
    m.request_exit(sid, "keeper")
    expected_order = [first, second, "keeper", "keeper", "keeper"]

    # Settle until the queue drains; record every payout.
    all_settled = []
    while m.snapshot(sid)["queued"]:
        r = m.settle(sid)
        if not r["settled"]:
            break
        all_settled.extend(r["settled"])
    order = [x["holder"] for x in all_settled]
    keeper_paid = [x["paid_cents"] for x in all_settled if x["holder"] == "keeper"]
    holder_paid = [x["paid_cents"] for x in all_settled if x["holder"] != "keeper"]
    fifo = order == expected_order
    same_price = (
        bool(keeper_paid) and bool(holder_paid)
        and len(set(keeper_paid + holder_paid)) == 1
    )
    log.append("settlement order %s — FIFO %s" % (order, fifo))
    log.append("keeper paid %s, holders paid %s — identical %s"
               % ([usd(c) for c in keeper_paid], [usd(c) for c in holder_paid],
                  same_price))
    log.append("receipts %s, solvent %s"
               % (m.treasury.verify_receipts(), m.treasury.check_solvency(sid)))

    s = m.snapshot(sid)
    return {
        "name": "founder-parity",
        "series": sid,
        "log": log,
        "floor_log": s["floor_log"],
        "final": s,
        "receipts_ok": m.treasury.verify_receipts(),
        "solvent": m.treasury.check_solvency(sid),
        "fifo_order": fifo,
        "identical_price": same_price,
    }


def run_all_scenarios() -> List[Dict[str, Any]]:
    """Run the three founding scenarios. Deterministic."""
    return [scenario_first_light(), scenario_bank_run(), scenario_founder_parity()]


# ---------------------------------------------------------------------------
# The keeper's floor: N=1000, in writing, before mint
# ---------------------------------------------------------------------------

def scenario_thousand_cap() -> Dict[str, Any]:
    """Healthy path at the keeper's floor: 1000-cap series, ledger-gated.

    The year's N is banked in writing BEFORE the series opens — the gate
    under test is that no N on the books means no mint at all.

    The claim under test: a sold-out 1000-cap still walks its floor above
    mint on royalty compounding against a capped, shrinking supply — the
    value-raise mechanism at real scale, proven on paper.

    SCENARIO PRICES — $50 mint and $100 resales below are illustration
    only. They are not official prices; the keeper prices each series.

    The honest scale note this scenario proves: at N=1000 the crossing
    needs real secondary volume — a few hundred resales move nothing,
    thousands do. That is the keeper's volume-over-margin lane doing the
    work the small-cap proof only hinted at.
    """
    m = PaperMarket()
    ledger = SeriesLedger()
    ledger.record_year(
        2027,
        1000,
        decided_by="keeper",
        decided_at="2026-09-18T21:00:00+00:00",
        note="keeper's floor: a thousand at least",
    )
    sid = m.open_series(2027, cap=1000, mint_price_cents=5_000, ledger=ledger)
    log: List[str] = []
    log.append("SCENARIO PRICES — $50 mint / $100 resales are illustration, not official")

    # Primary: full sellout. 20% of $50,000 gross -> $10,000 treasury.
    for i in range(1000):
        m.primary_sale(sid, "holder-%04d" % i)
    s = m.snapshot(sid)
    log.append("after primary sellout 1000/1000: floor %s, treasury %s, backing %s"
               % (s["floor"], s["balance"], s["backing_per_token"]))
    floor_after_primary = s["floor_cents"]

    # Secondary: 6,000 resales at $100 — 7.5% royalties compound.
    # Any current holder may sell; the royalty accrues per sale regardless.
    for i in range(6000):
        m.secondary_sale(sid, _any_holder(m, sid), "trader-%04d" % i, 10_000)
    s = m.snapshot(sid)
    log.append("after 6000 resales @ $100: floor %s, treasury %s, backing %s"
               % (s["floor"], s["balance"], s["backing_per_token"]))
    floor_after_secondary = s["floor_cents"]

    # Ten holders exit at the standing floor — the invariant must hold:
    # buybacks at full backing leave backing-per-token unchanged.
    exited = [h for h in list(m.holdings) if m.holdings[h].get(sid)][:10]
    for h in exited:
        m.request_exit(sid, h)
    r = m.settle(sid)
    s = m.snapshot(sid)
    log.append(
        "after 10 exits + settle: floor %s, outstanding %d, treasury %s, receipts %s"
        % (s["floor"], s["outstanding"], s["balance"], m.treasury.verify_receipts())
    )
    floor_after_exits = s["floor_cents"]

    # More secondary volume on the shrunken supply — the ratchet tightens.
    for i in range(2000):
        m.secondary_sale(sid, _any_holder(m, sid), "late-%04d" % i, 10_000)
    m.settle(sid)
    s = m.snapshot(sid)
    log.append("after 2000 more resales: floor %s, treasury %s, backing %s"
               % (s["floor"], s["balance"], s["backing_per_token"]))

    return {
        "name": "thousand-cap",
        "series": sid,
        "log": log,
        "floor_log": s["floor_log"],
        "final": s,
        "receipts_ok": m.treasury.verify_receipts(),
        "solvent": m.treasury.check_solvency(sid),
        "ledger_ok": ledger.verify_ledger(),
        "floor_after_primary": floor_after_primary,
        "floor_after_secondary": floor_after_secondary,
        "floor_after_exits": floor_after_exits,
    }


def run_floor_scenarios() -> List[Dict[str, Any]]:
    """The thousand-cap scenario, deterministic — same script, same trajectory."""
    return [scenario_thousand_cap()]


def print_report(report: Dict[str, Any]) -> str:
    """Render a scenario report as plain text."""
    lines = ["=== scenario: %s (%s) ===" % (report["name"], report["series"])]
    lines.extend("  " + entry for entry in report["log"])
    lines.append("  floor trajectory: %s"
                 % ", ".join("%s@e%d" % (f, e) for e, f in report["floor_log"]))
    lines.append("  receipts intact: %s | solvent: %s"
                 % (report["receipts_ok"], report["solvent"]))
    return "\n".join(lines)


if __name__ == "__main__":
    for report in run_all_scenarios():
        print(print_report(report))
        print()
    for report in run_floor_scenarios():
        print(print_report(report))
        print()
