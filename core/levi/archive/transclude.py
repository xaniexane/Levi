"""Transclusion and backlinks — the Xanadu revival for the LEVI Archive.

Ted Nelson's Project Xanadu (1960\u2013) promised transclusion \u2014 a
virtual instance of content across a boundary with the original's
identity maintained \u2014 and two-way links, so a document knows who
cites it. The web shipped fragile one-way links instead, and today's
platforms harvest the citation graph from users and sell it back to
them as "insights".

LEVI takes the mechanism, not the docuverse: inside the local Archive,
a record body may embed ``{{transclude:<record-id>}}``. Rendering
resolves the marker to the quoted record with its origin glued on, and
a backlink index answers "who cites this record?" \u2014 the graph stays
local, complete, and owned by the keeper.

Stdlib only. Pure functions over :class:`ArchiveStore`; no network.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

TRANSCLUDE_RE = re.compile(
    r"\{\{\s*transclude\s*:\s*([A-Za-z0-9][A-Za-z0-9_-]*)\s*\}\}"
)

#: Record text fields scanned for transclusion markers.
TEXT_FIELDS = ("summary", "mechanism", "decline", "revival_recipe", "levi_application")

MAX_DEPTH = 5


def find_transclusions(text: str) -> List[str]:
    """Return the record ids referenced by ``{{transclude:<id>}}`` markers,
    in order of first appearance, deduplicated."""
    seen: List[str] = []
    for match in TRANSCLUDE_RE.finditer(text or ""):
        rid = match.group(1)
        if rid not in seen:
            seen.append(rid)
    return seen


def record_transclusions(record) -> List[str]:
    """All transclusion targets referenced anywhere in a record's text."""
    seen: List[str] = []
    for field in TEXT_FIELDS:
        for rid in find_transclusions(getattr(record, field, "") or ""):
            if rid not in seen:
                seen.append(rid)
    return seen


def _resolve_text(
    text: str, store, depth: int, trail: Tuple[str, ...]
) -> Tuple[str, List[str]]:
    """Substitute transclusion markers in free text.

    Returns ``(resolved_text, transcluded_ids)``. Cycles, unknown ids,
    and over-deep nesting are left in place with an honest note.
    """
    transcluded: List[str] = []

    def _replace(match: "re.Match") -> str:
        rid = match.group(1)
        if rid in trail:
            return match.group(0) + " [circular transclusion \u2014 left as-is]"
        if depth >= MAX_DEPTH:
            return match.group(0) + " [max transclusion depth \u2014 left as-is]"
        target = store.get(rid)
        if target is None:
            return match.group(0) + " [unknown record \u2014 left as-is]"
        if rid not in transcluded:
            transcluded.append(rid)
        resolved_summary, deeper = _resolve_text(
            target.summary or "", store, depth + 1, trail + (rid,)
        )
        transcluded.extend(r for r in deeper if r not in transcluded)
        lines = ["> [transcluded from %s \u2014 %s]" % (target.id, target.title)]
        for line in resolved_summary.splitlines():
            lines.append("> " + line if line.strip() else ">")
        return "\n".join(lines)

    return TRANSCLUDE_RE.sub(_replace, text or ""), transcluded


def render_record(record, store) -> Tuple[str, List[str]]:
    """Render a record with transclusion markers resolved.

    Returns ``(rendered_text, transcluded_ids)``. Cycles and unknown
    ids are left in place with an honest note instead of breaking the
    render; nesting deeper than :data:`MAX_DEPTH` stops the same way.
    """
    parts = []
    all_transcluded: List[str] = []
    for field in TEXT_FIELDS:
        resolved, transcluded = _resolve_text(
            getattr(record, field, "") or "", store, 0, (record.id,)
        )
        all_transcluded.extend(r for r in transcluded if r not in all_transcluded)
        parts.append("## %s\n%s" % (field, resolved))
    header = "# %s\n(%s)" % (record.title, record.id)
    return header + "\n\n" + "\n\n".join(parts), all_transcluded


def build_backlinks(store) -> Dict[str, List[str]]:
    """Reverse citation index: ``target_id -> [citing record ids]``.

    A record cites a target when any of its text fields carries a
    ``{{transclude:<target>}}`` marker. Self-citations are ignored.
    """
    backlinks: Dict[str, List[str]] = {}
    for record in store.all():
        for target_id in record_transclusions(record):
            if target_id == record.id:
                continue
            backlinks.setdefault(target_id, [])
            if record.id not in backlinks[target_id]:
                backlinks[target_id].append(record.id)
    for citing in backlinks.values():
        citing.sort()
    return backlinks


def cited_by(store, record_id: str) -> List[str]:
    """Record ids whose text transcludes ``record_id``. Empty, never None."""
    return build_backlinks(store).get(record_id, [])
