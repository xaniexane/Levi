---
skill_id: fairplay.audit_offer
name: Audit a Game Offer
description: Run the sly-trade detector over an offer dict and report the verdict with an honest alternative for every finding.
category: fairplay
risk: info
permissions: []
requires_confirmation: false
tags: [fairplay, audit, honest-design, blue-team]
version: 1.0.0
---

# Audit a Game Offer

Defensive blue-team only: this skill names predatory offer patterns so
they can be refused or inverted. It never designs a funnel, never runs a
till, never optimizes conversion.

## Procedure

1. Describe the offer as a flat dict of declared claims. Every field is
   optional; absence is read as "not claimed" and the report says so
   honestly. Recognized fields:
   - `paid_random_draws`, `odds_published`, `pity_ceiling_declared`,
     `worst_case_spend_declared`
   - `progress_expiry`: `"never"`, `"season"`, or `"event"`
   - `sale_is_license`, `license_revocable`, `eol_covenant`
   - `paid_power`, `server_only_inventory`, `inventory_exportable`
   - `marketing_language`: list of phrases from the store page
2. Run `levi.fairplay.audit.audit_offer(offer)`. The audit is pure: the
   offer dict is read, never mutated.
3. Read the verdict: `predatory` (any sly finding), `risky` (caution
   only), or `honest` (clean).
4. For every finding, carry its `honest_alternative` forward.
   Detection without a way out is just a lecture — the alternative is
   the deliverable.
5. Re-audit on every offer change. A clean verdict describes the offer
   as declared, not the offer as shipped.

## Severity guide

- `sly`: the pattern is predatory as declared (opaque odds, expiring
  earned progress, revocable "purchases", paid power, vanishing
  inventory).
- `caution`: the letter is followed but the spirit is not (odds with no
  pity ceiling, a covenant with no concrete fallback, evasive language).
- `clean`: the declared design is honest. Keep it.
