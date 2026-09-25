"""Cross-instance visibility view (transvisibility).

Studied from: interfaces-hunt-20260915/report.md [1. Project Xanadu]

Functional description: when the same source passage appears in several
documents, each appearance is an *instance*. Transvisibility is the view
from one instance to all its siblings — "this exact passage also lives in
these other places, here is how each one looks around it." The module owns
only this visibility view: registering instances (document + span + local
context excerpt), finding sibling instances of the same source span, and
rendering each sibling with its surroundings so you can see across them.

Care note: adjacent to ``levi.revival.xanadu``. This module does NOT rebuild
the transclusion substrate; instances are plain (source_id, span, context)
records — the substrate's identity model is not duplicated here.

Pure Python, stdlib only. No provider branding. Not artificial — synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

ORIGIN = "levi-revival/transvisibility"


@dataclass
class Instance:
    """One appearance of a source span inside a document."""

    id: int
    source_id: str  # identity of the transcluded source passage
    doc_id: str  # the document hosting this instance
    span: Tuple[int, int]  # character offsets of the passage in the host doc
    context_before: str = ""
    context_after: str = ""
    note: str = ""


class Transvisibility:
    """The cross-instance visibility view over registered instances."""

    def __init__(self) -> None:
        self._instances: Dict[int, Instance] = {}
        self._next_id = 1

    # -- registration ----------------------------------------------------
    def register(
        self,
        source_id: str,
        doc_id: str,
        span: Tuple[int, int],
        context_before: str = "",
        context_after: str = "",
        note: str = "",
    ) -> Instance:
        if not source_id or not doc_id:
            raise ValueError("source_id and doc_id are required")
        start, end = span
        if start < 0 or end < start:
            raise ValueError(f"invalid span: {span}")
        inst = Instance(
            self._next_id,
            source_id,
            doc_id,
            (start, end),
            context_before,
            context_after,
            note,
        )
        self._instances[inst.id] = inst
        self._next_id += 1
        return inst

    def remove(self, instance_id: int) -> bool:
        return self._instances.pop(instance_id, None) is not None

    def get(self, instance_id: int) -> Instance:
        return self._instances[instance_id]

    # -- visibility -------------------------------------------------------
    def siblings(self, instance_id: int) -> List[Instance]:
        """Other instances of the same source span, ordered by document."""
        me = self.get(instance_id)
        out = [
            i
            for i in self._instances.values()
            if i.source_id == me.source_id and i.id != me.id
        ]
        out.sort(key=lambda i: (i.doc_id, i.span))
        return out

    def visibility(self, instance_id: int) -> Dict[str, object]:
        """The see-across view: this instance plus every sibling with context."""
        me = self.get(instance_id)
        sibs = self.siblings(instance_id)
        return {
            "instance": self._view(me, current=True),
            "siblings": [self._view(s, current=False) for s in sibs],
            "sibling_count": len(sibs),
        }

    @staticmethod
    def _view(inst: Instance, current: bool) -> Dict[str, object]:
        snippet = f"{inst.context_before}[…]{inst.context_after}"
        return {
            "id": inst.id,
            "doc_id": inst.doc_id,
            "span": list(inst.span),
            "context": snippet,
            "note": inst.note,
            "current": current,
        }

    def sources(self) -> List[str]:
        """All source passages that have at least one visible instance."""
        return sorted({i.source_id for i in self._instances.values()})

    def instances_of(self, source_id: str) -> List[Instance]:
        out = [i for i in self._instances.values() if i.source_id == source_id]
        out.sort(key=lambda i: (i.doc_id, i.span))
        return out


def demo_visibility() -> Dict[str, object]:
    tv = Transvisibility()
    a = tv.register(
        "manifesto:12",
        "essay",
        (40, 120),
        context_before="We hold that ",
        context_after=" is the whole of the law.",
    )
    tv.register(
        "manifesto:12",
        "pamphlet",
        (5, 85),
        context_before="Printed bold: ",
        context_after=" — take it to heart.",
        note="abridged printing",
    )
    tv.register("other:3", "essay", (200, 260), context_before="Meanwhile, ")
    view = tv.visibility(a.id)
    return {
        "sibling_count": view["sibling_count"],
        "sibling_docs": [s["doc_id"] for s in view["siblings"]],  # type: ignore[index]
        "sources": tv.sources(),
    }


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(demo_visibility(), indent=2))
