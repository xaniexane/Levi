"""
Multi-type Memory Architecture
Working / Episodic / Semantic / Preference / Project / Procedural / Relationship / Device
Local-first, versioned, user-controllable.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime, timezone
import uuid


class MemoryType(str, Enum):
    WORKING = "working"  # Current conversation / task
    EPISODIC = "episodic"  # Past interactions and events
    SEMANTIC = "semantic"  # Facts and knowledge
    PREFERENCE = "preference"  # User preferences
    PROJECT = "project"  # Project-scoped information
    PROCEDURAL = "procedural"  # Learned workflows and routines
    RELATIONSHIP = "relationship"  # Entities and connections
    DEVICE = "device"  # Connected device state/capabilities


@dataclass
class MemoryEntry:
    id: str
    memory_type: MemoryType
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    source: str = "user"
    tags: List[str] = field(default_factory=list)
    project_id: Optional[str] = None
    embedding_ref: Optional[str] = None  # future vector reference
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["memory_type"] = self.memory_type.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        data = dict(data)
        data["memory_type"] = MemoryType(data["memory_type"])
        return cls(**data)


def new_entry(
    memory_type: MemoryType,
    content: str,
    importance: float = 0.5,
    source: str = "user",
    tags: Optional[List[str]] = None,
    project_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> MemoryEntry:
    return MemoryEntry(
        id=str(uuid.uuid4()),
        memory_type=memory_type,
        content=content,
        importance=importance,
        source=source,
        tags=tags or [],
        project_id=project_id,
        metadata=metadata or {},
    )
