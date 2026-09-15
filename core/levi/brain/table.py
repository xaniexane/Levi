"""
Indexed brain table — spreadsheet-like second brain (local JSON).

Columns: id | domain | key | value | source | tags | updated_at
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime, timezone
import json
import uuid


DEFAULT = Path.home() / ".levi" / "brain_table.json"


@dataclass
class BrainRow:
    id: str
    domain: str
    key: str
    value: str
    source: str = ""
    tags: List[str] = None  # type: ignore
    updated_at: str = ""

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if not self.updated_at:
            self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BrainTable:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DEFAULT
        self.rows: Dict[str, BrainRow] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for d in raw.get("rows") or []:
                r = BrainRow(
                    id=d.get("id") or str(uuid.uuid4())[:8],
                    domain=d.get("domain") or "general",
                    key=d.get("key") or "",
                    value=d.get("value") or "",
                    source=d.get("source") or "",
                    tags=list(d.get("tags") or []),
                    updated_at=d.get("updated_at") or "",
                )
                self.rows[r.id] = r
        except Exception:
            self.rows = {}

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "rows": [r.to_dict() for r in self.rows.values()],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def upsert(
        self,
        domain: str,
        key: str,
        value: str,
        source: str = "",
        tags: Optional[List[str]] = None,
    ) -> BrainRow:
        # update existing same domain+key
        for r in self.rows.values():
            if r.domain == domain and r.key == key:
                r.value = value
                r.source = source or r.source
                r.tags = list(tags or r.tags)
                r.updated_at = datetime.now(timezone.utc).isoformat()
                self._persist()
                return r
        r = BrainRow(
            id=str(uuid.uuid4())[:8],
            domain=domain,
            key=key,
            value=value,
            source=source,
            tags=list(tags or []),
        )
        self.rows[r.id] = r
        self._persist()
        return r

    def search(self, query: str = "", domain: Optional[str] = None) -> List[BrainRow]:
        q = (query or "").lower()
        out = []
        for r in self.rows.values():
            if domain and r.domain != domain:
                continue
            blob = f"{r.key} {r.value} {' '.join(r.tags)}".lower()
            if not q or q in blob:
                out.append(r)
        return sorted(out, key=lambda x: x.updated_at, reverse=True)

    def format(
        self, query: str = "", domain: Optional[str] = None, limit: int = 30
    ) -> str:
        rows = self.search(query, domain)[:limit]
        if not rows:
            return "Brain table empty. Set: levi brain set --domain x --key y --value z"
        lines = ["=== LEVI Indexed Brain (table) ===", ""]
        lines.append(f"{'domain':12} {'key':20} value")
        lines.append("-" * 60)
        for r in rows:
            lines.append(f"{r.domain[:12]:12} {r.key[:20]:20} {r.value[:40]}")
        return "\n".join(lines)
