---
skill_id: fairplay.pattern_catalog
name: Sly-Trade Pattern Catalog
description: The seven predatory offer patterns from the 2010-2024 record, each with its tell and its honest alternative.
category: fairplay
risk: info
permissions: []
requires_confirmation: false
tags: [fairplay, catalog, honest-design, blue-team]
version: 1.0.0
---

# Sly-Trade Pattern Catalog

From the 2010-2024 record (archived `predators-hunt-20260928-evening`).
Each pattern names the tell and the honest alternative. Detection is
defensive: name the pattern to refuse it or invert it, never to build it.

## The seven patterns

1. **opaque-odds** (sly) — paid random draws with no published odds.
   The loot box as it shipped 2010-2017. *Alternative:* publish a
   sum-validated odds card before the first draw.

2. **no-worst-case** (caution) — odds published, but no pity ceiling and
   no declared worst-case spend. Complying with the letter while the
   mercy rule stays hidden. *Alternative:* declare the pity ceiling in
   the contract and print the worst-case draws-to-tier on the tin.

3. **time-fenced-grind** (sly) — every reward visible, but the buy is
   really "a $10 promise to play as much as possible for the length of
   a season"; unearned tiers evaporate forever. *Alternative:* earned
   tiers never expire and pause across seasons.

4. **revocable-license** (sly) — the storefront says BUY, the EULA says
   LICENSE, the license is revocable. The Crew kill, March 2024.
   *Alternative:* publish a machine-readable end-of-life covenant at the
   point of sale (offline mode / local server / data export); label
   revocable licenses RENTAL.

5. **pay-to-win** (sly) — gameplay power gated behind paying.
   *Alternative:* sell cosmetics only; power is earned by play.

6. **vanishing-inventory** (sly) — acquired items live only on the
   seller's server with no export; the Stadia January 2023 shape.
   *Alternative:* player-held, hash-chained, portable ownership ledger.

7. **euphemism** (caution) — the language of evasion: "surprise
   mechanics" and friends. *Alternative:* name the mechanism plainly —
   odds, grind, license.

## Reading the catalog

The catalog is documentation over `levi.fairplay.audit.audit_offer`,
which is the executable source of truth. If the catalog and the
detector ever disagree, the detector wins and the catalog gets fixed.
