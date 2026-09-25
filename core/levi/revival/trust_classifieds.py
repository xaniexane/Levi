"""Trust-graph classifieds — local listings with mutual-connection signals.

Studied from: giant-patterns-hunt-20260916-0016/report.md [Additions 20].

The mechanism under study: classified listings where trust comes from the
user's own connection graph — mutual connections between viewer and
seller — rather than from a platform reputation score or an ad layer.
Listings are portable (plain data, exportable as JSON-ready dicts) and
federation-friendly (merge another board's listings + connections without
a central authority). There is deliberately no ad layer: no promoted
slots, no skimming, no pay-to-rank.

Trust scoring is a transparent heuristic, stated plainly:
- direct connection to the seller: strong signal;
- shared mutual connections: counted and listed;
- graph distance beyond two hops: no signal (reported as "unknown").
Scores are for ordering a local feed only; they are not a global rating.

Public surface:
- ``Board``: add_listing / remove_listing / add_connection /
  trust(viewer, seller) / feed(viewer) / export / merge.

stdlib-only. No network. Connections are undirected and local.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

ORIGIN = "levi-revival/trust-classifieds"


class ClassifiedsError(ValueError):
    """Raised when a classifieds operation is invalid."""


@dataclass
class Listing:
    listing_id: str
    title: str
    description: str = ""
    category: str = "misc"
    price: Optional[float] = None
    seller: str = ""
    created_at: float = 0.0


@dataclass
class TrustSignal:
    seller: str
    score: float  # 0.0 .. 1.0, heuristic
    direct: bool
    mutuals: List[str]
    hops: Optional[int]  # None when unconnected

    def explain(self) -> str:
        if self.direct:
            return f"{self.seller} is a direct connection"
        if self.mutuals:
            names = ", ".join(self.mutuals[:3])
            more = f" +{len(self.mutuals) - 3}" if len(self.mutuals) > 3 else ""
            return f"{len(self.mutuals)} mutual connection(s): {names}{more}"
        if self.hops is not None:
            return f"{self.hops} hop(s) away, no mutual connections"
        return "no connection path — unknown"


class Board:
    """A local classifieds board over the user's own trust graph."""

    def __init__(self, name: str = "board") -> None:
        self.name = name
        self._listings: Dict[str, Listing] = {}
        self._graph: Dict[str, Set[str]] = {}
        self._seq = 0

    # ---- listings ---------------------------------------------------
    def add_listing(
        self,
        title: str,
        seller: str,
        description: str = "",
        category: str = "misc",
        price: Optional[float] = None,
        created_at: float = 0.0,
    ) -> Listing:
        if not title or not seller:
            raise ClassifiedsError("title and seller must not be empty")
        if price is not None and price < 0:
            raise ClassifiedsError("price must not be negative")
        self._seq += 1
        listing = Listing(
            f"listing-{self._seq}",
            title,
            description,
            category,
            price,
            seller,
            created_at,
        )
        self._listings[listing.listing_id] = listing
        self._graph.setdefault(seller, set())
        return listing

    def remove_listing(self, listing_id: str) -> bool:
        return self._listings.pop(listing_id, None) is not None

    def get_listing(self, listing_id: str) -> Listing:
        try:
            return self._listings[listing_id]
        except KeyError:
            raise ClassifiedsError(f"no listing {listing_id!r}") from None

    def search(self, query: str = "", category: str = "") -> List[Listing]:
        q = query.lower()
        results = []
        for listing in self._listings.values():
            if category and listing.category != category:
                continue
            if q and q not in (listing.title + " " + listing.description).lower():
                continue
            results.append(listing)
        return results

    # ---- trust graph --------------------------------------------------
    def add_connection(self, a: str, b: str) -> None:
        if not a or not b:
            raise ClassifiedsError("connection names must not be empty")
        if a == b:
            raise ClassifiedsError("cannot connect a person to themselves")
        self._graph.setdefault(a, set()).add(b)
        self._graph.setdefault(b, set()).add(a)

    def remove_connection(self, a: str, b: str) -> bool:
        removed = False
        for x, y in ((a, b), (b, a)):
            if x in self._graph and y in self._graph[x]:
                self._graph[x].remove(y)
                removed = True
        return removed

    def _hops(self, viewer: str, seller: str) -> Optional[int]:
        if viewer == seller:
            return 0
        seen = {viewer}
        queue = deque([(viewer, 0)])
        while queue:
            node, dist = queue.popleft()
            for nxt in self._graph.get(node, ()):
                if nxt == seller:
                    return dist + 1
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, dist + 1))
        return None

    def trust(self, viewer: str, seller: str) -> TrustSignal:
        """Transparent heuristic trust signal between viewer and seller."""
        direct = seller in self._graph.get(viewer, set())
        viewer_friends = self._graph.get(viewer, set())
        seller_friends = self._graph.get(seller, set())
        mutuals = sorted(viewer_friends & seller_friends - {viewer, seller})
        hops = self._hops(viewer, seller)
        if direct:
            score = 0.9
        elif mutuals:
            score = min(0.8, 0.3 + 0.1 * len(mutuals))
        elif hops == 2:
            score = 0.2
        else:
            score = 0.0
        return TrustSignal(seller, score, direct, mutuals, hops)

    def feed(
        self, viewer: str, category: str = ""
    ) -> List[Tuple[Listing, TrustSignal]]:
        """Listings ordered by trust for this viewer, then newest first.

        No promoted slots: ordering is trust score, then recency. The
        viewer's own listings sort to the top (direct self-trust).
        """
        scored = []
        for listing in self.search(category=category):
            signal = self.trust(viewer, listing.seller)
            if viewer == listing.seller:
                signal = TrustSignal(listing.seller, 1.0, True, [], 0)
            scored.append((listing, signal))
        scored.sort(key=lambda pair: (pair[1].score, pair[0].created_at), reverse=True)
        return scored

    # ---- portability ----------------------------------------------------
    def export(self) -> Dict:
        return {
            "name": self.name,
            "listings": [vars(item) for item in self._listings.values()],
            "connections": sorted(
                (a, b) for a, friends in self._graph.items() for b in friends if a < b
            ),
        }

    def merge(self, data: Dict) -> Tuple[int, int]:
        """Fold another board's export into this one. Returns
        (listings_added, connections_added). Listing ids are re-minted."""
        added_l, added_c = 0, 0
        for ldata in data.get("listings", []):
            listing = self.add_listing(
                ldata["title"],
                ldata["seller"],
                ldata.get("description", ""),
                ldata.get("category", "misc"),
                ldata.get("price"),
                ldata.get("created_at", 0.0),
            )
            added_l += 1
            _ = listing
        for a, b in data.get("connections", []):
            before = len(self._graph.get(a, ())) + len(self._graph.get(b, ()))
            self.add_connection(a, b)
            after = len(self._graph.get(a, ())) + len(self._graph.get(b, ()))
            if after > before:
                added_c += 1
        return added_l, added_c

    def to_json(self) -> str:
        return json.dumps(self.export(), indent=2)
