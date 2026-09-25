"""Pages as drawing commands plus client-side cached assets: thin vector pages.

Studied from: dead-networks-20260916/report.md [Prodigy]

The studied shape: over dial-up, pages were not bitmaps — they were
streams of *drawing commands* plus assets (icons, tiles, glyphs) that
the client cached locally. First view paid the asset cost; every
later page referencing the same asset paid only a short cache key.
Flat-rate pricing meant the protocol optimized for bytes on the
wire, not billable time.

LEVI-native re-expression: a wire-efficient page protocol.
**Drawing commands** (``rect``, ``line``, ``text``, ``blit``) form a
**Page**; a client-side **AssetCache** stores blobs by content hash.
``Page.encode()`` serializes commands as compact text with assets
referenced by hash — the wire never carries a cached asset twice.
``Page.decode()`` rebuilds the command list; the renderer resolves
hashes against its own cache.

Operations:

* ``AssetCache.put(blob)`` → content hash; ``get(hash)``;
  ``stats()`` → hits/misses/bytes-saved
* ``Page.add_rect/line/text/blit(...)`` — append drawing commands
* ``Page.encode()`` — compact text; asset blobs referenced by hash
* ``Page.decode(payload, cache)`` — rebuild; missing assets listed
* ``wire_bytes(payload)`` — honest byte count of the encoded page

Honest limits: this is a *protocol* — encoding, caching, and byte
accounting are real, but there is no renderer here; ``blit`` with an
uncached hash decodes to a placeholder, not pixels. Byte counts are
for the encoded payload, not a real transport's framing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/thin-vector-pages"


def _hash(blob: bytes) -> str:
    return sha256(blob).hexdigest()[:16]


@dataclass
class AssetCache:
    """Client-side asset store keyed by content hash."""

    _store: Dict[str, bytes] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0
    bytes_saved: int = 0  # blob bytes NOT re-fetched thanks to hits

    def put(self, blob: bytes) -> str:
        h = _hash(blob)
        self._store.setdefault(h, blob)
        return h

    def get(self, h: str) -> Optional[bytes]:
        blob = self._store.get(h)
        if blob is None:
            self.misses += 1
            return None
        self.hits += 1
        self.bytes_saved += len(blob)
        return blob

    def has(self, h: str) -> bool:
        return h in self._store

    def stats(self) -> Dict[str, int]:
        return {
            "assets": len(self._store),
            "hits": self.hits,
            "misses": self.misses,
            "bytes_saved": self.bytes_saved,
        }


# Command tuple: (op, args...). blit args: (asset_hash, x, y, w, h).
Command = Tuple[str, ...]


@dataclass
class Page:
    """A page as drawing commands; assets travel by hash, not by blob."""

    commands: List[Command] = field(default_factory=list)
    title: str = ""

    def add_rect(self, x: int, y: int, w: int, h: int, fill: str) -> "Page":
        self.commands.append(("rect", str(x), str(y), str(w), str(h), fill))
        return self

    def add_line(self, x0: int, y0: int, x1: int, y1: int, color: str) -> "Page":
        self.commands.append(("line", str(x0), str(y0), str(x1), str(y1), color))
        return self

    def add_text(self, x: int, y: int, text: str, size: int = 12) -> "Page":
        safe = text.replace("\n", " ").replace("|", "/")
        self.commands.append(("text", str(x), str(y), safe, str(size)))
        return self

    def add_blit(
        self, asset: bytes, x: int, y: int, w: int, h: int, cache: AssetCache
    ) -> "Page":
        """Reference ``asset`` by hash, registering it in ``cache`` first."""
        h = cache.put(asset)
        self.commands.append(("blit", h, str(x), str(y), str(w), str(h)))
        return self

    def encode(self) -> str:
        """Compact text encoding: one command per line, ``|``-separated."""
        lines = [f"page|{self.title}"]
        for cmd in self.commands:
            lines.append("|".join(cmd))
        return "\n".join(lines) + "\n"

    @classmethod
    def decode(cls, payload: str, cache: AssetCache) -> Tuple["Page", List[str]]:
        """Rebuild the page; returns (page, missing_asset_hashes).

        Cached blobs are *not* re-transferred — only counted as hits.
        """
        lines = payload.splitlines()
        title = (
            lines[0].split("|", 1)[1] if lines and lines[0].startswith("page|") else ""
        )
        page = cls(title=title)
        missing: List[str] = []
        for line in lines[1:]:
            parts = line.split("|")
            op = parts[0]
            if op == "blit":
                h = parts[1]
                if not cache.has(h):
                    cache.misses += 1
                    if h not in missing:
                        missing.append(h)
                else:
                    cache.hits += 1
                    cache.bytes_saved += len(cache._store[h])
            page.commands.append(tuple(parts))
        return page, missing


def wire_bytes(payload: str) -> int:
    """Honest byte count of an encoded page on the wire (UTF-8)."""
    return len(payload.encode("utf-8"))
