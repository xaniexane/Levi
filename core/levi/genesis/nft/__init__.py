"""Genesis NFTs: the lifetime one-copy buy as a token.

Keeper's canon (2026-09-18): the one-time lifetime copies ARE NFTs. Each
year mints a capped number; any holder — the keeper included — can opt out
their weight through the buyback treasury, and the design must make value
rise for them.

PAPER ONLY. No chain, no testnet, no funds, no payments. This package is
the economics as data plus pure functions:

- ``economics`` — the token design, the annual series model (1,000-copy
  floor, keeper-decided), the confirmed royalty rule, the white-label law,
  the securities-safe license terms.
- ``ledger`` — the series ledger: each year's N banked in writing,
  hash-chained; the gate between the decision and the mint.
- ``contract`` — the chain-agnostic contract interface spec: the function
  surface a real deployment must expose, the invariants it must hold, and
  the reference rule implementations it must match. Chain decided: Base
  (keeper, 2026-09-18); nothing deploys until he orders the rail.
- ``treasury`` — the buyback treasury: funding, the floor-price formula,
  the buyback queue, burns, founder-reserve parity, receipted.
- ``simulate`` — the paper market: runs mints, sales, resales, buybacks
  and burns through the treasury and prints floor-price trajectories, so
  the math is proven before real money exists.

See ``DESIGN.md`` beside this file for the full design in committed prose.
"""

from __future__ import annotations

from . import contract, economics, ledger, simulate, treasury

__all__ = ["contract", "economics", "ledger", "simulate", "treasury"]
