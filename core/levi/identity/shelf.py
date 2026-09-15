"""
Project shelf — stories, factory projects, automations in one place.
Retention: "continue where you left off"
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ShelfItem:
    kind: str  # story | factory | automation
    id: str
    title: str
    summary: str
    updated_at: str
    meta: Dict[str, Any]


def collect_shelf() -> List[ShelfItem]:
    items: List[ShelfItem] = []
    try:
        from levi.graph.story_fabric import StoryFabric
        for s in StoryFabric().list()[:20]:
            items.append(ShelfItem(
                kind="story",
                id=s.id,
                title=s.title,
                summary=f"genre={s.genre} · {s.premise[:80]}",
                updated_at=s.updated_at or s.created_at,
                meta={"genre": s.genre},
            ))
    except Exception:
        pass
    try:
        from levi.factory.pipeline import SoftwareFactory
        for p in SoftwareFactory().list()[:20]:
            items.append(ShelfItem(
                kind="factory",
                id=p.id,
                title=p.name,
                summary=f"stage={p.stage.value} · {p.idea[:80]}",
                updated_at=p.updated_at or p.created_at,
                meta={"stage": p.stage.value},
            ))
    except Exception:
        pass
    try:
        from levi.daemon.automation import AutomationRegistry
        for a in AutomationRegistry().list()[:20]:
            items.append(ShelfItem(
                kind="automation",
                id=a.id,
                title=a.name,
                summary=f"{a.status.value} · {a.description[:80]}",
                updated_at=a.created_at,
                meta={"status": a.status.value},
            ))
    except Exception:
        pass
    items.sort(key=lambda x: x.updated_at or "", reverse=True)
    return items


def format_shelf(items: Optional[List[ShelfItem]] = None, limit: int = 12) -> str:
    items = items if items is not None else collect_shelf()
    if not items:
        return "Shelf is empty. Build something or write a story to fill it."
    lines = ["══ Your shelf ══", ""]
    for it in items[:limit]:
        lines.append(f"  [{it.kind:11}] {it.id}")
        lines.append(f"               {it.title}")
        lines.append(f"               {it.summary}")
        lines.append("")
    lines.append("Continue: levi continue")
    lines.append("Or: levi ask \"expand story\" / levi factory --advance <id>")
    return "\n".join(lines)


def latest_item() -> Optional[ShelfItem]:
    items = collect_shelf()
    return items[0] if items else None


def shelf_status() -> str:
    """Thin continuity surface for symbiosis with vault."""
    try:
        from levi.identity.profile import ProfileStore
        p = ProfileStore().load()
        return f"Shelf/profile loaded. name={getattr(p, 'display_name', None) or getattr(p, 'name', '—')}"
    except Exception as e:
        return f"Shelf partial: {e}"
