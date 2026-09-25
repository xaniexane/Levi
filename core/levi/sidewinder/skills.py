"""Sidewinder skills — shared-core registration for the SkillRegistry.

Two INFO-risk skills; the platform API is the data path, so wave agents
that share the DNA core inherit the whole course through these:

* ``sidewinder_doctrine`` — the five laws, verbatim.
* ``sidewinder_field_manual`` — keyword/domain search over the course via
  the platform API; handler takes ``{"query": ..., "domain": ...,
  "track": ..., "edition": ..., "team": ..., "limit": ...}`` and returns
  terse Sidewinder-formatted entries. Read-only, no confirmation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from levi.skill.registry import Skill, SkillRisk
from levi.sidewinder import SIDEWINDER_DOCTRINE
from levi.sidewinder.platform.api import CoursePlatform

_platform: Optional[CoursePlatform] = None


def _api() -> CoursePlatform:
    global _platform
    if _platform is None:
        _platform = CoursePlatform()
    return _platform


def _doctrine_handler(_args: Dict[str, Any] | None = None) -> str:
    return SIDEWINDER_DOCTRINE


def _manual_handler(args: Dict[str, Any] | None = None) -> str:
    args = args or {}
    api = _api()
    query = str(args.get("query") or args.get("q") or "").strip()
    domain = args.get("domain")
    track = args.get("track")
    edition = args.get("edition")
    team = args.get("team")
    try:
        limit = max(1, min(10, int(args.get("limit", 3))))
    except (TypeError, ValueError):
        limit = 3
    try:
        view_entries = api._view(edition, team).entries
    except KeyError as exc:
        return str(exc)
    if not query:
        counts: Dict[str, int] = {}
        for entry in view_entries:
            counts[entry["domain"]] = counts.get(entry["domain"], 0) + 1
        lines = [f"Sidewinder field manual: {len(view_entries)} entries across {len(counts)} domains."]
        for d in sorted(counts):
            lines.append(f"  {d}: {counts[d]}")
        lines.append("Pass a query to search, or a domain/track to narrow it.")
        return "\n".join(lines)
    hits = api.search(query, domain=domain, track=track, edition=edition, team=team, limit=limit)
    if not hits:
        scope = " ".join(
            x
            for x in (
                f"in domain {domain!r}" if domain else "",
                f"on track {track!r}" if track else "",
                f"in edition {edition!r}" if edition else "",
                f"for team {team!r}" if team else "",
            )
            if x
        )
        return f"No field-manual entries match {query!r}" + (f" {scope}." if scope else ".")
    return "\n\n---\n\n".join(api.format_entry(e) for e in hits)


SIDEWINDER_SKILLS: List[Skill] = [
    Skill(
        id="sidewinder_doctrine",
        name="Sidewinder Doctrine",
        description="The five laws of field improvisation: see the mechanism, substitute from on-hand, protect the work, know the stop, no improvisation where precision is law.",
        category="fieldcraft",
        risk_level=SkillRisk.INFO,
        tags=["sidewinder", "fieldcraft", "improvisation", "doctrine"],
        version="1.0.0",
        handler=_doctrine_handler,
    ),
    Skill(
        id="sidewinder_field_manual",
        name="Sidewinder Field Manual",
        description="Search the data-driven course via the platform API by keyword, domain, track, edition pack, or agent team (mechanism check, improvised tools, steps, stop conditions).",
        category="fieldcraft",
        risk_level=SkillRisk.INFO,
        tags=["sidewinder", "fieldcraft", "improvisation", "howto"],
        version="1.0.0",
        handler=_manual_handler,
    ),
]
