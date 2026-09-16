"""ArchiveRecord: one curated trophy in the LEVI Archive.

Every record is a preserved find — a forgotten piece of software, a method,
or a technique — with its mechanism, its cause of death, a revival recipe,
and full provenance. Validation is strict and deny-closed: a malformed
record is refused, never half-stored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

KINDS = ("software", "method", "technique")

RATINGS = ("load-bearing", "useful-pattern", "inspirational", "unrated")

STATUSES = ("dead", "alive-underused", "preserved", "absorbed", "technique-alive")

_ID_RE = re.compile(r"^arch-[a-z0-9]+(?:-[a-z0-9]+)*$")


def slugify(text: str, max_len: int = 60) -> str:
    """Lowercase ASCII slug for titles/eras."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:max_len].strip("-") or "untitled"


def make_id(kind: str, report_tag: str, title: str, era: str, n: int = 0) -> str:
    """Deterministic record id.

    The report tag is part of the id on purpose: the same find described by
    two different research hunts yields two records that coexist with their
    own provenance — conflicts are never silently merged away.
    """
    base = "arch-%s-%s-%s" % (report_tag, slugify(kind), slugify(title))
    if era:
        base += "-%s" % slugify(era, max_len=24)
    if n:
        base += "-%d" % n
    return base


@dataclass(frozen=True)
class Provenance:
    found_date: str          # ISO date the research hunt completed
    research_slug: str       # research_notes/<slug> directory name
    notes: str = ""          # researcher caveats, verification basis, etc.

    def to_dict(self) -> Dict[str, str]:
        return {"found_date": self.found_date,
                "research_slug": self.research_slug,
                "notes": self.notes}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Provenance":
        if not isinstance(data, dict):
            raise ValueError("provenance must be a mapping")
        found_date = data.get("found_date", "")
        research_slug = data.get("research_slug", "")
        if not found_date or not research_slug:
            raise ValueError("provenance requires found_date and research_slug")
        return cls(found_date=found_date,
                   research_slug=research_slug,
                   notes=str(data.get("notes", "")))


@dataclass(frozen=True)
class ArchiveRecord:
    """One curated find. All text fields are the researcher's own words."""

    id: str
    title: str
    era: str                       # free text, e.g. "Apple, 1987-2004"; may be ""
    kind: str                      # software | method | technique
    summary: str                   # what it was / when — the exhibit placard
    mechanism: str                 # the ahead-of-its-time mechanism
    decline: str                   # the real cause of death/decline
    revival_recipe: str            # how to revive it with modern capability
    levi_application: str          # one concrete local-first AI application
    sources: List[str] = field(default_factory=list)
    rating: str = "unrated"        # load-bearing | useful-pattern | inspirational
    status: str = "dead"           # dead | alive-underused | preserved | ...
    skepticism: str = ""           # disputed/romanticized history flags
    provenance: Optional[Provenance] = None

    def __post_init__(self):
        if not _ID_RE.match(self.id):
            raise ValueError("bad record id: %r" % self.id)
        if not self.title or not self.title.strip():
            raise ValueError("record %s: title is required" % self.id)
        if self.kind not in KINDS:
            raise ValueError("record %s: kind %r not in %r"
                             % (self.id, self.kind, KINDS))
        for name in ("summary", "mechanism", "decline",
                     "revival_recipe", "levi_application"):
            if not getattr(self, name) or not getattr(self, name).strip():
                raise ValueError("record %s: %s is required" % (self.id, name))
        if self.rating not in RATINGS:
            raise ValueError("record %s: rating %r not in %r"
                             % (self.id, self.rating, RATINGS))
        if self.status not in STATUSES:
            raise ValueError("record %s: status %r not in %r"
                             % (self.id, self.status, STATUSES))
        for url in self.sources:
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                raise ValueError("record %s: bad source URL %r" % (self.id, url))
        if self.provenance is not None and not isinstance(self.provenance, Provenance):
            raise ValueError("record %s: provenance must be a Provenance" % self.id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "era": self.era,
            "kind": self.kind,
            "summary": self.summary,
            "mechanism": self.mechanism,
            "decline": self.decline,
            "revival_recipe": self.revival_recipe,
            "levi_application": self.levi_application,
            "sources": list(self.sources),
            "rating": self.rating,
            "status": self.status,
            "skepticism": self.skepticism,
            "provenance": self.provenance.to_dict() if self.provenance else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArchiveRecord":
        if not isinstance(data, dict):
            raise ValueError("record must be a mapping")
        prov = data.get("provenance")
        return cls(
            id=str(data.get("id", "")),
            title=str(data.get("title", "")),
            era=str(data.get("era", "")),
            kind=str(data.get("kind", "")),
            summary=str(data.get("summary", "")),
            mechanism=str(data.get("mechanism", "")),
            decline=str(data.get("decline", "")),
            revival_recipe=str(data.get("revival_recipe", "")),
            levi_application=str(data.get("levi_application", "")),
            sources=list(data.get("sources", []) or []),
            rating=str(data.get("rating", "unrated")),
            status=str(data.get("status", "dead")),
            skepticism=str(data.get("skepticism", "")),
            provenance=Provenance.from_dict(prov) if prov else None,
        )

    def placard(self) -> str:
        """Short museum-style exhibit placard."""
        lines = [
            "%s  [%s · %s · %s]" % (self.title, self.kind, self.rating, self.status),
        ]
        if self.era:
            lines.append("Era: %s" % self.era)
        lines.append("")
        lines.append(self.summary)
        return "\n".join(lines)
