"""Legion bot — the monetizable bot product (Chauncey canon, 2026-09-18).

One face the customer talks to, the legion (a tailored team of agents)
behind it doing the work. "For we are many."

Genesis-style lifetime one-copy buy, white-labeled per business;
specialist add-on packs; tailored team = Site Lift analysis + installed
crew. Money: price-advisor quotes, Cybrus gateway, 70/30 split — all
paper-only until a real rail exists.

Submodules:
  product      one-face router config + white-label config schema/validation
  team         tailored team assembly from the existing agent population
  packs        specialist add-on packs (restaurant, salon, shop, generic)
  sitelift_link  Site Lift report -> proposed crew (the tailored offer)
  sale         paper-only money seam: quote, checkout record, license
  cli          thin CLI hook (levi legion ...)

All money paths here are paper: quotes, plans, and ledger lines only.
The Cybrus MoneyGateway is fail-closed; nothing here ever executes a
movement, marks anything paid, or invents income.
"""

__all__ = [
    "product",
    "team",
    "packs",
    "sitelift_link",
    "sale",
    "cli",
]

PRODUCT = "legion"
PRODUCT_FULL_NAME = "Legion bot"
OPERATOR_REGISTRY_PENDING = False  # registry live: levi.operator.registry
