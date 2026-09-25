"""Agent memory tiers + MemGPT OS-virtual-memory framing.

Studied from: ai-si-software-internals-20260916-0005/report.md (§2.7)

Functional description: four memory tiers with different lifetimes —

- working: pinned facts, a rolling summary, and the last turns verbatim
  (what is "in mind" right now);
- episodic: per-session episodes, append-only, the raw material;
- semantic: extracted durable facts, deduplicated;
- procedural: workflow templates (how to do recurring tasks).

Plus the MemGPT framing: main context is RAM (small, fast, precious),
archival storage is disk (large, cheap), and recall is paging — but pages
move ONLY through explicit ``page_in`` / ``page_out`` calls issued by the
agent itself. Nothing is auto-injected into the working context; recall is
a tool call the agent chooses to make, so the context window stays honest
about what it holds.

Pure Python, stdlib only. No provider branding. Not artificial — synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ORIGIN = "levi-revival/memtiers"


@dataclass
class MemoryItem:
    key: str
    text: str
    tier: str  # working | episodic | semantic | procedural
    pinned: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Episode:
    session_id: str
    turns: List[str] = field(default_factory=list)

    def append(self, turn: str) -> None:
        self.turns.append(turn)


class WorkingMemory:
    """RAM: pinned facts, rolling summary, last turns verbatim."""

    def __init__(self, turn_window: int = 10) -> None:
        self.pinned: Dict[str, MemoryItem] = {}
        self.summary: str = ""
        self.recent_turns: List[str] = []
        self.turn_window = turn_window

    def pin(self, key: str, text: str) -> None:
        self.pinned[key] = MemoryItem(key=key, text=text, tier="working", pinned=True)

    def unpin(self, key: str) -> bool:
        return self.pinned.pop(key, None) is not None

    def add_turn(self, turn: str) -> None:
        self.recent_turns.append(turn)
        self.recent_turns = self.recent_turns[-self.turn_window :]

    def roll_summary(self, new_summary: str) -> None:
        self.summary = new_summary

    def snapshot(self) -> Dict[str, Any]:
        return {
            "pinned": {k: v.text for k, v in self.pinned.items()},
            "summary": self.summary,
            "recent_turns": list(self.recent_turns),
        }


class ArchivalStore:
    """Disk: episodic / semantic / procedural tiers live here."""

    def __init__(self) -> None:
        self.episodic: List[Episode] = []
        self.semantic: Dict[str, MemoryItem] = {}
        self.procedural: Dict[str, MemoryItem] = {}

    # -- episodic ------------------------------------------------------
    def log_episode(self, episode: Episode) -> None:
        self.episodic.append(episode)

    # -- semantic ------------------------------------------------------
    def store_fact(
        self, key: str, text: str, meta: Optional[Dict[str, Any]] = None
    ) -> None:
        self.semantic[key] = MemoryItem(
            key=key, text=text, tier="semantic", meta=meta or {}
        )

    def forget_fact(self, key: str) -> bool:
        return self.semantic.pop(key, None) is not None

    # -- procedural ----------------------------------------------------
    def store_template(
        self, name: str, steps: List[str], meta: Optional[Dict[str, Any]] = None
    ) -> None:
        self.procedural[name] = MemoryItem(
            key=name,
            text="\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps)),
            tier="procedural",
            meta=meta or {},
        )

    def get_template(self, name: str) -> Optional[MemoryItem]:
        return self.procedural.get(name)

    # -- recall (search, not injection) --------------------------------
    def search(
        self, query: str, tier: str = "semantic", limit: int = 5
    ) -> List[MemoryItem]:
        q = query.lower().split()
        pool = {"semantic": self.semantic, "procedural": self.procedural}.get(tier, {})
        scored = []
        for item in pool.values():
            text = item.text.lower()
            hits = sum(1 for t in q if t in text)
            if hits:
                scored.append((hits, item))
        scored.sort(key=lambda p: -p[0])
        return [item for _s, item in scored[:limit]]


@dataclass
class PageEvent:
    direction: str  # "in" | "out"
    key: str
    tier: str


class MemoryOS:
    """MemGPT framing: main context is RAM, archival is disk, and the agent
    pages explicitly. ``page_in`` copies an archival item into working
    memory; ``page_out`` evicts a working item back to archival. Every page
    is logged — the agent always knows what is resident."""

    def __init__(
        self,
        working: Optional[WorkingMemory] = None,
        archival: Optional[ArchivalStore] = None,
    ) -> None:
        self.working = working or WorkingMemory()
        self.archival = archival or ArchivalStore()
        self.page_log: List[PageEvent] = []

    def page_in(self, key: str, tier: str = "semantic") -> bool:
        """Agent-issued: bring an archival item into working memory."""
        pool = {
            "semantic": self.archival.semantic,
            "procedural": self.archival.procedural,
        }.get(tier, {})
        item = pool.get(key)
        if item is None:
            return False
        self.working.pin(f"paged:{tier}:{key}", item.text)
        self.page_log.append(PageEvent("in", key, tier))
        return True

    def page_out(
        self, pinned_key: str, tier: str = "semantic", dest_key: Optional[str] = None
    ) -> bool:
        """Agent-issued: evict a working item back to archival."""
        item = self.working.pinned.pop(pinned_key, None)
        if item is None:
            return False
        key = dest_key or pinned_key
        if tier == "semantic":
            self.archival.store_fact(key, item.text, meta={"paged_out": True})
        elif tier == "procedural":
            self.archival.store_template(key, item.text.splitlines())
        else:
            return False
        self.page_log.append(PageEvent("out", key, tier))
        return True

    def recall(
        self, query: str, tier: str = "semantic", limit: int = 5
    ) -> List[MemoryItem]:
        """Tool-call recall: search archival WITHOUT injecting into context.
        The agent reads the results and decides what — if anything — to
        page in."""
        return self.archival.search(query, tier=tier, limit=limit)

    def resident_keys(self) -> List[str]:
        return list(self.working.pinned.keys())
