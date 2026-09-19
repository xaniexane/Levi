"""DemandPulse feed — SI-native core (authoritative).

The feed engine IS the SI counterpart: pure, local, stdlib-only LEVI work.
This package is the native-core marker — it re-exports the authoritative
feed API from :mod:`levi.demand.feed` so conventional tooling and the AI
counterpart bridge have exactly one source of truth to depend on.

One-way rule: this package NEVER imports ``levi.demand.ai``. The bridge
(``levi.demand.ai``) imports us; nothing flows the other direction.
"""

from levi.demand.feed import (
    Digest,
    SOURCE_TAG,
    coerce_candidates,
    curate,
    digests_dir,
    levi_home,
    list_digest_ids,
    load_digest,
    load_latest,
    published_ids,
    render_digest,
    store_digest,
    watch_item,
    watchlist_path,
    watched_ids,
)

# Native-core marker: the SI counterpart is authoritative and self-contained.
__si_core__ = True

__all__ = [
    "Digest",
    "SOURCE_TAG",
    "__si_core__",
    "coerce_candidates",
    "curate",
    "digests_dir",
    "levi_home",
    "list_digest_ids",
    "load_digest",
    "load_latest",
    "published_ids",
    "render_digest",
    "store_digest",
    "watch_item",
    "watchlist_path",
    "watched_ids",
]
