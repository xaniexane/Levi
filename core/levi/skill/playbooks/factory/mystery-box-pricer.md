---
skill_id: factory.mystery_box_pricer
name: Mystery Box Pricer
description: Prices a mystery box's contents from listing drafts and suggests the profitable bundle split.
risk: info
permissions: []
requires_confirmation: false
tags: [factory, pricing, resale, mystery-box]
version: 1.0.0
---

# Mystery Box Pricer

Advisory only: reads listing drafts and emits pricing guidance. It never
lists anything for sale, never contacts buyers, spends nothing, touches no
accounts. All money math is labeled projection — never invented comps,
buyers, or revenue.

## How to price a box

1. List every item in the box with its estimated resale value (from the
   seller's own comps or stated estimates — never invented).
2. Sum the item estimates → box contents value.
3. Price the box at 60–75% of contents value (the mystery discount — the
   buyer gambles on contents; the seller keeps margin).
4. Floor check: price must cover sourcing cost + packaging + a stated
   minimum margin, or say plainly the box doesn't pencil out.

## Bundle-split suggestion

1. Sort items by estimated value, highest first.
2. Anchor items (highest value) go one per box; fillers distribute evenly.
3. Never put two anchor items in one box unless the price tier rises to
   match — the math must stay honest on every box.
4. Report per-box contents value, suggested price, and margin.

## Example

```
Contents value: $120 → price $72–$90 (60–75%)
Anchor: vintage figure ($40) | Fillers: 8 items ~$10 each
Sourcing cost: $35, packaging: $5 → margin at $80: $40
```

## Laws

- Projection math only: every number is estimated, cited, or labeled.
- Never invents sold comps, buyers, or revenue.
- Drafts only — nothing is ever listed or sold by this skill.
