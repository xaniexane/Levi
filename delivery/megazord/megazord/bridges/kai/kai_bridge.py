"""
Kai Bridge — logic runtime, persistent memory, cross-orchestration.
Kai is Levi's second brain: stores memories, resolves context,
and coordinates between personas.
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from ..levi_bridge import LeviBridge
import uuid, time, json

@dataclass
class MemoryEntry:
    id:       str
    key:      str
    value:    Any
    tags:     List[str] = field(default_factory=list)
    ts:       float = field(default_factory=time.time)
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def touch(self):
        self.access_count += 1

class MemoryStore:
    """In-memory, tag-indexed storage. Drop-in for Redis/vector store in production."""

    def __init__(self):
        self._entries: Dict[str, MemoryEntry] = {}
        self._tags: Dict[str, set] = {}   # tag → entry IDs

    def store(self, key: str, value: Any, tags: Optional[List[str]] = None) -> MemoryEntry:
        e = MemoryEntry(id=str(uuid.uuid4())[:12], key=key, value=value, tags=tags or [])
        self._entries[e.id] = e
        for tag in e.tags:
            self._tags.setdefault(tag, set()).add(e.id)
        return e

    def retrieve(self, key_or_id: str) -> Optional[Any]:
        for e in self._entries.values():
            if e.key == key_or_id or e.id == key_or_id:
                e.touch()
                return e.value
        return None

    def search_tags(self, tags: List[str]) -> List[MemoryEntry]:
        if not tags:
            return list(self._entries.values())
        ids = set.intersection(*[self._tags.get(t, set()) for t in tags])
        return [self._entries[i] for i in ids if i in self._entries]

    def all(self) -> List[MemoryEntry]:
        return list(self._entries.values())

    def stats(self) -> Dict[str, Any]:
        return {
            "total":  len(self._entries),
            "tags":   len(self._tags),
            "most_accessed": sorted(self._entries.values(),
                                    key=lambda e: e.access_count, reverse=True)[:5],
        }

    def export_json(self) -> str:
        return json.dumps([{"key":e.key,"value":e.value,"tags":e.tags,"ts":e.ts}
                           for e in self._entries.values()], indent=2)


class KaiBrain:
    """Kai's reasoning engine: resolves context, stores facts, coordinates personas."""

    def __init__(self):
        self.levi  = LeviBridge(persona="kai")
        self.store = MemoryStore()

    def memorize(self, key: str, value: Any, tags: Optional[List[str]] = None) -> MemoryEntry:
        return self.store.store(key, value, tags)

    def recall(self, key_or_id: str) -> Optional[Any]:
        return self.store.retrieve(key_or_id)

    def context_window(self, n: int = 20) -> List[MemoryEntry]:
        """Return the n most recently accessed memories."""
        return sorted(self.store.all(), key=lambda e: (e.ts, -e.access_count), reverse=True)[:n]

    def coordinate(self, persona_from: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Route a coordination message between personas."""
        return {
            "coordinator": "kai",
            "from": persona_from,
            "message": message,
            "context_window": [e.key for e in self.context_window(5)],
            "soul": self.levi.bridge.build(persona="kai")["soul"],
        }


class KaiBridge:
    """
    Kai's external bridge — wraps KaiBrain with a L.W.P.-compatible interface.
    """
    def __init__(self):
        self.brain = KaiBrain()

    def think(self, prompt: str) -> Dict[str, Any]:
        self.brain.memorize(f"prompt_{uuid.uuid4().hex[:8]}", prompt, tags=["prompt"])
        return self.brain.coordinate("kai", {"type": "thought", "text": prompt})

    def store_memory(self, key: str, value: Any, tags: Optional[List[str]] = None) -> Dict[str, Any]:
        e = self.brain.memorize(key, value, tags)
        return {"stored": True, "key": key, "memory_id": e.id}

    def recall(self, key: str) -> Dict[str, Any]:
        v = self.brain.recall(key)
        return {"found": v is not None, "key": key, "value": v}

    def status(self) -> Dict[str, Any]:
        s = self.brain.store.stats()
        return {"persona": "KAI", "memory_entries": s["total"], "soul": {"joy":0.3,"trust":0.85,"fear":0.2,"surprise":0.3,"sadness":0.0}}
