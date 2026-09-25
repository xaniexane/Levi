"""
Local-first Memory Store
File-backed JSONL + simple index. SQLite upgrade path later.
Never requires network. User can export / delete.
"""

from __future__ import annotations
import json
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from .types import MemoryEntry, MemoryType, new_entry


DEFAULT_DATA_DIR = Path.home() / ".levi" / "memory"


def _require_id(entry_id: str) -> str:
    """Validate a memory entry id (non-empty string)."""
    if not isinstance(entry_id, str) or not entry_id.strip():
        raise ValueError(
            "MemoryStore: entry_id must be a non-empty string, got %r" % (entry_id,)
        )
    return entry_id


def _require_importance(value: float) -> float:
    """Clamp importance into 0..1 (callers pass confidences; keep it safe)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError(
            "MemoryStore: importance must be a number, got %r" % (value,)
        ) from None
    return max(0.0, min(1.0, v))


def _require_tags(tags: Optional[List[str]]) -> List[str]:
    if tags is None:
        return []
    if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
        raise ValueError("MemoryStore: tags must be a list of strings")
    return list(tags)


class MemoryStore:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.data_dir / "index.json"
        self._entries: Dict[str, MemoryEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self._index_path.exists():
            return
        try:
            raw = json.loads(self._index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # Whole file unreadable: quarantine it and start fresh rather than
            # silently discarding the user's memories.
            self._quarantine_corrupt("unreadable: %s" % exc)
            return
        if not isinstance(raw, dict):
            self._quarantine_corrupt(
                "top level is %s, not an object" % type(raw).__name__
            )
            return
        entries = raw.get("entries", [])
        if not isinstance(entries, list):
            self._quarantine_corrupt(
                "entries is %s, not a list" % type(entries).__name__
            )
            return
        for lineno, item in enumerate(entries, 1):
            try:
                entry = MemoryEntry.from_dict(item)
            except Exception as exc:
                # Partial ingestion: skip the bad entry, keep the rest.
                print(
                    "memory: skipping corrupt entry #%d (%s)" % (lineno, exc),
                )
                continue
            self._entries[entry.id] = entry

    def _quarantine_corrupt(self, reason: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = self._index_path.with_name(f"index.corrupt-{ts}.json")
        try:
            shutil.move(str(self._index_path), str(backup))
            print(
                "memory: index.json is corrupt (%s); moved to %s and started fresh"
                % (reason, backup.name)
            )
        except OSError as exc:
            print(
                "memory: index.json is corrupt (%s); cannot back up: %s" % (reason, exc)
            )

    def _persist(self) -> None:
        payload = {
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "entries": [e.to_dict() for e in self._entries.values()],
        }
        tmp = self._index_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
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
        """Add an entry. Raises ValueError on invalid inputs.

        ``importance`` is clamped into 0..1; content must be a
        non-empty string; ``memory_type`` must be a MemoryType.
        """
        if not isinstance(memory_type, MemoryType):
            raise ValueError(
                "MemoryStore.add: memory_type must be a MemoryType, got %r"
                % (memory_type,)
            )
        if not isinstance(content, str) or not content.strip():
            raise ValueError("MemoryStore.add: content must be a non-empty string")
        if not isinstance(source, str) or not source.strip():
            raise ValueError("MemoryStore.add: source must be a non-empty string")
        tags = _require_tags(tags)
        importance = _require_importance(importance)
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("MemoryStore.add: metadata must be a dict or None")
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
        _require_id(entry_id)
        return self._entries.get(entry_id)

    def list(
        self,
        memory_type: Optional[MemoryType] = None,
        project_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[MemoryEntry]:
        if memory_type is not None and not isinstance(memory_type, MemoryType):
            raise ValueError(
                "MemoryStore.list: memory_type must be a MemoryType or None, got %r"
                % (memory_type,)
            )
        if not isinstance(limit, int) or limit < 1:
            raise ValueError(
                "MemoryStore.list: limit must be a positive int, got %r" % (limit,)
            )
        if tags is not None:
            tags = _require_tags(tags)
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
        if not isinstance(query, str):
            raise ValueError(
                "MemoryStore.search: query must be a string, got %s"
                % type(query).__name__
            )
        if not isinstance(limit, int) or limit < 1:
            raise ValueError(
                "MemoryStore.search: limit must be a positive int, got %r" % (limit,)
            )
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
        _require_id(entry_id)
        if entry_id in self._entries:
            del self._entries[entry_id]
            self._persist()
            return True
        return False

    def update(
        self,
        entry_id: str,
        *,
        content: str | None = None,
        importance: float | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Optional[MemoryEntry]:
        """Update an entry in place (used by growth corroboration).

        Returns the updated entry, or None when the id is unknown.
        Raises ValueError on an invalid entry_id or malformed new values.
        """
        _require_id(entry_id)
        entry = self._entries.get(entry_id)
        if entry is None:
            return None
        if content is not None:
            if not isinstance(content, str) or not content.strip():
                raise ValueError(
                    "MemoryStore.update: content must be a non-empty string"
                )
            entry.content = content
        if importance is not None:
            entry.importance = _require_importance(importance)
        if tags is not None:
            entry.tags = _require_tags(tags)
        if metadata is not None:
            if not isinstance(metadata, dict):
                raise ValueError("MemoryStore.update: metadata must be a dict")
            entry.metadata = dict(metadata)
        entry.updated_at = datetime.now(timezone.utc).isoformat()
        entry.version += 1
        self._persist()
        return entry

    def clear_type(self, memory_type: MemoryType) -> int:
        if not isinstance(memory_type, MemoryType):
            raise ValueError(
                "MemoryStore.clear_type: memory_type must be a MemoryType, got %r"
                % (memory_type,)
            )
        to_remove = [
            eid for eid, e in self._entries.items() if e.memory_type == memory_type
        ]
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
