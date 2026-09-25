"""C10 builder ladder + local/delta split (WORKING TITLE: naming is Chauncey's).

A builder ladder (visitor → resident → builder → architect; rank is
earned, never granted) plus Habitat's split: heavy assets stay local
and content-addressed, only state deltas sync.

Plain rules:
- ``attempt_build()`` refuses builds above the builder's rank (T1).
- ``validate_addition()`` gates every addition on the world's schema
  and the safety rungs (``RungStub`` is deny-by-default on unknown
  ops) — rejection happens pre-apply (T2).
- ``sync_delta()`` ships ops only; assets are referenced by content
  hash and fetched lazily, only what the receiver renders (T3, T4).
- ``Spool`` queues deltas while the link is down and applies them in
  order when it returns (T5).
- All state serializes canonically; same delta sequence → same bytes
  (T6). Stdlib-only, zero network at runtime.
"""

from __future__ import annotations

from .ranks import (
    CAPABILITIES,
    RANK_THRESHOLDS,
    Builder,
    Rank,
    advance,
    demote,
    has_capability,
)
from .regions import (
    Delta,
    Region,
    RungStub,
    apply_delta,
    attempt_build,
    make_delta,
    new_region,
    payload_bytes,
    validate_addition,
)
from .sync import Spool, fetch_assets, receiver_apply

__all__ = [
    "Builder",
    "CAPABILITIES",
    "Delta",
    "RANK_THRESHOLDS",
    "Rank",
    "Region",
    "RungStub",
    "Spool",
    "advance",
    "apply_delta",
    "attempt_build",
    "demote",
    "fetch_assets",
    "has_capability",
    "make_delta",
    "new_region",
    "payload_bytes",
    "receiver_apply",
    "validate_addition",
]
