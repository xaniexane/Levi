"""SupraStreet — commerce with royalty splits (Execution Layer organ).

Canon: SupraStreet is the commerce organ of the SER architecture.
Attested in the founder corpus alongside GenEX (ledger) and Eden
(experiments): the dead-software inventory (§16, docs-level) AND the
recovered SER-18 UI sources in the drive-sweep corpus
(``work/x/1O6MuzsNuHDGOzBoM0NRjUt7E_GpecPIA/src/components/``):
SupraStreet = "Commerce, Royalty Cut, & Liquidity Throttle" /
"Commerce/Royalty" — "Monetization and contract cut distribution
gatekeeper" that "calculates payouts, automatically enforcing a strict
15% royalty cut allocated to the Founder wallet on every settlement"
(``SER18Orchestrator.tsx``).

LEVI-native build from scratch. It is NOT
:mod:`core.levi.revival.transparent_commerce` (friction-symmetry:
cancel must cost no more steps than signup) — a different concept.

A product registers royalty recipients as integer basis-point splits
that must sum to exactly 10_000 (100%). Every sale distributes the
gross across recipients into a paper settlement ledger — accounting
entries, not real payouts. Money stays paper-only per the standing
law.

Law (declared up front; tests are the proof):
1. SPLITS SUM TO 100% — product registration refuses splits that do
   not sum to exactly 10_000 basis points.
2. CONSERVATION — sum of distributed amounts == gross sale amount.
   No dust, no leakage: integer math, remainder goes to the first
   recipient by registration order (deterministic).
3. PAPER-ONLY — no network, no payment rails; settlements are ledger
   receipts. ``settle()`` writes accounting entries only.
4. IDEMPOTENCY — recording the same ``sale_id`` twice settles once;
   the second call returns the original settlement unchanged.
5. FOUNDER'S CUT (original SER-18 mechanic) — ``register_product_with_founder_cut``
   enforces the strict 15% founder / 85% seller split through the same
   guarded path as every other product.
"""

from .commerce import FOUNDER_CUT_BP, FOUNDER_WALLET, RoyaltyError, SupraStreet

__all__ = ["SupraStreet", "RoyaltyError", "FOUNDER_CUT_BP", "FOUNDER_WALLET"]
