"""
Local-first Memory Store
File-backed JSONL + simple index. SQLite upgrade path later.
Never requires network. User can export / delete.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from .types import MemoryEntry, MemoryType, new_entry


DEFAULT_DATA_DIR = Path.home() / ".levi" / "memory"


class MemoryStore:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.data_dir / "index.json"
        self._entries: Dict[str, MemoryEntry] = {}
        self._load()

    def _load(self) -> None:
        if self._index_path.exists():
            try:
                raw = json.loads(self._index_path.read_text(encoding="utf-8"))
                for item in raw.get("entries", []):
                    entry = MemoryEntry.from_dict(item)
                    self._entries[entry.id] = entry
            except Exception:
                self._entries = {}

    def _persist(self) -> None:
        payload = {
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "entries": [e.to_dict() for e in self._entries.values()],
        }
        tmp = self._index_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._index_path)

    def add(
        self,
        memory_type: MemoryType,
        content: str,
        importance: float = 0.5,
        source: str = "user",
        tags: Optional[List[str]] = None,
        project_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryEntry:
        entry = new_entry(
            memory_type=memory_type,
            content=content,
            importance=importance,
            source=source,
            tags=tags,
            project_id=project_id,
            metadata=metadata,
        )
        self._entries[entry.id] = entry
        self._persist()
        return entry

    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        return self._entries.get(entry_id)

    def list(
        self,
        memory_type: Optional[MemoryType] = None,
        project_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[MemoryEntry]:
        results = list(self._entries.values())
        if memory_type:
            results = [e for e in results if e.memory_type == memory_type]
        if project_id:
            results = [e for e in results if e.project_id == project_id]
        if tags:
            tagset = set(tags)
            results = [e for e in results if tagset.intersection(e.tags)]
        results.sort(key=lambda e: (e.importance, e.updated_at), reverse=True)
        return results[:limit]

    def search(self, query: str, limit: int = 20) -> List[MemoryEntry]:
        """Simple keyword search. Vector search comes later."""
        q = query.lower().strip()
        if not q:
            return []
        scored = []
        for e in self._entries.values():
            text = (e.content + " " + " ".join(e.tags)).lower()
            if q in text:
                score = e.importance + (0.3 if q in e.content.lower() else 0.0)
                scored.append((score, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    def delete(self, entry_id: str) -> bool:
        if entry_id in self._entries:
            del self._entries[entry_id]
            self._persist()
            return True
        return False

    def clear_type(self, memory_type: MemoryType) -> int:
        to_remove = [eid for eid, e in self._entries.items() if e.memory_type == memory_type]
        for eid in to_remove:
            del self._entries[eid]
        if to_remove:
            self._persist()
        return len(to_remove)

    def stats(self) -> Dict[str, Any]:
        counts: Dict[str, int] = {}
        for e in self._entries.values():
            counts[e.memory_type.value] = counts.get(e.memory_type.value, 0) + 1
        return {
            "total": len(self._entries),
            "by_type": counts,
            "data_dir": str(self.data_dir),
        }
