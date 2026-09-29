---
skill_id: fairplay.write_honest_offer
name: Write an Honest Offer
description: Checklist for stating a game offer so plainly that the sly-trade detector finds nothing to flag.
category: fairplay
risk: info
permissions: []
requires_confirmation: false
tags: [fairplay, honest-design, checklist, blue-team]
version: 1.0.0
---

# Write an Honest Offer

An offer the sly-trade detector cannot flag is an offer stated
plainly. Work the checklist top to bottom; every unchecked line is a
finding waiting to happen.

## The checklist

1. **Odds on the tin.** Any paid random draw ships with a published,
   sum-validated odds card before the first draw is sold.
2. **Mercy in the contract.** The pity ceiling and the worst-case spend
   are declared where the player pays, not buried in support articles.
3. **Effort never evaporates.** Earned progress never expires. If a
   season ends, tiers pause — they do not vanish.
4. **Buy means buy.** If the player cannot keep it after you shut down,
   the button does not say BUY. Revocable licenses are labeled RENTAL.
5. **A covenant at the point of sale.** Every license ships with a
   machine-readable end-of-life covenant: offline mode, local server,
   or data export — named concretely, not "we may."
6. **Power is earned.** Gameplay power comes from play. The store sells
   cosmetics, convenience, and content — never advantage.
7. **Carry what you bought.** Inventory is exportable by the player:
   player-held, hash-chained, portable. Nothing lives only on your
   server with no way out.
8. **Plain words.** Name the mechanism: odds, grind, license. No
   "surprise mechanics," no "player choice," no fog.

## The test

Describe the finished offer as a dict of declared claims and run
`levi.fairplay.audit.audit_offer` over it. Verdict `honest` means the
checklist held. Anything else names the exact line to fix — fix the
offer, not the description of the offer.
