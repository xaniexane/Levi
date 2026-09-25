"""
Multi-type Memory Architecture
Working / Episodic / Semantic / Preference / Project / Procedural / Relationship / Device
Local-first, versioned, user-controllable.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict, fields
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
        """Rebuild an entry from its persisted dict form.

        Raises ValueError with an actionable message on any schema
        violation (non-mapping, unknown memory_type, missing fields,
        unknown fields, malformed values) — never a raw
        TypeError/ValueError traceback.
        """
        if not isinstance(data, dict):
            raise ValueError(
                "MemoryEntry.from_dict: expected a dict, got %s" % type(data).__name__
            )
        data = dict(data)
        raw_type = data.get("memory_type")
        try:
            data["memory_type"] = MemoryType(raw_type)
        except ValueError:
            raise ValueError(
                "MemoryEntry.from_dict: unknown memory_type %r "
                "(expected one of: %s)"
                % (raw_type, ", ".join(t.value for t in MemoryType))
            ) from None
        field_names = {f.name for f in fields(cls)}
        unknown = sorted(k for k in data if k not in field_names)
        if unknown:
            raise ValueError(
                "MemoryEntry.from_dict: unknown field(s) %s; expected %s"
                % (", ".join(unknown), ", ".join(sorted(field_names)))
            )
        missing = sorted(n for n in field_names if n not in data)
        if missing:
            raise ValueError(
                "MemoryEntry.from_dict: missing field(s) %s" % ", ".join(missing)
            )
        try:
            return cls(**data)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "MemoryEntry.from_dict: malformed entry (%s)" % exc
            ) from exc


def new_entry(
    memory_type: MemoryType,
    content: str,
    importance: float = 0.5,
    source: str = "user",
    tags: Optional[List[str]] = None,
    project_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> MemoryEntry:
    """Build a new :class:`MemoryEntry`, validating the inputs.

    Raises :class:`ValueError` on a non-:class:`MemoryType` type, empty
    content, or tags that are not a list of strings.
    """
    if not isinstance(memory_type, MemoryType):
        raise ValueError(
            "new_entry: memory_type must be a MemoryType, got %r" % (memory_type,)
        )
    if not isinstance(content, str) or not content.strip():
        raise ValueError("new_entry: content must be a non-empty string")
    if tags is not None and (
        not isinstance(tags, list) or any(not isinstance(t, str) for t in tags)
    ):
        raise ValueError("new_entry: tags must be a list of strings")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("new_entry: source must be a non-empty string")
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
