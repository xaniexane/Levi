"""LEVI's creed — persistent laws, swappable tone masks, promotion rule.

The creed is the immutable spine under every tone LEVI can wear:

* :mod:`levi.creed.laws` — LEVI's binding laws, written in LEVI's own
  words. Immutable through every API this package exposes.
* :mod:`levi.creed.masks` — swappable tone masks (steady, drill,
  architect, mirror, terse, candid). A mask changes ONLY tone/voice
  guidance; it can never alter the laws.
* :mod:`levi.creed.promotion` — the promotion rule: a candidate fact
  enters the persistent creed block only after 3 recorded
  reinforcements, or one explicit ``promote()``.

Facts live in :class:`~levi.memory.store.MemoryStore` with a ``creed``
tag. Growth corroboration notifies the promotion tracker through an
adapter hook (see :mod:`levi.growth.consolidate`), never by rewriting
the growth pipeline.

Origin: LEVI-native rebuild of the *mechanism* behind persistent-law /
tone-mask / promotion-rule systems (seen as a labeled reference only).
All wording, law names, and mask names are original to LEVI.
"""

from __future__ import annotations

from levi.creed.laws import LAWS, Law, get_laws, laws_block, laws_digest
from levi.creed.masks import (
    DEFAULT_MASK,
    Mask,
    MaskManager,
    get_mask,
    list_masks,
    set_mask,
    system_prompt,
)
from levi.creed.promotion import (
    PROMOTED,
    PROMOTION_THRESHOLD,
    PROVISIONAL,
    PromotionTracker,
    consolidation_corroboration_hook,
    fact_status,
)

__all__ = [
    "LAWS",
    "DEFAULT_MASK",
    "PROMOTED",
    "PROMOTION_THRESHOLD",
    "PROVISIONAL",
    "Law",
    "Mask",
    "MaskManager",
    "PromotionTracker",
    "consolidation_corroboration_hook",
    "fact_status",
    "get_laws",
    "get_mask",
    "laws_block",
    "laws_digest",
    "list_masks",
    "set_mask",
    "system_prompt",
]
