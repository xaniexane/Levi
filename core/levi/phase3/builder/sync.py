"""Sync machinery: lazy asset fetch and the offline spool.

Assets are content-addressed and local. A delta references them by
hash; the receiver fetches ONLY the assets it will render — unrendered
assets never cross. ``Spool`` holds deltas while the link is down and
applies them in FIFO order when the link returns.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Set

from .regions import Delta, Region, apply_delta

__all__ = ["Spool", "fetch_assets", "receiver_apply"]


def fetch_assets(
    delta: Delta,
    assets_to_render: Set[str],
    local_store: Dict[str, str],
    crossed: Optional[List[str]] = None,
) -> Dict[str, str]:
    """Fetch only the assets the receiver will render.

    ``local_store`` maps content hash -> bytes (the local asset pool).
    Returns asset_id -> bytes for rendered assets present locally;
    records every hash that "crossed" into ``crossed`` for accounting.
    """
    fetched: Dict[str, str] = {}
    for op in delta.ops:
        for asset_id, content_hash in op.get("asset_refs", {}).items():
            if asset_id not in assets_to_render:
                continue
            if crossed is not None:
                crossed.append(content_hash)
            if content_hash in local_store:
                fetched[asset_id] = local_store[content_hash]
    return fetched


def receiver_apply(region: Region, delta: Delta, expected_base: int) -> None:
    """Receiver-side apply: base_version must match the receiver's version."""
    if delta.base_version != expected_base:
        raise ValueError("receiver base mismatch")
    apply_delta(region, delta)


@dataclass
class Spool:
    """Graded-spool stand-in: FIFO delta queue with a link flag.

    Offline-first: ``enqueue()`` while the link is down stores deltas;
    ``flush()`` applies them in order once the link returns.
    """

    queue: Deque[Delta] = field(default_factory=deque)
    link_up: bool = True
    applied: List[int] = field(default_factory=list)  # base_versions applied, in order

    def enqueue(self, delta: Delta) -> None:
        self.queue.append(delta)

    def flush(self, region: Region) -> int:
        """Apply queued deltas in order; requires the link. Returns count."""
        if not self.link_up:
            return 0
        count = 0
        while self.queue:
            delta = self.queue.popleft()
            apply_delta(region, delta)
            self.applied.append(delta.base_version)
            count += 1
        return count
