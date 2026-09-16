"""Ingest: parse finished research reports into ArchiveRecords.

Three report formats are supported (parsers are keyed by heading style, not
by filename, so future hunts that follow the same conventions ingest
unchanged):

- sw30: ``### N. Title (era)`` + ``- **Label:** value`` bullets
        (retired-software-revival-research-20260916-0004)
- sw50: ``## N. Title <badge> — **RATING**`` + numbered ``1.``–``5.`` fields
        (revival-50-more-20260916-0009, parts 1 and 2)
- m40:  ``## N. Title — RATING`` + ``**Label:** value`` paragraphs
        (forgotten-methods-wave3-20260916-0015)

Reports are read-only inputs and are never modified. Dedup is by identity
(title+era) within one ingest run; the report tag is part of every record
id, so the same find described by two hunts coexists with its own
provenance instead of being merged or overwritten.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .record import ArchiveRecord, Provenance, make_id, slugify

# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------

_ENTRY_HEADING = re.compile(r"^#{2,4}\s+(\d+)\.\s+(.*\S)\s*$")
_ANY_HEADING = re.compile(r"^#{1,4}\s+")
_BADGE_STATUS = {"🔴": "dead", "🟡": "alive-underused",
                 "🟠": "preserved", "🔵": "technique-alive"}
_RATING_RE = re.compile(r"\*\*\s*(LOAD-BEARING|USEFUL PATTERN|INSPIRATIONAL)\s*\*\*")
_URL_LINE = re.compile(r"^-\s+(https?://\S+)\s*$")


def _norm_rating(raw: str) -> str:
    return raw.strip().lower().replace(" ", "-")


def _split_entry_blocks(text: str) -> List[Tuple[str, List[str]]]:
    """Split markdown into (heading_text, body_lines) for numbered entries.

    Stops at the first non-numbered heading (ranked lists, audits, sources).
    """
    blocks: List[Tuple[str, List[str]]] = []
    current: Optional[Tuple[str, List[str]]] = None
    for line in text.splitlines():
        m = _ENTRY_HEADING.match(line)
        if m:
            if current is not None:
                blocks.append(current)
            current = (m.group(2), [])
            continue
        if _ANY_HEADING.match(line):
            if current is not None:
                blocks.append(current)
                current = None
            continue
        if current is not None:
            current[1].append(line)
    if current is not None:
        blocks.append(current)
    return blocks


def _badge_status(heading: str) -> str:
    for badge, status in _BADGE_STATUS.items():
        if badge in heading:
            if "absorb" in heading.lower():
                return "absorbed"
            return status
    if "absorb" in heading.lower():
        return "absorbed"
    return "dead"


def _guess_status_sw30(summary: str, decline: str) -> str:
    text = (summary + " " + decline).lower()
    if any(k in text for k in ("absorbed into", "technical ancestor",
                              "folded into", "became part of")):
        return "absorbed"
    if any(k in text for k in ("still alive", "alive today", "never died",
                              "alive in research", "still operating",
                              "revived 2008", "remains alive", "still sold",
                              "half-retired", "still active")):
        return "alive-underused"
    return "dead"


def _title_era(heading: str) -> Tuple[str, str]:
    """Split 'Title (era)' into (title, era); era is the trailing parens."""
    m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", heading)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return heading.strip(), ""


# ---------------------------------------------------------------------------
# sw30 parser
# ---------------------------------------------------------------------------

_SW30_BULLET = re.compile(r"^-\s+\*\*(.+?):\*\*\s*(.*)$")


def _map_sw30_label(label: str) -> Optional[str]:
    low = label.lower()
    if "what/when" in low or "what it was" in low:
        return "summary"
    if "mechanism" in low:
        return "mechanism"
    if low.startswith("why"):
        return "decline"
    if "revival" in low:
        return "revival_recipe"
    if "application" in low:
        return "levi_application"
    if "skepticism" in low:
        return "skepticism"
    return None


def parse_sw30(text: str, provenance: Provenance) -> List[ArchiveRecord]:
    records = []
    for heading, body in _split_entry_blocks(text):
        title, era = _title_era(heading)
        fields: Dict[str, str] = {}
        current: Optional[str] = None
        for line in body:
            bm = _SW30_BULLET.match(line)
            if bm:
                key = _map_sw30_label(bm.group(1))
                current = key
                if key:
                    fields[key] = bm.group(2).strip()
                continue
            if current and line.strip() and not line.lstrip().startswith("-"):
                fields[current] += " " + line.strip()
        fields_rec = dict(
            title=title, era=era,
            summary=fields.get("summary", ""),
            mechanism=fields.get("mechanism", ""),
            decline=fields.get("decline", ""),
            revival_recipe=fields.get("revival_recipe", ""),
            levi_application=fields.get("levi_application", ""),
            sources=[],
            rating="unrated",
            status=_guess_status_sw30(fields.get("summary", ""),
                                      fields.get("decline", "")),
            skepticism=fields.get("skepticism", ""),
            provenance=provenance,
        )
        records.append((fields_rec, title, era))
    return _assign_ids(records, "sw30", "software")


# ---------------------------------------------------------------------------
# sw50 parser
# ---------------------------------------------------------------------------

_SW50_FIELD = re.compile(r"^(\d)\.\s*(.*)$")
_SW50_LABEL = re.compile(r'^["\']?(mechanism|died|revival|app|application)["\']?\s*:\s*',
                         re.IGNORECASE)
_SW50_ORDER = {1: "summary", 2: "mechanism", 3: "decline",
               4: "revival_recipe", 5: "levi_application"}
_SW50_DASH = re.compile(r"\s+[—–-]\s*")
_RATING_RE_LOOSE = re.compile(r"(LOAD-BEARING|USEFUL PATTERN|INSPIRATIONAL)\s*\*{0,2}\s*$")


def _clean_sw50_heading(heading: str) -> Tuple[str, str, str]:
    """Return (title, rating, status) from a sw50 entry heading."""
    rating = "unrated"
    rm = _RATING_RE.search(heading)
    if rm:
        rating = _norm_rating(rm.group(1))
        heading = heading[:rm.start()].strip()
    status = _badge_status(heading)
    # strip badge + parenthetical notes (e.g. "(absorbed — ...)"), then
    # keep the text before the dash as the title
    for badge in _BADGE_STATUS:
        heading = heading.replace(badge, "")
    heading = re.sub(r"\s*\([^()]*\)", "", heading)
    parts = _SW50_DASH.split(heading, maxsplit=1)
    title = parts[0].strip()
    return title, rating, status


def parse_sw50(text: str, provenance: Provenance) -> List[ArchiveRecord]:
    records = []
    for heading, body in _split_entry_blocks(text):
        title, rating, status = _clean_sw50_heading(heading)
        fields: Dict[str, str] = {}
        sources: List[str] = []
        current: Optional[str] = None
        for line in body:
            um = _URL_LINE.match(line)
            if um:
                sources.append(um.group(1).rstrip(").,"))
                continue
            fm = _SW50_FIELD.match(line)
            if fm and fm.group(1) in "12345":
                key = _SW50_ORDER[int(fm.group(1))]
                value = _SW50_LABEL.sub("", fm.group(2)).strip()
                fields[key] = value
                current = key
                continue
            if current and line.strip():
                if line.strip().lower().rstrip(":") == "sources":
                    current = None  # "Sources:" header — URLs follow as bullets
                    continue
                fields[current] += " " + line.strip()
        fields_rec = dict(
            title=title, era="",
            summary=fields.get("summary", ""),
            mechanism=fields.get("mechanism", ""),
            decline=fields.get("decline", ""),
            revival_recipe=fields.get("revival_recipe", ""),
            levi_application=fields.get("levi_application", ""),
            sources=sources,
            rating=rating,
            status=status,
            skepticism="",
            provenance=provenance,
        )
        records.append((fields_rec, title, ""))
    return _assign_ids(records, "sw50", "software")


# ---------------------------------------------------------------------------
# m40 parser
# ---------------------------------------------------------------------------

_M40_FIELD = re.compile(r"^\*\*(.+?):\*\*\s*(.*)$")


def _clean_m40_heading(heading: str) -> Tuple[str, str]:
    rating = "unrated"
    rm = _RATING_RE.search(heading)
    if rm is None:
        rm = _RATING_RE_LOOSE.search(heading)  # m40 ratings are not bolded
    if rm:
        rating = _norm_rating(rm.group(1))
        heading = heading[:rm.start()].strip()
    parts = _SW50_DASH.split(heading, maxsplit=1)
    title = parts[0].strip() if len(parts) > 1 else heading.strip()
    return title, rating


def parse_m40(text: str, provenance: Provenance) -> List[ArchiveRecord]:
    records = []
    for heading, body in _split_entry_blocks(text):
        title, rating = _clean_m40_heading(heading)
        fields: Dict[str, str] = {}
        sources: List[str] = []
        current: Optional[str] = None
        for line in body:
            um = _URL_LINE.match(line)
            if um:
                sources.append(um.group(1).rstrip(").,"))
                continue
            fm = _M40_FIELD.match(line)
            if fm:
                key = _map_sw30_label(fm.group(1))
                current = key
                if key:
                    fields[key] = fm.group(2).strip()
                continue
            if current and line.strip():
                fields[current] += " " + line.strip()
        fields_rec = dict(
            title=title, era="",
            summary=fields.get("summary", ""),
            mechanism=fields.get("mechanism", ""),
            decline=fields.get("decline", ""),
            revival_recipe=fields.get("revival_recipe", ""),
            levi_application=fields.get("levi_application", ""),
            sources=sources,
            rating=rating,
            status="dead",
            skepticism=fields.get("skepticism", ""),
            provenance=provenance,
        )
        records.append((fields_rec, title, ""))
    return _assign_ids(records, "m40", "method")


# ---------------------------------------------------------------------------
# JSONL findings parser — for waves that ship findings.jsonl directly
# ---------------------------------------------------------------------------


def parse_findings_jsonl(text: str,
                         provenance: Provenance) -> List[ArchiveRecord]:
    """Parse one-ArchiveRecord-per-line JSONL (the hunt-record format)."""
    import json as _json

    records: List[ArchiveRecord] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            data = _json.loads(line)
        except ValueError as exc:
            raise ValueError("bad JSON on line %d: %s" % (lineno, exc)) from exc
        rec = ArchiveRecord.from_dict(data)
        records.append(rec)
    return records


# ---------------------------------------------------------------------------
# id assignment + dedup
# ---------------------------------------------------------------------------

def _assign_ids(triples: List[Tuple[Dict, str, str]],
                report_tag: str, kind: str) -> List[ArchiveRecord]:
    """Assign deterministic ids; dedup true repeats by identity (title+era)."""
    out: List[ArchiveRecord] = []
    seen_identities = set()
    for fields_rec, title, era in triples:
        identity = (slugify(title), slugify(era))
        if identity in seen_identities:
            continue  # true duplicate within this report — skip, never store twice
        seen_identities.add(identity)
        n = 0
        while True:
            rid = make_id(kind, report_tag, title, era, n)
            if all(r.id != rid for r in out):
                break
            n += 1
        out.append(ArchiveRecord(id=rid, kind=kind, **fields_rec))
    return out


# ---------------------------------------------------------------------------
# top-level ingest
# ---------------------------------------------------------------------------

REPORTS = [
    {
        "slug": "retired-software-revival-research-20260916-0004",
        "files": ["report.md"],
        "parser": parse_sw30,
        "tag": "sw30",
        "notes": ("Index-sourced 2026-09-16; 2+ sources per entry; no live "
                  "page reads. No per-entry source URLs in the report."),
    },
    {
        "slug": "revival-50-more-20260916-0009",
        "files": ["report-part1.md", "report-part2.md"],
        "parser": parse_sw50,
        "tag": "sw50",
        "notes": ("Index-sourced 2026-09-16 UTC; no live verification. "
                  "Status badges: dead / alive-underused / preserved / "
                  "technique-alive. Part 2 carries the ranked top 10."),
    },
    {
        "slug": "forgotten-methods-wave3-20260916-0015",
        "files": ["report.md"],
        "parser": parse_m40,
        "tag": "m40",
        "notes": ("Index-sourced 2026-09-16; two independent sources per "
                  "entry. Disputed/romanticized history flagged per entry "
                  "and in the nostalgia audit."),
    },
    {
        "slug": "games-hunt-20260916-0022",
        "files": ["findings.jsonl"],
        "parser": parse_findings_jsonl,
        "tag": "games",
        "notes": ("Web-verified 2026-09-16; guesses marked; findings carry "
                  "embedded provenance. JSONL is the hunt-record format."),
    },
]


def ingest_reports(research_root: Path,
                   slugs: Optional[List[str]] = None) -> Tuple[List[ArchiveRecord], List[str]]:
    """Parse finished research reports into records.

    Returns (records, errors). Reports are read-only inputs; any parse
    problem is reported as an error string — never raised, never patched
    around silently.
    """
    records: List[ArchiveRecord] = []
    errors: List[str] = []
    for spec in REPORTS:
        if slugs is not None and spec["slug"] not in slugs:
            continue
        prov = Provenance(found_date="2026-09-16",
                          research_slug=spec["slug"],
                          notes=spec["notes"])
        for fname in spec["files"]:
            path = research_root / spec["slug"] / fname
            if not path.is_file():
                errors.append("missing report file: %s" % path)
                continue
            try:
                text = path.read_text(encoding="utf-8")
                records.extend(spec["parser"](text, prov))
            except Exception as exc:  # fail-closed: report, don't half-ingest
                errors.append("parse failed for %s: %s" % (path, exc))
    return records, errors
