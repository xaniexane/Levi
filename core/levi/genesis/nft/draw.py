"""The randomized mint draw.

Every agent gets a form and an avatar — that is universal, never gated on
tokenization. But not every pack becomes an NFT: each year's mint is a
random draw of N packs from the eligible pool, where N is the year's
banked number (keeper's floor: 1,000 minimum).

Honesty rules for the draw:
- Deterministic from a committed seed: anyone re-running
  ``draw_mint`` with the banked seed and the banked eligible list gets
  the identical draw. The draw cannot be quietly re-rolled.
- The seed is banked on the series ledger BEFORE the draw is run, so the
  seed cannot be picked to favor a pack.
- Draw order is the mint order; the receipt records it.
"""
from __future__ import annotations

import random
from typing import List, Sequence


class DrawError(Exception):
    pass


def draw_mint(
    eligible_pack_ids: Sequence[str],
    n: int,
    *,
    seed: str,
) -> List[str]:
    """Draw ``n`` pack ids from ``eligible_pack_ids`` using ``seed``.

    Deterministic: same inputs, same draw, every time. Raises
    :class:`DrawError` on empty seed, empty pool, ``n < 1``, ``n`` above
    the pool size, or duplicate pack ids in the pool.
    """
    if not (seed or "").strip():
        raise DrawError("draw seed is required and must be banked before the draw")
    pool = list(eligible_pack_ids)
    if not pool:
        raise DrawError("eligible pool is empty")
    if len(set(pool)) != len(pool):
        raise DrawError("eligible pool contains duplicate pack ids")
    if n < 1:
        raise DrawError("draw n must be at least 1")
    if n > len(pool):
        raise DrawError("draw n exceeds the eligible pool")
    rng = random.Random(seed)
    return rng.sample(pool, n)


def verify_draw(
    eligible_pack_ids: Sequence[str],
    n: int,
    *,
    seed: str,
    drawn: Sequence[str],
) -> bool:
    """True iff ``drawn`` is exactly what ``draw_mint`` produces."""
    try:
        return draw_mint(eligible_pack_ids, n, seed=seed) == list(drawn)
    except DrawError:
        return False


def draw_mint_with_reserve(
    eligible_pack_ids: Sequence[str],
    n: int,
    *,
    seed: str,
    reserve_pack_id: str,
) -> dict:
    """The keeper's copy comes out of N, not on top of it.

    ``reserve_pack_id`` is the keeper's named pick — banked openly on the
    series ledger, pulled from the pool BEFORE the random draw. The draw
    then fills the remaining ``n - 1`` from the rest, so the total minted
    is still exactly ``n`` and the published cap is never breached.
    Returns ``{"reserve": ..., "drawn": [...]}``.
    """
    reserve = (reserve_pack_id or "").strip()
    if not reserve:
        raise DrawError("reserve pack id is required — the keeper names his copy openly")
    pool = list(eligible_pack_ids)
    if not pool:
        raise DrawError("eligible pool is empty")
    if len(set(pool)) != len(pool):
        raise DrawError("eligible pool contains duplicate pack ids")
    if reserve not in pool:
        raise DrawError("reserve pack is not in the eligible pool")
    if n < 1:
        raise DrawError("draw n must be at least 1")
    if n > len(pool):
        raise DrawError("draw n exceeds the eligible pool")
    remaining = [p for p in pool if p != reserve]
    rng = random.Random(seed)
    return {"reserve": reserve, "drawn": rng.sample(remaining, n - 1)}


def verify_draw_with_reserve(
    eligible_pack_ids: Sequence[str],
    n: int,
    *,
    seed: str,
    reserve_pack_id: str,
    drawn: Sequence[str],
) -> bool:
    """True iff the reserve + draw match ``draw_mint_with_reserve``."""
    try:
        expect = draw_mint_with_reserve(
            eligible_pack_ids, n, seed=seed, reserve_pack_id=reserve_pack_id
        )
    except DrawError:
        return False
    return expect["drawn"] == list(drawn)
