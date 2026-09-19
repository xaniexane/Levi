# NeighborOS Differentiators — the Legion Service Technique

Five instruments that make NeighborOS delivery unreplicable. Stdlib-only,
hermetic, owner-scoped under `<LEVI_HOME>/neighboros/`.

## 1. Receipt-chained delivery (`receipt_chain.py`)

Every stage of the legion pipeline — analyze → quote → deliver → paid →
showcase — mints a sealed receipt linked to the prior envelope hash, a
tamper-evident chain of custody for the whole engagement. The verifier
checks seals, link integrity, envelope hashes, and stage regressions
(a stage receipt may never precede its predecessor).

## 2. Adversarial quote audit (`quote_audit.py`)

Quotes are reviewed adversarially through the deterministic `weigh`
engine: advisor band, line-item reconciliation, scope, and timeline.
**Objective line-item/total mismatch is a hard flag** — the weighing
balance can no longer pass a quote whose line items don't reconcile.

## 3. Showcase-as-proof (`showcase_proof.py`)

Delivery automatically creates a showcase *draft*. Nothing publishes
without explicit client consent — and actual publication still inherits
the bounty showcase gates: paid state and Cybrus proof.

## 4. Decay-monitored delivery (`decay_monitor.py`)

Delivered work is registered for recurring health checks; the monitor
produces pull-based nudges for unhealthy or overdue deliveries. Honest
limit: no push-notification rail is claimed — nudges are pull-based.

## 5. Stake-under-fog quoting (`stake_quote.py`)

Providers stake reputation on quote accuracy before the work lands.
Settlement compares the final price against a configurable tolerance and
tracks honest Brier calibration across quotes — the same calibration
math the academy uses for learners.

## Sealing

`_seal.py` is the NeighborOS-scoped Veil-lineage seal with its own
keeper key — separate from the academy's. Honest limit: documented
stdlib HMAC construction, not AES-GCM.

## Tests

`tests/test_neighboros_differentiators.py` — 18 tests, all green,
home-scoped, deterministic, no network.
