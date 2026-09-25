"""Cybrus evidence ledger — findings require evidence before validation.

Append-only, digest-chained ledger of evidence records. Each record carries
a sha256 digest over (kind, source, timestamp, content, previous digest),
so tampering with history breaks the chain. Concept adapted from the
recovered security-fabric lineage; original implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Dict, List, Optional


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EvidenceRecord:
    kind: str
    source: str
    content: str
    timestamp: str = field(default_factory=_utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    prev_digest: str = "genesis"
    sealed_digest: str = ""

    @property
    def digest(self) -> str:
        raw = "|".join(
            (self.kind, self.source, self.timestamp, self.content, self.prev_digest)
        )
        return sha256(raw.encode("utf-8")).hexdigest()

    def seal(self) -> str:
        """Freeze the digest at creation; tampering breaks verification."""
        self.sealed_digest = self.digest
        return self.sealed_digest

    def to_dict(self) -> Dict[str, Any]:
        d = dict(self.__dict__)
        d["digest"] = self.digest
        return d


class EvidenceLedger:
    def __init__(self) -> None:
        self.records: List[EvidenceRecord] = []

    def append(self, kind: str, source: str, content: str, **metadata: Any) -> str:
        prev = self.records[-1].digest if self.records else "genesis"
        rec = EvidenceRecord(
            kind=kind,
            source=source,
            content=content,
            metadata=dict(metadata),
            prev_digest=prev,
        )
        self.records.append(rec)
        return rec.seal()

    def verify_chain(self) -> bool:
        """True when every record is untampered and links to its predecessor."""
        prev = "genesis"
        for rec in self.records:
            if not rec.sealed_digest or rec.digest != rec.sealed_digest:
                return False
            if rec.prev_digest != prev:
                return False
            prev = rec.digest
        return True

    def find(
        self, kind: Optional[str] = None, source: Optional[str] = None
    ) -> List[EvidenceRecord]:
        return [
            r
            for r in self.records
            if (kind is None or r.kind == kind)
            and (source is None or r.source == source)
        ]

    def __len__(self) -> int:
        return len(self.records)
