"""Gateway-intermediary architecture: the transcoding proxy.

Studied from: dead-networks-20260916 (WAP section of report.md).
WAP put a gateway between the constrained handset and the web server:
the gateway translated and shrank web content at the edge so a weak
device could consume it. The shape is a *transcoding proxy*: content
arrives in rich form, a device profile describes what the client can
handle, and a pipeline of adapters rewrites the content down to fit.

This module implements that shape without any network I/O. The gateway
receives a content item plus a device profile (given by the caller, who
fetched the content), runs registered transformers over it, and records
exactly what was adapted. Heuristics are labelled as such; the gateway
never invents content, only reduces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

__all__ = [
    "DeviceProfile",
    "ContentItem",
    "Adaptation",
    "TranscodingGateway",
    "strip_markup",
    "truncate_text",
    "downscale_media",
]

ORIGIN = "levi-revival/wap"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeviceProfile:
    """What the constrained client can handle."""

    name: str
    max_payload_bytes: int
    text_only: bool = False  # cannot render rich media; strip images/video
    max_image_width: int = 0  # 0 = no images at all
    prefers: tuple[str, ...] = ()  # preferred media types, best first


@dataclass
class ContentItem:
    """One unit of content to adapt. ``kind`` is a media type like
    "text/html", "text/plain", "image/png", "video/mp4"."""

    kind: str
    payload: bytes
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Adaptation:
    """One transformation applied during gatewaying: what changed and why."""

    transformer: str
    before_bytes: int
    after_bytes: int
    note: str


# ---------------------------------------------------------------------------
# Built-in transformers (heuristics, labelled as such)
# ---------------------------------------------------------------------------


def strip_markup(
    item: ContentItem, profile: DeviceProfile
) -> tuple[ContentItem, Adaptation]:
    """Heuristic: drop HTML-ish tags, leaving visible text for text-only clients."""
    if not item.kind.startswith("text/") or not profile.text_only:
        return item, Adaptation(
            "strip_markup", len(item.payload), len(item.payload), "not applicable"
        )
    text = item.payload.decode("utf-8", errors="replace")
    out_chars: list[str] = []
    in_tag = False
    for ch in text:
        if ch == "<":
            in_tag = True
        elif ch == ">":
            in_tag = False
        elif not in_tag:
            out_chars.append(ch)
    stripped = " ".join("".join(out_chars).split()).encode("utf-8")
    before = len(item.payload)
    return (
        ContentItem(kind="text/plain", payload=stripped, meta=dict(item.meta)),
        Adaptation(
            "strip_markup", before, len(stripped), "tags removed; plain text kept"
        ),
    )


def truncate_text(
    item: ContentItem, profile: DeviceProfile
) -> tuple[ContentItem, Adaptation]:
    """Cut text payloads to the client's byte budget, marking truncation."""
    if not item.kind.startswith("text/"):
        return item, Adaptation(
            "truncate_text", len(item.payload), len(item.payload), "not applicable"
        )
    before = len(item.payload)
    if before <= profile.max_payload_bytes:
        return item, Adaptation("truncate_text", before, before, "within budget")
    budget = profile.max_payload_bytes
    marker = b" [...]"
    kept = item.payload[: max(0, budget - len(marker))] + marker
    return (
        ContentItem(
            kind=item.kind, payload=kept, meta={**item.meta, "truncated": True}
        ),
        Adaptation("truncate_text", before, len(kept), "cut to byte budget"),
    )


def downscale_media(
    item: ContentItem, profile: DeviceProfile
) -> tuple[ContentItem, Adaptation]:
    """Heuristic: shrink oversized media to the client's limits.

    Without a real codec this is metadata-driven: the gateway records the
    target dimensions and scales the payload proportionally to the area
    ratio — a stand-in for true transcoding, labelled as such in the note.
    """
    if not (item.kind.startswith("image/") or item.kind.startswith("video/")):
        return item, Adaptation(
            "downscale_media", len(item.payload), len(item.payload), "not applicable"
        )
    width = int(item.meta.get("width", 0))
    height = int(item.meta.get("height", 0))
    before = len(item.payload)
    limit = profile.max_image_width
    if width <= 0 or height <= 0 or limit <= 0 or width <= limit:
        if (
            limit <= 0
            and item.kind.startswith(("image/", "video/"))
            and profile.text_only
        ):
            return (
                ContentItem(
                    kind="text/plain", payload=b"[media removed]", meta=dict(item.meta)
                ),
                Adaptation(
                    "downscale_media",
                    before,
                    15,
                    "text-only client: media replaced with placeholder",
                ),
            )
        return item, Adaptation("downscale_media", before, before, "within limits")
    scale = limit / width
    new_payload = item.payload[: max(1, int(before * scale * scale))]
    new_meta = {
        **item.meta,
        "width": limit,
        "height": int(height * scale),
        "downscaled": True,
    }
    return (
        ContentItem(kind=item.kind, payload=new_payload, meta=new_meta),
        Adaptation(
            "downscale_media",
            before,
            len(new_payload),
            "heuristic proportional shrink (no real codec); dimensions recorded in meta",
        ),
    )


# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------

Transformer = Callable[[ContentItem, DeviceProfile], "tuple[ContentItem, Adaptation]"]


class TranscodingGateway:
    """Adapts content items to device profiles through a transformer pipeline."""

    def __init__(self) -> None:
        self._transformers: list[tuple[str, Transformer]] = []
        self.register("strip_markup", strip_markup)
        self.register("downscale_media", downscale_media)
        self.register("truncate_text", truncate_text)

    def register(self, name: str, transformer: Transformer) -> None:
        """Add a transformer to the end of the pipeline."""
        if not name:
            raise ValueError("transformer name must be non-empty")
        if not callable(transformer):
            raise ValueError("transformer must be callable")
        self._transformers.append((name, transformer))

    def adapt(
        self, item: ContentItem, profile: DeviceProfile
    ) -> tuple[ContentItem, list[Adaptation]]:
        """Run the pipeline over ``item`` for ``profile``.

        Returns the adapted item and one Adaptation record per transformer,
        in order — the caller can audit exactly what the edge changed.
        """
        adaptations: list[Adaptation] = []
        current = item
        for _name, transformer in self._transformers:
            current, record = transformer(current, profile)
            adaptations.append(record)
        return current, adaptations
