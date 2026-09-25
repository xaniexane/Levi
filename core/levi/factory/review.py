"""Factory Bag review gate — the second pair of eyes.

Drafts are cheap; shipped words are not. A draft may only move to
``delivered`` after :func:`review_draft` passes it. The checklist is
rebuilt natively from established editorial QA practice (remix law —
studied, own words):

- **Brief honored** — the review checks the draft against the brief,
  the way content QA checks a piece against its assignment (contentoo:
  "brief requirements met ... specific enough to answer yes or no").
- **No filler** — every paragraph earns its place; canned openers and
  hype words fail the draft (github-well-architected: "no waffle or
  filler — every paragraph earns its place").
- **Concrete specifics** — claims must be concrete: numbers, dates, names
  (rampstackco editorial-qa: statistics and named specifics must be real,
  not plausible-sounding; endings land, not throat-clearing).

Review records live under ``<factory-dir>/bag_reviews/<item_id>.json``.
:func:`load_review` is what the delivery gate consults.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

DRAFT_BANNER = "DRAFT"

# Canned openers and hype words that fail a draft on sight.
FILLER_MARKERS = (
    "in today's",
    "in the ever-evolving",
    "delve",
    "tapestry",
    "landscape",
    "game-changer",
    "game changer",
    "cutting-edge",
    "cutting edge",
    "robust ecosystem",
    "leverage",
    "synergy",
    "paradigm shift",
    "unlock the power",
    "in conclusion,",
)

_DATE_RE = re.compile(
    r"\b(?:19|20)\d{2}\b"
    r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"\d")
_NAME_RE = re.compile(r"\b[A-Z][a-z]{2,}\b")


def reviews_dir(home: Optional[Path] = None) -> Path:
    base = Path(home) if home is not None else Path.home() / ".levi" / "factory"
    d = base / "bag_reviews"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_json(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _keywords(title: str, brief: str) -> List[str]:
    words = re.findall(r"[A-Za-z]{5,}", f"{title} {brief}")
    seen = []
    for w in words:
        lw = w.lower()
        if lw not in seen:
            seen.append(lw)
    return seen


def _check_banner(text: str) -> tuple[bool, str]:
    head = "\n".join(text.splitlines()[:3])
    ok = DRAFT_BANNER in head
    return ok, "banner present" if ok else "missing DRAFT banner in the first lines"


def _check_brief(text: str, title: str, brief: str) -> tuple[bool, str]:
    keywords = _keywords(title, brief)
    if not keywords:
        return True, "no keywords to check"
    lowered = text.lower()
    found = [w for w in keywords if w in lowered]
    need = min(3, len(keywords))
    ok = len(found) >= need
    return ok, (
        f"{len(found)}/{len(keywords)} brief keywords honored"
        if ok
        else f"brief not honored — only {len(found)}/{len(keywords)} keywords "
        f"({', '.join(keywords[:6])})"
    )


def _check_filler(text: str) -> tuple[bool, str]:
    lowered = text.lower()
    hits = [m for m in FILLER_MARKERS if m in lowered]
    ok = not hits
    return ok, "no filler markers" if ok else f"filler found: {', '.join(hits)}"


def _check_specifics(text: str) -> tuple[bool, str]:
    has_number = bool(_NUMBER_RE.search(text))
    has_date = bool(_DATE_RE.search(text))
    names = set(_NAME_RE.findall(text))
    has_names = len(names) >= 3
    ok = has_number and (has_date or has_names)
    detail = (
        f"numbers={'yes' if has_number else 'no'}, "
        f"dates={'yes' if has_date else 'no'}, "
        f"named specifics={len(names)}"
    )
    return ok, f"concrete specifics: {detail}" if ok else f"too vague — {detail}"


def review_draft(
    item_id: str,
    draft_path: str,
    title: str = "",
    brief: str = "",
    home: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Second-pass review of a draft. Returns the review record.

    The record is ``{"item_id", "passed", "checklist", "notes",
    "reviewed_at"}`` and is persisted under the reviews dir. ``passed`` is
    True only when every checklist item passes.
    """
    path = Path(draft_path)
    if not path.exists():
        record = {
            "item_id": item_id,
            "passed": False,
            "checklist": {},
            "notes": [f"draft file not found: {draft_path}"],
            "reviewed_at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(now or time.time())
            ),
        }
        _write_json(reviews_dir(home) / f"{item_id}.json", record)
        return record

    text = path.read_text(encoding="utf-8", errors="replace")
    checks = [
        ("banner", _check_banner(text)),
        ("brief_honored", _check_brief(text, title, brief)),
        ("no_filler", _check_filler(text)),
        ("concrete_specifics", _check_specifics(text)),
    ]
    checklist = {name: {"passed": ok, "note": note} for name, (ok, note) in checks}
    passed = all(ok for _, (ok, _) in checks)
    notes = [c["note"] for c in checklist.values() if not c["passed"]]
    record = {
        "item_id": item_id,
        "passed": passed,
        "checklist": checklist,
        "notes": notes,
        "reviewed_at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(now or time.time())
        ),
    }
    _write_json(reviews_dir(home) / f"{item_id}.json", record)
    return record


def load_review(home: Optional[Path], item_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a stored review record, or None when never reviewed."""
    path = reviews_dir(home) / f"{item_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
