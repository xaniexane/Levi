"""Document record for the honest-search index."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def doc_id_for(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


@dataclass
class Document:
    """One indexed page or file."""

    doc_id: str
    url: str
    title: str
    text: str
    outlinks: List[str] = field(default_factory=list)
    source: str = "crawl"  # "crawl" | "file"
    fetched_at: str = ""

    def __post_init__(self) -> None:
        if not self.fetched_at:
            self.fetched_at = now_iso()

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict) -> "Document":
        return cls(
            doc_id=str(raw["doc_id"]),
            url=str(raw["url"]),
            title=str(raw.get("title", "")),
            text=str(raw.get("text", "")),
            outlinks=list(raw.get("outlinks") or []),
            source=str(raw.get("source", "crawl")),
            fetched_at=str(raw.get("fetched_at", "")),
        )
