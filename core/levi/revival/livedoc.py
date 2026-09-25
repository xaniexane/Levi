"""livedoc — compound documents of swappable live components.

Studied from: retired-software-revival-research-20260916-0004/report.md (Section 9).

The load-bearing idea: a document is not a passive blob — it is an
ordered list of *live components* (text, checklist, table, note), and
there is no "main app" hovering above it. The document is the center
of the world; components can be swapped at runtime without rebuilding
the document.

LEVI's take: ``LiveDoc`` holds a list of ``Component``s drawn from a
small ``REGISTRY``. ``swap(index, kind, **data)`` replaces a component
in place — same position, new behavior — so a note can become a
checklist mid-session and the document never blinks. Everything is
plain data + methods; rendering is the caller's business.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

ORIGIN = "levi-revival/livedoc"


class Component:
    """One live component inside a document."""

    kind: str = "component"

    def __init__(self, **data: Any) -> None:
        self.data: Dict[str, Any] = dict(data)

    def summary(self) -> str:
        """One-line human rendering of this component."""
        return f"<{self.kind}>"

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "data": dict(self.data)}

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Component":
        kind = payload.get("kind", "component")
        factory = REGISTRY.get(kind)
        if factory is None:
            raise ValueError(f"unknown component kind: {kind!r}")
        return factory(**payload.get("data", {}))


class TextBlock(Component):
    kind = "text"

    def summary(self) -> str:
        return self.data.get("body", "")[:80]


class Checklist(Component):
    kind = "checklist"

    def __init__(self, items: List[Any] | None = None, **data: Any) -> None:
        super().__init__(**data)
        self.items: List[Dict[str, Any]] = []
        for item in items or []:
            if isinstance(item, dict):
                self.items.append(
                    {"label": item.get("label", ""), "done": bool(item.get("done"))}
                )
            else:
                self.items.append({"label": item, "done": False})

    def check(self, index: int) -> None:
        self.items[index]["done"] = True

    def uncheck(self, index: int) -> None:
        self.items[index]["done"] = False

    def summary(self) -> str:
        done = sum(1 for item in self.items if item["done"])
        return f"checklist {done}/{len(self.items)} done"

    def to_dict(self) -> Dict[str, Any]:
        payload = super().to_dict()
        payload["data"]["items"] = [
            {"label": i["label"], "done": i["done"]} for i in self.items
        ]
        return payload


class Table(Component):
    kind = "table"

    def __init__(self, columns: List[str] | None = None, **data: Any) -> None:
        data.setdefault("columns", columns or [])
        super().__init__(**data)
        self.columns: List[str] = list(columns or data.get("columns", []))
        self.rows: List[List[Any]] = [list(r) for r in data.get("rows", [])]

    def add_row(self, *values: Any) -> None:
        if len(values) != len(self.columns):
            raise ValueError(
                f"row has {len(values)} values but table has {len(self.columns)} columns"
            )
        self.rows.append(list(values))

    def summary(self) -> str:
        return f"table {len(self.rows)}x{len(self.columns)}"

    def to_dict(self) -> Dict[str, Any]:
        payload = super().to_dict()
        payload["data"]["columns"] = list(self.columns)
        payload["data"]["rows"] = [list(r) for r in self.rows]
        return payload


class Note(Component):
    kind = "note"

    def summary(self) -> str:
        return f"note: {self.data.get('body', '')[:60]}"


# The component registry: kind -> factory. Document-centered — no app
# class sits above it; this mapping IS the extension point.
REGISTRY: Dict[str, Callable[..., Component]] = {
    "text": TextBlock,
    "checklist": Checklist,
    "table": Table,
    "note": Note,
}


class LiveDoc:
    """A document that is an ordered list of live components."""

    def __init__(self, title: str = "") -> None:
        self.title = title
        self.parts: List[Component] = []

    # -- composition ---------------------------------------------------
    def append(self, kind: str, **data: Any) -> Component:
        factory = REGISTRY.get(kind)
        if factory is None:
            raise ValueError(f"unknown component kind: {kind!r}")
        comp = factory(**data)
        self.parts.append(comp)
        return comp

    def swap(self, index: int, kind: str, **data: Any) -> Component:
        """Swap the component at ``index`` for a new live one, in place.

        Position, neighbors, and document identity are untouched — only
        the component's kind and behavior change.
        """
        factory = REGISTRY.get(kind)
        if factory is None:
            raise ValueError(f"unknown component kind: {kind!r}")
        new = factory(**data)
        self.parts[index] = new
        return new

    # -- document-centered views ---------------------------------------
    def outline(self) -> List[str]:
        return [part.summary() for part in self.parts]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "parts": [part.to_dict() for part in self.parts],
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "LiveDoc":
        doc = cls(title=payload.get("title", ""))
        for part in payload.get("parts", []):
            doc.parts.append(Component.from_dict(part))
        return doc
