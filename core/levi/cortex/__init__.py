"""cortex: skill/education; the how-to library (LEVI-native).

Canon role (ORGANISM_FORMS): "skill/education; the how-to library".

Canon evidence (founder corpus: copilot-sweep/ser13-18-21-master-conversation.md):
  - "Cortex (Skill/Education) — how-to library (cortex_docs/)."
  - The founder's hierarchy places Cortex in the Execution Layer alongside
    Omega, Vector, NexusNetwork, SupraStreet, GenEX, Eden, CyberPulse.

This is a LEVI-native recreation with LEVI's own twist — never a copy of
anything from the original code. Cortex is an indexed, queryable library
of markdown how-to documents:

  - :class:`CortexLibrary` indexes ``*.md`` files under a docs directory.
  - Each how-to is identified by filename stem; the title is the first
    ``# `` heading; tags come from a ``<!-- tags: a, b -->`` marker or a
    ``Tags:`` line.
  - Fail-closed intake: documents with no title heading are QUARANTINED
    with a reason — never indexed, never served.
  - How-tos are DATA: ``search``/``get`` return documents for reading;
    Cortex never executes anything it indexes (hostile documents are read
    as data and quarantined at intake).

Cortex does not compete with ``levi.skill``'s registry (executable skills
under policy); it is the reading library — the methodical archive of
how-tos a mind consults before it acts.

Ready-for-review by the keeper. Never claims his review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

FORM_NAME = "cortex"

_TAG_MARKER = re.compile(r"<!--\s*tags:\s*(.*?)\s*-->", re.IGNORECASE | re.DOTALL)
_TAG_LINE = re.compile(r"^\s*tags\s*:\s*(.+)$", re.IGNORECASE)
_HEADING = re.compile(r"^#\s+(.+)$")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class HowTo:
    id: str
    title: str
    path: str
    tags: List[str] = field(default_factory=list)
    risk: str = "info"
    excerpt: str = ""


@dataclass
class Quarantine:
    id: str
    reason: str


class CortexLibrary:
    """An indexed how-to library over a directory of markdown documents."""

    def __init__(self, docs_dir: Any) -> None:
        if docs_dir is None:
            raise ValueError("docs_dir is required; Cortex indexes a real directory")
        self.docs_dir = Path(docs_dir)
        if not self.docs_dir.is_dir():
            raise ValueError(f"docs_dir is not a directory: {self.docs_dir}")
        self._index: Dict[str, HowTo] = {}
        self._quarantine: List[Quarantine] = []
        self._indexed_at: Optional[str] = None

    # -- intake -----------------------------------------------------------

    def _parse(self, path: Path) -> Optional[HowTo]:
        """Parse one markdown file; None when it fails intake."""
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            self._quarantine.append(Quarantine(path.stem, f"unreadable: {exc}"))
            return None
        title: Optional[str] = None
        for line in text.splitlines():
            m = _HEADING.match(line)
            if m:
                title = m.group(1).strip()
                break
        if not title:
            self._quarantine.append(
                Quarantine(
                    path.stem, "no '# ' title heading: cannot index untitled document"
                )
            )
            return None
        tags: List[str] = []
        marker = _TAG_MARKER.search(text)
        if marker:
            tags = [t.strip().lower() for t in marker.group(1).split(",") if t.strip()]
        else:
            for line in text.splitlines():
                m = _TAG_LINE.match(line)
                if m:
                    tags = [
                        t.strip().lower() for t in m.group(1).split(",") if t.strip()
                    ]
                    break
        risk = "info"
        if "high-risk" in tags or "critical" in tags:
            risk = "high"
        excerpt = "\n".join(
            l for l in text.splitlines() if l.strip() and not l.startswith("#")
        )[:400]
        return HowTo(
            id=path.stem,
            title=title,
            path=str(path),
            tags=tags,
            risk=risk,
            excerpt=excerpt,
        )

    def index(self) -> Dict[str, Any]:
        """(Re)build the index. Pure read; never executes documents."""
        self._index.clear()
        self._quarantine.clear()
        for path in sorted(self.docs_dir.glob("*.md")):
            howto = self._parse(path)
            if howto is not None:
                self._index[howto.id] = howto
        self._indexed_at = _utcnow()
        return {
            "form": FORM_NAME,
            "status": "indexed",
            "indexed": len(self._index),
            "quarantined": len(self._quarantine),
            "reason": f"{len(self._index)} how-tos indexed, "
            f"{len(self._quarantine)} quarantined (never served)",
            "at": self._indexed_at,
        }

    # -- query (documents are data; nothing executes) ----------------------

    def search(self, query: Any) -> List[HowTo]:
        """Case-insensitive match over title, tags, and excerpt."""
        if not isinstance(query, str) or not query.strip():
            return []
        q = query.strip().lower()
        hits = []
        for h in self._index.values():
            hay = " ".join([h.title, " ".join(h.tags), h.excerpt]).lower()
            if q in hay:
                hits.append(h)
        return hits

    def get(self, howto_id: Any) -> HowTo:
        if not isinstance(howto_id, str) or howto_id not in self._index:
            raise KeyError(f"no indexed how-to {howto_id!r}")
        return self._index[howto_id]

    def quarantine(self) -> List[Quarantine]:
        return list(self._quarantine)

    def status(self) -> Dict[str, Any]:
        return {
            "form": FORM_NAME,
            "indexed": len(self._index),
            "quarantined": len(self._quarantine),
            "docs_dir": str(self.docs_dir),
            "indexed_at": self._indexed_at,
            "honest_limit": (
                "Cortex is a reading library. It indexes and serves how-to "
                "documents as data; it never executes what it indexes."
            ),
        }
