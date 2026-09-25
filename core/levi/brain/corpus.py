"""
Corpus — append-only knowledge body for LEVI.

Every unit is tagged: OBSERVED | INFERENCE | HYPOTHESIS | UNKNOWN
so archaeology and service work never launder guesses as facts.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime, timezone
import json
import uuid


DEFAULT = Path.home() / ".levi" / "corpus.jsonl"
KINDS = frozenset({"OBSERVED", "INFERENCE", "HYPOTHESIS", "UNKNOWN"})


@dataclass
class CorpusUnit:
    id: str
    kind: str
    text: str
    source: str = ""
    tags: List[str] = None  # type: ignore
    created_at: str = ""

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        self.kind = (self.kind or "UNKNOWN").upper()
        if self.kind not in KINDS:
            self.kind = "UNKNOWN"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Corpus:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DEFAULT
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(
        self,
        text: str,
        kind: str = "OBSERVED",
        source: str = "",
        tags: Optional[List[str]] = None,
    ) -> CorpusUnit:
        """Append one unit. Raises ValueError on empty text or bad tags."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Corpus.add: text must be a non-empty string")
        if not isinstance(source, str):
            raise ValueError("Corpus.add: source must be a string")
        if tags is not None and (
            not isinstance(tags, list) or any(not isinstance(t, str) for t in tags)
        ):
            raise ValueError("Corpus.add: tags must be a list of strings")
        u = CorpusUnit(
            id=str(uuid.uuid4())[:8],
            kind=kind,
            text=(text or "").strip(),
            source=source,
            tags=list(tags or []),
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(u.to_dict(), ensure_ascii=False) + "\n")
        return u

    def list(self, limit: int = 50, kind: Optional[str] = None) -> List[CorpusUnit]:
        if not isinstance(limit, int) or limit < 1:
            raise ValueError(
                "Corpus.list: limit must be a positive int, got %r" % (limit,)
            )
        if not self.path.exists():
            return []
        rows: List[CorpusUnit] = []
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    # Corrupt line: skip loudly, keep the rest (partial ingestion).
                    print("brain corpus: skipping corrupt line in %s" % self.path.name)
                    continue
                if not isinstance(d, dict):
                    print(
                        "brain corpus: skipping non-object line in %s" % self.path.name
                    )
                    continue
                try:
                    u = CorpusUnit(
                        id=d.get("id") or "",
                        kind=d.get("kind") or "UNKNOWN",
                        text=d.get("text") or "",
                        source=d.get("source") or "",
                        tags=list(d.get("tags") or []),
                        created_at=d.get("created_at") or "",
                    )
                    if kind and u.kind != kind.upper():
                        continue
                    rows.append(u)
                except Exception as exc:
                    print("brain corpus: skipping malformed row (%s)" % exc)
                    continue
        return rows[-limit:]

    def search(self, query: str, limit: int = 20) -> List[CorpusUnit]:
        if not isinstance(query, str):
            raise ValueError(
                "Corpus.search: query must be a string, got %s" % type(query).__name__
            )
        if not isinstance(limit, int) or limit < 1:
            raise ValueError(
                "Corpus.search: limit must be a positive int, got %r" % (limit,)
            )
        q = (query or "").lower()
        hits = [
            u
            for u in self.list(limit=500)
            if q in u.text.lower() or q in " ".join(u.tags).lower()
        ]
        return hits[-limit:]

    def format(self, limit: int = 20) -> str:
        if not isinstance(limit, int) or limit < 1:
            raise ValueError(
                "Corpus.format: limit must be a positive int, got %r" % (limit,)
            )
        units = list(reversed(self.list(limit)))
        if not units:
            return 'Corpus empty. Add with: levi brain corpus --add "…" --kind OBSERVED'
        lines = ["=== LEVI Corpus ===", ""]
        for u in units:
            lines.append(f"[{u.id}] {u.kind}  {u.text[:120]}")
            if u.source or u.tags:
                lines.append(f"     src={u.source or '—'}  tags={u.tags or []}")
        return "\n".join(lines)
