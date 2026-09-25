"""Refined-pack ingest — the doorway into the corpus.

Chauncey refines a pack in his chat apps and saves it back to Drive as
JSON or Markdown. ingest_refined() validates it and writes a knowledge
entry to days/YYYY-MM-DD.jsonl (same pattern as knowledge/news).

Law 3 — ingest accepts ONLY genuinely refined packs:
  - schema == "levi.video_learn.refined/1"
  - refined_by non-empty (a name, not a blank)
  - origin_pack_hash matches a pack we actually exported (registry
    lookup in ~/.levi/video_learn/exports.jsonl) — no orphaned knowledge
  - refined_summary or key_points non-empty — no empty entries
  - dedupe by source_url hash: re-ingesting the same URL returns
    {"status": "duplicate"} instead of writing twice.

The corpus layout mirrors knowledge/news: one JSONL per day, each line
{date, schema, source_url, title, refined_summary, key_points, tags,
 origin_pack_hash, refined_by, ingested_at}. The full collective-
intelligence layer is spec-stage; this file writes the corpus it will
read. It does not fake the layer.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

REFINED_SCHEMA = "levi.video_learn.refined/1"
CORPUS_SCHEMA = "levi.video_learn.entry/1"
BASE = Path(__file__).resolve().parent
DAYS = BASE / "days"


class RefineParseError(ValueError):
    """The refined file is not parseable as JSON or as our Markdown shape."""


class IngestRejected(ValueError):
    """The refined pack failed law-3 validation. Carries the reason."""


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def parse_refined(path: Path) -> Dict:
    """Parse a refined file (JSON or Markdown) into a refined-pack dict."""
    text = Path(path).read_text(encoding="utf-8")
    if text.lstrip().startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise RefineParseError(f"invalid JSON in {path}: {exc}")
    return _parse_refined_markdown(text, path)


def _parse_refined_markdown(text: str, path: Path) -> Dict:
    lines = text.splitlines()
    title: Optional[str] = None
    meta: Dict[str, str] = {}
    summary_lines: List[str] = []
    points: List[str] = []
    section: Optional[str] = None
    for line in lines:
        s = line.strip()
        if not title and s.startswith("# "):
            title = s[2:].strip()
            continue
        m = re.match(r"^(refined_by|origin_pack_hash|source_url|tags)\s*:\s*(.+)$", s, re.I)
        if m and section is None:
            meta[m.group(1).lower()] = m.group(2).strip()
            continue
        if re.match(r"^##+\s*summary", s, re.I):
            section = "summary"
            continue
        if re.match(r"^##+\s*key\s*points", s, re.I):
            section = "points"
            continue
        if s.startswith("##"):
            section = None
            continue
        if section == "summary" and s:
            summary_lines.append(s)
        elif section == "points" and re.match(r"^[-*]\s+", s):
            points.append(re.sub(r"^[-*]\s+", "", s).strip())
    if not title:
        raise RefineParseError(f"{path}: Markdown refined file needs a '# Title' line")
    tags = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
    return {
        "schema": REFINED_SCHEMA,
        "title": title,
        "refined_by": meta.get("refined_by", ""),
        "origin_pack_hash": meta.get("origin_pack_hash", ""),
        "source_url": meta.get("source_url", ""),
        "refined_summary": "\n".join(summary_lines).strip(),
        "key_points": points,
        "tags": tags,
    }


def _registry_has(origin_hash: str, registry_file: Path) -> bool:
    if not registry_file.exists():
        return False
    for line in registry_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            if json.loads(line).get("pack_hash") == origin_hash:
                return True
        except json.JSONDecodeError:
            continue
    return False


def _corpus_has_url(url: str, days_dir: Optional[Path] = None) -> bool:
    uh = _url_hash(url)
    root = days_dir or DAYS
    if not root.exists():
        return False
    for day_file in root.glob("*.jsonl"):
        for line in day_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                if json.loads(line).get("url_hash") == uh:
                    return True
            except json.JSONDecodeError:
                continue
    return False


def ingest_refined(
    refined: Dict,
    *,
    registry_file: Optional[Path] = None,
    days_dir: Optional[Path] = None,
    today: Optional[date] = None,
) -> Dict:
    """Validate (law 3) and write a corpus entry. Returns a status dict."""
    reg = registry_file or (Path.home() / ".levi" / "video_learn" / "exports.jsonl")
    root = days_dir or DAYS

    if refined.get("schema") != REFINED_SCHEMA:
        raise IngestRejected(f"wrong schema: {refined.get('schema')!r}")
    refined_by = (refined.get("refined_by") or "").strip()
    if not refined_by:
        raise IngestRejected("refined_by is empty — ingest needs a named refiner")
    origin = (refined.get("origin_pack_hash") or "").strip()
    if not origin:
        raise IngestRejected("origin_pack_hash missing — cannot verify provenance")
    if not _registry_has(origin, reg):
        raise IngestRejected(
            f"origin_pack_hash {origin[:12]}... not in the export registry — "
            "refined packs must come from a pack we actually exported"
        )
    summary = (refined.get("refined_summary") or "").strip()
    points = [p for p in (refined.get("key_points") or []) if str(p).strip()]
    if not summary and not points:
        raise IngestRejected("empty refined content — nothing to ingest")
    url = (refined.get("source_url") or "").strip()
    if not url:
        raise IngestRejected("source_url missing")
    if _corpus_has_url(url, root):
        return {"status": "duplicate", "url": url}

    day = (today or date.today()).isoformat()
    root.mkdir(parents=True, exist_ok=True)
    entry = {
        "schema": CORPUS_SCHEMA,
        "date": day,
        "source_url": url,
        "url_hash": _url_hash(url),
        "title": (refined.get("title") or "").strip(),
        "refined_summary": summary,
        "key_points": points,
        "tags": refined.get("tags") or [],
        "origin_pack_hash": origin,
        "refined_by": refined_by,
        "ingested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with (root / f"{day}.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"status": "ingested", "date": day, "url": url, "refined_by": refined_by}
