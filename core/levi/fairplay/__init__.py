"""fairplay: honest games for a local-first machine.

The games industry's dominant trade is predation with a toy on top:
loot boxes with hidden odds (Belgium, 2018), battle passes that delete
your grind on a season clock, libraries of "bought" games that vanish
when the server dies (Stadia, Jan 2023), and endgames where power is
gated behind a fortune (Diablo Immortal, 2022).

fairplay inverts each trade into structure, never into a competing
storefront:

- ``honestdraw``: a transparent, seeded, auditable draw engine. The
  machine shows its math: published odds, hard pity ceiling, replayable
  log. No till, no funnel.
- ``ownedtrack``: a progression track that never expires. Swap freely,
  pause forever, cosmetics only. The Halo Infinite rule: once it's
  yours, the clock cannot take it.
- ``library``: an ownership ledger for games. Hash-chained receipts,
  exportable saves with checksums, no revocation primitive at all.
  The Stadia law: a bought game must survive its seller.

PACKAGE LAW (enforced by tests, not prose): no module in fairplay
accepts, stores, references, or simulates currency, till, or trade.
The honest game has no checkout.
"""

from __future__ import annotations

from levi.fairplay import honestdraw, library, ownedtrack

__all__ = ["honestdraw", "ownedtrack", "library"]
